# api/website_graph.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — LANGGRAPH CORE
# ============================================================================
# Authority: Claude 4.5 Opus Final Decision
#
# UPDATES IN v2.0:
# - Added intelligence_node for Trinity integration
# - Enhanced error handling for empty/failed Trinity responses
# - director_node state persistence improvements
# - Generative UI card generation in responses
# ============================================================================

import logging
import json
import uuid
import re
import asyncio
from typing import Dict, Any, List, Optional, Literal, Sequence, Annotated, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import operator

# LangGraph/LangChain imports
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Local imports
from schemas.event_definitions import (
    CompetitorAnalysisCard,
    PersonaCard,
    ROICalculatorCard,
    AssistantMessage,
    RenderCard,
    Intent,
    TenantTier,
)
from agents.trinity_bridge import (
    TrinityBridge,
    get_trinity_bridge,
    is_competitive_query,
    extract_competitor,
)
from agents.persona_generator import (
    is_persona_query,
    process_persona_query,
)
from agents.script_generator import (
    is_script_query,
    process_script_query,
)
from agents.roi_generator import (
    is_roi_query,
    process_roi_query,
)
from agents.intake_detector import (
    is_intake_query,
    get_intake_intent_confidence,
    create_initial_intake_state,
    activate_intake_mode,
    get_current_question,
    process_answer,
    is_intake_complete,
    get_opening_script,
    format_question_prompt,
    generate_completion_summary,
    intake_to_client_config,
    save_client_config,
    get_intake_system_context,
    IntakePhase,
)

logger = logging.getLogger("BarriosA2I.WebsiteAssistant")


# ============================================================================
# SECTION 1: ENUMS & CONSTANTS
# ============================================================================

# Cost ceilings per conversation (USD)
COST_CEILINGS = {
    "starter": {"target": 0.03, "hard_cap": 0.05},
    "pro":     {"target": 0.10, "hard_cap": 0.15},
    "elite":   {"target": 0.35, "hard_cap": 0.50},
}

# Frustration keywords trigger immediate escalation
FRUSTRATION_KEYWORDS = frozenset({
    "human", "representative", "real person", "manager", "supervisor",
    "useless", "stupid", "terrible", "worst", "incompetent",
    "speak to someone", "talk to someone", "actual person",
    "this is ridiculous", "waste of time", "not working"
})

# Pattern limits
MAX_HOPS_PER_TURN = 5
MAX_VALIDATION_RETRIES = 2


# ============================================================================
# SECTION 2: MODEL ROUTING SERVICE
# ============================================================================

@dataclass
class RoutingDecision:
    """Result of model routing decision."""
    model: str
    max_tokens: int
    temperature: float
    reasoning: str
    estimated_cost: float
    fallback_model: Optional[str] = None


class ModelRoutingService:
    """Deterministic model routing utility."""
    
    def __init__(self):
        self.model_costs = {
            "claude-3-5-haiku-20241022":  {"input": 0.25,  "output": 1.25},
            "claude-3-5-sonnet-20241022": {"input": 3.00,  "output": 15.00},
            "claude-3-opus-20240229":     {"input": 15.00, "output": 75.00},
            "gpt-4o-mini":                {"input": 0.15,  "output": 0.60},
            "gpt-4o":                     {"input": 5.00,  "output": 15.00},
        }
    
    def route(
        self,
        agent_role: str,
        tier: str,
        current_cost: float = 0.0
    ) -> RoutingDecision:
        """Route to appropriate model based on agent role and tier."""
        
        remaining = COST_CEILINGS.get(tier, COST_CEILINGS["starter"])["hard_cap"] - current_cost
        if remaining <= 0:
            return self._emergency_fallback("Cost ceiling exceeded")
        
        routes = {
            "supervisor":        self._route_supervisor,
            "website_assistant": self._route_website_assistant,
            "retrieval_agent":   self._route_retrieval,
            "lead_qualifier":    self._route_lead_qualifier,
            "booking_agent":     self._route_booking,
            "intelligence":      self._route_intelligence,
        }
        
        router = routes.get(agent_role, self._emergency_fallback)
        return router(tier) if callable(router) else self._emergency_fallback(f"Unknown: {agent_role}")
    
    def _route_supervisor(self, tier: str) -> RoutingDecision:
        if tier == "elite":
            return RoutingDecision("claude-3-5-sonnet-20241022", 512, 0.0, "Elite precision", 0.005)
        return RoutingDecision("claude-3-5-haiku-20241022", 512, 0.0, "Classification: Haiku", 0.0005)
    
    def _route_website_assistant(self, tier: str) -> RoutingDecision:
        if tier == "elite":
            return RoutingDecision("claude-3-5-sonnet-20241022", 600, 0.7, "Elite conversationalist", 0.01)
        return RoutingDecision("gpt-4o-mini", 400, 0.7, "Fast chat: mini", 0.0008)
    
    def _route_retrieval(self, tier: str) -> RoutingDecision:
        if tier == "elite":
            return RoutingDecision("claude-3-5-sonnet-20241022", 2048, 0.2, "Elite synthesis", 0.02)
        return RoutingDecision("gpt-4o-mini", 1024, 0.2, "Starter synthesis", 0.002)
    
    def _route_lead_qualifier(self, tier: str) -> RoutingDecision:
        """REVENUE CRITICAL: Never below Sonnet."""
        if tier == "elite":
            return RoutingDecision("claude-3-opus-20240229", 1024, 0.3, "Elite: max sales EQ", 0.10)
        return RoutingDecision("claude-3-5-sonnet-20241022", 1024, 0.3, "Revenue critical", 0.03)
    
    def _route_booking(self, tier: str) -> RoutingDecision:
        if tier == "elite":
            return RoutingDecision("gpt-4o", 1024, 0.1, "Elite booking", 0.005)
        return RoutingDecision("claude-3-5-haiku-20241022", 1024, 0.1, "Booking: Haiku", 0.001)
    
    def _route_intelligence(self, tier: str) -> RoutingDecision:
        """Intelligence synthesis - always use good model."""
        if tier == "elite":
            return RoutingDecision("claude-3-5-sonnet-20241022", 1500, 0.5, "Elite intel", 0.02)
        return RoutingDecision("claude-3-5-sonnet-20241022", 1000, 0.5, "Intel synthesis", 0.015)
    
    def _emergency_fallback(self, reason: str) -> RoutingDecision:
        logger.warning(f"Emergency fallback: {reason}")
        return RoutingDecision("gpt-4o-mini", 256, 0.0, f"EMERGENCY: {reason}", 0.0002)


