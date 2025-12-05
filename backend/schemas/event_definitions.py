# schemas/event_definitions.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — EVENT SCHEMAS + GENERATIVE UI
# ============================================================================
# Authority: Claude 4.5 Opus Final Decision
# Purpose: Type-safe event definitions with Generative UI card payloads
#
# NEW IN v2.0:
# - Generative UI card schemas (CompetitorAnalysisCard, PersonaCard, etc.)
# - RenderCard union type for polymorphic frontend rendering
# - TrinityBridge integration types for competitive intelligence
# ============================================================================

from typing import Dict, Any, List, Optional, Literal, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import uuid


# ============================================================================
# SECTION 1: SHARED DEFINITIONS
# ============================================================================

class TraceContext(BaseModel):
    """OpenTelemetry distributed tracing context."""
    trace_id: str = Field(min_length=32, max_length=32)
    span_id: str = Field(min_length=16, max_length=16)
    parent_span_id: Optional[str] = None
    
    @classmethod
    def create(cls, parent: Optional["TraceContext"] = None) -> "TraceContext":
        return cls(
            trace_id=parent.trace_id if parent else uuid.uuid4().hex,
            span_id=uuid.uuid4().hex[:16],
            parent_span_id=parent.span_id if parent else None
        )


class ConfigVersion(BaseModel):
    """Version tracking for debugging."""
    agent_registry: str = "2.0.0"
    event_schema: str = "2.0.0"
    graph_version: str = "2.0.0"


