"""Guards module — request authorization guards."""

from aura.guards.base import Guard
from aura.guards.rate_limit import RateLimitGuard

__all__ = [
    "Guard",
    "RateLimitGuard",
]

# JWTGuard is optional (requires aura-web[jwt])
try:
    from aura.guards.jwt import JWTGuard

    __all__ = __all__ + ["JWTGuard"]
except ImportError:
    pass
