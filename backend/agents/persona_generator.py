# agents/persona_generator.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — PERSONA GENERATOR
# ============================================================================
# Purpose: Detect persona queries and generate PersonaCard payloads
#
# ARCHITECTURE:
# - Detects buyer persona questions via regex patterns
# - Returns pre-built personas based on context
# - Generates PersonaCard for frontend rendering
# ============================================================================

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from schemas.event_definitions import (
    PersonaCard,
    PainPoint,
)

logger = logging.getLogger("BarriosA2I.PersonaGenerator")


# ============================================================================
# SECTION 1: PATTERN DETECTION
# ============================================================================

PERSONA_PATTERNS = [
    r"(?:who|what).*(?:ideal|target).*(?:customer|buyer|client)",
    r"customer\s*(?:profile|persona|avatar)",
    r"who\s+should\s+we\s+target",
    r"(?:buyer|customer)\s*persona",
    r"ideal\s*(?:customer|client|buyer)",
    r"target\s*(?:audience|market|customer)",
    r"who\s+(?:buys|uses|needs)\s+(?:this|your)",
    r"(?:describe|show|tell).*(?:customer|buyer|persona)",
]

PERSONA_TRIGGERS = [
    "ideal customer", "target customer", "buyer persona", "customer profile",
    "who buys", "who should we target", "target audience", "customer avatar",
    "ideal client", "who uses", "target market", "customer segment"
]


def is_persona_query(message: str) -> bool:
    """Check if message is asking about buyer personas."""
    msg_lower = message.lower()

    # Check triggers first
    if any(trigger in msg_lower for trigger in PERSONA_TRIGGERS):
        return True

    # Check patterns
    for pattern in PERSONA_PATTERNS:
        if re.search(pattern, msg_lower, re.IGNORECASE):
            return True

    return False


def extract_persona_context(message: str) -> Dict[str, Any]:
    """Extract context from message to select appropriate persona."""
    msg_lower = message.lower()

    context = {
        "industry": None,
        "company_size": None,
        "role": None,
    }

    # Detect industry hints
    if any(word in msg_lower for word in ["agency", "agencies", "creative"]):
        context["industry"] = "agency"
    elif any(word in msg_lower for word in ["ecommerce", "e-commerce", "retail", "dtc"]):
        context["industry"] = "ecommerce"
    elif any(word in msg_lower for word in ["saas", "software", "tech", "b2b"]):
        context["industry"] = "b2b_saas"

    # Detect company size hints
    if any(word in msg_lower for word in ["enterprise", "large", "fortune"]):
        context["company_size"] = "enterprise"
    elif any(word in msg_lower for word in ["startup", "small", "smb"]):
        context["company_size"] = "small"
    else:
        context["company_size"] = "mid_market"

    return context


# ============================================================================
# SECTION 2: PRE-BUILT PERSONAS
# ============================================================================

