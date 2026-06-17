"""Aura background worker — processes tasks from configured queues."""

from __future__ import annotations

import asyncio
import signal
from typing import Any

from rich.console import Console

console = Console()


class AuraWorker:
    """Aura background worker that processes tasks from one or more queues.

    The worker connects to the configured backend, consumes tasks from the
    specified queues, and executes them with the given concurrency level.

    Graceful shutdown is handled automatically on SIGTERM and SIGINT.

    When ``AURA__JOBS__BROKER_URL`` is set (or ``broker_url`` is passed), the
    worker delegates to SAQ's native worker loop.  Otherwise, the in-process
    :class:`~aura.jobs.backends.memory.MemoryBackend` is used.

    **Multi-queue filtering:**
    When using SAQBackend with Redis, multi-queue support is achieved by passing
    a single Queue object to the SAQWorker (not the list of queue names).
    The Queue object's internal list determines which queues are polled.
    This is a SAQ worker design — it does not accept a ``queues`` parameter.

    Args:
        backend: The :class:`~aura.jobs.backends.base.TaskBackend` to use.
                 Defaults to the auto-detected backend (SAQ or Memory).
        queues: List of queue names to consume from (default: ``["default"]``).
        concurrency: Maximum number of tasks executed in parallel.
        burst: If ``True``, the worker exits once the queue is drained rather
               than waiting for new tasks.
        broker_url: Redis URL that overrides ``AURA__JOBS__BROKER_URL``.
                    When provided, forces ``SAQBackend`` regardless of the env
                    var.

    Usage (programmatic)::

        worker = AuraWorker(backend=redis_backend, queues=["default", "emails"])
        await worker.run()

    Usage (CLI)::

        aura worker --queue default --concurrency 4
        aura worker --broker-url redis://localhost:6379 -q emails
    """

    def __init__(
        self,
        backend: Any = None,
        *,
        queues: list[str] | None = None,
        concurrency: int = 4,
        burst: bool = False,
        broker_url: str | None = None,
    ) -> None:
        if backend is None:
            if broker_url:
                # Explicit broker URL always selects SAQBackend
                from aura.jobs.backends.saq_backend import SAQBackend

                backend = SAQBackend(redis_url=broker_url)
            else:
                # Auto-detect from env or fall back to MemoryBackend
                from aura.jobs.decorators import _get_default_backend

                backend = _get_default_backend()
        self._backend = backend
        self.queues = queues or ["default"]
        self._concurrency = concurrency
        self.burst = burst
        self._running = False
        self._tasks: list[asyncio.Task[Any]] = []

    async def run(self) -> None:
        """Start the worker and block until shutdown."""
        console.print("[bold green]Aura Worker[/] starting...")
        console.print(f"  Queues: [cyan]{', '.join(self.queues)}[/]")
        console.print(f"  Concurrency: [cyan]{self._concurrency}[/]")
        if self.burst:
            console.print("  Mode: [yellow]burst (exit when queue empty)[/]")

        self._running = True
        self._setup_signal_handlers()

        await self._backend.startup()

        try:
            if self._is_saq_backend():
                await self._run_saq_worker()
            elif self._is_database_backend():
                await self._run_database_worker()
            else:
                await self._process_loop()
        finally:
            await self._shutdown()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_saq_backend(self) -> bool:
        """Return True when the active backend is SAQBackend."""
        try:
            from aura.jobs.backends.saq_backend import SAQBackend

            return isinstance(self._backend, SAQBackend)
        except ImportError:
            return False

    def _is_database_backend(self) -> bool:
        """Return True when the active backend is DatabaseBackend."""
        try:
            from aura.jobs.backends.database import DatabaseBackend

            return isinstance(self._backend, DatabaseBackend)
        except ImportError:
            return False

    async def _run_saq_worker(self) -> None:
        """Delegate task processing to SAQ's native worker loop.

        Collects all functions registered in the :class:`~aura.jobs.base.TaskRegistry`
        and hands them to SAQ's ``Worker``.  SAQ handles polling, retries,
        and concurrency internally.

        Passes ``burst`` parameter to SAQ's Worker to enable:
        - Burst mode (exit on empty): ``--burst``
        """
        try:
            from saq import Worker as SAQWorker
        except ImportError as exc:
            raise RuntimeError(
                "SAQ is required to run the SAQ worker. "
                "Install with: pip install aura-framework[saq,redis]"
            ) from exc

        from aura.jobs.backends.saq_backend import wrap_saq_task
        from aura.jobs.base import TaskRegistry

        functions = [
            wrap_saq_task(task_def.func)
            for task_def in TaskRegistry.all().values()
        ]
        if not functions:
            console.print("[yellow]Warning:[/] No tasks registered in TaskRegistry.")

        saq_worker = SAQWorker(
            queue=self._backend._queue,
            functions=functions,
            concurrency=self._concurrency,
            burst=self.burst,
        )
        console.print(
            f"[bold green]SAQ Worker[/] started — "
            f"[cyan]{len(functions)}[/] function(s) registered."
        )
        await saq_worker.start()

    async def _process_loop(self) -> None:
        """Main processing loop for MemoryBackend.

        MemoryBackend workers already handle tasks via their own asyncio loop.
        This loop keeps the worker process alive until a shutdown signal is
        received.
        """
        try:
            while self._running:  # noqa: ASYNC110
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    async def _run_database_worker(self) -> None:
        """Poll the database for pending jobs and execute them."""
        from aura.jobs.backends.database import DatabaseBackend
        from aura.jobs.base import TaskRegistry

        backend = self._backend
        if not isinstance(backend, DatabaseBackend):
            return

        console.print(
            f"[bold green]Database Worker[/] started — "
            f"[cyan]{len(TaskRegistry.all())}[/] task(s) registered."
        )

        workers = [
            asyncio.create_task(self._database_worker_loop(backend))
            for _ in range(self._concurrency)
        ]
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            pass

    async def _database_worker_loop(self, backend: Any) -> None:
        """Consume pending jobs from the database for a single worker slot."""
        while self._running:
            jobs = await backend.claim_pending_jobs(self.queues, limit=1)
            if not jobs:
                if self.burst and not await backend.has_pending_jobs(self.queues):
                    return
                await asyncio.sleep(0.5)
                continue

            await self._execute_database_job(backend, jobs[0])

    async def _execute_database_job(self, backend: Any, job: Any) -> None:
        """Execute a claimed database job via :class:`~aura.jobs.base.TaskRegistry`."""
        from aura.jobs.backends.database import ClaimedJob, DatabaseBackend
        from aura.jobs.base import TaskRegistry

        if not isinstance(backend, DatabaseBackend) or not isinstance(job, ClaimedJob):
            return

        task_def = TaskRegistry.get(job.task_name)
        if task_def is None:
            await backend.mark_failed(
                job.id,
                f"Task {job.task_name!r} not found in TaskRegistry",
            )
            return

        max_attempts = job.max_retries + 1
        attempts = 0

        while attempts < max_attempts:
            try:
                coro = task_def.func(*job.args, **job.kwargs)
                if task_def.timeout is not None:
                    raw = await asyncio.wait_for(coro, timeout=task_def.timeout)
                else:
                    raw = await coro

                await backend.mark_success(job.id, raw)
                return

            except asyncio.TimeoutError:
                attempts += 1
                error = f"Task timed out after {task_def.timeout}s"
                if attempts < max_attempts:
                    await backend.mark_retry(job.id, error, attempts)
                else:
                    await backend.mark_failed(job.id, error)

            except Exception as exc:  # noqa: BLE001
                attempts += 1
                error = f"{type(exc).__name__}: {exc}"
                if attempts < max_attempts:
                    await backend.mark_retry(job.id, error, attempts)
                else:
                    await backend.mark_failed(job.id, error)

    def _setup_signal_handlers(self) -> None:
        """Register OS signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        def _stop(_signum: int, _frame: Any) -> None:
            console.print("\n[yellow]Signal received — initiating graceful shutdown...[/]")
            self._running = False

        # Register only when running in the main thread to avoid errors
        try:
            loop.add_signal_handler(signal.SIGTERM, lambda: _stop(signal.SIGTERM, None))
            loop.add_signal_handler(signal.SIGINT, lambda: _stop(signal.SIGINT, None))
        except (NotImplementedError, RuntimeError):
            # Windows or non-main thread; fall back to signal module
            signal.signal(signal.SIGTERM, _stop)
            signal.signal(signal.SIGINT, _stop)

    async def _shutdown(self) -> None:
        """Shut down the backend and wait for in-flight tasks."""
        console.print("[yellow]Worker shutting down gracefully...[/]")
        self._running = False

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        await self._backend.shutdown()
        console.print("[green]Worker stopped.[/]")
