# agents/__init__.py
from agents.trinity_bridge import (
    TrinityBridge,
    TrinityConfig,
    get_trinity_bridge,
    analyze_competitor,
    is_competitive_query,
    extract_competitor,
)

from agents.persona_generator import (
    is_persona_query,
    process_persona_query,
    extract_persona_context,
    select_persona,
    PERSONAS,
)

from agents.script_generator import (
    is_script_query,
    process_script_query,
    extract_script_context,
    select_script,
    SCRIPTS,
)

from agents.roi_generator import (
    is_roi_query,
    process_roi_query,
    extract_roi_context,
    calculate_roi,
    generate_roi_card,
)

__all__ = [
    # Trinity Bridge (Competitor Analysis)
    "TrinityBridge",
    "TrinityConfig",
    "get_trinity_bridge",
    "analyze_competitor",
    "is_competitive_query",
    "extract_competitor",
    # Persona Generator
    "is_persona_query",
    "process_persona_query",
    "extract_persona_context",
    "select_persona",
    "PERSONAS",
    # Script Generator
    "is_script_query",
    "process_script_query",
    "extract_script_context",
    "select_script",
    "SCRIPTS",
    # ROI Generator
    "is_roi_query",
    "process_roi_query",
    "extract_roi_context",
    "calculate_roi",
    "generate_roi_card",
]
