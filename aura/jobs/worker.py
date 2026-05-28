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

    async def _run_saq_worker(self) -> None:
        """Delegate task processing to SAQ's native worker loop.

        Collects all functions registered in the :class:`~aura.jobs.base.TaskRegistry`
        and hands them to SAQ's ``Worker``.  SAQ handles polling, retries,
        and concurrency internally.
        """
        try:
            from saq import Worker as SAQWorker
        except ImportError as exc:
            raise RuntimeError(
                "SAQ is required to run the SAQ worker. "
                "Install with: pip install aura-framework[saq,redis]"
            ) from exc

        from aura.jobs.base import TaskRegistry

        functions = [task_def.func for task_def in TaskRegistry.all().values()]
        if not functions:
            console.print("[yellow]Warning:[/] No tasks registered in TaskRegistry.")

        saq_worker = SAQWorker(
            queue=self._backend._queue,
            functions=functions,
            concurrency=self._concurrency,
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
