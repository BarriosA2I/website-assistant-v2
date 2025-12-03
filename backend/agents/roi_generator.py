# agents/roi_generator.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — ROI GENERATOR
# ============================================================================
# Purpose: Detect ROI/pricing queries and generate ROICalculatorCard
#
# ARCHITECTURE:
# - Detects ROI and value calculation requests via regex patterns
# - Generates interactive ROI calculator with sliders and projections
# - Returns ROICalculatorCard for frontend rendering
# ============================================================================

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from schemas.event_definitions import (
    ROICalculatorCard,
    ROISlider,
    ROIProjection,
)

logger = logging.getLogger("BarriosA2I.ROIGenerator")


# ============================================================================
# SECTION 1: PATTERN DETECTION
# ============================================================================

ROI_PATTERNS = [
    r"(?:roi|return\s*on\s*investment)",
    r"(?:how\s+much|what).*(?:save|cost|spend|pay)",
    r"(?:calculate|show|estimate).*(?:savings|value|roi|cost)",
    r"(?:pricing|cost)\s*(?:calculator|comparison|breakdown)",
    r"(?:worth|value)\s*(?:it|the\s*investment)",
    r"(?:payback|break.?even)\s*(?:period|time)",
    r"(?:total\s*)?(?:cost\s*of\s*ownership|tco)",
    r"(?:budget|spend).*(?:video|commercial|content)",
]

ROI_TRIGGERS = [
    "roi", "return on investment", "how much can i save",
    "cost savings", "calculate savings", "pricing calculator",
    "worth it", "value proposition", "payback period",
    "break even", "cost comparison", "budget", "spending",
    "how much does", "what does it cost", "save money"
]


def is_roi_query(message: str) -> bool:
    """Check if message is asking about ROI/savings."""
    msg_lower = message.lower()

    # Check triggers first
    if any(trigger in msg_lower for trigger in ROI_TRIGGERS):
        return True

    # Check patterns
    for pattern in ROI_PATTERNS:
        if re.search(pattern, msg_lower, re.IGNORECASE):
            return True

    return False


def extract_roi_context(message: str) -> Dict[str, Any]:
    """Extract ROI calculation parameters from message."""
    msg_lower = message.lower()

    context = {
        "videos_per_month": 10,  # Default
        "current_cost_per_video": 5000,  # Default
        "focus": "general",
    }

    # Try to extract video volume
    volume_match = re.search(r"(\d+)\s*(?:videos?|commercials?|ads?)", msg_lower)
    if volume_match:
        context["videos_per_month"] = int(volume_match.group(1))

    # Try to extract current cost
    cost_match = re.search(r"\$\s*(\d+[,\d]*)", msg_lower)
    if cost_match:
        cost_str = cost_match.group(1).replace(",", "")
        context["current_cost_per_video"] = int(cost_str)

    # Detect focus area
    if any(word in msg_lower for word in ["time", "speed", "fast", "quick"]):
        context["focus"] = "time"
    elif any(word in msg_lower for word in ["cost", "money", "budget", "save"]):
        context["focus"] = "cost"
    elif any(word in msg_lower for word in ["scale", "volume", "grow", "more"]):
        context["focus"] = "scale"

    return context


# ============================================================================
# SECTION 2: ROI CALCULATION
# ============================================================================

def calculate_roi(
    videos_per_month: int = 10,
    current_cost_per_video: float = 5000,
    current_time_per_video_days: float = 14,
) -> Dict[str, Any]:
    """Calculate ROI based on inputs."""

    # RAGNAROK constants
    ragnarok_cost_per_video = 2.60
    ragnarok_time_per_video_minutes = 4

    # Monthly calculations
    current_monthly_cost = videos_per_month * current_cost_per_video
    ragnarok_monthly_cost = videos_per_month * ragnarok_cost_per_video

    monthly_savings = current_monthly_cost - ragnarok_monthly_cost
    annual_savings = monthly_savings * 12

    # Time savings (in hours)
    current_time_hours = videos_per_month * current_time_per_video_days * 8  # 8 hour days
    ragnarok_time_hours = videos_per_month * (ragnarok_time_per_video_minutes / 60)
    time_saved_hours = current_time_hours - ragnarok_time_hours

    # Cost reduction percentage
    cost_reduction_percent = ((current_monthly_cost - ragnarok_monthly_cost) / current_monthly_cost) * 100 if current_monthly_cost > 0 else 0

    # Speed improvement factor
    speed_improvement = (current_time_per_video_days * 24 * 60) / ragnarok_time_per_video_minutes if ragnarok_time_per_video_minutes > 0 else 0

    return {
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
        "cost_reduction_percent": cost_reduction_percent,
        "time_saved_hours": time_saved_hours,
        "speed_improvement": speed_improvement,
        "videos_per_month": videos_per_month,
        "ragnarok_monthly_cost": ragnarok_monthly_cost,
    }


