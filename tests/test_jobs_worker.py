"""Tests for AuraWorker, backend auto-detection, and the worker CLI command."""

from __future__ import annotations

import asyncio
import importlib
import sys
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run_coro(coro: Any) -> Any:
    """Drive a coroutine to completion on a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_decorators() -> Any:
    """Re-import decorators with a clean global state."""
    mod_name = "aura.jobs.decorators"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


# ---------------------------------------------------------------------------
# Task 1: backend auto-detection
# ---------------------------------------------------------------------------


class TestBackendAutoDetection:
    """Verify that _get_default_backend() selects the right backend."""

    def test_memory_backend_auto_selected_without_broker_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without AURA__JOBS__BROKER_URL, MemoryBackend must be chosen."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.decorators import _get_default_backend

        backend = _get_default_backend()
        assert isinstance(backend, MemoryBackend)

    def test_saq_backend_selected_with_broker_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With AURA__JOBS__BROKER_URL set, SAQBackend must be instantiated."""
        monkeypatch.setenv("AURA__JOBS__BROKER_URL", "redis://localhost:6379")

        # Ensure we get a fresh call — _get_default_backend always creates new
        from aura.jobs.decorators import _get_default_backend

        backend = _get_default_backend()

        # Import here so we can introspect the type
        from aura.jobs.backends.saq_backend import SAQBackend

        assert isinstance(backend, SAQBackend)
        assert backend._redis_url == "redis://localhost:6379"

    def test_get_backend_initialises_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_get_backend() should return the same object on repeated calls."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        # Force re-initialisation of the module-level global
        import aura.jobs.decorators as dec

        dec._default_backend = None  # reset

        b1 = dec._get_backend()
        b2 = dec._get_backend()
        assert b1 is b2

    def test_set_backend_replaces_global(self) -> None:
        """set_backend() must replace the module-level default."""
        import aura.jobs.decorators as dec

        sentinel = MagicMock()
        dec.set_backend(sentinel)
        assert dec._get_backend() is sentinel

        # Restore default so other tests are not affected
        dec._default_backend = None


# ---------------------------------------------------------------------------
# Task 2: AuraWorker backend selection
# ---------------------------------------------------------------------------