class ConversationTurn(BaseModel):
    """Turn tracking for ordering."""
    turn_number: int = Field(ge=1)
    hop_count: int = Field(ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# SECTION 2: ENUMS
# ============================================================================

class TenantTier(str, Enum):
    STARTER = "starter"
    PRO = "pro"
    ELITE = "elite"


class Intent(str, Enum):
    FAQ = "faq"
    SUPPORT = "support"
    LEAD_QUALIFICATION = "lead_qualification"
    BOOKING = "booking"
    COMPLEX_REASONING = "complex_reasoning"
    COMPETITIVE_INTEL = "competitive_intel"  # NEW: Trinity integration
    UNKNOWN = "unknown"


class LeadTier(str, Enum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"


class ValidationAction(str, Enum):
    SEND_AS_IS = "send_as_is"
    REQUEST_REANSWER = "request_reanswer"
    BLOCK_AND_ESCALATE = "block_and_escalate"


class CardType(str, Enum):
    """Types of Generative UI cards."""
    COMPETITOR_ANALYSIS = "competitor_analysis"
    PERSONA = "persona"
    SCRIPT_PREVIEW = "script_preview"
    ROI_CALCULATOR = "roi_calculator"
    PRICING_COMPARISON = "pricing_comparison"
    MARKET_TREND = "market_trend"
    # v3.0 additions
    CHECKOUT = "checkout"
    PRODUCTION_TRACKER = "production_tracker"
    BRIEF_REVIEW = "brief_review"
    ORDER_TRACKING = "order_tracking"


# ============================================================================
# SECTION 3: GENERATIVE UI CARD SCHEMAS
# ============================================================================

class CompetitorStat(BaseModel):
    """Single stat comparison between us and competitor."""
    metric: str = Field(description="Name of the metric (e.g., 'Video Quality')")
    our_value: str = Field(description="Our value for this metric")
    their_value: str = Field(description="Competitor's value")
    advantage: Literal["us", "them", "tie"] = Field(description="Who has the advantage")
    delta_percent: Optional[float] = Field(default=None, description="Percentage difference")


class KillShot(BaseModel):
    """The single most compelling competitive advantage."""
    headline: str = Field(max_length=80, description="Punchy headline")
    detail: str = Field(max_length=300, description="Supporting detail")
    proof_point: Optional[str] = Field(default=None, description="Data or testimonial backing")


class CompetitorAnalysisCard(BaseModel):
    """
    Generative UI card for competitive intelligence.
    Rendered as "Vs. Mode" layout with red/green stats.
    """
    type: Literal[CardType.COMPETITOR_ANALYSIS] = CardType.COMPETITOR_ANALYSIS
    
    # Header
    title: str = Field(default="Competitive Analysis")
    competitor_name: str = Field(description="Name of the competitor")
    competitor_logo_url: Optional[str] = None
    our_logo_url: Optional[str] = None
    
    # Stats comparison (max 6 for UI clarity)
    stats: List[CompetitorStat] = Field(max_length=6)
    
    # The kill shot - highlighted in neon
    kill_shot: KillShot
    
    # Confidence and source
    confidence_score: float = Field(ge=0.0, le=1.0)
    data_freshness: str = Field(description="e.g., 'Updated 2 days ago'")
    sources: List[str] = Field(default_factory=list, max_length=5)
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    trace_id: Optional[str] = None


class PainPoint(BaseModel):
    """Individual pain point for a persona."""
    title: str = Field(max_length=60)
    severity: Literal["low", "medium", "high", "critical"]
    description: str = Field(max_length=200)


class PersonaCard(BaseModel):
    """
    Generative UI card for buyer persona visualization.
    Rendered as ID card style with avatar.
    """
    type: Literal[CardType.PERSONA] = CardType.PERSONA
    
    # Identity
    persona_name: str = Field(description="e.g., 'Marketing Manager Maria'")
    title: str = Field(description="Job title")
    company_type: str = Field(description="e.g., 'Mid-market SaaS'")
    avatar_url: Optional[str] = None
    
    # Demographics
    age_range: str = Field(description="e.g., '35-45'")
    income_range: str = Field(description="e.g., '$120K - $180K'")
    income_percentile: float = Field(ge=0.0, le=1.0, description="For progress bar")
    
    # Psychographics
    pain_points: List[PainPoint] = Field(max_length=5)
    goals: List[str] = Field(max_length=4)
    objections: List[str] = Field(max_length=3)
    
    # Decision making
    decision_drivers: List[str] = Field(max_length=3)
    budget_authority: Literal["none", "influence", "approve", "final_decision"]
    buying_timeline: str
    
    # Metadata
    confidence_score: float = Field(ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ScriptSection(BaseModel):
    """Section of a generated script."""
    section_type: Literal["hook", "problem", "solution", "proof", "cta"]
    content: str
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None


class ScriptPreviewCard(BaseModel):
    """
    Generative UI card for script preview/editor.
    Rendered as minimalist editor with regenerate/approve buttons.
    """
    type: Literal[CardType.SCRIPT_PREVIEW] = CardType.SCRIPT_PREVIEW
    
    # Script metadata
    script_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    format: Literal["15s", "30s", "60s", "90s"]
    tone: Literal["professional", "casual", "urgent", "inspirational"]
    
    # Content
    sections: List[ScriptSection]
    full_script: str = Field(description="Combined script text")
    word_count: int
    estimated_duration_seconds: int
    
    # Targeting
    target_persona: Optional[str] = None
    target_platform: Literal["youtube", "tiktok", "instagram", "linkedin", "tv"]
    
    # Status
    status: Literal["draft", "pending_approval", "approved", "rejected"]
    revision_number: int = 1
    
    # Actions available
    can_regenerate: bool = True
    can_edit: bool = True
    can_approve: bool = True
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ROISlider(BaseModel):
    """Interactive slider for ROI calculator."""
    id: str
    label: str
    min_value: float
    max_value: float
    default_value: float
    step: float
    unit: str = Field(description="e.g., '$', '%', 'hours'")
    tooltip: Optional[str] = None


class ROIProjection(BaseModel):
    """Projected ROI metric."""
    metric_name: str
    current_value: float
    projected_value: float
    improvement_percent: float
    timeframe: str = Field(description="e.g., 'per month', 'per year'")


class ROICalculatorCard(BaseModel):
    """
    Generative UI card for interactive ROI calculator.
    Rendered with sliders and glowing green projections.
    """
    type: Literal[CardType.ROI_CALCULATOR] = CardType.ROI_CALCULATOR
    
    # Header
    title: str = "ROI Calculator"
    subtitle: Optional[str] = None
    
    # Input sliders (max 5 for UI clarity)
    sliders: List[ROISlider] = Field(max_length=5)
    
    # Projections
    projections: List[ROIProjection] = Field(max_length=6)
    
    # Summary
    total_savings: float
    savings_currency: str = "USD"
    payback_period_months: Optional[float] = None
    
    # Formula transparency
    formula_description: Optional[str] = Field(
        default=None,
        description="Human-readable explanation of ROI calculation"
    )
    
    # CTA
    cta_text: str = "Get Your Custom Quote"
    cta_action: Literal["book_call", "start_trial", "contact_sales"]
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class PricingTier(BaseModel):
    """Single pricing tier for comparison."""
    name: str
    price: float
    period: Literal["one-time", "monthly", "yearly"]
    features: List[str]
    is_recommended: bool = False
    competitor_price: Optional[float] = None
    savings_vs_competitor: Optional[float] = None


class PricingComparisonCard(BaseModel):
    """
    Generative UI card for pricing comparison.
    """
    type: Literal[CardType.PRICING_COMPARISON] = CardType.PRICING_COMPARISON
    
    title: str = "Pricing Comparison"
    tiers: List[PricingTier] = Field(max_length=4)
    competitor_name: Optional[str] = None
    
    # Value props
    key_differentiators: List[str] = Field(max_length=4)
    money_back_guarantee: Optional[str] = None
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class TrendDataPoint(BaseModel):
    """Single data point in a trend."""
    date: str
    value: float
    label: Optional[str] = None


class MarketTrendCard(BaseModel):
    """
    Generative UI card for market trend visualization.
    """
    type: Literal[CardType.MARKET_TREND] = CardType.MARKET_TREND
    
    title: str
    trend_direction: Literal["up", "down", "stable"]
    trend_percent: float
    timeframe: str
    
    data_points: List[TrendDataPoint] = Field(max_length=12)
    
    insight: str = Field(max_length=300, description="AI-generated insight")
    recommendation: str = Field(max_length=200)
    
    sources: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# SECTION 4: V3.0 GENERATIVE UI CARDS (BriefReview, OrderTracking)
# ============================================================================

class BriefItem(BaseModel):
    """Single item in the creative brief."""
    label: str
    value: str
    editable: bool = True
    warning: Optional[str] = None  # From USP validation


class BriefReviewCard(BaseModel):
    """
    Interactive card for reviewing/editing the creative brief before payment.

    Displays in the Cyberpunk HUD as an editable form.
    """
    type: Literal[CardType.BRIEF_REVIEW] = CardType.BRIEF_REVIEW

    # Header
    title: str = "Review Your Creative Brief"
    subtitle: str = "Confirm details before we create your commercial"

    # Brief sections
    business_info: List[BriefItem] = Field(
        description="Business name, industry, target audience"
    )
    creative_direction: List[BriefItem] = Field(
        description="Tone, style, key message, USP"
    )
    technical_specs: List[BriefItem] = Field(
        description="Duration, format, delivery requirements"
    )

    # Validation status
    validation_passed: bool = True
    validation_warnings: List[str] = Field(default_factory=list)

    # Actions
    can_proceed: bool = True
    proceed_label: str = "Approve & Continue to Payment"
    edit_label: str = "Request Changes"

    # Metadata
    session_id: str
    brief_version: int = 1
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class OrderPhase(BaseModel):
    """Single phase in the order lifecycle."""
    id: str
    name: str
    status: Literal["pending", "active", "completed", "failed"] = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    details: Optional[str] = None


class OrderTrackingCard(BaseModel):
    """
    Persistent HUD element showing order status from payment to delivery.

    Updates in real-time via WebSocket. Cyberpunk aesthetic.
    """
    type: Literal[CardType.ORDER_TRACKING] = CardType.ORDER_TRACKING

    # Order identification
    order_id: str
    order_number: str  # Human-readable, e.g., "ORD-2024-0042"

    # Current status
    status: Literal[
        "payment_pending",
        "payment_confirmed",
        "brief_review",
        "production_queued",
        "production_active",
        "production_complete",
        "delivery_processing",
        "delivered",
        "failed"
    ]
    status_label: str
    status_description: str

    # Progress
    progress_percent: int = Field(ge=0, le=100)
    current_phase: str
    phases: List[OrderPhase]

    # Timing
    created_at: datetime
    estimated_completion: Optional[datetime] = None
    actual_completion: Optional[datetime] = None

    # Delivery (when complete)
    video_url: Optional[str] = None
    video_thumbnail: Optional[str] = None
    download_expires_at: Optional[datetime] = None

    # Actions
    can_cancel: bool = False
    can_download: bool = False
    support_url: str = "mailto:support@barriosa2i.com"

    # Metadata
    session_id: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# SECTION 5: RENDER CARD UNION TYPE
# ============================================================================

RenderCard = Union[
    CompetitorAnalysisCard,
    PersonaCard,
    ScriptPreviewCard,
    ROICalculatorCard,
    PricingComparisonCard,
    MarketTrendCard,
    BriefReviewCard,
    OrderTrackingCard
]


# ============================================================================
# SECTION 5: ASSISTANT MESSAGE WITH GENERATIVE UI
# ============================================================================

class AssistantMessage(BaseModel):
    """
    Complete assistant response including optional Generative UI card.
    
    The frontend checks `render_card` - if present, renders the appropriate
    component instead of plain text.
    """
    # Text response (always present)
    content: str
    
    # Optional Generative UI payload
    render_card: Optional[RenderCard] = None
    
    # Metadata
    intent: str
    confidence: float
    model_used: str
    latency_ms: float
    cost_usd: float
    
    # Trace
    trace_id: str
    session_id: str
    turn_number: int


# ============================================================================
# SECTION 6: TRINITY BRIDGE TYPES
# ============================================================================

class TrinityQuery(BaseModel):
    """Query to Trinity intelligence system."""
    query_type: Literal["competitor", "market", "persona", "trend"]
    competitor_name: Optional[str] = None
    industry: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    max_results: int = 5
    freshness_hours: int = 168  # 1 week default


class TrinityResponse(BaseModel):
    """Response from Trinity intelligence system."""
    success: bool
    query_type: str
    data: Dict[str, Any]
    sources: List[str]
    confidence: float
    generated_at: datetime
    cache_hit: bool = False
    error_message: Optional[str] = None


# ============================================================================
# SECTION 7: EXISTING EVENT TYPES (from v1.1)
# ============================================================================

class BaseEvent(BaseModel):
    """Base class for all events."""
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trace_context: TraceContext
    config_version: ConfigVersion = Field(default_factory=ConfigVersion)
    conversation_turn: ConversationTurn
    tenant_id: str
    site_id: str
    session_id: str
    
    class Config:
        use_enum_values = True


class LeadData(BaseModel):
    """Collected lead information."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    service_interest: Optional[str] = None
    timeline: Optional[str] = None
    budget_range: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class SupervisorDecision(BaseEvent):
    """Event emitted by supervisor after intent classification."""
    event_type: Literal["supervisor_decision"] = "supervisor_decision"
    detected_intent: Intent
    intent_confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    target_node: str
    model_used: str
    frustration_detected: bool = False
    cycle_detected: bool = False


class LeadQualificationResult(BaseEvent):
    """Event emitted after lead qualification turn."""
    event_type: Literal["lead_qualification_result"] = "lead_qualification_result"
    lead_score: float = Field(ge=0.0, le=1.0)
    lead_tier: LeadTier
    questions_asked: int = Field(ge=0, le=10)
    value_offered: bool
    qualification_complete: bool
    lead_data: LeadData
    model_used: str


class IntelligenceResult(BaseEvent):
    """
    Event emitted after Trinity intelligence query.
    NEW IN v2.0
    """
    event_type: Literal["intelligence_result"] = "intelligence_result"
    query_type: str
    competitor_name: Optional[str] = None
    render_card: Optional[RenderCard] = None
    success: bool
    error_message: Optional[str] = None
    model_used: str
    trinity_latency_ms: float


# ============================================================================
# SECTION 8: EXPORTS
# ============================================================================

__all__ = [
    # Shared
    "TraceContext",
    "ConfigVersion",
    "ConversationTurn",
    
    # Enums
    "TenantTier",
    "Intent",
    "LeadTier",
    "ValidationAction",
    "CardType",
    
    # Generative UI Cards
    "CompetitorStat",
    "KillShot",
    "CompetitorAnalysisCard",
    "PainPoint",
    "PersonaCard",
    "ScriptSection",
    "ScriptPreviewCard",
    "ROISlider",
    "ROIProjection",
    "ROICalculatorCard",
    "PricingTier",
    "PricingComparisonCard",
    "TrendDataPoint",
    "MarketTrendCard",
    "RenderCard",

    # v3.0 Generative UI Cards
    "BriefItem",
    "BriefReviewCard",
    "OrderPhase",
    "OrderTrackingCard",
    
    # Messages
    "AssistantMessage",
    
    # Trinity
    "TrinityQuery",
    "TrinityResponse",
    
    # Events
    "BaseEvent",
    "LeadData",
    "SupervisorDecision",
    "LeadQualificationResult",
    "IntelligenceResult",
]
