from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aura.admin.base import ModelAdmin, _registry
from aura.admin.security import ensure_csrf_token, validate_csrf, verify_password
from aura.core.request import AuraRequest
from aura.core.response import redirect
from aura.di.decorators import injectable
from aura.exceptions.http import NotFoundException
from aura.forms.modelform import build_admin_form_fields, parse_model_form_data
from aura.orm.base import AuraModel
from aura.routing.decorators import delete, get, post
from aura.templates.response import HtmlResponse

# Configure Jinja2 environment pointing to local templates directory
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=True,
)


async def render_admin(template_name: str, context: dict[str, Any]) -> HtmlResponse:
    """Helper to render templates inside the admin local folder."""
    # Add navigation/sidebar info with sorted model names
    models_nav = []
    for m in _registry.keys():
        models_nav.append({
            "name": m.__name__,
            "path_name": m.__name__.lower(),
        })
    models_nav.sort(key=lambda x: x["name"])

    full_context = {
        "models_nav": models_nav,
        "getattr": getattr,
        "isinstance": isinstance,
        "str": str,
        "bool": bool,
        "datetime": datetime,
        "date": date,
        "has_password": bool(
            os.getenv("AURA_ADMIN_PASSWORD")
            or os.getenv("AURA__ADMIN__PASSWORD")
        ),
        **context,
    }

    template = env.get_template(template_name)
    html_content = await template.render_async(**full_context)
    return HtmlResponse(html_content)


