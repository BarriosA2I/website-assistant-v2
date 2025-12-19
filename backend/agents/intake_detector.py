"""
Nexus Intake Detector
=====================
Detects commercial/video interest and manages the intake conversation flow.
Integrates with Website Assistant v2.0 to guide prospects through
the 30-question intake process for RAGNAROK commercial generation.
"""

import json
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime
import re


# =========================================================================
# INTAKE TRIGGER DETECTION
# =========================================================================

INTAKE_TRIGGERS = [
    # Direct commercial requests
    "create a commercial",
    "make a video ad",
    "i need a commercial",
    "video production",
    "want to advertise",
    "need marketing videos",
    "commercial for my business",
    "how much for a video",
    "pricing for commercials",
    "video ad for my",
    "make me a commercial",
    "produce a video",
    "video marketing",
    "create video content",
    "need video ads",
    "want video ads",
    "looking for video",
    "interested in commercials",
    "get a commercial made",
    "video for my brand",
    "promotional video",
    "advertising video",
    "brand video",
    "marketing video",
]

# Keywords that strongly indicate commercial interest
COMMERCIAL_KEYWORDS = [
    "commercial", "video ad", "video ads", "advertisement",
    "promotional", "promo video", "brand video", "marketing video",
    "video production", "video content", "tv ad", "youtube ad",
    "linkedin ad", "social media video", "explainer video"
]


def is_intake_query(message: str) -> bool:
    """
    Check if message triggers intake mode.

    Returns True if the message contains phrases indicating
    interest in creating a commercial or video ad.
    """
    if not message:
        return False

    msg_lower = message.lower().strip()

    # Check exact phrase triggers
    for trigger in INTAKE_TRIGGERS:
        if trigger in msg_lower:
            return True

    # Check for keyword combinations
    has_video = any(kw in msg_lower for kw in ["video", "commercial", "ad", "advertisement"])
    has_action = any(kw in msg_lower for kw in ["create", "make", "need", "want", "get", "produce", "looking for"])
    has_business = any(kw in msg_lower for kw in ["business", "company", "brand", "my", "our"])

    if has_video and has_action:
        return True

    if has_video and has_business:
        return True

    return False


def get_intake_intent_confidence(message: str) -> float:
    """
    Calculate confidence score (0-1) for intake intent.
    Higher score = more likely they want a commercial.
    """
    if not message:
        return 0.0

    msg_lower = message.lower()
    score = 0.0

    # Strong signals (0.3 each, max 0.9)
    strong_signals = [
        "commercial", "video ad", "advertising video",
        "marketing video", "promo video", "brand video"
    ]
    for signal in strong_signals:
        if signal in msg_lower:
            score += 0.3
            if score >= 0.9:
                return min(1.0, score)

    # Medium signals (0.15 each)
    medium_signals = [
        "video", "advertisement", "promote", "marketing",
        "create", "make", "produce", "need"
    ]
    for signal in medium_signals:
        if signal in msg_lower:
            score += 0.15

    # Weak signals (0.05 each)
    weak_signals = [
        "business", "brand", "company", "product", "service"
    ]
    for signal in weak_signals:
        if signal in msg_lower:
            score += 0.05

    return min(1.0, score)


# =========================================================================
# INTAKE STATE MANAGEMENT
# =========================================================================

class IntakePhase:
    """Intake phase constants."""
    QUALIFY = "phase_1_qualify"
    BRAND = "phase_2_brand"
    PRODUCT = "phase_3_product"
    PAIN_POINTS = "phase_4_pain_points"
    BENEFITS = "phase_5_benefits"
    SOCIAL_PROOF = "phase_6_social_proof"
    TARGETING = "phase_7_targeting"
    CREATIVE = "phase_8_creative"
    CTA = "phase_9_cta"
    QUALIFICATION = "phase_10_qualification"


PHASE_ORDER = [
    IntakePhase.QUALIFY,
    IntakePhase.BRAND,
    IntakePhase.PRODUCT,
    IntakePhase.PAIN_POINTS,
    IntakePhase.BENEFITS,
    IntakePhase.SOCIAL_PROOF,
    IntakePhase.TARGETING,
    IntakePhase.CREATIVE,
    IntakePhase.CTA,
    IntakePhase.QUALIFICATION,
]

