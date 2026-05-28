"""Router implementation for the Aura framework."""

from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any, cast

from starlette.responses import Response
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

            response_type = meta.get("response_type", "json")

            if method == "WS":
                route: Route | WebSocketRoute = WebSocketRoute(
                    path,
                    endpoint=_wrap_ws_handler(handler, all_guards),
                    name=getattr(handler, "__name__", None),
                )
                routes.append(route)
            elif response_type == "html":
                endpoint = _wrap_html_handler(
                    handler,
                    all_guards,
                    template=meta.get("template"),
                    status=meta.get("status", 200),
                )
                route = Route(
                    path,
                    endpoint=endpoint,
                    methods=[method],
                    name=getattr(handler, "__name__", None),
                )
                routes.append(route)
            elif response_type == "sse":
                endpoint = _wrap_sse_handler(handler, all_guards)
                route = Route(
                    path,
                    endpoint=endpoint,
                    methods=["GET"],
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
        try:
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
            return _to_response(result, getattr(handler, "__aura_route__", {}).get("status", 200))

        except Exception as exc:  # noqa: BLE001
            return _handle_exception(exc)

    return endpoint


def _wrap_html_handler(
    handler: Callable[..., Any],
    guards: list[Any],
    *,
    template: str | None = None,
    status: int = 200,
) -> Callable[..., Any]:
    """Wrap a route handler decorated with ``@html`` to render HTML templates.

    The handler return value is converted as follows:

    - Existing Starlette ``Response`` → returned as-is.
    - :class:`~aura.templates.context.TemplateContext` → rendered via the
      template engine using *template*.
    - ``str`` → wrapped in :class:`~aura.templates.response.HtmlResponse`.
    - ``dict`` with a *template* → rendered via the template engine.
    - Anything else → falls back to JSON (edge-case safety).

    Args:
        handler: The original async route handler.
        guards: Guards to evaluate before calling the handler.
        template: Default template name (from ``@html(template=...)``).
        status: HTTP status code.

    Returns:
        An async ASGI-compatible endpoint callable.
    """
    from starlette.requests import Request
    from starlette.responses import Response

    async def endpoint(request: Request) -> Response:
        try:
            for guard in guards:
                allowed = await guard.can_activate(request)
                if not allowed:
                    await guard.on_denied(request)

            kwargs = await _resolve_params(handler, request)

            result = handler(**kwargs)
            if inspect.iscoroutine(result):
                result = await result

            return await _to_html_response(result, template=template, status=status)

        except Exception as exc:  # noqa: BLE001
            return _handle_html_exception(exc)

    return endpoint


def _wrap_sse_handler(
    handler: Callable[..., Any],
    guards: list[Any],
) -> Callable[..., Any]:
    """Wrap an async-generator handler as a Server-Sent Events endpoint.

    The handler must be an async generator that yields strings or dicts.
    Dicts are serialised to JSON and sent as ``data:`` lines.

    Args:
        handler: The original async generator route handler.
        guards: Guards to evaluate before streaming begins.

    Returns:
        An async ASGI-compatible endpoint callable.
    """
    from starlette.requests import Request
    from starlette.responses import Response

    async def endpoint(request: Request) -> Response:
        try:
            for guard in guards:
                allowed = await guard.can_activate(request)
                if not allowed:
                    await guard.on_denied(request)

            kwargs = await _resolve_params(handler, request)

            async def event_stream() -> AsyncGenerator[bytes, None]:
                import json as _json

                gen = handler(**kwargs)
                if inspect.isasyncgen(gen):
                    async for item in gen:
                        if isinstance(item, dict):
                            data = _json.dumps(item, default=str)
                            yield f"data: {data}\n\n".encode()
                        elif isinstance(item, str):
                            # Already-formatted SSE line (may include "event:", "id:", etc.)
                            if item.startswith("data:") or item.startswith("event:"):
                                yield f"{item}\n\n".encode()
                            else:
                                yield f"data: {item}\n\n".encode()
                        elif hasattr(item, "model_dump"):
                            data = _json.dumps(item.model_dump(mode="json"), default=str)
                            yield f"data: {data}\n\n".encode()
                        else:
                            yield f"data: {item!s}\n\n".encode()
                else:
                    # Regular async function that returns an iterable
                    result = gen
                    if inspect.iscoroutine(result):
                        result = await result
                    if hasattr(result, "__aiter__"):
                        async for item in result:
                            data = _json.dumps(item, default=str) if isinstance(item, dict) else str(item)
                            yield f"data: {data}\n\n".encode()

            from starlette.responses import StreamingResponse
            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        except Exception as exc:  # noqa: BLE001
            return _handle_exception(exc)

    return endpoint


async def _to_html_response(
    result: Any,
    *,
    template: str | None,
    status: int,
) -> Response:
    """Convert a handler return value to an HTML response.

    Args:
        result: Value returned by the route handler.
        template: Template name to use when *result* is a context or dict.
        status: HTTP status code.

    Returns:
        A Starlette response object with ``Content-Type: text/html``.
    """
    from starlette.responses import Response

    # Already a fully-formed response — pass through
    if isinstance(result, Response):
        return result

    # Plain string → wrap as HTML
    if isinstance(result, str):
        try:
            from aura.templates.response import HtmlResponse
            return HtmlResponse(result, status_code=status)
        except ImportError:
            from starlette.responses import HTMLResponse
            return HTMLResponse(result, status_code=status)

    # TemplateContext (has to_template_dict) — render via engine
    if hasattr(result, "to_template_dict"):
        if template is None:
            raise ValueError(
                "Handler returned a TemplateContext but no template was specified. "
                "Use @html('/path', template='my_template.html') to set one."
            )
        try:
            from aura.templates.shortcuts import render as aura_render
            return await aura_render(template, result, status=status)
        except ImportError:
            raise RuntimeError(
                "Template engine not installed. "
                "Run: pip install 'aura-web[templates]'"
            )

    # dict with a template → render via engine
    if isinstance(result, dict) and template:
        try:
            from aura.templates.shortcuts import render as aura_render
            return await aura_render(template, result, status=status)
        except ImportError:
            pass  # fall through to JSON fallback

    # Pydantic model / dict / list — fall back to JSON
    # (edge case: @html handler returned data without a template)
    from starlette.responses import JSONResponse
    if hasattr(result, "model_dump"):
        return JSONResponse(content=result.model_dump(mode="json"), status_code=status)
    if isinstance(result, (dict, list)):
        return JSONResponse(content=result, status_code=status)

    from starlette.responses import HTMLResponse
    return HTMLResponse(str(result), status_code=status)


def _handle_html_exception(exc: Exception) -> "Response":
    """Convert an exception raised in an ``@html`` handler to an HTML error response.

    HTTP exceptions render a minimal HTML error page.
    Other exceptions fall back to the JSON error handler so error monitoring
    still captures the stack trace.

    Args:
        exc: The exception to convert.

    Returns:
        A Starlette response object.
    """
    try:
        from aura.exceptions.http import HTTPException as AuraHTTPException
        if isinstance(exc, AuraHTTPException):
            html_content = (
                "<!DOCTYPE html><html><head>"
                f"<title>Error {exc.status_code}</title></head><body>"
                f"<h1>{exc.status_code}</h1>"
                f"<p>{exc.message}</p>"
                "</body></html>"
            )
            try:
                from aura.templates.response import HtmlResponse
                return HtmlResponse(html_content, status_code=exc.status_code)
            except ImportError:
                from starlette.responses import HTMLResponse
                return HTMLResponse(html_content, status_code=exc.status_code)
    except ImportError:
        pass

    # Non-HTTP exception → JSON 500 (preserves stack-trace logging)
    return _handle_exception(exc)


def _handle_exception(exc: Exception) -> "Response":
    """Convert an exception raised in a route handler to an HTTP response.

    Handles:
    - :class:`~aura.exceptions.http.HTTPException` subclasses → structured JSON.
    - :class:`pydantic.ValidationError` → 422 with field details.
    - All other exceptions → 500 (sanitised — no stack trace exposed).

    Args:
        exc: The exception to convert.

    Returns:
        A Starlette :class:`~starlette.responses.JSONResponse` response.
    """
    from starlette.responses import JSONResponse

    # Aura HTTP exceptions (NotFoundException, BadRequestException, etc.)
    try:
        from aura.exceptions.http import HTTPException as AuraHTTPException
        if isinstance(exc, AuraHTTPException):
            return JSONResponse(
                content=exc.to_dict(),
                status_code=exc.status_code,
                headers=exc.headers,
            )
    except ImportError:
        pass

    # Pydantic validation errors
    try:
        from pydantic import ValidationError
        if isinstance(exc, ValidationError):
            errors = [
                {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                for e in exc.errors()
            ]
            return JSONResponse(content={"detail": errors}, status_code=422)
    except ImportError:
        pass

    # Fallback: 500
    import logging
    logging.getLogger("aura.routing").exception("Unhandled error in route handler")
    return JSONResponse(
        content={"error": {"status": 500, "message": "Internal server error"}},
        status_code=500,
    )


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

        # Inject AuraRequest / starlette Request by type — no marker required
        if inspect.isclass(inner_type):
            from starlette.requests import Request as _StarletteRequest
            if issubclass(inner_type, _StarletteRequest):
                # If the request is already the right type, reuse it directly.
                # Otherwise wrap it (e.g. plain starlette Request → AuraRequest).
                if isinstance(request, inner_type):
                    kwargs[param_name] = request
                else:
                    try:
                        from collections.abc import Awaitable, MutableMapping
                        _send = cast(
                            Callable[[MutableMapping[str, Any]], Awaitable[None]],
                            getattr(request, "_send", None),
                        )
                        kwargs[param_name] = inner_type(
                            request.scope, request.receive, _send
                        )
                    except Exception:
                        kwargs[param_name] = request
                continue

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


def _to_response(result: Any, status: int) -> "Response":
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