model_router = ModelRoutingService()


# ============================================================================
# SECTION 3: STATE DEFINITIONS
# ============================================================================

from typing import TypedDict


class TraceContext(TypedDict):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]


class LeadState(TypedDict):
    score: float
    tier: Optional[Literal["cold", "warm", "hot"]]
    questions_asked: int
    value_offered: bool
    collected_data: Dict[str, Any]
    qualification_complete: bool


class ValidationState(TypedDict):
    required: bool
    passed: Optional[bool]
    action: Optional[Literal["send_as_is", "request_reanswer", "block_and_escalate"]]
    issues: List[str]


class MetricsState(TypedDict):
    total_cost_usd: float
    total_latency_ms: float
    models_used: List[str]


class DirectorState(TypedDict):
    """
    Director (Creative Director) state for multi-turn conversations.
    Persists across turns for context continuity.
    """
    persona_context: Optional[Dict[str, Any]]
    competitor_context: Optional[Dict[str, Any]]
    script_context: Optional[Dict[str, Any]]
    conversation_theme: Optional[str]
    last_card_type: Optional[str]


class IntakeState(TypedDict):
    """
    Nexus Intake state for commercial lead qualification.
    Tracks progress through the 30-question intake flow.
    """
    active: bool
    phase: Optional[str]
    question_index: int
    answers: Dict[str, Any]
    skipped: List[str]
    started_at: Optional[str]
    completed: bool
    lead_score: Optional[int]
    recommended_package: Optional[str]
    client_id: Optional[str]


class WebsiteAssistantState(TypedDict):
    """Global state for the Website Assistant LangGraph."""
    # Messages (append-only)
    messages: Annotated[Sequence[BaseMessage], operator.add]
    
    # Identity
    tenant_id: str
    site_id: str
    session_id: str
    user_tier: Literal["starter", "pro", "elite"]
    
    # Traceability
    trace_context: TraceContext
    
    # Turn tracking
    turn_number: int
    hop_count: int
    retry_count: int
    
    # Routing
    current_node: str
    next_node: str
    detected_intent: str
    intent_confidence: float
    router_reasoning: str
    
    # Business state
    lead: LeadState
    rag_contexts: List[Dict[str, Any]]
    booking_status: Optional[str]
    
    # Generative UI
    render_card: Optional[Dict[str, Any]]
    
    # Director state (persisted)
    director: DirectorState

    # Intake state (persisted for commercial lead flow)
    intake: IntakeState

    # Validation
    validation: ValidationState
    
    # Metrics
    metrics: MetricsState
    
    # Flags
    frustration_detected: bool
    human_handoff_requested: bool
    has_contact_info: bool


# ============================================================================
# SECTION 4: UTILITY FUNCTIONS
# ============================================================================

def get_llm(model: str, temperature: float = 0.7, max_tokens: int = 1024):
    """Factory for LLM instances."""
    if model.startswith("claude"):
        return ChatAnthropic(model=model, temperature=temperature, max_tokens=max_tokens)
    elif model.startswith("gpt"):
        return ChatOpenAI(model=model, temperature=temperature, max_tokens=max_tokens)
    raise ValueError(f"Unknown model: {model}")