# ============================================================================
# SECTION 3: CARD GENERATION
# ============================================================================

def generate_roi_card(context: Dict[str, Any]) -> ROICalculatorCard:
    """Generate an ROICalculatorCard based on context."""

    videos = context.get("videos_per_month", 10)
    current_cost = context.get("current_cost_per_video", 5000)

    # Calculate ROI
    roi = calculate_roi(
        videos_per_month=videos,
        current_cost_per_video=current_cost,
    )

    return ROICalculatorCard(
        title="ROI Calculator",
        subtitle="See how much RAGNAROK can save your business",

        sliders=[
            ROISlider(
                id="videos_per_month",
                label="Videos Per Month",
                min_value=1,
                max_value=100,
                default_value=float(videos),
                step=1,
                unit="videos",
                tooltip="How many video commercials do you need monthly?"
            ),
            ROISlider(
                id="current_cost",
                label="Current Cost Per Video",
                min_value=500,
                max_value=25000,
                default_value=float(current_cost),
                step=500,
                unit="$",
                tooltip="What do you currently pay per video (agency, freelancer, in-house)?"
            ),
            ROISlider(
                id="production_days",
                label="Current Production Time",
                min_value=1,
                max_value=30,
                default_value=14.0,
                step=1,
                unit="days",
                tooltip="How long does video production currently take?"
            ),
        ],

        projections=[
            ROIProjection(
                metric_name="Monthly Cost",
                current_value=float(videos * current_cost),
                projected_value=float(roi["ragnarok_monthly_cost"]),
                improvement_percent=roi["cost_reduction_percent"],
                timeframe="per month"
            ),
            ROIProjection(
                metric_name="Annual Savings",
                current_value=0.0,
                projected_value=float(roi["annual_savings"]),
                improvement_percent=0.0,
                timeframe="per year"
            ),
            ROIProjection(
                metric_name="Time Saved",
                current_value=float(videos * 14 * 8),  # hours
                projected_value=float(roi["time_saved_hours"]),
                improvement_percent=99.0,  # ~99% time reduction
                timeframe="hours/month"
            ),
            ROIProjection(
                metric_name="Speed Improvement",
                current_value=1.0,
                projected_value=float(roi["speed_improvement"]),
                improvement_percent=(roi["speed_improvement"] - 1) * 100,
                timeframe="times faster"
            ),
        ],

        total_savings=float(roi["annual_savings"]),
        savings_currency="USD",
        payback_period_months=0.1,  # Instant - first video pays for itself

        formula_description=f"Based on {videos} videos/month at ${current_cost:,.0f} each vs RAGNAROK at $2.60/video",

        cta_text="Start Saving Now",
        cta_action="start_trial",

        generated_at=datetime.utcnow()
    )


# ============================================================================
# SECTION 4: MAIN PROCESSING FUNCTION
# ============================================================================

async def process_roi_query(
    message: str,
    session_id: str,
    existing_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process an ROI query and return ROICalculatorCard.

    Args:
        message: User's message
        session_id: Session identifier
        existing_context: Previous conversation context

    Returns:
        Dict with render_card, text_response, and success flag
    """
    # Extract context from message
    context = extract_roi_context(message)

    # Generate ROI card
    card = generate_roi_card(context)

    # Calculate summary for text response
    roi = calculate_roi(
        videos_per_month=context["videos_per_month"],
        current_cost_per_video=context["current_cost_per_video"],
    )

    # Generate conversational response
    text_response = f"""Here's your personalized ROI analysis!

**Based on your current video production:**
- **{context['videos_per_month']} videos/month** at **${context['current_cost_per_video']:,}/video**
- Current monthly spend: **${context['videos_per_month'] * context['current_cost_per_video']:,}**

**With RAGNAROK ($2.60/video):**
- Monthly spend: **${roi['ragnarok_monthly_cost']:,.2f}**
- **Monthly savings: ${roi['monthly_savings']:,.0f}**
- **Annual savings: ${roi['annual_savings']:,.0f}**

That's a **{roi['cost_reduction_percent']:.0f}% cost reduction** with videos delivered **{roi['speed_improvement']:.0f}x faster**!

Use the interactive calculator below to adjust the numbers and see your custom projections:"""

    logger.info(f"Generated ROI card: ${roi['annual_savings']:,.0f} annual savings for session {session_id}")

    return {
        "render_card": card,
        "text_response": text_response,
        "success": True,
        "annual_savings": roi["annual_savings"],
        "cost_reduction_percent": roi["cost_reduction_percent"],
        "confidence": 0.92
    }


# ============================================================================
# SECTION 5: EXPORTS
# ============================================================================

__all__ = [
    "is_roi_query",
    "process_roi_query",
    "extract_roi_context",
    "calculate_roi",
    "generate_roi_card",
]
