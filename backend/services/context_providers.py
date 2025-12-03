# services/context_providers.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — CONTEXT PROVIDERS
# ============================================================================
# Functions to retrieve historical context for smarter responses
# ============================================================================

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from storage import get_storage, DataType

logger = logging.getLogger("BarriosA2I.ContextProviders")


async def get_context_for_competitor_query(
    query: str,
    session_id: str
) -> Dict[str, Any]:
    """
    Get historical context for a competitor analysis query.

    Returns:
        - Recent intel for the same competitor (cache hit potential)
        - Previous competitor queries in session
        - Common objections raised
    """
    storage = await get_storage()
    context = {
        "recent_intel": [],
        "session_history": [],
        "common_objections": [],
    }

    try:
        # Get recent competitive intel (last 24 hours)
        recent = await storage.query_recent(DataType.COMPETITIVE_INTEL, hours=24)
        context["recent_intel"] = recent[:5]

        # Get session history
        session_docs = await storage.query_recent(
            DataType.CONVERSATIONS,
            hours=168,  # Last week
            session_id=session_id
        )
        context["session_history"] = session_docs[:10]

        # Extract competitor from query for matching
        query_lower = query.lower()
        for doc in recent:
            if doc.get("competitor_name", "").lower() in query_lower:
                # Found matching competitor - prioritize this
                context["matching_intel"] = doc
                break

        logger.debug(f"Competitor context: {len(context['recent_intel'])} recent, "
                    f"{len(context['session_history'])} session")

    except Exception as e:
        logger.warning(f"Failed to get competitor context: {e}")

    return context


async def get_context_for_persona_query(
    query: str,
    session_id: str
) -> Dict[str, Any]:
    """
    Get historical context for a persona query.

    Returns:
        - Previously generated personas
        - Industry hints from conversation
        - Pain points mentioned
    """
    storage = await get_storage()
    context = {
        "recent_personas": [],
        "session_history": [],
        "industry_hints": [],
    }

    try:
        # Get recent personas
        recent = await storage.query_recent(DataType.PERSONAS, hours=168)
        context["recent_personas"] = recent[:10]

        # Get session history
        session_docs = await storage.query_recent(
            DataType.CONVERSATIONS,
            hours=168,
            session_id=session_id
        )
        context["session_history"] = session_docs[:10]

        # Extract industry hints from conversation
        for doc in session_docs:
            msg = doc.get("user_message", "").lower()
            if "agency" in msg or "creative" in msg:
                context["industry_hints"].append("agency")
            if "ecommerce" in msg or "d2c" in msg or "retail" in msg:
                context["industry_hints"].append("ecommerce")
            if "saas" in msg or "b2b" in msg or "software" in msg:
                context["industry_hints"].append("b2b_saas")

        logger.debug(f"Persona context: {len(context['recent_personas'])} recent, "
                    f"hints: {context['industry_hints']}")

    except Exception as e:
        logger.warning(f"Failed to get persona context: {e}")

    return context


async def get_context_for_script_query(
    query: str,
    session_id: str
) -> Dict[str, Any]:
    """
    Get historical context for a script generation query.

    Returns:
        - Approved scripts as templates
        - Previous script iterations
        - Persona context if available
    """
    storage = await get_storage()
    context = {
        "approved_scripts": [],
        "recent_drafts": [],
        "session_persona": None,
    }

    try:
        # Get approved scripts (use as templates)
        all_scripts = await storage.retrieve(DataType.SCRIPTS, limit=50)
        context["approved_scripts"] = [
            s for s in all_scripts
            if s.get("status") == "approved"
        ][:5]

        # Get recent drafts
        recent = await storage.query_recent(DataType.SCRIPTS, hours=48)
        context["recent_drafts"] = recent[:5]

        # Check for persona in session
        session_docs = await storage.query_recent(
            DataType.PERSONAS,
            hours=24,
            session_id=session_id
        )
        if session_docs:
            context["session_persona"] = session_docs[0].get("persona_name")

        logger.debug(f"Script context: {len(context['approved_scripts'])} approved, "
                    f"persona: {context['session_persona']}")

    except Exception as e:
        logger.warning(f"Failed to get script context: {e}")

    return context


async def get_context_for_roi_query(
    query: str,
    session_id: str
) -> Dict[str, Any]:
    """
    Get historical context for an ROI calculation query.

    Returns:
        - Average ROI metrics from past calculations
        - User's previous ROI inputs
        - Industry benchmarks
    """
    storage = await get_storage()
    context = {
        "average_savings": None,
        "previous_calculations": [],
        "industry_benchmarks": {},
    }

    try:
        # Get recent ROI calculations
        recent = await storage.query_recent(DataType.ROI_CALCULATIONS, hours=720)  # 30 days
        context["previous_calculations"] = recent[:10]

        # Calculate average savings
        if recent:
            savings = [
                r.get("total_savings", 0)
                for r in recent
                if r.get("total_savings")
            ]
            if savings:
                context["average_savings"] = sum(savings) / len(savings)

        # Get session-specific calculations
        session_docs = await storage.query_recent(
            DataType.ROI_CALCULATIONS,
            hours=168,
            session_id=session_id
        )
        if session_docs:
            context["user_previous_inputs"] = session_docs[0].get("card_data", {})

        # Industry benchmarks (static for now, could be dynamic)
        context["industry_benchmarks"] = {
            "avg_video_cost": 5000,
            "avg_production_days": 14,
            "avg_videos_per_month": 10,
        }

        logger.debug(f"ROI context: {len(context['previous_calculations'])} calculations, "
                    f"avg savings: {context['average_savings']}")

    except Exception as e:
        logger.warning(f"Failed to get ROI context: {e}")

    return context