def detect_frustration(message: str) -> bool:
    """Check if message contains frustration signals."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in FRUSTRATION_KEYWORDS)


def extract_contact_info(message: str) -> Dict[str, str]:
    """Extract email and phone from message."""
    info = {}
    email = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', message)
    if email:
        info["email"] = email.group()
    phone = re.search(r'[\d]{3}[-.\s]?[\d]{3}[-.\s]?[\d]{4}', message)
    if phone:
        info["phone"] = phone.group()
    return info


def create_initial_state(
    user_message: BaseMessage,
    tenant_id: str,
    site_id: str,
    session_id: str,
    user_tier: str = "starter"
) -> WebsiteAssistantState:
    """Factory to create properly initialized state."""
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    
    return WebsiteAssistantState(
        messages=[user_message],
        tenant_id=tenant_id,
        site_id=site_id,
        session_id=session_id,
        user_tier=user_tier,
        trace_context={"trace_id": trace_id, "span_id": span_id, "parent_span_id": None},
        turn_number=1,
        hop_count=0,
        retry_count=0,
        current_node="entry",
        next_node="supervisor",
        detected_intent="unknown",
        intent_confidence=0.0,
        router_reasoning="",
        lead=LeadState(
            score=0.0, tier=None, questions_asked=0,
            value_offered=False, collected_data={}, qualification_complete=False
        ),
        rag_contexts=[],
        booking_status=None,
        render_card=None,
        director=DirectorState(
            persona_context=None,
            competitor_context=None,
            script_context=None,
            conversation_theme=None,
            last_card_type=None
        ),
        intake=IntakeState(
            active=False,
            phase=None,
            question_index=0,
            answers={},
            skipped=[],
            started_at=None,
            completed=False,
            lead_score=None,
            recommended_package=None,
            client_id=None
        ),
        validation=ValidationState(required=False, passed=None, action=None, issues=[]),
        metrics=MetricsState(total_cost_usd=0.0, total_latency_ms=0.0, models_used=[]),
        frustration_detected=False,
        human_handoff_requested=False,
        has_contact_info=False
    )


# ============================================================================
# SECTION 5: NODE IMPLEMENTATIONS
# ============================================================================

async def entry_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """Entry point. Checks frustration, extracts contact info."""
    last_msg = state["messages"][-1]
    msg_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
    
    frustration = detect_frustration(msg_text)
    contact = extract_contact_info(msg_text)
    
    updates = {
        "current_node": "entry",
        "next_node": "human_escalation" if frustration else "supervisor",
        "frustration_detected": frustration,
        "hop_count": 0,
        "render_card": None  # Clear previous render_card
    }
    
    if contact:
        lead = dict(state["lead"])
        lead["collected_data"] = {**lead["collected_data"], **contact}
        updates["lead"] = lead
        updates["has_contact_info"] = True
    
    return updates


async def supervisor_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """Supervisor: Classifies intent and routes."""
    
    # Cycle detection
    if state["hop_count"] >= MAX_HOPS_PER_TURN:
        logger.warning(f"Cycle detected: {state['hop_count']} hops. Escalating.")
        return {
            "current_node": "supervisor",
            "next_node": "human_escalation",
            "frustration_detected": True,
            "router_reasoning": "Max hops exceeded",
            "hop_count": state["hop_count"] + 1
        }
    
    if state["frustration_detected"]:
        return {
            "current_node": "supervisor",
            "next_node": "human_escalation",
            "router_reasoning": "Frustration detected",
            "hop_count": state["hop_count"] + 1
        }
    
    tier = state["user_tier"]
    config = model_router.route("supervisor", tier, state["metrics"]["total_cost_usd"])
    
    last_msg = state["messages"][-1]
    msg_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    # =========================================================================
    # INTAKE MODE DETECTION - Highest priority for commercial leads
    # =========================================================================

    # If already in active intake mode, continue the intake flow
    if state.get("intake", {}).get("active"):
        logger.info("Intake mode active, routing to intake node")
        return {
            "current_node": "supervisor",
            "next_node": "intake",
            "detected_intent": "intake_continuation",
            "intent_confidence": 1.0,
            "router_reasoning": "Active intake session - continuing flow",
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.0001
            }
        }

    # Check for NEW intake trigger (commercial interest)
    if is_intake_query(msg_text):
        logger.info("Commercial interest detected, activating intake mode")
        confidence = get_intake_intent_confidence(msg_text)
        return {
            "current_node": "supervisor",
            "next_node": "intake",
            "detected_intent": "commercial_inquiry",
            "intent_confidence": confidence,
            "router_reasoning": "Commercial/video interest detected - starting intake",
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.0001
            }
        }

    # =========================================================================
    # Standard intent detection (after intake check)
    # =========================================================================

    # Check for competitive intelligence queries FIRST
    if is_competitive_query(msg_text):
        logger.info(f"Competitive query detected, routing to intelligence node")
        return {
            "current_node": "supervisor",
            "next_node": "intelligence",
            "detected_intent": "competitive_intel",
            "intent_confidence": 0.9,
            "router_reasoning": "Competitive query detected",
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.0001  # Minimal cost for detection
            }
        }

    # Check for persona queries SECOND
    if is_persona_query(msg_text):
        logger.info(f"Persona query detected, routing to persona node")
        return {
            "current_node": "supervisor",
            "next_node": "persona",
            "detected_intent": "persona_query",
            "intent_confidence": 0.9,
            "router_reasoning": "Persona/customer profile query detected",
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.0001  # Minimal cost for detection
            }
        }

    # Check for script/commercial queries THIRD
    if is_script_query(msg_text):
        logger.info(f"Script query detected, routing to script node")
        return {
            "current_node": "supervisor",
            "next_node": "script",
            "detected_intent": "script_query",
            "intent_confidence": 0.9,
            "router_reasoning": "Script/commercial writing query detected",
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.0001  # Minimal cost for detection
            }
        }

    # Check for ROI/pricing queries FOURTH
    if is_roi_query(msg_text):
        logger.info(f"ROI query detected, routing to roi node")
        return {
            "current_node": "supervisor",
            "next_node": "roi",
            "detected_intent": "roi_query",
            "intent_confidence": 0.9,
            "router_reasoning": "ROI/pricing calculator query detected",
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.0001  # Minimal cost for detection
            }
        }

    # Standard intent classification
    system_prompt = """You are an intent classifier. Classify the user's intent.

