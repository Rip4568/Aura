"""Aura Forms — v0.6.0

HTML/API form validation with full type safety and async support.

Quick start::

    from aura.forms import AuraForm, CharField, EmailField, IntField

    class SignupForm(AuraForm):
        username = CharField(max_length=30)
        email    = EmailField()
        age      = IntField(required=False)

    form = SignupForm(raw_data={"username": "alice", "email": "a@b.com"})
    if await form.is_valid():
        print(form.cleaned_data)
"""

from aura.forms.base import AuraForm
from aura.forms.exceptions import FieldValidationError, FormValidationError
from aura.forms.fields import (
    BoolField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    Field,
    FileField,
    FloatField,
    ForeignKeyField,
    IntField,
    JSONField,
    ManyToManyField,
    MultipleChoiceField,
    SlugField,
    TextField,
    TimeField,
    URLField,
    UUIDField,
)
from aura.forms.validators import (
    validate_email,
    validate_max_length,
    validate_max_value,
    validate_min_length,
    validate_min_value,
    validate_regex,
    validate_slug,
    validate_url,
)

__all__ = [
    # Base form
    "AuraForm",
    # Exceptions
    "FieldValidationError",
    "FormValidationError",
    # Abstract base
    "Field",
    # Scalar fields
    "CharField",
    "TextField",
    "IntField",
    "FloatField",
    "DecimalField",
    "BoolField",
    "EmailField",
    "URLField",
    "SlugField",
    # Date/time fields
    "DateField",
    "DateTimeField",
    "TimeField",
    # Special fields
    "UUIDField",
    "JSONField",
    # Choice fields
    "ChoiceField",
    "MultipleChoiceField",
    # File field
    "FileField",
    # Relational fields
    "ForeignKeyField",
    "ManyToManyField",
    # Validators
    "validate_min_length",
    "validate_max_length",
    "validate_min_value",
    "validate_max_value",
    "validate_email",
    "validate_url",
    "validate_slug",
    "validate_regex",
]

# ---------------------------------------------------------------------------
# v0.6.1 extras — not yet implemented (imported lazily to avoid hard errors)
# ---------------------------------------------------------------------------
try:
    from aura.forms.modelform import ModelForm  # noqa: F401
except ImportError:
    pass

try:
    from aura.forms.widgets import Widget  # noqa: F401
except ImportError:
    pass
