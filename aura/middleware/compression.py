"""Compression middleware for Aura — gzip/brotli response compression."""

from __future__ import annotations

import importlib
from typing import Any


class CompressionMiddleware:
    """Response compression middleware supporting gzip and brotli encoding.

    Transparently compresses responses when the client indicates support via
    the ``Accept-Encoding`` request header.  Brotli is preferred over gzip
    when both are available.

    Args:
        minimum_size: Minimum response body size (bytes) to compress.
                      Smaller responses are sent uncompressed.
        gzip_level: Gzip compression level (1–9, default 6).  Applied only when
                    brotli is not installed; ignored when BrotliMiddleware is used.
        brotli_quality: Brotli compression quality (0–11, default 4).  Applied only
                        when ``brotli`` / ``starlette_brotli`` are installed.

    Example::

        app = Aura(
            middleware=[
                CompressionMiddleware(minimum_size=512, brotli_quality=6),
            ]
        )
    """

    def __init__(
        self,
        minimum_size: int = 500,
        gzip_level: int = 6,
        brotli_quality: int = 4,
    ) -> None:
        if not 1 <= gzip_level <= 9:
            raise ValueError("gzip_level must be between 1 and 9")
        if not 0 <= brotli_quality <= 11:
            raise ValueError("brotli_quality must be between 0 and 11")
        self.minimum_size = minimum_size
        self.gzip_level = gzip_level
        self.brotli_quality = brotli_quality

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
            from starlette.middleware.gzip import GZipMiddleware
        except ImportError as exc:
            raise ImportError(
                "starlette is required for CompressionMiddleware."
            ) from exc

        # Prefer brotli if available
        try:
            importlib.import_module("brotli")
            brotli_middleware_cls = importlib.import_module(
                "starlette_brotli"
            ).BrotliMiddleware
            return brotli_middleware_cls(
                app,
                minimum_size=self.minimum_size,
                quality=self.brotli_quality,
            )
        except ImportError:
            pass

        return GZipMiddleware(
            app,
            minimum_size=self.minimum_size,
            compresslevel=self.gzip_level,
        )

    def __call__(self, app: Any) -> Any:
        """Alias for :meth:`build`."""
        return self.build(app)