OPTIONS:
- faq: General questions, pricing info, "what do you do?"
- support: Help requests, complaints, errors
- lead_qualification: Interest in services, "I want to buy", specific inquiry
- booking: "Book a call", "schedule", "calendar"
- complex_reasoning: Deep technical questions needing research

Output JSON only: {"intent": "...", "confidence": 0.0-1.0, "reasoning": "..."}"""

    try:
        llm = get_llm(config.model, config.temperature, config.max_tokens)
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=msg_text)
        ])
        result = json.loads(response.content)
        intent = result.get("intent", "faq")
        confidence = result.get("confidence", 0.7)
        reasoning = result.get("reasoning", "")
    except Exception as e:
        logger.error(f"Supervisor error: {e}")
        intent, confidence, reasoning = "faq", 0.5, f"Fallback: {e}"
    
    next_map = {
        "lead_qualification": "lead_qualifier",
        "booking": "lead_qualifier" if not state["has_contact_info"] else "booking_agent",
        "complex_reasoning": "retrieval_agent",
        "support": "human_escalation" if confidence < 0.6 else "website_assistant",
        "faq": "website_assistant"
    }
    next_node = next_map.get(intent, "website_assistant")
    
    logger.info(f"Supervisor: {intent} -> {next_node} (conf={confidence:.2f})")
    
    new_metrics = dict(state["metrics"])
    new_metrics["total_cost_usd"] += config.estimated_cost
    new_metrics["models_used"] = state["metrics"]["models_used"] + [config.model]
    
    return {
        "current_node": "supervisor",
        "next_node": next_node,
        "detected_intent": intent,
        "intent_confidence": confidence,
        "router_reasoning": reasoning,
        "hop_count": state["hop_count"] + 1,
        "metrics": new_metrics
    }


async def intelligence_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """
    Intelligence Node: Handles competitive analysis via Trinity.
    
    CRITICAL ERROR HANDLING:
    - If Trinity is down, returns graceful degradation
    - If response is empty, provides helpful fallback
    - Never crashes the graph
    """
    start_time = datetime.utcnow()
    
    last_msg = state["messages"][-1]
    msg_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
    
    tier = state["user_tier"]
    config = model_router.route("intelligence", tier, state["metrics"]["total_cost_usd"])
    
    try:
        bridge = await get_trinity_bridge()
        result = await bridge.process_intelligence_query(
            message=msg_text,
            session_id=state["session_id"]
        )
        
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Handle failed or empty response
        if not result.get("success") or not result.get("render_card"):
            logger.warning(f"Trinity returned empty/failed response: {result.get('error', 'Unknown')}")
            
            # Graceful degradation - still provide helpful response
            competitor = extract_competitor(msg_text) or "the competitor"
            fallback_response = AIMessage(content=f"""I'd love to help you understand how we compare to {competitor}! 

While I'm gathering the latest competitive intelligence, here's what I can tell you:

**Our Key Advantages:**
• **Speed**: We generate videos in under 4 minutes vs. industry average of 15-30 minutes
• **Cost**: At $2.60 per video, we're typically 70-80% more cost-effective
• **Quality**: 97.5% success rate with broadcast-quality output
• **Automation**: Full 9-agent orchestration vs. manual workflows

Would you like me to dive deeper into any of these areas, or should I connect you with our team for a detailed competitive analysis?""")
            
            return {
                "current_node": "intelligence",
                "next_node": END,
                "messages": [fallback_response],
                "render_card": None,
                "hop_count": state["hop_count"] + 1,
                "metrics": {
                    **state["metrics"],
                    "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                    "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                    "models_used": state["metrics"]["models_used"] + [config.model]
                }
            }
        
        # Success path - we have a render_card
        render_card = result["render_card"]
        text_response = result["text_response"]
        
        response_message = AIMessage(content=text_response)
        
        # Update director state for context persistence
        director = dict(state["director"])
        director["competitor_context"] = {
            "competitor_name": result.get("competitor"),
            "confidence": result.get("confidence"),
            "timestamp": datetime.utcnow().isoformat()
        }
        director["last_card_type"] = "competitor_analysis"
        
        logger.info(f"Intelligence node success: {result.get('competitor')} (latency={latency_ms:.0f}ms)")
        
        return {
            "current_node": "intelligence",
            "next_node": END,
            "messages": [response_message],
            "render_card": render_card.model_dump() if hasattr(render_card, 'model_dump') else render_card,
            "director": director,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                "models_used": state["metrics"]["models_used"] + [config.model]
            }
        }
        
    except Exception as e:
        logger.error(f"Intelligence node error: {e}", exc_info=True)
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Error fallback - never crash
        error_response = AIMessage(content="""I'm having a moment of difficulty accessing our competitive intelligence system. 

No worries though! Our team can provide you with a detailed competitive analysis. Would you like me to:
1. **Schedule a call** with our solutions team for a personalized comparison
2. **Try again** with a different competitor question
3. **Explore our pricing** and see how we stack up

