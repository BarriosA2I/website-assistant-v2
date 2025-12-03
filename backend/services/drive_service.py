# services/drive_service.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — DRIVE SERVICE
# ============================================================================
# High-level storage service for conversations, cards, and analytics
# ============================================================================

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from storage import get_storage, DataType

logger = logging.getLogger("BarriosA2I.DriveService")


async def get_drive_storage():
    """Get initialized Google Drive storage instance."""
    return await get_storage()


async def store_conversation(
    session_id: str,
    user_message: str,
    assistant_response: str,
    card_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Store a conversation turn to Google Drive.

    Args:
        session_id: Session identifier
        user_message: User's message
        assistant_response: Assistant's response
        card_type: Type of card shown (if any)
        metadata: Additional metadata

    Returns:
        File ID of stored document
    """
    storage = await get_storage()

    data = {
        "session_id": session_id,
        "user_message": user_message,
        "assistant_response": assistant_response,
        "card_type": card_type,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": metadata or {}
    }

    try:
        file_id = await storage.store(DataType.CONVERSATIONS, data)
        logger.debug(f"Stored conversation for session {session_id[:8]}...")
        return file_id
    except Exception as e:
        logger.error(f"Failed to store conversation: {e}")
        raise


async def store_card(
    card_type: str,
    card_data: Dict[str, Any],
    session_id: str
) -> str:
    """
    Store a generated card to the appropriate folder.

    Args:
        card_type: Type of card (competitor, persona, script, roi)
        card_data: Card data dictionary
        session_id: Session identifier

    Returns:
        File ID of stored document
    """
    storage = await get_storage()

    # Map card type to data type
    type_mapping = {
        "competitor": DataType.COMPETITIVE_INTEL,
        "competitor_analysis": DataType.COMPETITIVE_INTEL,
        "persona": DataType.PERSONAS,
        "script": DataType.SCRIPTS,
        "script_preview": DataType.SCRIPTS,
        "roi": DataType.ROI_CALCULATIONS,
        "roi_calculator": DataType.ROI_CALCULATIONS,
    }

    data_type = type_mapping.get(card_type.lower())
    if not data_type:
        logger.warning(f"Unknown card type: {card_type}, using ANALYTICS")
        data_type = DataType.ANALYTICS

    # Prepare document
    data = {
        "session_id": session_id,
        "card_type": card_type,
        "card_data": card_data,
        "created_at": datetime.utcnow().isoformat(),
    }

    # Extract key fields based on card type
    if card_type in ["competitor", "competitor_analysis"]:
        data["competitor_name"] = card_data.get("competitor_name")
        data["confidence"] = card_data.get("confidence_score")
    elif card_type == "persona":
        data["persona_name"] = card_data.get("persona_name")
        data["company_type"] = card_data.get("company_type")
    elif card_type in ["script", "script_preview"]:
        data["script_title"] = card_data.get("title")
        data["format"] = card_data.get("format")
        data["status"] = card_data.get("status", "draft")
    elif card_type in ["roi", "roi_calculator"]:
        data["total_savings"] = card_data.get("total_savings")
        data["payback_months"] = card_data.get("payback_period_months")

    try:
        file_id = await storage.store(data_type, data)
        logger.info(f"Stored {card_type} card for session {session_id[:8]}...")
        return file_id
    except Exception as e:
        logger.error(f"Failed to store card: {e}")
        raise


async def log_analytics(
    event_type: str,
    event_data: Dict[str, Any],
    session_id: str
) -> str:
    """
    Log an analytics event to Google Drive.

    Args:
        event_type: Type of event (card_generated, lead_captured, etc.)
        event_data: Event data dictionary
        session_id: Session identifier

    Returns:
        File ID of stored document
    """
    storage = await get_storage()

    data = {
        "session_id": session_id,
        "event_type": event_type,
        "event_data": event_data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        file_id = await storage.store(DataType.ANALYTICS, data)
        logger.debug(f"Logged analytics event: {event_type}")
        return file_id
    except Exception as e:
        logger.error(f"Failed to log analytics: {e}")
        raise
