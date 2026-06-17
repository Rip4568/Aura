"""Tests for DatabaseBackend — persistent job queue without Redis."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest

from aura.jobs.backends.database import DatabaseBackend
from aura.jobs.base import TaskDefinition, TaskRegistry, TaskStatus
from aura.jobs.decorators import _get_default_backend
from aura.jobs.models import AuraJob
from aura.jobs.worker import AuraWorker
from aura.orm.session import DatabaseManager


@pytest.fixture
async def db_manager() -> AsyncIterator[DatabaseManager]:
    """Fresh in-memory SQLite DatabaseManager with aura_jobs table."""
    manager = DatabaseManager()
    manager.init("sqlite+aiosqlite:///:memory:", echo=False)
    from aura.orm.base import _AuraRegistry

    await manager.create_all(_AuraRegistry)
    yield manager
    await manager.close()


@pytest.fixture
async def backend(db_manager: DatabaseManager) -> AsyncIterator[DatabaseBackend]:
    """DatabaseBackend bound to the in-memory test database."""
    be = DatabaseBackend(db=db_manager)
    await be.startup()
    yield be
    await be.shutdown()


# ---------------------------------------------------------------------------
# Backend basics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_startup_creates_aura_jobs_table(db_manager: DatabaseManager) -> None:
  backend = DatabaseBackend(db=db_manager)
  await backend.startup()

  async with db_manager.session() as session:
    job = AuraJob(
      id="test-id",
      task_name="sample",
      queue="default",
      status=TaskStatus.PENDING.value,
    )
    session.add(job)

  result = await backend.get_result("test-id")
  assert result is not None
  assert result.task_id == "test-id"
  await backend.shutdown()


@pytest.mark.asyncio
async def test_enqueue_inserts_pending_job(backend: DatabaseBackend) -> None:
  async def sample_task(value: int) -> int:
    return value * 2

  task = TaskDefinition(name="tests.sample_task", func=sample_task, queue="emails")
  result = await backend.enqueue(task, args=(21,), kwargs={"extra": True})

  assert result.status == TaskStatus.PENDING
  assert result.task_id

  stored = await backend.get_result(result.task_id)
  assert stored is not None
  assert stored.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_enqueue_sets_scheduled_at_for_delay(backend: DatabaseBackend) -> None:
  async def delayed_task() -> None:
    return None

  task = TaskDefinition(name="tests.delayed", func=delayed_task)
  before = datetime.now(tz=timezone.utc)
  result = await backend.enqueue(task, delay=60)

  async with backend.db.session() as session:
    row = await session.get(AuraJob, result.task_id)
    assert row is not None
    assert row.scheduled_at is not None
    scheduled = row.scheduled_at
    if scheduled.tzinfo is None:
      scheduled = scheduled.replace(tzinfo=timezone.utc)
    assert scheduled >= before + timedelta(seconds=59)


@pytest.mark.asyncio
async def test_get_result_returns_none_for_missing_id(backend: DatabaseBackend) -> None:
  assert await backend.get_result("missing-id") is None


@pytest.mark.asyncio
async def test_get_result_maps_success_fields(backend: DatabaseBackend) -> None:
  now = datetime.now(tz=timezone.utc)
  async with backend.db.session() as session:
    session.add(
      AuraJob(
        id="done-1",
        task_name="tests.done",
        queue="default",
        status=TaskStatus.SUCCESS.value,
        result_json={"ok": True},
        started_at=now,
        completed_at=now,
      )
    )

  result = await backend.get_result("done-1")
  assert result is not None
  assert result.status == TaskStatus.SUCCESS
  assert result.result == {"ok": True}
  assert result.started_at is not None
  assert result.completed_at is not None


# ---------------------------------------------------------------------------
# Claim / execute lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_pending_jobs_claims_ready_job(backend: DatabaseBackend) -> None:
  async with backend.db.session() as session:
    session.add(
      AuraJob(
        id="job-1",
        task_name="tests.work",
        queue="default",
        args_json=[1, 2],
        kwargs_json={"flag": True},
        status=TaskStatus.PENDING.value,
        max_retries=2,
      )
    )

  claimed = await backend.claim_pending_jobs(["default"], limit=1)
  assert len(claimed) == 1
  assert claimed[0].id == "job-1"
  assert claimed[0].args == (1, 2)
  assert claimed[0].kwargs == {"flag": True}

  stored = await backend.get_result("job-1")
  assert stored is not None
  assert stored.status == TaskStatus.RUNNING


@pytest.mark.asyncio
async def test_claim_skips_future_scheduled_jobs(backend: DatabaseBackend) -> None:
  future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
  async with backend.db.session() as session:
    session.add(
      AuraJob(
        id="future-1",
        task_name="tests.future",
        queue="default",
        status=TaskStatus.PENDING.value,
        scheduled_at=future,
      )
    )

  claimed = await backend.claim_pending_jobs(["default"], limit=1)
  assert claimed == []


@pytest.mark.asyncio
async def test_mark_success_and_failed_update_row(backend: DatabaseBackend) -> None:
  async with backend.db.session() as session:
    session.add(
      AuraJob(
        id="run-1",
        task_name="tests.run",
        queue="default",
        status=TaskStatus.RUNNING.value,
      )
    )

  await backend.mark_success("run-1", {"value": 42})
  success = await backend.get_result("run-1")
  assert success is not None
  assert success.status == TaskStatus.SUCCESS
  assert success.result == {"value": 42}
  assert success.completed_at is not None

  async with backend.db.session() as session:
    session.add(
      AuraJob(
        id="run-2",
        task_name="tests.run",
        queue="default",
        status=TaskStatus.RUNNING.value,
      )
    )

  await backend.mark_failed("run-2", "boom")
  failed = await backend.get_result("run-2")
  assert failed is not None
  assert failed.status == TaskStatus.FAILED
  assert failed.error == "boom"


@pytest.mark.asyncio
async def test_mark_retry_requeues_job(backend: DatabaseBackend) -> None:
  async with backend.db.session() as session:
    session.add(
      AuraJob(
        id="retry-1",
        task_name="tests.retry",
        queue="default",
        status=TaskStatus.RUNNING.value,
        retry_count=0,
      )
    )

  await backend.mark_retry("retry-1", "transient", 1)
  result = await backend.get_result("retry-1")
  assert result is not None
  assert result.status == TaskStatus.PENDING
  assert result.error == "transient"


# ---------------------------------------------------------------------------
# Worker integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_executes_database_job(
  backend: DatabaseBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
  results: list[int] = []

  async def add_numbers(a: int, b: int) -> int:
    results.append(a + b)
    return a + b

  TaskRegistry.register(
    TaskDefinition(name="tests.add_numbers", func=add_numbers, queue="default")
  )

  enqueued = await backend.enqueue(
    TaskDefinition(name="tests.add_numbers", func=add_numbers, queue="default"),
    args=(2, 3),
  )

  worker = AuraWorker(backend=backend, queues=["default"], concurrency=1, burst=True)
  monkeypatch.setattr(worker, "_running", True)

  async def _stop_after_one_loop() -> None:
    for _ in range(50):
      stored = await backend.get_result(enqueued.task_id)
      if stored and stored.status == TaskStatus.SUCCESS:
        worker._running = False
        return
      await asyncio.sleep(0.05)
    worker._running = False

  await backend.startup()
  await asyncio.gather(worker._run_database_worker(), _stop_after_one_loop())

  final = await backend.get_result(enqueued.task_id)
  assert final is not None
  assert final.status == TaskStatus.SUCCESS
  assert final.result == 5
  assert results == [5]


@pytest.mark.asyncio
async def test_worker_marks_missing_task_as_failed(backend: DatabaseBackend) -> None:
  async with backend.db.session() as session:
    session.add(
      AuraJob(
        id="orphan-1",
        task_name="tests.missing",
        queue="default",
        status=TaskStatus.PENDING.value,
      )
    )

  worker = AuraWorker(backend=backend, queues=["default"], concurrency=1, burst=True)
  worker._running = True
  await worker._run_database_worker()

  result = await backend.get_result("orphan-1")
  assert result is not None
  assert result.status == TaskStatus.FAILED
  assert "not found" in (result.error or "")


@pytest.mark.asyncio
async def test_worker_retries_failed_task(backend: DatabaseBackend) -> None:
  attempts = {"count": 0}

  async def flaky() -> str:
    attempts["count"] += 1
    if attempts["count"] < 2:
      raise RuntimeError("not yet")
    return "ok"

  task = TaskDefinition(name="tests.flaky", func=flaky, queue="default", retry=1)
  TaskRegistry.register(task)
  enqueued = await backend.enqueue(task)

  worker = AuraWorker(backend=backend, queues=["default"], concurrency=1, burst=True)
  worker._running = True
  await worker._run_database_worker()

  final = await backend.get_result(enqueued.task_id)
  assert final is not None
  assert final.status == TaskStatus.SUCCESS
  assert final.result == "ok"
  assert attempts["count"] == 2


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


def test_get_default_backend_selects_database(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setenv("AURA__JOBS__BACKEND", "database")
  monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

  backend = _get_default_backend()
  assert isinstance(backend, DatabaseBackend)


def test_database_backend_takes_priority_over_broker_url(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setenv("AURA__JOBS__BACKEND", "database")
  monkeypatch.setenv("AURA__JOBS__BROKER_URL", "redis://localhost:6379")

  backend = _get_default_backend()
  assert isinstance(backend, DatabaseBackend)
