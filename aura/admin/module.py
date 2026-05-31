from __future__ import annotations

from aura.admin.views import AdminController
from aura.modules.base import Module


@Module(controllers=[AdminController])
class AdminModule:
    """Aura Module wrapper for the administrative control panel."""
    pass