class TestAuraWorkerInit:
    """Verify that AuraWorker picks the correct backend."""

    def test_worker_uses_memory_backend_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without env var or broker_url, worker should use MemoryBackend."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.worker import AuraWorker

        worker = AuraWorker()
        assert isinstance(worker._backend, MemoryBackend)

    def test_worker_uses_saq_backend_with_broker_url_arg(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Passing broker_url= forces SAQBackend selection."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        from aura.jobs.backends.saq_backend import SAQBackend
        from aura.jobs.worker import AuraWorker

        worker = AuraWorker(broker_url="redis://localhost:6379")
        assert isinstance(worker._backend, SAQBackend)
        assert worker._backend._redis_url == "redis://localhost:6379"

    def test_worker_uses_saq_backend_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AURA__JOBS__BROKER_URL env var selects SAQBackend in the worker."""
        monkeypatch.setenv("AURA__JOBS__BROKER_URL", "redis://localhost:6379")

        # Reset cached default so the env var is re-read
        import aura.jobs.decorators as dec

        dec._default_backend = None

        from aura.jobs.backends.saq_backend import SAQBackend
        from aura.jobs.worker import AuraWorker

        worker = AuraWorker()
        assert isinstance(worker._backend, SAQBackend)

        # Restore
        dec._default_backend = None

    def test_worker_respects_explicit_backend(self) -> None:
        """Passing an explicit backend must bypass all auto-detection."""
        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.worker import AuraWorker

        explicit = MemoryBackend(concurrency=1)
        worker = AuraWorker(backend=explicit)
        assert worker._backend is explicit


# ---------------------------------------------------------------------------
# Task 2: AuraWorker.run() memory path
# ---------------------------------------------------------------------------


class TestAuraWorkerRun:
    """Verify AuraWorker.run() behaves correctly for MemoryBackend."""

    async def test_worker_run_starts_and_stops_memory_backend(self) -> None:
        """Worker.run() calls startup/shutdown on MemoryBackend."""
        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.worker import AuraWorker

        backend = MemoryBackend(concurrency=1)
        cast(Any, backend).startup = AsyncMock(wraps=backend.startup)
        cast(Any, backend).shutdown = AsyncMock(wraps=backend.shutdown)

        worker = AuraWorker(backend=backend, concurrency=1)
        # Patch _process_loop to return immediately
        cast(Any, worker)._process_loop = AsyncMock()

        await worker.run()

        cast(Any, backend.startup).assert_awaited_once()
        cast(Any, backend.shutdown).assert_awaited_once()

    async def test_worker_detects_memory_backend_not_saq(self) -> None:
        """_is_saq_backend() must return False for MemoryBackend."""
        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.worker import AuraWorker

        worker = AuraWorker(backend=MemoryBackend())
        assert worker._is_saq_backend() is False


# ---------------------------------------------------------------------------
# Task 3: CLI command tests
# ---------------------------------------------------------------------------


class TestWorkerCommand:
    """Tests for the ``aura worker`` CLI command."""

    def test_worker_command_runs_memory_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """worker_command() should create AuraWorker and call asyncio.run."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        run_calls: list[Any] = []

        async def _fake_run(self: Any) -> None:  # noqa: ANN001
            run_calls.append(self)

        with patch("aura.jobs.worker.AuraWorker.run", _fake_run):
            import asyncio

            original_run = asyncio.run
            captured: list[Any] = []

            def _mock_asyncio_run(coro: Any, **kw: Any) -> None:
                captured.append(coro)
                # Drive the coroutine to completion synchronously
                import asyncio as _aio

                loop = _aio.new_event_loop()
                try:
                    loop.run_until_complete(coro)
                finally:
                    loop.close()

            with patch("asyncio.run", _mock_asyncio_run):
                from aura.cli.commands.worker import worker_command

                worker_command(
                    queues=["default"],
                    concurrency=2,
                    burst=False,
                    app_path=cast(str, None),
                    broker_url=cast(str, None),
                )

            assert original_run is not None  # sanity — asyncio.run still importable

        assert len(run_calls) == 1

    def test_worker_command_passes_queues_and_concurrency(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """worker_command() must forward queue/concurrency to AuraWorker."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        created_workers: list[Any] = []
        original_init = __import__(
            "aura.jobs.worker", fromlist=["AuraWorker"]
        ).AuraWorker.__init__

        def _capture_init(
            self: Any,
            backend: Any = None,
            *,
            queues: Any = None,
            concurrency: int = 4,
            burst: bool = False,
            broker_url: Any = None,
        ) -> None:
            original_init(
                self,
                backend=backend,
                queues=queues,
                concurrency=concurrency,
                burst=burst,
                broker_url=broker_url,
            )
            created_workers.append(self)

        with (
            patch("aura.jobs.worker.AuraWorker.__init__", _capture_init),
            patch("aura.jobs.worker.AuraWorker.run", AsyncMock()),
            patch("asyncio.run", _run_coro),
        ):
            from aura.cli.commands.worker import worker_command

            worker_command(
                queues=["emails", "default"],
                concurrency=8,
                burst=True,
                app_path=cast(str, None),
                broker_url=cast(str, None),
            )

        assert len(created_workers) == 1
        w = created_workers[0]
        assert w.queues == ["emails", "default"]
        assert w._concurrency == 8
        assert w.burst is True

    def test_worker_command_with_broker_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--broker-url must be forwarded to AuraWorker as broker_url."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        created_workers: list[Any] = []
        original_init = __import__(
            "aura.jobs.worker", fromlist=["AuraWorker"]
        ).AuraWorker.__init__

        def _capture_init(
            self: Any,
            backend: Any = None,
            *,
            queues: Any = None,
            concurrency: int = 4,
            burst: bool = False,
            broker_url: Any = None,
        ) -> None:
            original_init(
                self,
                backend=backend,
                queues=queues,
                concurrency=concurrency,
                burst=burst,
                broker_url=broker_url,
            )
            created_workers.append((self, broker_url))

        with (
            patch("aura.jobs.worker.AuraWorker.__init__", _capture_init),
            patch("aura.jobs.worker.AuraWorker.run", AsyncMock()),
            patch("asyncio.run", _run_coro),
        ):
            from aura.cli.commands.worker import worker_command

            worker_command(
                queues=["default"],
                concurrency=4,
                burst=False,
                app_path=cast(str, None),
                broker_url="redis://myhost:6379",
            )

        assert len(created_workers) == 1
        _w, captured_url = created_workers[0]
        assert captured_url == "redis://myhost:6379"

    def test_worker_command_with_app_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """--app must import the module to register tasks."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        # Create a temporary module with a dummy app attribute
        app_module = tmp_path / "dummy_app.py"
        app_module.write_text("app = object()\n")
        monkeypatch.syspath_prepend(str(tmp_path))

        with (
            patch("aura.jobs.worker.AuraWorker.run", AsyncMock()),
            patch("asyncio.run", _run_coro),
        ):
            from aura.cli.commands.worker import worker_command

            # Should not raise — the module exists and has 'app'
            worker_command(
                queues=["default"],
                concurrency=4,
                burst=False,
                app_path="dummy_app:app",
                broker_url=cast(str, None),
            )

    def test_worker_command_bad_app_path_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid --app path must exit with typer.Exit(1)."""
        import typer

        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        from aura.cli.commands.worker import worker_command

        with pytest.raises(typer.Exit):
            worker_command(
                queues=["default"],
                concurrency=4,
                burst=False,
                app_path="no_such_module_xyz:app",
                broker_url=cast(str, None),
            )


# ---------------------------------------------------------------------------
# Task A8: TaskRegistry isolation
# ---------------------------------------------------------------------------


class TestTaskRegistryIsolation:
    """Tests for TaskRegistry clear() and fixture isolation."""

    def test_task_registry_clear_removes_all_tasks(self) -> None:
        """TaskRegistry.clear() should remove all registered tasks."""
        from aura.jobs.base import TaskDefinition, TaskRegistry

        # Register a task
        def dummy_func() -> None:
            pass

        task_def = TaskDefinition(func=dummy_func, name="test_task")
        TaskRegistry.register(task_def)

        # Verify it's registered
        assert "test_task" in TaskRegistry.all()

        # Clear
        TaskRegistry.clear()

        # Verify it's gone
        assert "test_task" not in TaskRegistry.all()
        assert len(TaskRegistry.all()) == 0

    def test_task_registry_isolates_between_registrations(self) -> None:
        """TaskRegistry should isolate tasks when clear() is called between calls."""
        from aura.jobs.base import TaskDefinition, TaskRegistry

        # Register task A
        def task_a() -> None:
            pass

        task_def_a = TaskDefinition(func=task_a, name="task_a")
        TaskRegistry.register(task_def_a)
        assert "task_a" in TaskRegistry.all()

        # Clear
        TaskRegistry.clear()
        assert "task_a" not in TaskRegistry.all()

        # Register task B
        def task_b() -> None:
            pass

        task_def_b = TaskDefinition(func=task_b, name="task_b")
        TaskRegistry.register(task_def_b)

        # Verify only task B is present (task A did not leak)
        registry = TaskRegistry.all()
        assert "task_b" in registry
        assert "task_a" not in registry
        assert len(registry) == 1


# ---------------------------------------------------------------------------
# Task A7: AuraWorker queues/burst parameters
# ---------------------------------------------------------------------------


class TestAuraWorkerQueuesAndBurst:
    """Tests for AuraWorker queues and burst parameters."""

    def test_worker_respects_queues_parameter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AuraWorker.queues should be set from constructor."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.worker import AuraWorker

        worker = AuraWorker(
            backend=MemoryBackend(),
            queues=["emails", "backups", "default"],
        )
        assert worker.queues == ["emails", "backups", "default"]

    def test_worker_respects_burst_parameter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AuraWorker.burst should be set from constructor."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.worker import AuraWorker

        worker = AuraWorker(
            backend=MemoryBackend(),
            burst=True,
        )
        assert worker.burst is True

    def test_worker_default_queues(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AuraWorker should default to ['default'] queue."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.worker import AuraWorker

        worker = AuraWorker(backend=MemoryBackend())
        assert worker.queues == ["default"]

    def test_worker_default_burst(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AuraWorker should default to burst=False."""
        monkeypatch.delenv("AURA__JOBS__BROKER_URL", raising=False)

        from aura.jobs.backends.memory import MemoryBackend
        from aura.jobs.worker import AuraWorker

        worker = AuraWorker(backend=MemoryBackend())
        assert worker.burst is False

