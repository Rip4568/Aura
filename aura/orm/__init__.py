"""Aura ORM layer — SQLAlchemy async wrapper with repository pattern."""

try:
    from aura.orm.aggregates import Avg, Count, Max, Min, Sum
    from aura.orm.base import AuraModel
    from aura.orm.repository import Page, PkType, Repository
    from aura.orm.expressions import Q
    from aura.orm.query import MultipleObjectsReturnedException, QuerySet
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
