"""Compression middleware for Aura — gzip/brotli response compression."""

from __future__ import annotations

from typing import Any


class CompressionMiddleware:
    """Response compression middleware supporting gzip and brotli encoding.

    Transparently compresses responses when the client indicates support via
    the ``Accept-Encoding`` request header.  Brotli is preferred over gzip
    when both are available.

    Args:
        minimum_size: Minimum response body size (bytes) to compress.
                      Smaller responses are sent uncompressed.
        gzip_level: Gzip compression level (1–9, default 6).

    Example::

        app = Aura(
            middleware=[
                CompressionMiddleware(minimum_size=512),
            ]
        )
    """

    def __init__(
        self,
        minimum_size: int = 500,
        gzip_level: int = 6,
    ) -> None:
        self.minimum_size = minimum_size
        self.gzip_level = gzip_level

    def build(self, app: Any) -> Any:
        """Wrap *app* with compression middleware.

        Tries to use Starlette's GZipMiddleware; if ``brotli`` is installed,
        BrotliMiddleware from ``starlette_brotli`` is preferred.

        Args:
            app: The ASGI application to wrap.

        Returns:
            A wrapped ASGI application.
        """
        try:
            from starlette.middleware.gzip import GZipMiddleware  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "starlette is required for CompressionMiddleware."
            ) from exc

        # Prefer brotli if available
        try:
            import brotli  # noqa: F401 — check availability
            from starlette_brotli import BrotliMiddleware  # type: ignore[import]
            return BrotliMiddleware(app, minimum_size=self.minimum_size)
        except ImportError:
            pass

        return GZipMiddleware(app, minimum_size=self.minimum_size)

    def __call__(self, app: Any) -> Any:
        """Alias for :meth:`build`."""
        return self.build(app)