What sounds best?""")
        
        return {
            "current_node": "intelligence",
            "next_node": END,
            "messages": [error_response],
            "render_card": None,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.001,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms
            }
        }


async def persona_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """
    Persona Node: Handles buyer persona queries.

    Generates PersonaCard with pain points, goals, objections.
    """
    start_time = datetime.utcnow()

    last_msg = state["messages"][-1]
    msg_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    tier = state["user_tier"]
    config = model_router.route("intelligence", tier, state["metrics"]["total_cost_usd"])

    try:
        # Get director context if available
        director_context = state.get("director", {})

        result = await process_persona_query(
            message=msg_text,
            session_id=state["session_id"],
            existing_context=director_context
        )

        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        if not result.get("success") or not result.get("render_card"):
            logger.warning(f"Persona generation failed: {result.get('error', 'Unknown')}")

            fallback_response = AIMessage(content="""I'd be happy to help you understand our ideal customer profile!

Our primary customers are typically:
- **Marketing Directors** at mid-market B2B SaaS companies
- **Agency Owners** looking to scale video production
- **E-commerce Managers** needing high-volume ad creative

Would you like me to dive deeper into any of these segments, or would you prefer a detailed persona card?""")

            return {
                "current_node": "persona",
                "next_node": END,
                "messages": [fallback_response],
                "render_card": None,
                "hop_count": state["hop_count"] + 1,
                "metrics": {
                    **state["metrics"],
                    "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                    "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                    "models_used": state["metrics"]["models_used"] + [config.model]
                }
            }

        # Success path - we have a render_card
        render_card = result["render_card"]
        text_response = result["text_response"]

        response_message = AIMessage(content=text_response)

        # Update director state for context persistence
        director = dict(state.get("director", {}))
        director["persona_context"] = {
            "persona_name": result.get("persona_name"),
            "confidence": result.get("confidence"),
            "timestamp": datetime.utcnow().isoformat()
        }
        director["last_card_type"] = "persona"

        logger.info(f"Persona node success: {result.get('persona_name')} (latency={latency_ms:.0f}ms)")

        return {
            "current_node": "persona",
            "next_node": END,
            "messages": [response_message],
            "render_card": render_card.model_dump() if hasattr(render_card, 'model_dump') else render_card,
            "director": director,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                "models_used": state["metrics"]["models_used"] + [config.model]
            }
        }

    except Exception as e:
        logger.error(f"Persona node error: {e}", exc_info=True)
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        error_response = AIMessage(content="""I'm having a moment of difficulty generating the persona profile.

No worries though! I can still help you understand our ideal customers. Would you like me to:
1. **Describe our typical buyer** in conversational terms
2. **Show agency owner profile** - for creative agencies
3. **Show e-commerce manager profile** - for D2C brands

What sounds most relevant to you?""")

        return {
            "current_node": "persona",
            "next_node": END,
            "messages": [error_response],
            "render_card": None,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.001,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms
            }
        }


async def script_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """
    Script Node: Handles script/commercial writing queries.

    Generates ScriptPreviewCard with sections and full script.
    """
    start_time = datetime.utcnow()

    last_msg = state["messages"][-1]
    msg_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    tier = state["user_tier"]
    config = model_router.route("intelligence", tier, state["metrics"]["total_cost_usd"])

    try:
        # Get director context if available
        director_context = state.get("director", {})

        result = await process_script_query(
            message=msg_text,
            session_id=state["session_id"],
            existing_context=director_context
        )

        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        if not result.get("success") or not result.get("render_card"):
            logger.warning(f"Script generation failed: {result.get('error', 'Unknown')}")

            fallback_response = AIMessage(content="""I'd be happy to help you create a video commercial script!

Here are some options:
- **15 second** - Perfect for TikTok, Instagram Reels
- **30 second** - Standard YouTube pre-roll, social ads
- **60 second** - LinkedIn, longer-form storytelling

What format would you like, and what product or service should the commercial be about?""")

            return {
                "current_node": "script",
                "next_node": END,
                "messages": [fallback_response],
                "render_card": None,
                "hop_count": state["hop_count"] + 1,
                "metrics": {
                    **state["metrics"],
                    "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                    "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                    "models_used": state["metrics"]["models_used"] + [config.model]
                }
            }

        # Success path - we have a render_card
        render_card = result["render_card"]
        text_response = result["text_response"]

        response_message = AIMessage(content=text_response)

        # Update director state for context persistence
        director = dict(state.get("director", {}))
        director["script_context"] = {
            "script_title": result.get("script_title"),
            "format": result.get("format"),
            "confidence": result.get("confidence"),
            "timestamp": datetime.utcnow().isoformat()
        }
        director["last_card_type"] = "script"

        logger.info(f"Script node success: {result.get('script_title')} (latency={latency_ms:.0f}ms)")

        return {
            "current_node": "script",
            "next_node": END,
            "messages": [response_message],
            "render_card": render_card.model_dump() if hasattr(render_card, 'model_dump') else render_card,
            "director": director,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                "models_used": state["metrics"]["models_used"] + [config.model]
            }
        }

    except Exception as e:
        logger.error(f"Script node error: {e}", exc_info=True)
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        error_response = AIMessage(content="""I'm having a moment of difficulty generating the script.

