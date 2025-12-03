# services/data_hooks.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — DATA HOOKS
# ============================================================================
# Event hooks for conversation completion, card interactions, and leads
# ============================================================================

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from storage import get_storage, DataType
from services.drive_service import log_analytics

logger = logging.getLogger("BarriosA2I.DataHooks")


async def on_conversation_complete(
    session_id: str,
    messages: List[Dict[str, str]],
    card_shown: Optional[Dict[str, Any]] = None
) -> str:
    """
    Hook called when a conversation turn completes.

    Args:
        session_id: Session identifier
        messages: List of message dicts with role and content
        card_shown: Card data if one was rendered

    Returns:
        Session document ID
    """
    storage = await get_storage()

    # Build session summary
    session_data = {
        "session_id": session_id,
        "message_count": len(messages),
        "messages": messages,
        "card_shown": card_shown is not None,
        "card_type": card_shown.get("type") if card_shown else None,
        "updated_at": datetime.utcnow().isoformat(),
    }

    try:
        file_id = await storage.store(DataType.SESSIONS, session_data)
        logger.info(f"Session updated: {session_id[:8]}... ({len(messages)} messages)")

        # Log analytics
        await log_analytics(
            event_type="conversation_complete",
            event_data={
                "message_count": len(messages),
                "card_shown": card_shown is not None,
                "card_type": card_shown.get("type") if card_shown else None,
            },
            session_id=session_id
        )

        return file_id
    except Exception as e:
        logger.error(f"Failed to process conversation complete: {e}")
        raise


async def on_card_interaction(
    session_id: str,
    card_type: str,
    action: str,
    action_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Hook called when user interacts with a card.

    Args:
        session_id: Session identifier
        card_type: Type of card (competitor, persona, script, roi)
        action: Action taken (regenerate, edit, approve, etc.)
        action_data: Additional action data

    Returns:
        Analytics event ID
    """
    try:
        file_id = await log_analytics(
            event_type="card_interaction",
            event_data={
                "card_type": card_type,
                "action": action,
                "action_data": action_data or {},
            },
            session_id=session_id
        )
        logger.info(f"Card interaction: {action} on {card_type}")
        return file_id
    except Exception as e:
        logger.error(f"Failed to log card interaction: {e}")
        raise


async def on_lead_captured(
    session_id: str,
    email: str,
    name: Optional[str] = None,
    company: Optional[str] = None,
    source: str = "website_assistant",
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Hook called when a lead is captured.

    Args:
        session_id: Session identifier
        email: Lead's email address
        name: Lead's name
        company: Lead's company
        source: Lead source
        metadata: Additional metadata

    Returns:
        Lead document ID
    """
    storage = await get_storage()

    lead_id = str(uuid.uuid4())

    lead_data = {
        "lead_id": lead_id,
        "session_id": session_id,
        "email": email,
        "name": name,
        "company": company,
        "source": source,
        "captured_at": datetime.utcnow().isoformat(),
        "metadata": metadata or {},
        "status": "new",
    }

    try:
        file_id = await storage.store(DataType.LEADS, lead_data)
        logger.info(f"Lead captured: {email} (session {session_id[:8]}...)")

        # Log analytics
        await log_analytics(
            event_type="lead_captured",
            event_data={
                "lead_id": lead_id,
                "source": source,
                "has_name": name is not None,
                "has_company": company is not None,
            },
            session_id=session_id
        )

        return lead_id
    except Exception as e:
        logger.error(f"Failed to capture lead: {e}")
        raise
