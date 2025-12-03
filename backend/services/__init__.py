# services/__init__.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — SERVICES MODULE
# ============================================================================
# Extended storage services, hooks, and context providers
# ============================================================================

from services.drive_service import (
    get_drive_storage,
    store_conversation,
    store_card,
    log_analytics,
)

from services.data_hooks import (
    on_conversation_complete,
    on_card_interaction,
    on_lead_captured,
)

from services.context_providers import (
    get_context_for_competitor_query,
    get_context_for_persona_query,
    get_context_for_script_query,
    get_context_for_roi_query,
)

__all__ = [
    # Drive service
    "get_drive_storage",
    "store_conversation",
    "store_card",
    "log_analytics",
    # Data hooks
    "on_conversation_complete",
    "on_card_interaction",
    "on_lead_captured",
    # Context providers
    "get_context_for_competitor_query",
    "get_context_for_persona_query",
    "get_context_for_script_query",
    "get_context_for_roi_query",
]