No worries though! I can still help you create a commercial. Would you like me to:
1. **Generate a 30 second commercial** - Standard format
2. **Generate a 15 second TikTok ad** - Short and punchy
3. **Generate a 60 second brand story** - Longer narrative

What sounds best for your needs?""")

        return {
            "current_node": "script",
            "next_node": END,
            "messages": [error_response],
            "render_card": None,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.001,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms
            }
        }


async def roi_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """
    ROI Node: Handles ROI/pricing calculator queries.

    Generates ROICalculatorCard with sliders and projections.
    """
    start_time = datetime.utcnow()

    last_msg = state["messages"][-1]
    msg_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    tier = state["user_tier"]
    config = model_router.route("intelligence", tier, state["metrics"]["total_cost_usd"])

    try:
        # Get director context if available
        director_context = state.get("director", {})

        result = await process_roi_query(
            message=msg_text,
            session_id=state["session_id"],
            existing_context=director_context
        )

        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        if not result.get("success") or not result.get("render_card"):
            logger.warning(f"ROI generation failed: {result.get('error', 'Unknown')}")

            fallback_response = AIMessage(content="""I'd be happy to help you calculate your ROI with RAGNAROK!

Here's a quick comparison:
- **Traditional video production**: $5,000-$15,000 per video, 2-3 weeks
- **RAGNAROK**: $2.60 per video, ~4 minutes

For a company producing 10 videos/month:
- Current cost: ~$50,000-$150,000/month
- With RAGNAROK: ~$26/month
- **Potential savings: $49,974-$149,974/month**

Would you like me to create an interactive ROI calculator with your specific numbers?""")

            return {
                "current_node": "roi",
                "next_node": END,
                "messages": [fallback_response],
                "render_card": None,
                "hop_count": state["hop_count"] + 1,
                "metrics": {
                    **state["metrics"],
                    "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                    "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                    "models_used": state["metrics"]["models_used"] + [config.model]
                }
            }

        # Success path - we have a render_card
        render_card = result["render_card"]
        text_response = result["text_response"]

        response_message = AIMessage(content=text_response)

        # Update director state for context persistence
        director = dict(state.get("director", {}))
        director["roi_context"] = {
            "annual_savings": result.get("annual_savings"),
            "cost_reduction_percent": result.get("cost_reduction_percent"),
            "confidence": result.get("confidence"),
            "timestamp": datetime.utcnow().isoformat()
        }
        director["last_card_type"] = "roi"

        logger.info(f"ROI node success: ${result.get('annual_savings', 0):,.0f} annual savings (latency={latency_ms:.0f}ms)")

        return {
            "current_node": "roi",
            "next_node": END,
            "messages": [response_message],
            "render_card": render_card.model_dump() if hasattr(render_card, 'model_dump') else render_card,
            "director": director,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                "models_used": state["metrics"]["models_used"] + [config.model]
            }
        }

    except Exception as e:
        logger.error(f"ROI node error: {e}", exc_info=True)
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        error_response = AIMessage(content="""I'm having a moment of difficulty generating the ROI calculator.

No worries though! Here's the quick math:
- RAGNAROK costs **$2.60 per video**
- Traditional production: **$5,000-$15,000 per video**
- That's a **99.9% cost reduction**

Would you like me to:
1. **Try the calculator again** with specific numbers
2. **Connect you with our team** for a detailed analysis
3. **Show you case studies** from similar companies

What would be most helpful?""")

        return {
            "current_node": "roi",
            "next_node": END,
            "messages": [error_response],
            "render_card": None,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.001,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms
            }
        }


async def intake_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """
    Intake Node: Handles Nexus commercial intake flow.

    Guides prospects through the 30-question intake process to collect
    information for RAGNAROK commercial generation.

    Flow:
    1. If not active: Activate intake and show opening script
    2. If active: Process answer, advance to next question
    3. If complete: Generate summary, save client config, end
    """
    start_time = datetime.utcnow()

    last_msg = state["messages"][-1]
    msg_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    tier = state["user_tier"]
    config = model_router.route("website_assistant", tier, state["metrics"]["total_cost_usd"])

    # Get or create intake state
    intake = dict(state.get("intake", {}))

    try:
        # Case 1: Starting a new intake session
        if not intake.get("active"):
            logger.info("Starting new intake session (Nexus mode)")
            intake = activate_intake_mode({"intake": intake})

            # Generate opening + first question
            opening = get_opening_script()
            first_q = get_current_question(intake)
            first_q_text = format_question_prompt(first_q, is_first_in_phase=True, phase=intake["phase"]) if first_q else ""

            response_text = f"{opening}\n\n{first_q_text}"
            response_message = AIMessage(content=response_text)

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return {
                "current_node": "intake",
                "next_node": END,
                "messages": [response_message],
                "intake": intake,
                "render_card": None,
                "hop_count": state["hop_count"] + 1,
                "detected_intent": "intake_started",
                "metrics": {
                    **state["metrics"],
                    "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                    "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                    "models_used": state["metrics"]["models_used"] + [config.model]
                }
            }

        # Case 2: Continuing an active intake session
        logger.info(f"Continuing intake: phase={intake.get('phase')}, q_idx={intake.get('question_index')}")

        # Process the answer
        intake, next_response = process_answer(intake, msg_text)

        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Case 3: Intake is now complete
        if intake.get("completed"):
            logger.info("Intake completed! Generating summary and saving client config")

            # Generate client config
            client_config = intake_to_client_config(intake)
            intake["client_id"] = client_config["client_id"]

            # Save to disk
            try:
                config_path = save_client_config(client_config)
                logger.info(f"Saved client config to: {config_path}")
            except Exception as save_err:
                logger.error(f"Failed to save client config: {save_err}")

            response_message = AIMessage(content=next_response)

            return {
                "current_node": "intake",
                "next_node": END,
                "messages": [response_message],
                "intake": intake,
                "render_card": None,
                "hop_count": state["hop_count"] + 1,
                "detected_intent": "intake_completed",
                "metrics": {
                    **state["metrics"],
                    "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                    "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                    "models_used": state["metrics"]["models_used"] + [config.model]
                }
            }

        # Case 4: More questions to ask
        response_message = AIMessage(content=next_response)

        return {
            "current_node": "intake",
            "next_node": END,
            "messages": [response_message],
            "intake": intake,
            "render_card": None,
            "hop_count": state["hop_count"] + 1,
            "detected_intent": "intake_continuation",
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + config.estimated_cost,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms,
                "models_used": state["metrics"]["models_used"] + [config.model]
            }
        }

    except Exception as e:
        logger.error(f"Intake node error: {e}", exc_info=True)
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        error_response = AIMessage(content="""I apologize for the hiccup! Let me try that again.