PHASE_TRANSITIONS = {
    IntakePhase.QUALIFY: "Great! Sounds like AI-powered video could be a game-changer for you. Let me learn about your brand...",
    IntakePhase.BRAND: "Perfect, I can already picture the visual style. Now tell me about what you're selling...",
    IntakePhase.PRODUCT: "Got it! Now the important part - let's dig into what problems you solve for your customers...",
    IntakePhase.PAIN_POINTS: "This is gold for creating an emotional hook. Now what makes your solution special?",
    IntakePhase.BENEFITS: "Love it. Do you have any social proof we can feature?",
    IntakePhase.SOCIAL_PROOF: "Nice! Let's talk about who's going to see this commercial...",
    IntakePhase.TARGETING: "Almost there! A few questions about the creative direction...",
    IntakePhase.CREATIVE: "Perfect. What should viewers do after they see this?",
    IntakePhase.CTA: "Last section - this helps me recommend the right package for you...",
}

# Questions per phase
PHASE_QUESTIONS = {
    IntakePhase.QUALIFY: [
        {
            "id": "bottleneck",
            "question": "What's the biggest bottleneck in your marketing right now?",
            "type": "single_select",
            "options": [
                "Not getting enough leads",
                "Ads don't convert",
                "Can't produce content fast enough",
                "Competitors outspending us",
                "Don't know what's working"
            ],
            "required": True
        },
        {
            "id": "video_experience",
            "question": "Have you ever run video ads before?",
            "type": "single_select",
            "options": [
                "Yes, but results were disappointing",
                "Yes, and they worked - want more",
                "No, but we want to start",
                "No, not sure if it's right for us"
            ],
            "required": True
        }
    ],
    IntakePhase.BRAND: [
        {"id": "BRAND_NAME", "question": "What's your company name?", "type": "text", "required": True},
        {"id": "TAGLINE", "question": "What's your tagline or core message? What do you want people to remember?", "type": "text", "required": False},
        {"id": "PRIMARY_COLOR", "question": "What's your primary brand color? You can give me a hex code like #1E40AF or just say 'dark blue'.", "type": "text", "required": True},
        {"id": "SECONDARY_COLOR", "question": "Secondary brand color?", "type": "text", "required": False},
        {"id": "ACCENT_COLOR", "question": "Accent color for CTAs and highlights?", "type": "text", "required": False},
        {"id": "WEBSITE_URL", "question": "What's your website URL?", "type": "text", "required": True}
    ],
    IntakePhase.PRODUCT: [
        {"id": "PRODUCT_NAME", "question": "What product or service will this commercial promote?", "type": "text", "required": True},
        {"id": "INDUSTRY", "question": "What industry are you in? (B2B SaaS, E-commerce, Professional Services, Healthcare, Finance, Education, Manufacturing, Real Estate, Other)", "type": "text", "required": True},
        {"id": "PRODUCT_DESCRIPTION", "question": "In one sentence, what does your product/service do?", "type": "text", "required": True}
    ],
    IntakePhase.PAIN_POINTS: [
        {"id": "PAIN_POINT_1", "question": "What's the #1 pain your customers have BEFORE they find you? (This becomes the hook of your commercial)", "type": "text", "required": True},
        {"id": "PAIN_POINT_2", "question": "What's a secondary frustration they deal with?", "type": "text", "required": False},
        {"id": "FAILED_ALTERNATIVES", "question": "What have they probably tried that DIDN'T work?", "type": "text", "required": False}
    ],
    IntakePhase.BENEFITS: [
        {"id": "KEY_BENEFIT_1", "question": "What's the PRIMARY benefit customers get from your solution?", "type": "text", "required": True},
        {"id": "KEY_BENEFIT_2", "question": "What's a secondary benefit?", "type": "text", "required": False},
        {"id": "DIFFERENTIATOR", "question": "What makes you different from competitors?", "type": "text", "required": False}
    ],
    IntakePhase.SOCIAL_PROOF: [
        {"id": "SOCIAL_PROOF_STAT", "question": "Do you have a stat we can feature? Something like '500+ customers', '40% faster', or '$2M saved'", "type": "text", "required": False},
        {"id": "CLIENT_LOGOS", "question": "Any notable clients or logos we can mention?", "type": "text", "required": False},
        {"id": "TESTIMONIAL_QUOTE", "question": "Got a short testimonial quote we could use? (optional)", "type": "text", "required": False}
    ],
    IntakePhase.TARGETING: [
        {"id": "TARGET_AUDIENCE", "question": "Who is the ideal viewer of this commercial?", "type": "text", "required": True},
        {"id": "TARGET_TITLE", "question": "What's their job title or role?", "type": "text", "required": False},
        {"id": "PLATFORM", "question": "Where will this ad run? (LinkedIn, YouTube, Facebook/Instagram, TikTok, Website, Trade shows, Multiple platforms)", "type": "text", "required": True}
    ],
    IntakePhase.CREATIVE: [
        {"id": "TONE", "question": "What tone should the commercial have? (Professional & authoritative, Friendly & approachable, Bold & disruptive, Calm & reassuring, Energetic & exciting, Luxurious & premium)", "type": "text", "required": True},
        {"id": "STYLE_REFERENCE", "question": "Any brands whose style you admire? This helps us match the vibe.", "type": "text", "required": False}
    ],
    IntakePhase.CTA: [
        {"id": "CTA_ACTION", "question": "What action should viewers take after watching? (Visit website, Book demo, Start free trial, Download resource, Contact sales)", "type": "text", "required": True},
        {"id": "CTA_TEXT", "question": "What text should the CTA button say?", "type": "text", "required": True}
    ],
    IntakePhase.QUALIFICATION: [
        {"id": "TIMELINE", "question": "What's your timeline for this commercial? (ASAP, 2-4 weeks, 1-2 months, Just exploring)", "type": "text", "required": True},
        {"id": "BUDGET", "question": "Approximate budget range? (Under $5K, $5-15K, $15-50K, $50K+, Not sure yet)", "type": "text", "required": True},
        {"id": "EMAIL", "question": "What email should I send the commercial preview to?", "type": "email", "required": True}
    ]
}


