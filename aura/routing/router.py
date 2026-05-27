"""Router implementation for the Aura framework."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from aura.routing.params import (
    BodyMarker,
    CookieMarker,
    HeaderMarker,
    ParamMarker,
    QueryMarker,
)

logger = logging.getLogger("aura.routing")


class Router:
    """
    Collects route handlers and converts them to Starlette :class:`~starlette.routing.Route`
    objects.

    A :class:`Router` can be associated with a prefix so that all routes it
    contains share a common URL prefix.

    Routers are typically created implicitly by the module registry, but can
    also be created manually for more fine-grained control::

        router = Router(prefix="/api/v1")

        @router.add
        @get("/users")
        async def list_users() -> list[UserResponse]:
            ...

    Args:
        prefix: URL prefix prepended to every route path.
        tags: Default OpenAPI tags applied to all routes in this router.
        guards: Guards evaluated for every route in this router.
    """

    def __init__(
        self,
        *,
        prefix: str = "",
        tags: list[str] | None = None,
        guards: list[Any] | None = None,
    ) -> None:
        self.prefix = prefix.rstrip("/")
        self.tags = tags or []
        self.guards = guards or []
        self._handlers: list[tuple[Any, str]] = []  # (handler, controller_prefix)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def include_controller(self, controller: Any, prefix: str = "") -> None:
        """Register all decorated methods from a controller class or instance.

        Args:
            controller: A class or instance whose methods carry
                ``__aura_route__`` metadata.
            prefix: Additional URL prefix prepended to each route in the
                controller.
        """
        obj = controller if not isinstance(controller, type) else controller()
        for name in dir(obj):
            method = getattr(obj, name, None)
            if method is None:
                continue
            if hasattr(method, "__aura_route__"):
                self._handlers.append((method, prefix))

    def add_handler(self, handler: Callable[..., Any], prefix: str = "") -> None:
        """Register a single function/method that carries ``__aura_route__`` metadata.

        Args:
            handler: A callable decorated with one of the HTTP method decorators.
            prefix: Additional prefix for this handler.
        """
        if not hasattr(handler, "__aura_route__"):
            raise ValueError(
                f"{handler!r} does not have __aura_route__ metadata. "
                "Did you forget a route decorator?"
            )
        self._handlers.append((handler, prefix))

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build_routes(
        self,
        openapi_gen: Any | None = None,
        global_guards: list[Any] | None = None,
    ) -> list[Route | WebSocketRoute]:
        """Convert all registered handlers into Starlette route objects.

        Args:
            openapi_gen: Optional :class:`~aura.schema.openapi.OpenAPIGenerator`
                instance to register route metadata with.
            global_guards: Guards inherited from the parent application.

        Returns:
            List of :class:`~starlette.routing.Route` or
            :class:`~starlette.routing.WebSocketRoute` objects.
        """
        routes: list[Route | WebSocketRoute] = []
        all_global_guards = list(global_guards or []) + self.guards

        for handler, ctrl_prefix in self._handlers:
            meta: dict[str, Any] = handler.__aura_route__
            method: str = meta["method"]
            path = self.prefix + ctrl_prefix + meta["path"]

            all_guards = all_global_guards + meta.get("guards", [])

            if method == "WS":
                route = WebSocketRoute(
                    path,
                    endpoint=_wrap_ws_handler(handler, all_guards),
                    name=getattr(handler, "__name__", None),
                )
                routes.append(route)
            else:
                endpoint = _wrap_http_handler(handler, all_guards)
                route = Route(
                    path,
                    endpoint=endpoint,
                    methods=[method],
                    name=getattr(handler, "__name__", None),
                )
                routes.append(route)

            # Register with OpenAPI generator
            if openapi_gen is not None:
                openapi_gen.add_route(
                    {
                        **meta,
                        "path": path,
                        "operation_id": getattr(handler, "__name__", ""),
                    }
                )

            logger.debug("Route registered: %s %s", method, path)

        return routes


# ---------------------------------------------------------------------------
# Handler wrappers
# ---------------------------------------------------------------------------


def _wrap_http_handler(
    handler: Callable[..., Any],
    guards: list[Any],
) -> Callable[..., Any]:
    """Wrap a route handler to add guard evaluation and parameter injection.

    Args:
        handler: The original async route handler.
        guards: Guards to evaluate before calling the handler.

    Returns:
        An async ASGI-compatible endpoint callable.
    """
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response

    async def endpoint(request: Request) -> Response:
        # Evaluate guards
        for guard in guards:
            allowed = await guard.can_activate(request)
            if not allowed:
                await guard.on_denied(request)

        # Resolve handler parameters
        kwargs = await _resolve_params(handler, request)

        # Call the handler
        result = handler(**kwargs)
        if inspect.iscoroutine(result):
            result = await result

        # Convert result to response
        return _to_response(result, handler.__aura_route__.get("status", 200))

    return endpoint


def _wrap_ws_handler(
    handler: Callable[..., Any],
    guards: list[Any],
) -> Callable[..., Any]:
    """Wrap a WebSocket route handler.

    Args:
        handler: The original async WebSocket handler.
        guards: Guards to evaluate (against the initial HTTP upgrade request).

    Returns:
        An async WebSocket endpoint callable.
    """

    async def endpoint(websocket: WebSocket) -> None:
        for guard in guards:
            allowed = await guard.can_activate(websocket)
            if not allowed:
                await guard.on_denied(websocket)
                return
        result = handler(websocket)
        if inspect.iscoroutine(result):
            await result

    return endpoint


async def _resolve_params(
    handler: Callable[..., Any],
    request: Any,
) -> dict[str, Any]:
    """Inspect handler type hints and extract parameters from the request.

    Supports ``Annotated[T, BodyMarker()]``, ``Annotated[T, QueryMarker()]``,
    ``Annotated[T, ParamMarker()]``, ``Annotated[T, HeaderMarker()]``, and
    ``Annotated[T, CookieMarker()]``.

    Parameters that do not carry an Aura marker are skipped (the framework
    does not try to resolve them).

    Args:
        handler: The route handler function.
        request: The :class:`~starlette.requests.Request` object.

    Returns:
        Dictionary mapping parameter name → resolved value.
    """
    import typing

    kwargs: dict[str, Any] = {}
    sig = inspect.signature(handler)

    try:
        hints = typing.get_type_hints(handler, include_extras=True)
    except Exception:
        hints = {}

    for param_name, param in sig.parameters.items():
        hint = hints.get(param_name)
        if hint is None:
            continue

        # Unwrap Annotated
        origin = typing.get_origin(hint)
        if origin is typing.Annotated:
            args = typing.get_args(hint)
            inner_type = args[0]
            markers = args[1:]
        else:
            inner_type = hint
            markers = ()

        marker = next(
            (m for m in markers if isinstance(m, (
                BodyMarker, QueryMarker, ParamMarker, HeaderMarker, CookieMarker
            ))),
            None,
        )

        if isinstance(marker, BodyMarker):
            body_bytes = await request.body()
            if body_bytes:
                import json
                body_data = json.loads(body_bytes)
                if inspect.isclass(inner_type) and hasattr(inner_type, "model_validate"):
                    kwargs[param_name] = inner_type.model_validate(body_data)
                else:
                    kwargs[param_name] = body_data
            elif param.default is not inspect.Parameter.empty:
                kwargs[param_name] = param.default

        elif isinstance(marker, QueryMarker):
            alias = marker.alias or param_name
            value = request.query_params.get(alias)
            if value is not None:
                kwargs[param_name] = _coerce(value, inner_type)
            elif param.default is not inspect.Parameter.empty:
                kwargs[param_name] = param.default
            elif marker.default is not None:
                kwargs[param_name] = marker.default

        elif isinstance(marker, ParamMarker):
            alias = marker.alias or param_name
            value = request.path_params.get(alias)
            if value is not None:
                kwargs[param_name] = _coerce(value, inner_type)

        elif isinstance(marker, HeaderMarker):
            alias = marker.alias or param_name
            if marker.convert_underscores:
                alias = alias.replace("_", "-")
            value = request.headers.get(alias)
            if value is not None:
                kwargs[param_name] = _coerce(value, inner_type)
            elif param.default is not inspect.Parameter.empty:
                kwargs[param_name] = param.default

        elif isinstance(marker, CookieMarker):
            alias = marker.alias or param_name
            value = request.cookies.get(alias)
            if value is not None:
                kwargs[param_name] = _coerce(value, inner_type)
            elif param.default is not inspect.Parameter.empty:
                kwargs[param_name] = param.default

    return kwargs


def _coerce(value: str, target_type: Any) -> Any:
    """Best-effort type coercion from a string value.

    Args:
        value: The raw string from query/path/header/cookie.
        target_type: The target Python type.

    Returns:
        The coerced value, or the original string if coercion fails.
    """
    try:
        if target_type is int:
            return int(value)
        if target_type is float:
            return float(value)
        if target_type is bool:
            return value.lower() in ("true", "1", "yes")
        return value
    except (ValueError, TypeError):
        return value


def _to_response(result: Any, status: int) -> Any:
    """Convert a handler return value into a Starlette :class:`~starlette.responses.Response`.

    - ``None`` → :class:`~starlette.responses.Response` with the given *status*.
    - Pydantic model → :class:`~starlette.responses.JSONResponse`.
    - ``dict`` or ``list`` → :class:`~starlette.responses.JSONResponse`.
    - Existing Starlette ``Response`` → returned as-is.

    Args:
        result: The value returned by the route handler.
        status: HTTP status code to use when building a new response.

    Returns:
        A Starlette response object.
    """
    from starlette.responses import JSONResponse, Response

    if result is None:
        return Response(status_code=status)

    if isinstance(result, Response):
        return result

    if hasattr(result, "model_dump"):
        return JSONResponse(content=result.model_dump(mode="json"), status_code=status)

    if isinstance(result, (dict, list)):
        return JSONResponse(content=result, status_code=status)

    # Fallback: try JSON serialisation
    try:
        import json
        return JSONResponse(content=json.loads(json.dumps(result, default=str)), status_code=status)
    except Exception:
        return JSONResponse(content={"data": str(result)}, status_code=status)
