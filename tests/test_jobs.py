"""Tests for the Aura jobs system (tasks, dispatch, MemoryBackend)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest

from aura.jobs.backends.memory import MemoryBackend
from aura.jobs.base import TaskDefinition, TaskRegistry, TaskResult, TaskStatus
from aura.jobs.decorators import PeriodicTaskDefinition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _simple_task(x: int, y: int) -> int:
    """A simple test coroutine that adds two numbers."""
    return x + y


async def _failing_task() -> None:
    """A test coroutine that always raises."""
    raise ValueError("intentional failure")


async def _slow_task() -> str:
    """A test coroutine that takes longer than any test timeout."""
    await asyncio.sleep(10)
    return "done"


# ---------------------------------------------------------------------------
# MemoryBackend
# ---------------------------------------------------------------------------

class TestMemoryBackend:
    """Tests for the in-memory task queue backend."""

    @pytest.fixture
    async def backend(self) -> AsyncGenerator[MemoryBackend, None]:
        b = MemoryBackend(concurrency=2)
        await b.startup()
        yield b
        await b.shutdown()

    async def test_enqueue_returns_pending_result(self, backend: MemoryBackend) -> None:
        task_def = TaskDefinition(func=_simple_task, name="test.simple")
        result = await backend.enqueue(task_def, args=(1, 2))

        assert isinstance(result, TaskResult)
        assert result.task_id
        assert result.status == TaskStatus.PENDING

    async def test_task_completes_successfully(self, backend: MemoryBackend) -> None:
        task_def = TaskDefinition(func=_simple_task, name="test.simple_ok")
        result = await backend.enqueue(task_def, args=(3, 4))

        final = await backend.wait_for_result(result.task_id, timeout=5.0)
        assert final is not None
        assert final.status == TaskStatus.SUCCESS
        assert final.result == 7

    async def test_task_failure_sets_failed_status(self, backend: MemoryBackend) -> None:
        task_def = TaskDefinition(func=_failing_task, name="test.failing", retry=0)
        result = await backend.enqueue(task_def)

        final = await backend.wait_for_result(result.task_id, timeout=5.0)
        assert final is not None
        assert final.status == TaskStatus.FAILED
        assert "ValueError" in (final.error or "")

    async def test_task_retries_on_failure(self, backend: MemoryBackend) -> None:
        attempts: list[int] = []

        async def _flaky() -> str:
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("not ready yet")
            return "ok"

        task_def = TaskDefinition(func=_flaky, name="test.flaky", retry=3)
        result = await backend.enqueue(task_def)

        final = await backend.wait_for_result(result.task_id, timeout=5.0)
        assert final is not None
        assert final.status == TaskStatus.SUCCESS
        assert len(attempts) == 3

    async def test_task_timeout(self, backend: MemoryBackend) -> None:
        task_def = TaskDefinition(func=_slow_task, name="test.timeout", timeout=1)
        result = await backend.enqueue(task_def)

        final = await backend.wait_for_result(result.task_id, timeout=5.0)
        assert final is not None
        assert final.status == TaskStatus.FAILED
        assert "timed out" in (final.error or "").lower()

    async def test_delayed_enqueue(self, backend: MemoryBackend) -> None:
        task_def = TaskDefinition(func=_simple_task, name="test.delayed")
        result = await backend.enqueue(task_def, args=(10, 20), delay=1)

        # Should still be pending immediately
        immediate = await backend.get_result(result.task_id)
        assert immediate is not None
        assert immediate.status == TaskStatus.PENDING

        # After delay, should succeed
        final = await backend.wait_for_result(result.task_id, timeout=5.0)
        assert final is not None
        assert final.status == TaskStatus.SUCCESS
        assert final.result == 30

    async def test_get_result_unknown_id_returns_none(self, backend: MemoryBackend) -> None:
        result = await backend.get_result("non-existent-id")
        assert result is None

    async def test_kwargs_forwarded(self, backend: MemoryBackend) -> None:
        async def _greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        task_def = TaskDefinition(func=_greet, name="test.kwargs")
        result = await backend.enqueue(task_def, kwargs={"name": "Aura", "greeting": "Hi"})

        final = await backend.wait_for_result(result.task_id, timeout=5.0)
        assert final is not None
        assert final.status == TaskStatus.SUCCESS
        assert final.result == "Hi, Aura!"


# ---------------------------------------------------------------------------
# TaskRegistry
# ---------------------------------------------------------------------------

class TestTaskRegistry:
    """Tests for the global task registry."""

    def setup_method(self) -> None:
        TaskRegistry.clear()

    def test_register_and_retrieve(self) -> None:
        async def _dummy() -> None:
            pass

        task_def = TaskDefinition(func=_dummy, name="registry.test")
        TaskRegistry.register(task_def)

        retrieved = TaskRegistry.get("registry.test")
        assert retrieved is task_def

    def test_all_returns_copy(self) -> None:
        async def _a() -> None:
            pass

        async def _b() -> None:
            pass

        TaskRegistry.register(TaskDefinition(func=_a, name="a"))
        TaskRegistry.register(TaskDefinition(func=_b, name="b"))

        all_tasks = TaskRegistry.all()
        assert "a" in all_tasks
        assert "b" in all_tasks
        # Modify copy — should not affect registry
        del all_tasks["a"]
        assert TaskRegistry.get("a") is not None

    def test_get_unknown_returns_none(self) -> None:
        assert TaskRegistry.get("does.not.exist") is None

    def test_clear(self) -> None:
        async def _c() -> None:
            pass

        TaskRegistry.register(TaskDefinition(func=_c, name="c"))
        TaskRegistry.clear()
        assert TaskRegistry.all() == {}


# ---------------------------------------------------------------------------
# PeriodicTaskDefinition
# ---------------------------------------------------------------------------

class TestPeriodicTaskDefinition:
    """Tests for periodic task definition dataclass."""

    def test_cron_and_run_on_startup(self) -> None:
        async def _noop() -> None:
            pass

        defn = PeriodicTaskDefinition(
            func=_noop,
            name="periodic.noop",
            cron="0 8 * * *",
            run_on_startup=True,
        )
        assert defn.cron == "0 8 * * *"
        assert defn.run_on_startup is True
        assert defn.queue == "default"