I'm Nexus, your AI creative director. I was in the middle of learning about your business to create a custom commercial concept.

Could you please repeat your last answer? Or if you'd like to start fresh, just say "start over" and we'll begin again.""")

        return {
            "current_node": "intake",
            "next_node": END,
            "messages": [error_response],
            "intake": intake,  # Preserve state
            "render_card": None,
            "hop_count": state["hop_count"] + 1,
            "metrics": {
                **state["metrics"],
                "total_cost_usd": state["metrics"]["total_cost_usd"] + 0.001,
                "total_latency_ms": state["metrics"]["total_latency_ms"] + latency_ms
            }
        }


async def website_assistant_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """Website Assistant: General conversation handler."""
    
    tier = state["user_tier"]
    config = model_router.route("website_assistant", tier, state["metrics"]["total_cost_usd"])
    
    last_msg = state["messages"][-1]
    msg_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
    
    system_prompt = """You are a helpful AI assistant for Barrios A2I, a company that builds AI-powered video generation systems.

Key products:
- RAGNAROK: 9-agent video generation platform (generates videos in ~4 minutes for $2.60)
- Trinity: Market intelligence system
- Custom AI agents and automation solutions

Be friendly, helpful, and guide users toward solutions. Keep responses concise."""

    try:
        llm = get_llm(config.model, config.temperature, config.max_tokens)
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            *state["messages"]
        ])
        
        new_metrics = dict(state["metrics"])
        new_metrics["total_cost_usd"] += config.estimated_cost
        new_metrics["models_used"] = state["metrics"]["models_used"] + [config.model]
        
        return {
            "current_node": "website_assistant",
            "next_node": END,
            "messages": [response],
            "hop_count": state["hop_count"] + 1,
            "metrics": new_metrics
        }
        
    except Exception as e:
        logger.error(f"Website assistant error: {e}")
        return {
            "current_node": "website_assistant",
            "next_node": END,
            "messages": [AIMessage(content="I apologize, but I'm having trouble processing your request. Please try again.")],
            "hop_count": state["hop_count"] + 1
        }


async def human_escalation_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """Terminal node for human escalation."""
    
    escalation_message = AIMessage(content="""I understand you'd like to speak with someone from our team. 

I'm connecting you with a human representative who can better assist you. Someone will reach out within:
• **Elite customers**: 1 hour (phone callback)
• **Pro customers**: 4 hours (email + SMS)
• **All customers**: 24 hours (email)

