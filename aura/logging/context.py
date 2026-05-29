"""Context variables for request tracking and logging."""

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Coroutine
from typing import Any, TypeVar

# Keys that stdlib logging reserves in LogRecord.__dict__ — cannot appear in extra={}
_LOGRECORD_RESERVED: frozenset[str] = frozenset({
    "name", "msg", "args", "created", "filename", "funcName",
    "levelname", "levelno", "lineno", "message", "module", "msecs",
    "pathname", "process", "processName", "relativeCreated",
    "thread", "threadName", "exc_info", "exc_text", "stack_info", "taskName",
})

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_var: contextvars.ContextVar[int | str | None] = contextvars.ContextVar(
    "user_id", default=None
)
extra_context_var: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "extra_context", default={}
)

T = TypeVar("T")


def set_request_id(request_id: str) -> None:
    """Set the request ID for the current context.

    Args:
        request_id: Unique identifier for this request.
    """
    request_id_var.set(request_id)


def set_user_id(user_id: int | str) -> None:
    """Set the user ID for the current context.

    Args:
        user_id: User identifier (can be int or string).
    """
    user_id_var.set(user_id)


def get_current_context() -> dict[str, Any]:
    """Get the current context variables as a dictionary.

    Returns:
        Dictionary with keys: request_id, user_id, and any extra context.
    """
    context: dict[str, Any] = {}
    req_id = request_id_var.get()
    if req_id is not None:
        context["request_id"] = req_id

    user_id = user_id_var.get()
    if user_id is not None:
        context["user_id"] = user_id

    extra = extra_context_var.get()
    if extra:
        context.update({k: v for k, v in extra.items() if k not in _LOGRECORD_RESERVED})

    return context


def clear_context() -> None:
    """Clear all context variables."""
    request_id_var.set(None)
    user_id_var.set(None)
    extra_context_var.set({})


async def run_with_context(
    coro: Coroutine[Any, Any, T] | Awaitable[T], context_dict: dict[str, Any]
) -> T:
    """Run a coroutine with a specific logging context.

    This function propagates context variables (request_id, user_id, etc.) to
    background tasks and jobs, ensuring that logs in those tasks include the
    original request context.

    Args:
        coro: Coroutine or awaitable to execute.
        context_dict: Dictionary with context values (keys: "request_id",
                      "user_id", etc.).

    Returns:
        The result of the coroutine.

    Example::

        async def background_job(user_id: int) -> None:
            logger.info("Processing user")  # Will include user_id in context

        # In a request handler:
        from aura.logging.context import run_with_context

        @app.post("/users")
        async def create_user() -> dict[str, Any]:
            user = await repo.create(name="John")

            # Start background job with request context
            await run_with_context(
                background_job(user.id),
                context_dict={"user_id": user.id, "request_id": "xyz"}
            )
            return {"id": user.id}
    """
    # Set context variables and collect reset tokens so we can restore state on exit.
    tokens: list[tuple[contextvars.ContextVar[Any], contextvars.Token[Any]]] = []
    if "request_id" in context_dict:
        tokens.append((request_id_var, request_id_var.set(context_dict["request_id"])))
    if "user_id" in context_dict:
        tokens.append((user_id_var, user_id_var.set(context_dict["user_id"])))
    extra = {k: v for k, v in context_dict.items() if k not in ("request_id", "user_id")}
    if extra:
        tokens.append((extra_context_var, extra_context_var.set(extra)))

    try:
        return await coro
    finally:
        for var, token in tokens:
            var.reset(token)
