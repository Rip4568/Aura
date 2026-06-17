"""Tests for security controls and protection middleware."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Mapped, mapped_column
from starlette.testclient import TestClient

from aura import Aura, Module, get
from aura.middleware.security import SecurityHeadersMiddleware
from aura.orm import AuraModel, db


class SecurityUser(AuraModel):
    """Test model for security controls validation."""
    __tablename__ = "security_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    email: Mapped[str] = mapped_column()


class DummyController:
    @get("/hello")
    async def hello(self) -> str:
        return "secure world"


@Module(controllers=[DummyController])
class DummyModule:
    pass


# ---------------------------------------------------------------------------
# Test Security Headers Middleware
# ---------------------------------------------------------------------------

def test_security_headers_default_injection() -> None:
    app = Aura(
        modules=[DummyModule],
        middleware=[SecurityHeadersMiddleware],
    )
    client = TestClient(app)
    response = client.get("/hello")

    assert response.status_code == 200
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-xss-protection"] == "0"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "strict-transport-security" not in response.headers


def test_security_headers_customization() -> None:
    from starlette.middleware import Middleware
    app = Aura(
        modules=[DummyModule],
        middleware=[
            Middleware(
                SecurityHeadersMiddleware,
                content_security_policy="default-src 'self'",
                x_frame_options="SAMEORIGIN",
                hsts_max_age=3600,
            ),
        ],
    )
    client = TestClient(app)
    response = client.get("/hello")

    assert response.status_code == 200
    assert response.headers["content-security-policy"] == "default-src 'self'"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert response.headers["strict-transport-security"] == "max-age=3600; includeSubDomains"


# ---------------------------------------------------------------------------
# Test SQL Injection Prevention in explain()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_sql_injection_protection() -> None:
    # Initialize SQLite memory database
    db.init("sqlite+aiosqlite:///:memory:", echo=False)
    await db.create_all(AuraModel)

    try:
        # Create user with a potential SQL Injection payload inside name
        malicious_payload = "'; DROP TABLE security_users; --"
        
        # Build query set
        qs = SecurityUser.objects.filter(name=malicious_payload)
        
        # Call explain() - should successfully execute the EXPLAIN QUERY PLAN 
        # using parameter binding rather than literal interpolation (preventing injection).
        async with db.session() as session:
            explain_output = await qs.using(session).explain()
            assert isinstance(explain_output, str)
            assert len(explain_output) > 0

            sql_str, params, _ = qs.using(session)._compile_parameterized(qs._build_stmt())
            assert malicious_payload not in sql_str
            assert len(params) > 0

            # Double check database is completely intact (no DROP TABLE took effect)
            users = await qs.using(session).all()
            assert len(users) == 0

    finally:
        await db.drop_all(AuraModel)
        await db.close()


def test_production_secret_key_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from pydantic import ValidationError

    from aura.config.base import AuraConfig

    # Default secret key with debug=True should be allowed
    cfg_dev = AuraConfig(debug=True)
    assert cfg_dev.secret_key == "change-me-in-production-32chars!!"

    # Mock sys.modules to temporarily remove "pytest" so the validator executes
    fake_modules = dict(sys.modules)
    fake_modules.pop("pytest", None)
    monkeypatch.setattr(sys, "modules", fake_modules)

    # Default secret key with debug=False (production) should raise a validation error
    err_msg = "SECRET_KEY must be changed from the default value in production."
    with pytest.raises(ValidationError, match=err_msg):
        AuraConfig(debug=False)

    # Custom secret key with debug=False should be allowed
    cfg_prod = AuraConfig(debug=False, secret_key="custom-secure-secret-key-32chars!!")
    assert cfg_prod.secret_key == "custom-secure-secret-key-32chars!!"