PERSONAS = {
    "marketing_director": PersonaCard(
        persona_name="Marketing Director Marcus",
        title="Director of Marketing",
        company_type="Mid-Market B2B SaaS",
        avatar_url=None,
        age_range="35-45",
        income_range="$120K - $180K",
        income_percentile=0.82,
        pain_points=[
            PainPoint(
                title="Video Production Bottleneck",
                severity="critical",
                description="Current video production takes 2-3 weeks per asset, can't keep up with demand for social content."
            ),
            PainPoint(
                title="Budget Constraints",
                severity="high",
                description="Video agency costs $5K-$15K per commercial. Limited to 2-3 videos per quarter."
            ),
            PainPoint(
                title="Creative Consistency",
                severity="medium",
                description="Different vendors produce inconsistent brand messaging and visual styles."
            ),
        ],
        goals=[
            "Produce 10x more video content without increasing headcount",
            "Reduce cost-per-video from $10K to under $500",
            "Maintain broadcast-quality output for brand standards",
            "Enable marketing team to iterate quickly on campaigns",
        ],
        objections=[
            "AI video quality won't match agency-produced content",
            "Integration with existing MarTech stack seems complex",
            "Concerned about brand voice consistency in AI-generated scripts",
        ],
        decision_drivers=[
            "Proven ROI with case studies",
            "Enterprise security compliance (SOC2)",
            "Ability to start small and scale",
        ],
        budget_authority="approve",
        buying_timeline="1-3 months",
        confidence_score=0.89,
        generated_at=datetime.utcnow()
    ),

    "agency_owner": PersonaCard(
        persona_name="Agency Owner Alex",
        title="Founder & CEO",
        company_type="Digital Marketing Agency",
        avatar_url=None,
        age_range="40-50",
        income_range="$200K - $500K",
        income_percentile=0.94,
        pain_points=[
            PainPoint(
                title="Talent Shortage",
                severity="critical",
                description="Can't hire enough video editors fast enough. Lost 3 retainer clients due to delivery delays."
            ),
            PainPoint(
                title="Margin Pressure",
                severity="high",
                description="Video production margins shrinking as clients demand more content for less."
            ),
            PainPoint(
                title="Scale Limitations",
                severity="high",
                description="Revenue capped by team size. Can't take on new clients without hiring."
            ),
        ],
        goals=[
            "White-label video production to offer clients at scale",
            "Increase agency margins from 25% to 60%+ on video services",
            "Reduce delivery timelines from weeks to days",
            "Differentiate from competitors with AI-powered speed",
        ],
        objections=[
            "Clients expect human creative directors on their projects",
            "What if AI generates something off-brand or inappropriate?",
            "How do we position this to clients who expect 'handcrafted' work?",
        ],
        decision_drivers=[
            "White-label capabilities with custom branding",
            "API access for integration with client dashboards",
            "Volume pricing for agency model",
        ],
        budget_authority="final_decision",
        buying_timeline="Immediate - 1 month",
        confidence_score=0.92,
        generated_at=datetime.utcnow()
    ),

    "ecommerce_manager": PersonaCard(
        persona_name="E-commerce Manager Emma",
        title="Head of E-commerce",
        company_type="D2C Consumer Brand",
        avatar_url=None,
        age_range="28-35",
        income_range="$90K - $130K",
        income_percentile=0.75,
        pain_points=[
            PainPoint(
                title="Ad Creative Fatigue",
                severity="critical",
                description="Performance drops 40% after 2 weeks. Need 50+ ad variants per month to maintain ROAS."
            ),
            PainPoint(
                title="A/B Testing Volume",
                severity="high",
                description="Can only test 5-10 creatives at a time. Competitors are testing 100+."
            ),
            PainPoint(
                title="UGC Production Costs",
                severity="medium",
                description="Paying $500-$2K per UGC video. Need 20+ per month for campaigns."
            ),
        ],
        goals=[
            "Generate 100+ ad variants per month for testing",
            "Reduce creative production costs by 80%",
            "Improve ROAS through faster creative iteration",
            "Launch product videos same-day as inventory arrives",
        ],
        objections=[
            "Will AI-generated content perform as well as UGC?",
            "Meta's algorithm might penalize non-human content",
            "Our brand voice is very specific - can AI capture it?",
        ],
        decision_drivers=[
            "Direct integration with Meta/TikTok ad platforms",
            "Performance data from similar D2C brands",
            "Self-serve platform (no sales calls needed)",
        ],
        budget_authority="influence",
        buying_timeline="1-2 months",
        confidence_score=0.85,
        generated_at=datetime.utcnow()
    ),
}


# ============================================================================
# SECTION 3: PERSONA SELECTION
# ============================================================================

def select_persona(context: Dict[str, Any]) -> PersonaCard:
    """Select the most appropriate persona based on context."""
    industry = context.get("industry")

    if industry == "agency":
        return PERSONAS["agency_owner"]
    elif industry == "ecommerce":
        return PERSONAS["ecommerce_manager"]
    else:
        # Default to marketing director for B2B/SaaS or general queries
        return PERSONAS["marketing_director"]


# ============================================================================
# SECTION 4: MAIN PROCESSING FUNCTION
# ============================================================================

async def process_persona_query(
    message: str,
    session_id: str,
    existing_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a persona query and return PersonaCard.

    Args:
        message: User's message
        session_id: Session identifier
        existing_context: Previous conversation context

    Returns:
        Dict with render_card, text_response, and success flag
    """
    # Extract context from message
    context = extract_persona_context(message)

    # If we have existing context (e.g., previous competitor query), use it
    if existing_context:
        if existing_context.get("competitor_context"):
            # Adjust persona based on competitor mentioned
            pass

    # Select appropriate persona
    persona = select_persona(context)

    # Generate conversational response
    text_response = f"""Meet **{persona.persona_name}**, our ideal customer profile.

{persona.persona_name} is a {persona.title} at a {persona.company_type} company. Their biggest pain point? **{persona.pain_points[0].title}** - {persona.pain_points[0].description.lower()}

They're looking to {persona.goals[0].lower()}, and they have **{persona.budget_authority.replace('_', ' ')}** authority over purchasing decisions with a timeline of {persona.buying_timeline}.

Here's the full profile card with their pain points, goals, and common objections we need to address:"""

    logger.info(f"Generated persona card: {persona.persona_name} for session {session_id}")

    return {
        "render_card": persona,
        "text_response": text_response,
        "success": True,
        "persona_name": persona.persona_name,
        "confidence": persona.confidence_score
    }


# ============================================================================
# SECTION 5: EXPORTS
# ============================================================================

__all__ = [
    "is_persona_query",
    "process_persona_query",
    "extract_persona_context",
    "select_persona",
    "PERSONAS",
]
