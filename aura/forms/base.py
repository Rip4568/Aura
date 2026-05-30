"""AuraForm — base class for all Aura HTML/API forms."""

from __future__ import annotations

import inspect
from typing import Any, ClassVar

from aura.forms.exceptions import FieldValidationError, FormValidationError
from aura.forms.fields import Field, ForeignKeyField, ManyToManyField


class AuraForm:
    """Base class for Aura forms.

    Declare fields as class attributes::

        class SignupForm(AuraForm):
            username = CharField(max_length=30)
            email    = EmailField()
            age      = IntField(required=False)

    Usage::

        form = SignupForm(raw_data={"username": "alice", "email": "a@b.com"})
        if await form.is_valid():
            data = form.cleaned_data
        else:
            errors = form.errors  # dict[str, list[str]]

    With a database session (enables ForeignKeyField / ManyToManyField)::

        form = PostForm(raw_data=body, session=db_session)

    With an existing instance (for partial updates)::

        form = PostForm(raw_data=body, instance=post, session=session)

    Attributes:
        _fields: Collected Field descriptors keyed by attribute name.
                 Populated automatically by ``__init_subclass__``.
        cleaned_data: Validated Python values after ``is_valid()`` returns ``True``.
        errors: Dict mapping field names (or ``"__all__"``) to error lists.
    """

    _fields: ClassVar[dict[str, Field[Any]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # Collect fields from the entire MRO (base classes first so that
        # subclass fields override parent fields with the same name).
        collected: dict[str, Field[Any]] = {}
        for base in reversed(cls.__mro__):
            for name, attr in vars(base).items():
                if isinstance(attr, Field):
                    collected[name] = attr
        cls._fields = collected

    def __init__(
        self,
        raw_data: dict[str, Any] | None = None,
        *,
        session: Any = None,
        instance: Any = None,
    ) -> None:
        self._raw_data: dict[str, Any] = raw_data or {}
        self._session = session
        self._instance = instance
        self.cleaned_data: dict[str, Any] = {}
        self.errors: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Validation pipeline
    # ------------------------------------------------------------------

    async def full_clean(self) -> bool:
        """Run the full validation pipeline.

        Steps:
        1. For every field, coerce and validate the raw value.
           Fields with a session that are FK/M2M use ``to_python_with_session``.
        2. For every field with no error, call ``clean_<fieldname>()``
           if it exists.  The return value replaces the value in
           ``self.cleaned_data``.
        3. If no field errors exist, call ``clean()`` (cross-field validation).
           Errors raised there are stored under ``"__all__"``.

        Returns:
            ``True`` when there are no errors.
        """
        self.cleaned_data = {}
        self.errors = {}

        for name, field in self._fields.items():
            raw = self._raw_data.get(name)
            try:
                if self._session is not None and isinstance(
                    field, (ForeignKeyField, ManyToManyField)
                ):
                    value = await field.to_python_with_session(raw, self._session)
                    field.validate(value)
                else:
                    value = field.run(raw)
                self.cleaned_data[name] = value
            except FieldValidationError as exc:
                self.errors.setdefault(name, []).extend(exc.messages)

        # Per-field clean_<name>() hooks
        for name in list(self.cleaned_data.keys()):
            if name in self.errors:
                continue
            clean_method_name = f"clean_{name}"
            clean_method = getattr(self.__class__, clean_method_name, None)
            if clean_method is not None:
                try:
                    result = clean_method(self)
                    if inspect.iscoroutine(result):
                        result = await result
                    self.cleaned_data[name] = result
                except FieldValidationError as exc:
                    self.errors.setdefault(name, []).extend(exc.messages)

        # Cross-field clean()
        if not self.errors:
            try:
                await self.clean()
            except FieldValidationError as exc:
                self.errors.setdefault("__all__", []).extend(exc.messages)
            except FormValidationError as exc:
                for field_name, messages in exc.errors.items():
                    self.errors.setdefault(field_name, []).extend(messages)

        return not self.errors

    async def clean(self) -> None:
        """Cross-field validation hook.

        Override in subclasses to perform multi-field checks.
        Raise ``FieldValidationError`` to add errors to ``"__all__"``,
        or ``FormValidationError`` to distribute errors per field.
        """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def is_valid(self) -> bool:
        """Return ``True`` if the form is valid (runs ``full_clean``)."""
        return await self.full_clean()

    async def save(self, *, commit: bool = True) -> Any:
        """Validate and persist the form data.

        Raises:
            FormValidationError: when the form is invalid.
        """
        if not await self.full_clean():
            raise FormValidationError(self.errors)
        return await self._save(commit=commit)

    async def _save(self, *, commit: bool) -> Any:
        """Override in subclasses (or use ``ModelForm``) to persist data."""
        raise NotImplementedError("Implemente _save() ou use ModelForm.")

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @property
    def has_errors(self) -> bool:
        """``True`` when the form contains any validation errors."""
        return bool(self.errors)

    def errors_as_json(self) -> dict[str, list[str]]:
        """Return a JSON-serialisable copy of ``self.errors``."""
        return dict(self.errors)
