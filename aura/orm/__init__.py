"""Aura ORM layer — SQLAlchemy async wrapper with repository pattern."""

try:
    from aura.orm.aggregates import Avg, Count, Max, Min, Sum
    from aura.orm.base import AuraModel, email_type, pk_int, str_255, text_long
    from aura.orm.expressions import Q
    from aura.orm.factories import Factory, SubFactory
    from aura.orm.fields import (
        BooleanField,
        CharField,
        DateField,
        DateTimeField,
        DecimalField,
        EmailField,
        FloatField,
        ForeignKeyField,
        IntegerField,
        ManyToManyField,
        TextField,
        relationship,
    )
    from aura.orm.middleware import DatabaseMiddleware
    from aura.orm.query import MultipleObjectsReturnedException, QuerySet
    from aura.orm.repository import Page, PkType, Repository
    from aura.orm.seeders import (
        Seeder,
        ensure_seeded_table_exists,
        has_seeded,
        mark_as_seeded,
    )
    from aura.orm.session import DatabaseManager, db

    __all__ = [
        "AuraModel",
        "Repository",
        "Page",
        "PkType",
        "DatabaseManager",
        "db",
        "QuerySet",
        "Q",
        "MultipleObjectsReturnedException",
        "Count",
        "Sum",
        "Avg",
        "Min",
        "Max",
        "DatabaseMiddleware",
        "str_255",
        "email_type",
        "text_long",
        "pk_int",
        "CharField",
        "TextField",
        "EmailField",
        "BooleanField",
        "IntegerField",
        "FloatField",
        "DecimalField",
        "DateTimeField",
        "DateField",
        "ForeignKeyField",
        "ManyToManyField",
        "relationship",
        "Factory",
        "SubFactory",
        "Seeder",
        "ensure_seeded_table_exists",
        "has_seeded",
        "mark_as_seeded",
    ]
except ImportError:
    __all__ = []

try:
    from aura.orm.profiling import (
        AuraN1Warning,
        AuraQueryThresholdWarning,
        AuraSlowQueryWarning,
        QueryLog,
        QueryRecord,
        query_log,
        setup_query_profiling,
        track_queries,
    )

    __all__ += [
        "QueryLog",
        "QueryRecord",
        "AuraN1Warning",
        "AuraQueryThresholdWarning",
        "AuraSlowQueryWarning",
        "query_log",
        "track_queries",
        "setup_query_profiling",
    ]
except ImportError:
    pass