def create_initial_intake_state() -> Dict[str, Any]:
    """Create fresh intake state for new conversation."""
    return {
        "active": False,
        "phase": None,
        "question_index": 0,
        "answers": {},
        "skipped": [],
        "started_at": None,
        "completed": False,
        "lead_score": None,
        "recommended_package": None,
        "client_id": None
    }


def activate_intake_mode(state: Dict[str, Any]) -> Dict[str, Any]:
    """Activate intake mode and start the flow."""
    intake = state.get("intake", create_initial_intake_state())
    intake["active"] = True
    intake["phase"] = IntakePhase.QUALIFY
    intake["question_index"] = 0
    intake["started_at"] = datetime.now().isoformat()
    intake["answers"] = {}
    intake["skipped"] = []
    intake["completed"] = False
    return intake


def get_current_question(intake_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get the current question based on phase and index."""
    if not intake_state.get("active"):
        return None

    phase = intake_state.get("phase")
    if not phase or phase not in PHASE_QUESTIONS:
        return None

    questions = PHASE_QUESTIONS[phase]
    index = intake_state.get("question_index", 0)

    if index < len(questions):
        return questions[index]

    return None


def get_opening_script() -> str:
    """Return the Nexus opening script."""
    return """Hey! I'm Nexus, your AI creative director.

I help businesses create scroll-stopping video ads using our AI commercial system. In about 5 minutes, I'll learn enough about your brand to show you exactly what kind of commercial we can create for you.

Ready to see what AI-powered advertising looks like for your brand?"""


def format_question_prompt(question: Dict[str, Any], is_first_in_phase: bool = False, phase: str = None) -> str:
    """Format a question for display with optional phase transition."""
    parts = []

    # Add phase transition if starting new phase
    if is_first_in_phase and phase and phase in PHASE_TRANSITIONS:
        # Get previous phase transition message
        phase_idx = PHASE_ORDER.index(phase)
        if phase_idx > 0:
            prev_phase = PHASE_ORDER[phase_idx - 1]
            if prev_phase in PHASE_TRANSITIONS:
                parts.append(PHASE_TRANSITIONS[prev_phase])
                parts.append("")  # Empty line

    # Add the question
    q_text = question["question"]

    # Add options if it's a select type
    if question.get("type") == "single_select" and question.get("options"):
        q_text += "\n\nOptions:\n"
        for opt in question["options"]:
            q_text += f"- {opt}\n"

    parts.append(q_text)

    # Add optional hint
    if not question.get("required"):
        parts.append("\n(You can skip this if you don't have one)")

    return "\n".join(parts)


def process_answer(intake_state: Dict[str, Any], answer: str) -> Tuple[Dict[str, Any], str]:
    """
    Process user's answer and advance the intake flow.

    Returns:
        Tuple of (updated_intake_state, next_response)
    """
    if not intake_state.get("active"):
        return intake_state, ""

    current_q = get_current_question(intake_state)
    if not current_q:
        return intake_state, ""

    # Check if user wants to skip
    answer_lower = answer.lower().strip()
    is_skip = answer_lower in ["skip", "pass", "next", "n/a", "na", "none", ""]

    if is_skip and not current_q.get("required"):
        # Record as skipped
        intake_state["skipped"].append(current_q["id"])
    else:
        # Store the answer
        intake_state["answers"][current_q["id"]] = answer.strip()

    # Advance to next question
    intake_state["question_index"] += 1

    # Check if we need to move to next phase
    phase = intake_state["phase"]
    if intake_state["question_index"] >= len(PHASE_QUESTIONS.get(phase, [])):
        # Move to next phase
        phase_idx = PHASE_ORDER.index(phase)
        if phase_idx < len(PHASE_ORDER) - 1:
            intake_state["phase"] = PHASE_ORDER[phase_idx + 1]
            intake_state["question_index"] = 0
        else:
            # Intake complete
            intake_state["completed"] = True
            intake_state["active"] = False

    # Generate next response
    if intake_state.get("completed"):
        response = generate_completion_summary(intake_state)
    else:
        next_q = get_current_question(intake_state)
        if next_q:
            is_first = intake_state["question_index"] == 0
            response = format_question_prompt(next_q, is_first, intake_state["phase"])
        else:
            response = ""

    return intake_state, response


def is_intake_complete(intake_state: Dict[str, Any]) -> bool:
    """Check if intake has collected minimum required info."""
    answers = intake_state.get("answers", {})
    required = ["BRAND_NAME", "PRODUCT_NAME", "PAIN_POINT_1", "EMAIL"]
    return all(answers.get(field) for field in required)


# =========================================================================
# LEAD SCORING & PACKAGE RECOMMENDATION
# =========================================================================

def calculate_lead_score(answers: Dict[str, Any]) -> int:
    """Calculate lead score 0-100 based on answers."""
    score = 0.0

    # Budget weight (30%)
    budget_scores = {
        "under $5k": 20, "under_5k": 20,
        "$5-15k": 40, "5k_15k": 40, "$5,000 - $15,000": 40,
        "$15-50k": 70, "15k_50k": 70, "$15,000 - $50,000": 70,
        "$50k+": 100, "50k_plus": 100, "$50,000+": 100,
        "not sure": 30, "not_sure": 30
    }
    budget = answers.get("BUDGET", "not sure").lower()
    for key, val in budget_scores.items():
        if key in budget:
            score += val * 0.30
            break

    # Timeline weight (25%)
    timeline_scores = {
        "asap": 100, "within 1 week": 100,
        "2-4 weeks": 70, "soon": 70, "soon_2_4_weeks": 70,
        "1-2 months": 40, "planning": 40, "planning_1_2_months": 40,
        "exploring": 10, "just exploring": 10, "just_exploring": 10
    }
    timeline = answers.get("TIMELINE", "exploring").lower()
    for key, val in timeline_scores.items():
        if key in timeline:
            score += val * 0.25
            break

    # Completeness weight (20%)
    required = ["BRAND_NAME", "PRODUCT_NAME", "PAIN_POINT_1", "KEY_BENEFIT_1"]
    completed = sum(1 for f in required if answers.get(f))
    score += (completed / len(required)) * 100 * 0.20

    # Industry weight (15%)
    high_value = ["b2b saas", "saas", "finance", "fintech", "healthcare", "professional services"]
    industry = answers.get("INDUSTRY", "").lower()
    if any(hv in industry for hv in high_value):
        score += 100 * 0.15
    else:
        score += 50 * 0.15

    # Platform weight (10%)
    platform = answers.get("PLATFORM", "").lower()
    if "linkedin" in platform or "youtube" in platform:
        score += 100 * 0.10
    else:
        score += 50 * 0.10

    return min(100, int(score))


def recommend_package(answers: Dict[str, Any], lead_score: int) -> Dict[str, Any]:
    """Recommend package based on answers and lead score."""
    budget = answers.get("BUDGET", "").lower()
    timeline = answers.get("TIMELINE", "").lower()

    # Enterprise indicators
    if "50k" in budget or "$50,000" in budget:
        return {
            "name": "Enterprise",
            "price": 25000,
            "reason": "Based on your budget and scale needs",
            "includes": [
                "5+ commercial concepts",
                "15s, 30s, and 60s versions",
                "All platform optimizations",
                "Unlimited revisions",
                "Strategy consultation",
                "Competitor analysis"
            ]
        }

    # Professional indicators
    if ("$5" in budget or "$15" in budget or "15k" in budget or "5k_15k" in budget) and \
       ("asap" in timeline or "2-4" in timeline or "soon" in timeline):
        return {
            "name": "Professional",
            "price": 7500,
            "reason": "Based on your timeline and multi-platform needs",
            "includes": [
                "3 commercial concepts",
                "30-second duration each",
                "Multi-platform optimization",
                "3 rounds of revisions",
                "VEO prompt package",
                "Voiceover script"
            ]
        }

    if lead_score >= 70:
        return {
            "name": "Professional",
            "price": 7500,
            "reason": "Based on your engagement and goals",
            "includes": [
                "3 commercial concepts",
                "30-second duration each",
                "Multi-platform optimization",
                "3 rounds of revisions"
            ]
        }

    # Default to Starter
    return {
        "name": "Starter",
        "price": 2500,
        "reason": "Perfect for testing AI video ads",
        "includes": [
            "1 commercial concept",
            "15-second duration",
            "1 platform optimization",
            "1 round of revisions",
            "VEO prompt package"
        ]
    }


def generate_completion_summary(intake_state: Dict[str, Any]) -> str:
    """Generate the completion summary with concept preview."""
    answers = intake_state.get("answers", {})

    # Calculate lead score and package
    lead_score = calculate_lead_score(answers)
    package = recommend_package(answers, lead_score)

    # Store in state
    intake_state["lead_score"] = lead_score
    intake_state["recommended_package"] = package["name"]

    brand_name = answers.get("BRAND_NAME", "your brand")
    pain_point = answers.get("PAIN_POINT_1", "your biggest challenge")
    tone = answers.get("TONE", "Professional & authoritative")
    platform = answers.get("PLATFORM", "LinkedIn")
    email = answers.get("EMAIL", "your email")

    # Generate opening shot preview based on pain point
    shot_preview = generate_opening_shot_preview(pain_point, answers.get("TARGET_AUDIENCE", "your ideal customer"))

    summary = f"""Got it! Based on everything you've told me, I'm generating a custom commercial concept for **{brand_name}**.

Here's what I'm thinking:

**CONCEPT:** The Problem-Solution
**HOOK:** Opens with the pain of {pain_point}
**STYLE:** {tone} with your brand colors
**DURATION:** 30 seconds
**OPTIMIZED FOR:** {platform}

**Here's how it would open:**

> {shot_preview}

I'll send a full commercial concept to {email} within 24 hours.

Based on your profile, I'd recommend our **{package['name']}** package (${package['price']:,}):
{chr(10).join('- ' + item for item in package['includes'])}

Want me to walk you through the package options, or do you have any questions about the concept?"""

    return summary


def generate_opening_shot_preview(pain_point: str, target_audience: str) -> str:
    """Generate a preview description of the opening shot."""
    # Sanitize inputs
    pain = pain_point.lower() if pain_point else "the problem"
    audience = target_audience.lower() if target_audience else "professional"

    previews = [
        f"Extreme close-up: Exhausted {audience}'s face lit by harsh monitor glow. Eyes dart between screens. Another late night dealing with {pain}.",
        f"Camera slowly pushes in on {audience} staring at a mountain of work. Text overlay: 'Still doing this the hard way?'",
        f"Split screen: Left side shows chaos of {pain}. Right side: 'There's a better way.' Your brand colors pulse.",
    ]

    # Simple selection based on pain point content
    if "manual" in pain or "time" in pain or "hour" in pain:
        return previews[0]
    elif "error" in pain or "mistake" in pain:
        return previews[1]
    else:
        return previews[2]


# =========================================================================
# CLIENT CONFIG GENERATION
# =========================================================================

def generate_client_id(brand_name: str) -> str:
    """Generate unique client ID from brand name."""
    slug = re.sub(r'[^a-z0-9]', '_', brand_name.lower())
    slug = re.sub(r'_+', '_', slug).strip('_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{slug}_{timestamp}"


def intake_to_client_config(intake_state: Dict[str, Any]) -> Dict[str, Any]:
    """Convert intake answers to RAGNAROK-compatible client config."""
    answers = intake_state.get("answers", {})

    # Color normalization
    COLOR_MAP = {
        "red": "#EF4444", "blue": "#3B82F6", "dark blue": "#1E40AF",
        "light blue": "#60A5FA", "green": "#22C55E", "dark green": "#166534",
        "yellow": "#EAB308", "gold": "#F59E0B", "orange": "#F97316",
        "purple": "#A855F7", "pink": "#EC4899", "black": "#000000",
        "white": "#FFFFFF", "gray": "#6B7280", "teal": "#14B8A6", "cyan": "#06B6D4"
    }

    def normalize_color(color_input: str) -> str:
        if not color_input:
            return "#000000"
        if color_input.startswith("#"):
            return color_input
        color_lower = color_input.lower().strip()
        if color_lower in COLOR_MAP:
            return COLOR_MAP[color_lower]
        for name, hex_code in COLOR_MAP.items():
            if name in color_lower or color_lower in name:
                return hex_code
        return "#000000"

    brand_name = answers.get("BRAND_NAME", "Unknown")

    config = {
        "client_id": generate_client_id(brand_name),
        "created_at": datetime.now().isoformat(),
        "intake_completed": True,
        "source": "website_assistant_intake",

        "brand_config": {
            "BRAND_NAME": answers.get("BRAND_NAME", ""),
            "TAGLINE": answers.get("TAGLINE", ""),
            "PRIMARY_COLOR": normalize_color(answers.get("PRIMARY_COLOR", "")),
            "SECONDARY_COLOR": normalize_color(answers.get("SECONDARY_COLOR", "")),
            "ACCENT_COLOR": normalize_color(answers.get("ACCENT_COLOR", "")),
            "WEBSITE_URL": answers.get("WEBSITE_URL", ""),
            "INDUSTRY": answers.get("INDUSTRY", ""),
            "PRODUCT_NAME": answers.get("PRODUCT_NAME", ""),
            "PRODUCT_DESCRIPTION": answers.get("PRODUCT_DESCRIPTION", ""),
            "CTA_TEXT": answers.get("CTA_TEXT", "Learn More"),
            "CTA_ACTION": answers.get("CTA_ACTION", "visit_website"),
        },

        "pain_points": {
            "PAIN_POINT_1": answers.get("PAIN_POINT_1", ""),
            "PAIN_POINT_2": answers.get("PAIN_POINT_2", ""),
            "FAILED_ALTERNATIVES": answers.get("FAILED_ALTERNATIVES", ""),
        },

        "benefits": {
            "KEY_BENEFIT_1": answers.get("KEY_BENEFIT_1", ""),
            "KEY_BENEFIT_2": answers.get("KEY_BENEFIT_2", ""),
            "DIFFERENTIATOR": answers.get("DIFFERENTIATOR", ""),
        },

        "social_proof": {
            "SOCIAL_PROOF_STAT": answers.get("SOCIAL_PROOF_STAT", ""),
            "CLIENT_LOGOS": answers.get("CLIENT_LOGOS", ""),
            "TESTIMONIAL_QUOTE": answers.get("TESTIMONIAL_QUOTE", ""),
        },

        "targeting": {
            "TARGET_AUDIENCE": answers.get("TARGET_AUDIENCE", ""),
            "TARGET_TITLE": answers.get("TARGET_TITLE", ""),
            "PLATFORM": answers.get("PLATFORM", "linkedin"),
        },

        "creative": {
            "TONE": answers.get("TONE", "professional_authoritative"),
            "STYLE_REFERENCE": answers.get("STYLE_REFERENCE", ""),
        },

        "contact": {
            "email": answers.get("EMAIL", ""),
        },

        "qualification": {
            "TIMELINE": answers.get("TIMELINE", ""),
            "BUDGET": answers.get("BUDGET", ""),
            "bottleneck": answers.get("bottleneck", ""),
            "video_experience": answers.get("video_experience", ""),
        },

        "lead_score": intake_state.get("lead_score", 0),
        "recommended_package": intake_state.get("recommended_package", "starter"),
    }

    return config


def save_client_config(config: Dict[str, Any], output_dir: str = None) -> Path:
    """Save client config to JSON file."""
    if output_dir is None:
        # Default to nexus intake clients directory
        output_dir = Path("C:/Users/gary/barrios-a2i/nexus/intake/clients")
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{config['client_id']}.json"
    filepath = output_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return filepath


# =========================================================================
# INTAKE CONTEXT FOR LLM
# =========================================================================

def get_intake_system_context(intake_state: Dict[str, Any]) -> str:
    """
    Generate system context for the LLM when in intake mode.
    This helps the model understand how to handle the conversation.
    """
    if not intake_state.get("active"):
        return ""

    phase = intake_state.get("phase", "")
    phase_name = phase.replace("phase_", "").replace("_", " ").title() if phase else "Unknown"
    answers = intake_state.get("answers", {})
    current_q = get_current_question(intake_state)

    context = f"""
[INTAKE MODE ACTIVE]
You are Nexus, an AI Creative Director helping businesses create commercials.

Current Phase: {phase_name}
Questions Answered: {len(answers)}
Current Question: {current_q.get('question', 'None') if current_q else 'Intake complete'}

BEHAVIOR:
- Ask ONE question at a time
- Be conversational, not robotic
- React to answers naturally
- If user skips optional questions, that's okay
- If user asks questions mid-intake, answer briefly then return to the flow
- Pain points are the MOST IMPORTANT - spend extra time getting specific details

COLLECTED SO FAR:
{json.dumps(answers, indent=2) if answers else 'No answers yet'}
"""
    return context


# =========================================================================
# EXPORTS
# =========================================================================

__all__ = [
    # Detection
    "is_intake_query",
    "get_intake_intent_confidence",
    "INTAKE_TRIGGERS",

    # State management
    "create_initial_intake_state",
    "activate_intake_mode",
    "get_current_question",
    "process_answer",
    "is_intake_complete",

    # Scripts
    "get_opening_script",
    "format_question_prompt",
    "generate_completion_summary",

    # Scoring
    "calculate_lead_score",
    "recommend_package",

    # Client config
    "intake_to_client_config",
    "save_client_config",

    # LLM context
    "get_intake_system_context",

    # Constants
    "IntakePhase",
    "PHASE_ORDER",
    "PHASE_QUESTIONS",
    "PHASE_TRANSITIONS",
]
