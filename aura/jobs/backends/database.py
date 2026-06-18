"""Database-backed task queue using SQLAlchemy."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select, update

from aura.jobs.backends.base import TaskBackend
from aura.jobs.base import TaskDefinition, TaskResult, TaskStatus
from aura.jobs.models import AuraJob

if TYPE_CHECKING:
    from aura.orm.session import DatabaseManager


@dataclass(frozen=True)
class ClaimedJob:
    """Snapshot of a job claimed for execution by the worker."""

    id: str
    task_name: str
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    max_retries: int
    retry_count: int


def _json_safe(value: Any) -> Any:
    """Return a JSON-serialisable representation of *value*."""
    if value is None:
        return None
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


class DatabaseBackend(TaskBackend):
    """Task backend that persists jobs in a SQL database.

    Requires the ``sqlalchemy`` extra::

        pip install aura-web[sqlalchemy]

    Jobs are stored in the ``aura_jobs`` table and processed by
    :class:`~aura.jobs.worker.AuraWorker` polling the database.

    Args:
        db: An initialised :class:`~aura.orm.session.DatabaseManager`.
            When omitted, a new manager is created from ``database_url`` or
            ``AURA__DATABASE__URL``.
        database_url: SQLAlchemy async URL used when *db* is not provided.
    """

    def __init__(
        self,
        db: DatabaseManager | None = None,
        database_url: str | None = None,
    ) -> None:
        self._db = db
        self._database_url = database_url
        self._owns_db = db is None

    @property
    def db(self) -> DatabaseManager:
        if self._db is None:
            raise RuntimeError("DatabaseBackend not started. Call startup() first.")
        return self._db

    async def startup(self) -> None:
        """Initialise the database connection and ensure the jobs table exists."""
        try:
            from aura.orm.session import DatabaseManager
        except ImportError as exc:
            raise RuntimeError(
                "DatabaseBackend requires SQLAlchemy. "
                "Install with: pip install aura-web[sqlalchemy]"
            ) from exc

        if self._db is None:
            self._db = DatabaseManager()
            url = self._database_url or os.environ.get(
                "AURA__DATABASE__URL",
                "sqlite+aiosqlite:///./aura.db",
            )
            self._db.init(url)

        from aura.orm.base import _AuraRegistry

        await self._db.create_all(_AuraRegistry)

    async def shutdown(self) -> None:
        """Close the database connection when this backend owns the manager."""
        if self._owns_db and self._db is not None:
            await self._db.close()
            self._db = None

    async def enqueue(
        self,
        task: TaskDefinition,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        delay: int = 0,
    ) -> TaskResult:
        """Insert a new job row with PENDING status."""
        task_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)
        scheduled_at = now + timedelta(seconds=delay) if delay > 0 else None

        async with self.db.session() as session:
            session.add(
                AuraJob(
                    id=task_id,
                    task_name=task.name,
                    queue=task.queue,
                    args_json=list(args) if args else None,
                    kwargs_json=kwargs or None,
                    status=TaskStatus.PENDING.value,
                    retry_count=0,
                    max_retries=task.retry,
                    scheduled_at=scheduled_at,
                    created_at=now,
                )
            )

        return TaskResult(task_id=task_id, status=TaskStatus.PENDING)

    async def get_result(self, task_id: str) -> TaskResult | None:
        """Load a job row by id and map it to :class:`~aura.jobs.base.TaskResult`."""
        async with self.db.session() as session:
            job = await session.get(AuraJob, task_id)
            if job is None:
                return None
            return self._row_to_result(job)

    async def claim_pending_jobs(
        self,
        queues: list[str],
        limit: int = 1,
    ) -> list[ClaimedJob]:
        """Claim pending jobs ready for execution.

        Uses ``FOR UPDATE SKIP LOCKED`` on PostgreSQL; optimistic locking on
        other dialects (e.g. SQLite).
        """
        now = datetime.now(tz=timezone.utc)
        claimed: list[ClaimedJob] = []

        async with self.db.session() as session:
            stmt = (
                select(AuraJob)
                .where(
                    AuraJob.status == TaskStatus.PENDING.value,
                    AuraJob.queue.in_(queues),
                    or_(AuraJob.scheduled_at.is_(None), AuraJob.scheduled_at <= now),
                )
                .order_by(AuraJob.created_at)
                .limit(limit)
            )
            if self._is_postgresql():
                stmt = stmt.with_for_update(skip_locked=True)

            result = await session.execute(stmt)
            candidates = list(result.scalars().all())

            for job in candidates:
                if len(claimed) >= limit:
                    break

                if self._is_postgresql():
                    job.status = TaskStatus.RUNNING.value
                    job.started_at = now
                    claimed.append(self._snapshot_job(job))
                    continue

                upd = await session.execute(
                    update(AuraJob)
                    .where(
                        AuraJob.id == job.id,
                        AuraJob.status == TaskStatus.PENDING.value,
                    )
                    .values(status=TaskStatus.RUNNING.value, started_at=now)
                    .returning(AuraJob)
                )
                claimed_row = upd.scalar_one_or_none()
                if claimed_row is not None:
                    claimed.append(self._snapshot_job(claimed_row))

        return claimed

    async def has_pending_jobs(self, queues: list[str]) -> bool:
        """Return True when at least one pending job exists for *queues*."""
        now = datetime.now(tz=timezone.utc)
        async with self.db.session() as session:
            stmt = (
                select(AuraJob.id)
                .where(
                    AuraJob.status == TaskStatus.PENDING.value,
                    AuraJob.queue.in_(queues),
                    or_(AuraJob.scheduled_at.is_(None), AuraJob.scheduled_at <= now),
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def mark_success(self, job_id: str, result: Any) -> None:
        """Persist a successful job result."""
        now = datetime.now(tz=timezone.utc)
        async with self.db.session() as session:
            job = await session.get(AuraJob, job_id)
            if job is None:
                return
            job.status = TaskStatus.SUCCESS.value
            job.result_json = _json_safe(result)
            job.error = None
            job.completed_at = now

    async def mark_retry(self, job_id: str, error: str, retry_count: int) -> None:
        """Re-queue a job for another attempt."""
        async with self.db.session() as session:
            job = await session.get(AuraJob, job_id)
            if job is None:
                return
            job.status = TaskStatus.PENDING.value
            job.retry_count = retry_count
            job.error = error
            job.started_at = None

    async def mark_failed(self, job_id: str, error: str) -> None:
        """Mark a job as permanently failed."""
        now = datetime.now(tz=timezone.utc)
        async with self.db.session() as session:
            job = await session.get(AuraJob, job_id)
            if job is None:
                return
            job.status = TaskStatus.FAILED.value
            job.error = error
            job.completed_at = now

    def _is_postgresql(self) -> bool:
        return self.db.engine.dialect.name == "postgresql"

    @staticmethod
    def _row_to_result(job: AuraJob) -> TaskResult:
        return TaskResult(
            task_id=job.id,
            status=TaskStatus(job.status),
            result=job.result_json,
            error=job.error,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    @staticmethod
    def _snapshot_job(job: AuraJob) -> ClaimedJob:
        return ClaimedJob(
            id=job.id,
            task_name=job.task_name,
            args=tuple(job.args_json or ()),
            kwargs=dict(job.kwargs_json or {}),
            max_retries=job.max_retries,
            retry_count=job.retry_count,
        )
