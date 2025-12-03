# agents/script_generator.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — SCRIPT GENERATOR
# ============================================================================
# Purpose: Detect script/commercial queries and generate ScriptPreviewCard
#
# ARCHITECTURE:
# - Detects script writing requests via regex patterns
# - Generates video commercial scripts with proper structure
# - Returns ScriptPreviewCard for frontend rendering
# ============================================================================

import logging
import re
import uuid
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime

from schemas.event_definitions import (
    ScriptPreviewCard,
    ScriptSection,
)

logger = logging.getLogger("BarriosA2I.ScriptGenerator")


# ============================================================================
# SECTION 1: PATTERN DETECTION
# ============================================================================

SCRIPT_PATTERNS = [
    r"(?:write|create|generate|draft|make).*(?:script|commercial|ad|advertisement|video)",
    r"(?:script|commercial|ad).*(?:for|about)",
    r"(?:30|15|60|90)\s*(?:second|sec|s)\s*(?:script|commercial|ad|video)",
    r"(?:video|commercial|ad)\s*(?:script|copy|content)",
    r"(?:sales|marketing|promo|promotional)\s*(?:video|commercial|script)",
    r"(?:product|brand|company)\s*(?:video|commercial|promo)",
    r"(?:write|create|draft).*(?:copy|content).*(?:video|commercial)",
    r"(?:hook|cta|call.to.action).*(?:video|script)",
]

SCRIPT_TRIGGERS = [
    "write a script", "create a commercial", "generate a video",
    "30 second commercial", "15 second ad", "60 second video",
    "script for", "commercial for", "video ad", "promo video",
    "sales video", "marketing video", "product video",
    "write me a", "create me a", "draft a script"
]


def is_script_query(message: str) -> bool:
    """Check if message is requesting a script/commercial."""
    msg_lower = message.lower()

    # Check triggers first
    if any(trigger in msg_lower for trigger in SCRIPT_TRIGGERS):
        return True

    # Check patterns
    for pattern in SCRIPT_PATTERNS:
        if re.search(pattern, msg_lower, re.IGNORECASE):
            return True

    return False


def extract_script_context(message: str) -> Dict[str, Any]:
    """Extract script parameters from message."""
    msg_lower = message.lower()

    context = {
        "format": "30s",  # Default
        "tone": "professional",
        "platform": "youtube",
        "topic": None,
    }

    # Detect duration
    if "15" in msg_lower or "fifteen" in msg_lower:
        context["format"] = "15s"
    elif "60" in msg_lower or "sixty" in msg_lower or "1 minute" in msg_lower:
        context["format"] = "60s"
    elif "90" in msg_lower or "ninety" in msg_lower:
        context["format"] = "90s"

    # Detect tone
    if any(word in msg_lower for word in ["casual", "fun", "friendly", "playful"]):
        context["tone"] = "casual"
    elif any(word in msg_lower for word in ["urgent", "now", "limited", "hurry"]):
        context["tone"] = "urgent"
    elif any(word in msg_lower for word in ["inspiring", "inspirational", "emotional", "powerful"]):
        context["tone"] = "inspirational"

    # Detect platform
    if "tiktok" in msg_lower or "tik tok" in msg_lower:
        context["platform"] = "tiktok"
    elif "instagram" in msg_lower or "ig" in msg_lower or "reels" in msg_lower:
        context["platform"] = "instagram"
    elif "linkedin" in msg_lower:
        context["platform"] = "linkedin"
    elif "tv" in msg_lower or "television" in msg_lower or "broadcast" in msg_lower:
        context["platform"] = "tv"

    return context


# ============================================================================
# SECTION 2: PRE-BUILT SCRIPTS
# ============================================================================

