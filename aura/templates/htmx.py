"""htmx integration for the Aura template system.

htmx (https://htmx.org) allows making AJAX requests directly from HTML
attributes. The server returns HTML fragments instead of JSON, keeping
logic on the server without a full JS framework.

This module provides:
- :class:`HtmxInfo` — parsed htmx request headers
- :class:`HtmxResponseHeaders` — builder for htmx response directives
- Helper functions for detecting and responding to htmx requests

htmx request headers reference:
    HX-Request:         "true" when the request comes from htmx
    HX-Trigger:         id of the element that triggered the request
    HX-Trigger-Name:    name attribute of the triggering element
    HX-Target:          id of the target element
    HX-Current-URL:     URL of the page making the request
    HX-Boosted:         "true" if request is via hx-boost
    HX-Prompt:          value of a prompt shown to the user
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HtmxInfo:
    """Parsed htmx headers from an incoming request.

    Attached to every :class:`~aura.core.request.AuraRequest` as ``.htmx``.
    Check ``request.htmx.is_htmx`` to know if the request came from htmx.

    Example::

        @get("/users")
        async def list_users(self, request: AuraRequest) -> HtmlResponse:
            if request.htmx.is_htmx:
                # Return only the table rows fragment
                return render("partials/user_rows.html", ctx)
            # Return full page with layout
            return render("users/index.html", ctx)
    """

    is_htmx: bool = False
    trigger: str | None = None
    trigger_name: str | None = None
    target: str | None = None
    current_url: str | None = None
    boosted: bool = False
    prompt: str | None = None

    @classmethod
    def from_headers(cls, headers: Any) -> "HtmxInfo":
        """Parse htmx info from request headers.

        Args:
            headers: Mapping of HTTP headers (Starlette Headers or dict).

        Returns:
            A populated :class:`HtmxInfo` instance.
        """
        is_htmx = headers.get("hx-request", "").lower() == "true"
        return cls(
            is_htmx=is_htmx,
            trigger=headers.get("hx-trigger") or None,
            trigger_name=headers.get("hx-trigger-name") or None,
            target=headers.get("hx-target") or None,
            current_url=headers.get("hx-current-url") or None,
            boosted=headers.get("hx-boosted", "").lower() == "true",
            prompt=headers.get("hx-prompt") or None,
        )


@dataclass
class HtmxResponseHeaders:
    """Builder for htmx response control headers.

    htmx reads specific response headers to decide what to do after
    processing the server response: trigger events, redirect, refresh, etc.

    Example::

        response = render("partials/user_row.html", ctx)
        response.htmx.trigger("userCreated").retarget("#user-list")
        return response

    htmx response headers reference:
        HX-Trigger:         trigger events on the client
        HX-Redirect:        redirect to a new URL (full page load)
        HX-Location:        push URL without full reload (history)
        HX-Push-Url:        push a new URL into browser history
        HX-Reswap:          override the swap behaviour
        HX-Retarget:        override the target element
        HX-Refresh:         "true" to force a full refresh
        HX-Replace-Url:     replace the current URL in history
    """

    _headers: dict[str, str] = field(default_factory=dict)

    def trigger(self, *events: str | dict[str, Any]) -> "HtmxResponseHeaders":
        """Trigger client-side events after the response is processed.

        Args:
            events: Event names (str) or dicts with event + detail data.

        Example::

            htmx.trigger("userSaved", "toastShown")
            htmx.trigger({"userSaved": {"id": 42}})
        """
        import json
        if len(events) == 1 and isinstance(events[0], str):
            self._headers["HX-Trigger"] = events[0]
        else:
            payload: dict[str, Any] = {}
            for e in events:
                if isinstance(e, str):
                    payload[e] = {}
                else:
                    payload.update(e)
            self._headers["HX-Trigger"] = json.dumps(payload)
        return self

    def redirect(self, url: str) -> "HtmxResponseHeaders":
        """Redirect to a URL (full page load).

        Args:
            url: Target URL.
        """
        self._headers["HX-Redirect"] = url
        return self

    def push_url(self, url: str) -> "HtmxResponseHeaders":
        """Push a new URL into browser history without full page load.

        Args:
            url: URL to push, or ``"false"`` to prevent history update.
        """
        self._headers["HX-Push-Url"] = url
        return self

    def replace_url(self, url: str) -> "HtmxResponseHeaders":
        """Replace the current URL in browser history.

        Args:
            url: URL to set as the current URL.
        """
        self._headers["HX-Replace-Url"] = url
        return self

    def retarget(self, css_selector: str) -> "HtmxResponseHeaders":
        """Override the target element for the swap.

        Args:
            css_selector: CSS selector for the new target element.
        """
        self._headers["HX-Retarget"] = css_selector
        return self

    def reswap(self, strategy: str) -> "HtmxResponseHeaders":
        """Override the swap strategy.

        Args:
            strategy: Swap method (``"innerHTML"``, ``"outerHTML"``,
                ``"beforebegin"``, ``"afterend"``, ``"delete"``, etc.)
        """
        self._headers["HX-Reswap"] = strategy
        return self

    def refresh(self) -> "HtmxResponseHeaders":
        """Force a full page refresh."""
        self._headers["HX-Refresh"] = "true"
        return self

    def location(self, url: str, **kwargs: Any) -> "HtmxResponseHeaders":
        """Navigate without full page reload (htmx history push).

        Args:
            url: URL to navigate to.
            **kwargs: Extra htmx location options (target, select, swap, etc.)
        """
        import json
        if kwargs:
            self._headers["HX-Location"] = json.dumps({"path": url, **kwargs})
        else:
            self._headers["HX-Location"] = url
        return self

    def to_dict(self) -> dict[str, str]:
        """Return headers dict to pass to the response.

        Returns:
            Dictionary of HX-* headers.
        """
        return dict(self._headers)