In the meantime, feel free to ask me any other questions!""")
    
    return {
        "current_node": "human_escalation",
        "next_node": END,
        "messages": [escalation_message],
        "human_handoff_requested": True,
        "hop_count": state["hop_count"] + 1
    }


# Placeholder nodes for complete graph
async def retrieval_agent_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """RAG retrieval for complex queries."""
    return {
        "current_node": "retrieval_agent",
        "next_node": "website_assistant",
        "rag_contexts": [],
        "hop_count": state["hop_count"] + 1
    }


async def lead_qualifier_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """Lead qualification with 2-1-Close pattern."""
    return {
        "current_node": "lead_qualifier",
        "next_node": END,
        "messages": [AIMessage(content="I'd love to learn more about your needs! What's the main challenge you're looking to solve?")],
        "hop_count": state["hop_count"] + 1
    }


async def booking_agent_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """Booking agent for scheduling."""
    return {
        "current_node": "booking_agent",
        "next_node": END,
        "messages": [AIMessage(content="I'd be happy to help you book a call. What times work best for you this week?")],
        "hop_count": state["hop_count"] + 1
    }


async def validator_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """Validation gate."""
    return {
        "current_node": "validator",
        "next_node": END,
        "validation": {"required": False, "passed": True, "action": "send_as_is", "issues": []},
        "hop_count": state["hop_count"] + 1
    }


async def tool_executor_node(state: WebsiteAssistantState) -> Dict[str, Any]:
    """Tool execution."""
    return {
        "current_node": "tool_executor",
        "next_node": END,
        "hop_count": state["hop_count"] + 1
    }


# ============================================================================
# SECTION 6: ROUTING FUNCTIONS
# ============================================================================

def route_after_entry(state: WebsiteAssistantState) -> str:
    return state["next_node"]


def route_after_supervisor(state: WebsiteAssistantState) -> str:
    return state["next_node"]


# ============================================================================
# SECTION 7: GRAPH CONSTRUCTION
# ============================================================================

def build_website_assistant_graph() -> StateGraph:
    """Build the Website Assistant v2.0 LangGraph."""
    
    workflow = StateGraph(WebsiteAssistantState)
    
    # Add nodes
    workflow.add_node("entry", entry_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("intelligence", intelligence_node)  # Competitor analysis
    workflow.add_node("persona", persona_node)  # Persona card generation
    workflow.add_node("script", script_node)  # Script/commercial generation
    workflow.add_node("roi", roi_node)  # ROI calculator generation
    workflow.add_node("intake", intake_node)  # Nexus commercial intake
    workflow.add_node("website_assistant", website_assistant_node)
    workflow.add_node("retrieval_agent", retrieval_agent_node)
    workflow.add_node("lead_qualifier", lead_qualifier_node)
    workflow.add_node("booking_agent", booking_agent_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("tool_executor", tool_executor_node)
    workflow.add_node("human_escalation", human_escalation_node)
    
    # Set entry
    workflow.set_entry_point("entry")
    
    # Edges
    workflow.add_conditional_edges(
        "entry",
        route_after_entry,
        {
            "supervisor": "supervisor",
            "human_escalation": "human_escalation"
        }
    )
    
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "intake": "intake",  # Nexus commercial intake (highest priority)
            "intelligence": "intelligence",  # Competitor analysis
            "persona": "persona",  # Persona cards
            "script": "script",  # Script/commercial generation
            "roi": "roi",  # ROI calculator
            "website_assistant": "website_assistant",
            "retrieval_agent": "retrieval_agent",
            "lead_qualifier": "lead_qualifier",
            "booking_agent": "booking_agent",
            "human_escalation": "human_escalation"
        }
    )
    
    # Intelligence -> END (returns CompetitorCard directly)
    workflow.add_edge("intelligence", END)

    # Persona -> END (returns PersonaCard directly)
    workflow.add_edge("persona", END)

    # Script -> END (returns ScriptPreviewCard directly)
    workflow.add_edge("script", END)

    # ROI -> END (returns ROICalculatorCard directly)
    workflow.add_edge("roi", END)

    # Intake -> END (returns intake response directly)
    workflow.add_edge("intake", END)

    # Other edges
    workflow.add_edge("retrieval_agent", "website_assistant")
    workflow.add_edge("website_assistant", END)
    workflow.add_edge("lead_qualifier", END)
    workflow.add_edge("booking_agent", END)
    workflow.add_edge("validator", END)
    workflow.add_edge("tool_executor", END)
    workflow.add_edge("human_escalation", END)
    
    return workflow.compile()


# ============================================================================
# SECTION 8: PUBLIC API
# ============================================================================

_graph = None


def get_graph():
    """Singleton graph accessor."""
    global _graph
    if _graph is None:
        _graph = build_website_assistant_graph()
    return _graph


async def process_message(
    message: str,
    tenant_id: str,
    site_id: str,
    session_id: str,
    user_tier: str = "starter",
    existing_state: Optional[WebsiteAssistantState] = None
) -> Dict[str, Any]:
    """Main entry point for processing user messages."""
    
    graph = get_graph()
    
    if existing_state:
        state = dict(existing_state)
        state["messages"] = list(existing_state["messages"]) + [HumanMessage(content=message)]
        state["turn_number"] = existing_state["turn_number"] + 1
        state["hop_count"] = 0
        state["retry_count"] = 0
        state["render_card"] = None  # Clear previous card
    else:
        state = create_initial_state(
            user_message=HumanMessage(content=message),
            tenant_id=tenant_id,
            site_id=site_id,
            session_id=session_id,
            user_tier=user_tier
        )
    
    final_state = await graph.ainvoke(state)
    return final_state


def format_response(state: Dict[str, Any]) -> AssistantMessage:
    """Format state into AssistantMessage for frontend."""
    
    last_ai_message = None
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage):
            last_ai_message = msg.content
            break
    
    return AssistantMessage(
        content=last_ai_message or "I'm here to help!",
        render_card=state.get("render_card"),
        intent=state.get("detected_intent", "unknown"),
        confidence=state.get("intent_confidence", 0.0),
        model_used=state["metrics"]["models_used"][-1] if state["metrics"]["models_used"] else "unknown",
        latency_ms=state["metrics"]["total_latency_ms"],
        cost_usd=state["metrics"]["total_cost_usd"],
        trace_id=state["trace_context"]["trace_id"],
        session_id=state["session_id"],
        turn_number=state["turn_number"]
    )


# ============================================================================
# SECTION 9: EXPORTS
# ============================================================================

__all__ = [
    "WebsiteAssistantState",
    "get_graph",
    "process_message",
    "format_response",
    "create_initial_state",
    "AssistantMessage",
]
