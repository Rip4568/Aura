"""Aura built-in ASGI middleware."""

from aura.middleware.compression import CompressionMiddleware
from aura.middleware.cors import CORSMiddleware
from aura.middleware.rate_limit import RateLimitMiddleware

__all__ = [
    "CORSMiddleware",
    "CompressionMiddleware",
    "RateLimitMiddleware",
]

# SessionMiddleware is optional (requires aura-web[session])
try:
    from aura.middleware.session import SessionMiddleware

    __all__ = __all__ + ["SessionMiddleware"]
except ImportError:
    pass