SCRIPTS = {
    "video_generation_30s": ScriptPreviewCard(
        title="AI Video Generation - The Future is Now",
        format="30s",
        tone="professional",
        target_platform="youtube",
        sections=[
            ScriptSection(
                section_type="hook",
                content="What if you could create a broadcast-quality commercial in under 4 minutes?",
                duration_seconds=5,
                notes="Open with bold question, show timer counting"
            ),
            ScriptSection(
                section_type="problem",
                content="Traditional video production takes weeks and costs thousands. You're stuck waiting, while your competitors move faster.",
                duration_seconds=7,
                notes="Show frustrated marketer, slow calendar flipping"
            ),
            ScriptSection(
                section_type="solution",
                content="RAGNAROK changes everything. Our 9-agent AI system generates professional commercials in 243 seconds flat. For just $2.60.",
                duration_seconds=10,
                notes="Show RAGNAROK interface, agents working in parallel"
            ),
            ScriptSection(
                section_type="proof",
                content="230,000 videos generated. 97.5% success rate. Enterprise clients trust us.",
                duration_seconds=5,
                notes="Show stats with glowing numbers, client logos"
            ),
            ScriptSection(
                section_type="cta",
                content="Start creating today. Your first video is free.",
                duration_seconds=3,
                notes="End with URL and QR code"
            ),
        ],
        full_script="""What if you could create a broadcast-quality commercial in under 4 minutes?

Traditional video production takes weeks and costs thousands. You're stuck waiting, while your competitors move faster.

RAGNAROK changes everything. Our 9-agent AI system generates professional commercials in 243 seconds flat. For just $2.60.

230,000 videos generated. 97.5% success rate. Enterprise clients trust us.

Start creating today. Your first video is free.""",
        word_count=72,
        estimated_duration_seconds=30,
        status="draft",
        revision_number=1,
    ),

    "video_generation_15s": ScriptPreviewCard(
        title="RAGNAROK - Speed Sells",
        format="15s",
        tone="urgent",
        target_platform="tiktok",
        sections=[
            ScriptSection(
                section_type="hook",
                content="243 seconds. That's all it takes.",
                duration_seconds=3,
                notes="Fast cut, timer visual"
            ),
            ScriptSection(
                section_type="solution",
                content="RAGNAROK: 9 AI agents. One broadcast-quality commercial. $2.60.",
                duration_seconds=7,
                notes="Show agents working, video rendering"
            ),
            ScriptSection(
                section_type="cta",
                content="Create yours now. Link in bio.",
                duration_seconds=5,
                notes="End card with urgency"
            ),
        ],
        full_script="""243 seconds. That's all it takes.

RAGNAROK: 9 AI agents. One broadcast-quality commercial. $2.60.

Create yours now. Link in bio.""",
        word_count=26,
        estimated_duration_seconds=15,
        status="draft",
        revision_number=1,
    ),

    "video_generation_60s": ScriptPreviewCard(
        title="The RAGNAROK Story - Transform Your Marketing",
        format="60s",
        tone="inspirational",
        target_platform="linkedin",
        sections=[
            ScriptSection(
                section_type="hook",
                content="Every great brand has a story. But telling that story used to cost a fortune.",
                duration_seconds=8,
                notes="Cinematic opening, emotional music"
            ),
            ScriptSection(
                section_type="problem",
                content="$15,000 for a single commercial. 3 weeks of waiting. Revisions that cost extra. Most businesses simply can't compete at that level.",
                duration_seconds=12,
                notes="Show traditional production chaos"
            ),
            ScriptSection(
                section_type="solution",
                content="We built RAGNAROK to change that. Nine specialized AI agents working in perfect harmony. A Scriptwriter. A Director. A Voice Artist. A Music Composer. All collaborating to create your commercial in under 4 minutes.",
                duration_seconds=18,
                notes="Show each agent with visual representation"
            ),
            ScriptSection(
                section_type="proof",
                content="Over 230,000 videos created. A 97.5% success rate. Enterprise companies trust RAGNAROK for their most important campaigns.",
                duration_seconds=10,
                notes="Testimonials, client logos, success metrics"
            ),
            ScriptSection(
                section_type="cta",
                content="Your story deserves to be told. Tell it for $2.60. Try RAGNAROK free today.",
                duration_seconds=12,
                notes="Emotional close, clear CTA, website"
            ),
        ],
        full_script="""Every great brand has a story. But telling that story used to cost a fortune.

$15,000 for a single commercial. 3 weeks of waiting. Revisions that cost extra. Most businesses simply can't compete at that level.

We built RAGNAROK to change that. Nine specialized AI agents working in perfect harmony. A Scriptwriter. A Director. A Voice Artist. A Music Composer. All collaborating to create your commercial in under 4 minutes.

Over 230,000 videos created. A 97.5% success rate. Enterprise companies trust RAGNAROK for their most important campaigns.

Your story deserves to be told. Tell it for $2.60. Try RAGNAROK free today.""",
        word_count=118,
        estimated_duration_seconds=60,
        status="draft",
        revision_number=1,
    ),
}


# ============================================================================
# SECTION 3: SCRIPT SELECTION
# ============================================================================

def select_script(context: Dict[str, Any]) -> ScriptPreviewCard:
    """Select the most appropriate script based on context."""
    format_type = context.get("format", "30s")

    if format_type == "15s":
        return SCRIPTS["video_generation_15s"]
    elif format_type == "60s":
        return SCRIPTS["video_generation_60s"]
    else:
        return SCRIPTS["video_generation_30s"]


# ============================================================================
# SECTION 4: MAIN PROCESSING FUNCTION
# ============================================================================

async def process_script_query(
    message: str,
    session_id: str,
    existing_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a script query and return ScriptPreviewCard.

    Args:
        message: User's message
        session_id: Session identifier
        existing_context: Previous conversation context

    Returns:
        Dict with render_card, text_response, and success flag
    """
    # Extract context from message
    context = extract_script_context(message)

    # Select appropriate script
    script = select_script(context)

    # Update script with new ID and timestamp
    script.script_id = uuid.uuid4().hex[:12]
    script.generated_at = datetime.utcnow()

    # Apply context customizations
    if context.get("platform"):
        script.target_platform = context["platform"]
    if context.get("tone"):
        script.tone = context["tone"]

    # Generate conversational response
    text_response = f"""Here's your **{script.format}** commercial script!

**Title:** {script.title}
**Tone:** {script.tone.title()}
**Platform:** {script.target_platform.title()}
**Duration:** ~{script.estimated_duration_seconds} seconds ({script.word_count} words)

The script follows the proven **Hook → Problem → Solution → Proof → CTA** structure for maximum conversion.

You can:
- **Regenerate** for a different approach
- **Edit** any section directly
- **Approve** to send to video generation

Here's your editable script card:"""

    logger.info(f"Generated script: {script.title} ({script.format}) for session {session_id}")

    return {
        "render_card": script,
        "text_response": text_response,
        "success": True,
        "script_title": script.title,
        "format": script.format,
        "confidence": 0.88
    }


# ============================================================================
# SECTION 5: EXPORTS
# ============================================================================

__all__ = [
    "is_script_query",
    "process_script_query",
    "extract_script_context",
    "select_script",
    "SCRIPTS",
]