@injectable
class AdminController:
    """Administrative control panel interface and route endpoints."""

    @property
    def session(self) -> Any:
        """Resolve the active database session from ContextVar."""
        from aura.orm.session import current_session
        sess = current_session.get()
        if sess is None:
            raise RuntimeError(
                "Database session not initialized. Make sure DatabaseMiddleware is configured."
            )
        return sess

    def get_model_and_admin(self, model_name: str) -> tuple[type[AuraModel], ModelAdmin]:
        """Look up a registered model and its ModelAdmin by case-insensitive name."""
        for model, admin in _registry.items():
            if model.__name__.lower() == model_name.lower():
                return model, admin
        raise NotFoundException(f"Model '{model_name}' not found in registry.")

    def _session(self, request: AuraRequest) -> dict[str, Any]:
        sess: dict[str, Any] | None = getattr(request.state, "session", None)
        if sess is None:
            raise RuntimeError(
                "SessionMiddleware is required for Aura Admin security. "
                "Please add SessionMiddleware to your application's middleware list in main.py."
            )
        return sess

    def _csrf_context(self, request: AuraRequest) -> dict[str, str]:
        sess = getattr(request.state, "session", None)
        if sess is None:
            return {}
        return {"csrf_token": ensure_csrf_token(sess)}

    def _csrf_from_request(self, request: AuraRequest, form_data: Any = None) -> str | None:
        token = None
        if form_data is not None:
            token = form_data.get("csrf_token")
        if not token:
            token = request.headers.get("X-CSRF-Token")
        return str(token) if token else None

    def _require_csrf(self, request: AuraRequest, form_data: Any = None) -> None:
        from aura.exceptions.http import ForbiddenException

        if not validate_csrf(self._session(request), self._csrf_from_request(request, form_data)):
            raise ForbiddenException("Invalid or missing CSRF token")

    def check_auth(self, request: AuraRequest) -> Any | None:
        """Check if password security is active and the user is authenticated.

        Returns a RedirectResponse if redirect is needed, otherwise None.
        """
        password = os.getenv("AURA_ADMIN_PASSWORD") or os.getenv("AURA__ADMIN__PASSWORD")
        if not password:
            is_debug = os.getenv("AURA__DEBUG", "true").lower() in ("true", "1")
            if not is_debug:
                raise RuntimeError(
                    "AURA_ADMIN_PASSWORD must be configured in production "
                    "environments (AURA__DEBUG=false) to secure the "
                    "Administrative Panel. Please set the environment variable."
                )
            return None

        sess = getattr(request.state, "session", None)
        if sess is None:
            raise RuntimeError(
                "SessionMiddleware is required for Aura Admin password security. "
                "Please add SessionMiddleware to your application's middleware list in main.py."
            )

        if not sess.get("admin_authenticated"):
            from aura.core.response import redirect
            return redirect("/admin/login")

        return None

    @get("/admin/login")
    async def auth_login_get(self, request: AuraRequest) -> Any:
        """Render the admin login page."""
        password = os.getenv("AURA_ADMIN_PASSWORD") or os.getenv("AURA__ADMIN__PASSWORD")
        if not password:
            from aura.core.response import redirect
            return redirect("/admin")

        sess = getattr(request.state, "session", None)
        if sess is not None and sess.get("admin_authenticated"):
            from aura.core.response import redirect
            return redirect("/admin")

        return await render_admin("login.html", {"error": None, **self._csrf_context(request)})

    @post("/admin/login")
    async def auth_login_post(self, request: AuraRequest) -> Any:
        """Process the admin login submission."""
        password = os.getenv("AURA_ADMIN_PASSWORD") or os.getenv("AURA__ADMIN__PASSWORD")
        if not password:
            from aura.core.response import redirect
            return redirect("/admin")

        sess = getattr(request.state, "session", None)
        if sess is None:
            raise RuntimeError(
                "SessionMiddleware is required for Aura Admin password security. "
                "Please add SessionMiddleware to your application's middleware list in main.py."
            )

        form_data = await request.form()
        self._require_csrf(request, form_data)
        submitted = form_data.get("password")

        if submitted and verify_password(str(submitted), password):
            sess["admin_authenticated"] = True
            ensure_csrf_token(sess)
            from aura.core.response import redirect
            return redirect("/admin")

        return await render_admin(
            "login.html",
            {
                "error": "Chave de acesso incorreta. Tente novamente.",
                **self._csrf_context(request),
            },
        )

    @post("/admin/logout")
    async def auth_logout(self, request: AuraRequest) -> Any:
        """Log out from the administrative panel."""
        sess = getattr(request.state, "session", None)
        form_data = await request.form()
        if sess is not None:
            self._require_csrf(request, form_data)
            sess.pop("admin_authenticated", None)

        from aura.core.response import redirect
        return redirect("/admin/login")

    def apply_filters_and_search(
        self, stmt: Any, model: type[AuraModel], admin: ModelAdmin, query_params: Any
    ) -> Any:
        """Apply the search_fields and list_filters to a select/count statement."""
        from sqlalchemy import or_
        from sqlalchemy.sql.sqltypes import Boolean, Float, Integer

        # Search fields via `.like()`
        q = query_params.get("q", "").strip()
        if q and admin.search_fields:
            conds = []
            for field in admin.search_fields:
                col = getattr(model, field, None)
                if col is not None:
                    conds.append(col.like(f"%{q}%"))
            if conds:
                stmt = stmt.where(or_(*conds))

        # Filter fields via `==`
        for filter_field in admin.list_filter:
            val = query_params.get(filter_field)
            if val is not None and val != "":
                col = getattr(model, filter_field, None)
                if col is not None:
                    if isinstance(col.type, Boolean):
                        parsed_val: Any = val.lower() in ("true", "1", "yes")
                    elif isinstance(col.type, Integer):
                        try:
                            parsed_val = int(val)
                        except ValueError:
                            parsed_val = val
                    elif isinstance(col.type, Float):
                        try:
                            parsed_val = float(val)
                        except ValueError:
                            parsed_val = val
                    else:
                        parsed_val = val
                    stmt = stmt.where(col == parsed_val)
        return stmt

    @get("/admin")
    async def dashboard(self, request: AuraRequest) -> Any:
        """Dashboard home displaying registered models and row counts."""
        auth_res = self.check_auth(request)
        if auth_res:
            return auth_res

        from sqlalchemy import func, select

        counts: dict[str, int] = {}
        for model in _registry.keys():
            stmt = select(func.count()).select_from(model)
            res = await self.session.execute(stmt)
            counts[model.__name__] = res.scalar() or 0

        return await render_admin("dashboard.html", {
            "counts": counts,
            **self._csrf_context(request),
        })

    @get("/admin/{model_name}")
    async def list_records(self, request: AuraRequest, model_name: str) -> Any:
        """Paginated, searchable table of records for a given model."""
        auth_res = self.check_auth(request)
        if auth_res:
            return auth_res

        from sqlalchemy import func, select

        model, admin = self.get_model_and_admin(model_name)

        # Pagination
        try:
            page = int(request.query_params.get("page", "1"))
            if page < 1:
                page = 1
        except ValueError:
            page = 1

        per_page = 10
        offset = (page - 1) * per_page

        # Build filter & search criteria
        base_stmt = select(model)
        base_stmt = self.apply_filters_and_search(base_stmt, model, admin, request.query_params)

        # Count total records matching filters
        count_stmt = select(func.count()).select_from(model)
        count_stmt = self.apply_filters_and_search(count_stmt, model, admin, request.query_params)
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar() or 0

        # Fetch records (order by primary key descending)
        data_stmt = base_stmt.order_by(model.id.desc()).limit(per_page).offset(offset)
        data_res = await self.session.execute(data_stmt)
        items = list(data_res.scalars().all())

        # Determine display fields
        headers = admin.list_display if admin.list_display else list(model.__table__.columns.keys())

        # Generate distinct choices for filters
        filter_options = {}
        for f in admin.list_filter:
            col = getattr(model, f, None)
            if col is not None:
                from sqlalchemy.sql.sqltypes import Boolean
                if isinstance(col.type, Boolean):
                    filter_options[f] = [("true", "Yes"), ("false", "No")]
                else:
                    try:
                        distinct_stmt = select(col).distinct().order_by(col).limit(50)
                        res = await self.session.execute(distinct_stmt)
                        options = res.scalars().all()
                        filter_options[f] = [
                            (str(opt), str(opt)) for opt in options if opt is not None
                        ]
                    except Exception:
                        filter_options[f] = []

        # Calculate pagination metadata
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1

        q_param = request.query_params.get("q", "")

        active_filters = {}
        for f in admin.list_filter:
            val = request.query_params.get(f)
            if val is not None and val != "":
                active_filters[f] = val

        context = {
            "model_name": model.__name__,
            "model_name_lower": model.__name__.lower(),
            "admin": admin,
            "items": items,
            "headers": headers,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev,
            "q": q_param,
            "active_filters": active_filters,
            "filter_options": filter_options,
            **self._csrf_context(request),
        }

        if request.htmx.is_htmx:
            return await render_admin("table_body.html", context)
        return await render_admin("list.html", context)

    @get("/admin/{model_name}/create")
    async def create_form(self, request: AuraRequest, model_name: str) -> Any:
        """Display creation form with columns inspected and mapped to field types."""
        auth_res = self.check_auth(request)
        if auth_res:
            return auth_res

        model, admin = self.get_model_and_admin(model_name)

        return await render_admin("form.html", {
            "model_name": model.__name__,
            "model_name_lower": model.__name__.lower(),
            "fields": build_admin_form_fields(model),
            "is_create": True,
            **self._csrf_context(request),
        })

    @post("/admin/{model_name}/create")
    async def create_record(self, request: AuraRequest, model_name: str) -> Any:
        """Validate form data, persist creation, and redirect."""
        auth_res = self.check_auth(request)
        if auth_res:
            return auth_res

        model, admin = self.get_model_and_admin(model_name)
        form_data = await request.form()
        self._require_csrf(request, form_data)

        insert_data, errors = await parse_model_form_data(model, form_data)

        if errors:
            return await render_admin("form.html", {
                "model_name": model.__name__,
                "model_name_lower": model.__name__.lower(),
                "fields": build_admin_form_fields(
                    model, form_data=form_data, errors=errors
                ),
                "is_create": True,
                "errors": errors,
                **self._csrf_context(request),
            })

        obj = model(**insert_data)
        self.session.add(obj)
        await self.session.flush()

        if request.htmx.is_htmx:
            res = HtmlResponse()
            res.htmx.trigger("recordCreated").redirect(f"/admin/{model.__name__.lower()}")
            return res
        return redirect(f"/admin/{model.__name__.lower()}")

    @get("/admin/{model_name}/{record_id}/edit")
    async def edit_form(
        self, request: AuraRequest, model_name: str, record_id: int
    ) -> Any:
        """Display edit form populated with current database values."""
        auth_res = self.check_auth(request)
        if auth_res:
            return auth_res

        from sqlalchemy import select
        model, admin = self.get_model_and_admin(model_name)

        stmt = select(model).where(model.id == record_id)
        res = await self.session.execute(stmt)
        record = res.scalar()
        if not record:
            raise NotFoundException(f"Record with ID {record_id} not found.")

        values = {
            col.name: getattr(record, col.name)
            for col in model.__table__.columns
        }

        return await render_admin("form.html", {
            "model_name": model.__name__,
            "model_name_lower": model.__name__.lower(),
            "fields": build_admin_form_fields(model, values=values),
            "is_create": False,
            "record_id": record_id,
            **self._csrf_context(request),
        })

    @post("/admin/{model_name}/{record_id}/edit")
    async def edit_record(self, request: AuraRequest, model_name: str, record_id: int) -> Any:
        """Validate edit form, update record attributes, flush, and redirect."""
        auth_res = self.check_auth(request)
        if auth_res:
            return auth_res

        from sqlalchemy import select
        model, admin = self.get_model_and_admin(model_name)

        stmt = select(model).where(model.id == record_id)
        res = await self.session.execute(stmt)
        record = res.scalar()
        if not record:
            raise NotFoundException(f"Record with ID {record_id} not found.")

        form_data = await request.form()
        self._require_csrf(request, form_data)

        update_data, errors = await parse_model_form_data(model, form_data)

        if errors:
            return await render_admin("form.html", {
                "model_name": model.__name__,
                "model_name_lower": model.__name__.lower(),
                "fields": build_admin_form_fields(
                    model, form_data=form_data, errors=errors
                ),
                "is_create": False,
                "record_id": record_id,
                "errors": errors,
                **self._csrf_context(request),
            })

        for key, value in update_data.items():
            setattr(record, key, value)

        await self.session.flush()

        if request.htmx.is_htmx:
            res = HtmlResponse()
            res.htmx.trigger("recordUpdated").redirect(f"/admin/{model.__name__.lower()}")
            return res
        return redirect(f"/admin/{model.__name__.lower()}")

    @post("/admin/{model_name}/{record_id}/delete")
    async def delete_record_post(
        self, request: AuraRequest, model_name: str, record_id: int
    ) -> Any:
        """Endpoint to handle standard deletion form submission."""
        return await self.perform_delete(request, model_name, record_id)

    @delete("/admin/{model_name}/{record_id}")
    async def delete_record_delete(
        self, request: AuraRequest, model_name: str, record_id: int
    ) -> Any:
        """Endpoint to handle HTMX DELETE requests."""
        return await self.perform_delete(request, model_name, record_id)

    async def perform_delete(self, request: AuraRequest, model_name: str, record_id: int) -> Any:
        """Internal helper logic to execute record deletion."""
        auth_res = self.check_auth(request)
        if auth_res:
            return auth_res

        form_data = None
        if request.method == "POST":
            form_data = await request.form()
        self._require_csrf(request, form_data)

        from sqlalchemy import select
        model, admin = self.get_model_and_admin(model_name)

        stmt = select(model).where(model.id == record_id)
        res = await self.session.execute(stmt)
        record = res.scalar()
        if not record:
            raise NotFoundException(f"Record with ID {record_id} not found.")

        await self.session.delete(record)
        await self.session.flush()

        if request.htmx.is_htmx:
            res = HtmlResponse()
            res.htmx.trigger("recordDeleted").redirect(f"/admin/{model.__name__.lower()}")
            return res
        return redirect(f"/admin/{model.__name__.lower()}")
