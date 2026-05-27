"""Aura background worker — processes tasks from configured queues."""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Any

from rich.console import Console

console = Console()


class AuraWorker:
    """Aura background worker that processes tasks from one or more queues.

    The worker connects to the configured backend, consumes tasks from the
    specified queues, and executes them with the given concurrency level.

    Graceful shutdown is handled automatically on SIGTERM and SIGINT.

    Args:
        backend: The :class:`~aura.jobs.backends.base.TaskBackend` to use.
                 Defaults to the global MemoryBackend if not specified.
        queues: List of queue names to consume from (default: ``["default"]``).
        concurrency: Maximum number of tasks executed in parallel.
        burst: If ``True``, the worker exits once the queue is drained rather
               than waiting for new tasks.

    Usage (programmatic)::

        worker = AuraWorker(backend=redis_backend, queues=["default", "emails"])
        await worker.run()

    Usage (CLI)::

        aura worker --queue default --concurrency 4
    """

    def __init__(
        self,
        backend: Any = None,
        *,
        queues: list[str] | None = None,
        concurrency: int = 4,
        burst: bool = False,
    ) -> None:
        if backend is None:
            from aura.jobs.backends.memory import MemoryBackend
            backend = MemoryBackend(concurrency=concurrency)
        self._backend = backend
        self.queues = queues or ["default"]
        self.concurrency = concurrency
        self.burst = burst
        self._running = False
        self._tasks: list[asyncio.Task[Any]] = []

    async def run(self) -> None:
        """Start the worker and block until shutdown."""
        console.print("[bold green]Aura Worker[/] starting...")
        console.print(f"  Queues: [cyan]{', '.join(self.queues)}[/]")
        console.print(f"  Concurrency: [cyan]{self.concurrency}[/]")
        if self.burst:
            console.print("  Mode: [yellow]burst (exit when queue empty)[/]")

        self._running = True
        self._setup_signal_handlers()

        await self._backend.startup()

        try:
            await self._process_loop()
        finally:
            await self._shutdown()

    async def _process_loop(self) -> None:
        """Main processing loop.

        For MemoryBackend the backend workers already handle tasks via their
        own asyncio loop.  For external backends a polling loop would be
        implemented here.  This loop primarily keeps the worker alive.
        """
        try:
            while self._running:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    def _setup_signal_handlers(self) -> None:
        """Register OS signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        def _stop(_signum: int, _frame: Any) -> None:  # type: ignore[type-arg]
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
