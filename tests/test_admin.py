from __future__ import annotations

import re
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.orm import Mapped, mapped_column

from aura import Aura, Module
from aura.admin import AdminModule, ModelAdmin, register
from aura.admin.base import _registry
from aura.admin.security import hash_password
from aura.orm import AuraModel, db
from aura.orm.middleware import DatabaseMiddleware
from aura.testing.client import AuraTestClient


# 1. Declare a test model specifically for admin panel validation
class AdminTestItem(AuraModel):
    __tablename__ = "admin_test_items"

    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    price: Mapped[float] = mapped_column(default=0.0)
    is_available: Mapped[bool] = mapped_column(default=True)


# 2. Register the test model with list displays, filters, and search fields
@register(AdminTestItem)
class AdminTestItemAdmin(ModelAdmin):
    list_display = ["id", "name", "price", "is_available"]
    list_filter = ["is_available"]
    search_fields = ["name", "description"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def admin_app() -> AsyncGenerator[Aura, None]:
    # Initialize SQLite memory database
    db.init("sqlite+aiosqlite:///:memory:", echo=False)
    await db.create_all(AuraModel)

    from starlette.middleware import Middleware

    from aura import SessionMiddleware

    @Module(
        controllers=[],
        imports=[AdminModule],
        providers=[],
    )
    class TestRootModule:
        pass

    app = Aura(
        modules=[TestRootModule],
        middleware=[
            Middleware(SessionMiddleware, secret_key="test-session-secret"),
            DatabaseMiddleware,
        ],
    )
    yield app

    await db.drop_all(AuraModel)
    await db.close()


@pytest.fixture
async def admin_client(admin_app: Aura) -> AsyncGenerator[AuraTestClient, None]:
    async with AuraTestClient(admin_app) as client:
        yield client


class TestAdminPanel:
    """Integration and unit tests for Aura's Async Administrative Panel."""

    def test_registry_registration(self) -> None:
        """Verify that models register correctly into base registry."""
        assert AdminTestItem in _registry
        assert isinstance(_registry[AdminTestItem], AdminTestItemAdmin)
        assert _registry[AdminTestItem].model == AdminTestItem
        assert _registry[AdminTestItem].list_display == ["id", "name", "price", "is_available"]

    async def test_get_dashboard(self, admin_client: AuraTestClient) -> None:
        """Test GET /admin dashboard displays list of registered models."""
        response = await admin_client.get("/admin")
        assert response.status_code == 200
        text = response.text
        assert "Aura Admin" in text
        assert "AdminTestItem" in text
        assert "Dashboard" in text

    async def test_get_list_empty(self, admin_client: AuraTestClient) -> None:
        """Test GET /admin/{model} returns listing page with empty state."""
        response = await admin_client.get("/admin/admintestitem")
        assert response.status_code == 200
        text = response.text
        assert "AdminTestItem" in text
        assert "No records found" in text

    async def test_create_and_read_record(self, admin_client: AuraTestClient) -> None:
        """Test create GET, POST validation errors, and successful POST creation."""
        # 1. Render creation form
        form_response = await admin_client.get("/admin/admintestitem/create")
        assert form_response.status_code == 200
        assert 'name="name"' in form_response.text
        assert 'name="description"' in form_response.text

        # 2. POST with missing required 'name' should fail and re-render errors
        err_response = await admin_client.post(
            "/admin/admintestitem/create",
            data={"name": "", "price": "19.99", "is_available": "on"},
        )
        assert err_response.status_code == 200
        assert "is required" in err_response.text

        # 3. Successful POST create
        success_response = await admin_client.post(
            "/admin/admintestitem/create",
            data={
                "name": "Super Widget",
                "description": "Blazing fast aura widget",
                "price": "49.99",
                "is_available": "on",
            },
        )
        # Should redirect back to list view
        assert success_response.status_code == 307
        assert "/admin/admintestitem" in success_response.headers["Location"]

        # 4. View records in the list view
        list_response = await admin_client.get("/admin/admintestitem")
        assert list_response.status_code == 200
        assert "Super Widget" in list_response.text
        assert "49.99" in list_response.text

    async def test_edit_record(self, admin_client: AuraTestClient) -> None:
        """Test editing a record and updating attributes."""
        # Create a record first
        await admin_client.post(
            "/admin/admintestitem/create",
            data={
                "name": "Original Name",
                "description": "Old description",
                "price": "100.00",
            },
        )

        # Retrieve the record to find its ID
        async with db.session() as s:
            from sqlalchemy import select

            stmt = select(AdminTestItem).where(AdminTestItem.name == "Original Name")
            res = await s.execute(stmt)
            item = res.scalar()
            assert item is not None
            record_id = item.id

        # Render edit form
        edit_form_res = await admin_client.get(f"/admin/admintestitem/{record_id}/edit")
        assert edit_form_res.status_code == 200
        assert "Original Name" in edit_form_res.text

        # Update record attributes via POST edit
        update_res = await admin_client.post(
            f"/admin/admintestitem/{record_id}/edit",
            data={
                "name": "Updated Name",
                "description": "New description",
                "price": "150.00",
                "is_available": "on",
            },
        )
        assert update_res.status_code == 307

        # Verify attributes changed
        async with db.session() as s:
            updated_item = await s.get(AdminTestItem, record_id)
            assert updated_item is not None
            assert updated_item.name == "Updated Name"
            assert updated_item.price == 150.00
            assert updated_item.is_available is True

    async def test_delete_record(self, admin_client: AuraTestClient) -> None:
        """Test deleting a record via POST and DELETE requests."""
        # Create an item to delete
        await admin_client.post(
            "/admin/admintestitem/create",
            data={"name": "To Be Deleted", "price": "10.00"},
        )

        async with db.session() as s:
            from sqlalchemy import select

            stmt = select(AdminTestItem).where(AdminTestItem.name == "To Be Deleted")
            res = await s.execute(stmt)
            item = res.scalar()
            assert item is not None
            record_id = item.id

        # Get the list page to extract CSRF token
        list_res = await admin_client.get("/admin/admintestitem")
        assert list_res.status_code == 200
        
        # Extract CSRF token from the page - look for value="..." in hidden input
        import re
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', list_res.text)
        csrf_token = match.group(1) if match else ""
        assert csrf_token, "CSRF token not found in page"

        # Delete the item with CSRF token
        delete_res = await admin_client.post(
            f"/admin/admintestitem/{record_id}/delete",
            data={"csrf_token": csrf_token},
        )
        assert delete_res.status_code == 307

        # Verify it's gone
        async with db.session() as s:
            deleted_item = await s.get(AdminTestItem, record_id)
            assert deleted_item is None

    async def test_htmx_partial_rendering(self, admin_client: AuraTestClient) -> None:
        """Test HTMX request header returns only partial HTML (table body)."""
        # Create an item
        await admin_client.post(
            "/admin/admintestitem/create",
            data={"name": "HTMX Widget", "price": "2.99"},
        )

        # GET request with HX-Request header
        htmx_response = await admin_client.get(
            "/admin/admintestitem",
            headers={"hx-request": "true"},
        )
        assert htmx_response.status_code == 200
        # Partial template should NOT contain the layout structure
        # (like Aura Admin title or body tags)
        assert "<html" not in htmx_response.text
        assert "HTMX Widget" in htmx_response.text
        assert "<table" in htmx_response.text


class TestAdminPasswordSecurity:
    """Test suite validating admin panel password-only authentication and session lifecycle."""

    @staticmethod
    async def _csrf_from_login(client: AuraTestClient) -> str:
        login_page = await client.get("/admin/login")
        match = re.search(r'name="csrf_token" value="([^"]+)"', login_page.text)
        assert match is not None
        return match.group(1)

    @pytest.fixture
    async def secure_app(self, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Aura, None]:
        # Set the admin password env variable
        monkeypatch.setenv("AURA_ADMIN_PASSWORD", "super-secret-key")

        # Initialize SQLite memory database
        db.init("sqlite+aiosqlite:///:memory:", echo=False)
        await db.create_all(AuraModel)

        from aura import SessionMiddleware

        @Module(
            controllers=[],
            imports=[AdminModule],
            providers=[],
        )
        class TestRootModule:
            pass

        from starlette.middleware import Middleware
        app = Aura(
            modules=[TestRootModule],
            middleware=[
                Middleware(SessionMiddleware, secret_key="test-session-secret"),
                DatabaseMiddleware,
            ]
        )
        yield app

        await db.drop_all(AuraModel)
        await db.close()

    @pytest.fixture
    async def secure_client(self, secure_app: Aura) -> AsyncGenerator[AuraTestClient, None]:
        async with AuraTestClient(secure_app) as client:
            yield client

    async def test_requires_auth_redirects_to_login(self, secure_client: AuraTestClient) -> None:
        """Accessing the admin dashboard when password is set redirects to /admin/login."""
        res = await secure_client.get("/admin", follow_redirects=False)
        assert res.status_code == 307
        assert res.headers["location"] == "/admin/login"

        # Check rendering of the login page
        login_res = await secure_client.get("/admin/login")
        assert login_res.status_code == 200
        assert "Painel Administrativo" in login_res.text
        assert "Chave de Acesso" in login_res.text

    async def test_failed_login_shows_error(self, secure_client: AuraTestClient) -> None:
        """Submitting an invalid password re-renders login with error message."""
        csrf = await self._csrf_from_login(secure_client)
        res = await secure_client.post(
            "/admin/login",
            data={"password": "wrong-password", "csrf_token": csrf},
        )
        assert res.status_code == 200
        assert "Chave de acesso incorreta" in res.text

    async def test_login_rejects_missing_csrf(self, secure_client: AuraTestClient) -> None:
        res = await secure_client.post("/admin/login", data={"password": "super-secret-key"})
        assert res.status_code == 400

    async def test_successful_login_session_flow(self, secure_client: AuraTestClient) -> None:
        """Submitting correct password authenticates user, redirects to admin, and allows access."""
        csrf = await self._csrf_from_login(secure_client)
        login_res = await secure_client.post(
            "/admin/login",
            data={"password": "super-secret-key", "csrf_token": csrf},
        )
        assert login_res.status_code == 307
        assert login_res.headers["location"] == "/admin"

        dashboard_res = await secure_client.get("/admin")
        assert dashboard_res.status_code == 200
        assert "Dashboard" in dashboard_res.text
        assert "Sair" in dashboard_res.text

        csrf_match = re.search(
            r'name="csrf_token" value="([^"]+)"',
            dashboard_res.text,
        )
        assert csrf_match is not None
        logout_res = await secure_client.post(
            "/admin/logout",
            data={"csrf_token": csrf_match.group(1)},
            follow_redirects=False,
        )
        assert logout_res.status_code == 307
        assert logout_res.headers["location"] == "/admin/login"

        blocked_res = await secure_client.get("/admin", follow_redirects=False)
        assert blocked_res.status_code == 307
        assert blocked_res.headers["location"] == "/admin/login"

    async def test_hashed_password_from_env(
        self, secure_app: Aura, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PBKDF2-hashed admin password from env is accepted on login."""
        monkeypatch.setenv("AURA_ADMIN_PASSWORD", hash_password("hashed-admin-pass"))
        async with AuraTestClient(secure_app) as client:
            csrf = await self._csrf_from_login(client)
            res = await client.post(
                "/admin/login",
                data={"password": "hashed-admin-pass", "csrf_token": csrf},
            )
            assert res.status_code == 307

