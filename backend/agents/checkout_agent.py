"""
Checkout Agent - WEBSITE ASSISTANT v3.0
========================================
Triggers Brief Assembler → Payment Gateway flow when all 4 cards are complete.

Features:
- Validates all cards present
- Emits conversation.cards_complete event
- Generates checkout summary card
- Handles Stripe session creation callback
- WebSocket notification to frontend

pip install pydantic structlog stripe
"""

import logging
import json
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger().bind(agent="checkout_agent")


# =============================================================================
# PRICING TIERS
# =============================================================================

class VideoTier(str, Enum):
    """Video production tiers with pricing"""
    STARTER = "starter"      # 30s, basic
    PROFESSIONAL = "professional"  # 60s, full production
    ENTERPRISE = "enterprise"    # 90s+, premium


TIER_PRICING = {
    VideoTier.STARTER: {
        "price_usd": 2500,
        "duration_seconds": 30,
        "features": [
            "30-second commercial",
            "Professional voiceover",
            "Stock footage",
            "2 revision rounds",
            "HD delivery",
        ],
        "stripe_price_id": "price_starter_2500",
    },
    VideoTier.PROFESSIONAL: {
        "price_usd": 5000,
        "duration_seconds": 60,
        "features": [
            "60-second commercial",
            "Premium voiceover",
            "Custom footage + stock",
            "5 revision rounds",
            "4K delivery",
            "Social media cuts",
        ],
        "stripe_price_id": "price_professional_5000",
    },
    VideoTier.ENTERPRISE: {
        "price_usd": 15000,
        "duration_seconds": 90,
        "features": [
            "90-second commercial",
            "Celebrity voiceover options",
            "Full custom production",
            "Unlimited revisions",
            "4K + RAW delivery",
            "Full social media package",
            "Dedicated producer",
        ],
        "stripe_price_id": "price_enterprise_15000",
    },
}


# =============================================================================
# CHECKOUT CARD SCHEMA
# =============================================================================

class CheckoutSummaryItem(BaseModel):
    """Single item in checkout summary"""
    label: str
    value: str
    icon: Optional[str] = None


class CheckoutCard(BaseModel):
    """Generative UI card for checkout flow"""
    type: Literal["checkout"] = "checkout"
    
    # Header
    title: str = "Ready to Create Your Video!"
    subtitle: Optional[str] = None
    
    # Summary items
    summary_items: List[CheckoutSummaryItem] = Field(default_factory=list)
    
    # Pricing
    tier: VideoTier
    price_usd: int
    original_price_usd: Optional[int] = None  # For showing discounts
    discount_percent: Optional[int] = None
    
    # Features included
    features: List[str] = Field(default_factory=list)
    
    # Checkout state
    checkout_url: Optional[str] = None
    checkout_session_id: Optional[str] = None
    checkout_status: Literal["pending", "ready", "processing", "complete", "failed"] = "pending"
    
    # Urgency/scarcity (optional)
    urgency_message: Optional[str] = None
    
    # Metadata
    brief_id: Optional[str] = None
    session_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# EVENT PAYLOADS
# =============================================================================

class CardsCompletePayload(BaseModel):
    """Payload for conversation.cards_complete event"""
    session_id: str
    correlation_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    business_name: Optional[str] = None
    
    # The 4 cards
    persona_card: Dict[str, Any]
    competitor_card: Dict[str, Any]
    script_card: Dict[str, Any]
    roi_card: Dict[str, Any]
    
    # Pricing
    selected_tier: VideoTier
    price_usd: int
    
    # Metadata
    conversation_turns: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationCardsCompleteEvent(BaseModel):
    """Event emitted when all 4 cards are complete"""
    event_type: Literal["conversation.cards_complete"] = "conversation.cards_complete"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: CardsCompletePayload


# =============================================================================
# CHECKOUT AGENT
# =============================================================================

class CheckoutAgent:
    """
    Handles the transition from conversation to payment.
    
    Responsibilities:
    1. Validate all 4 cards are present and valid
    2. Determine appropriate pricing tier
    3. Generate checkout summary card
    4. Emit cards_complete event to Brief Assembler
    5. Handle checkout session creation callback
    """
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._logger = logger.bind(component="checkout_agent")
    
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process checkout from completed cards.
        
        Args:
            state: LangGraph state with all 4 cards
            
        Returns:
            Dict with checkout card and event emission status
        """
        correlation_id = str(uuid.uuid4())
        self._logger.info("processing_checkout", 
                         session_id=state.get("session_id"),
                         correlation_id=correlation_id)
        
        # Validate all cards present
        validation = self._validate_cards(state)
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"],
                "checkout_card": None,
            }
        
        # Determine pricing tier from script duration
        tier = self._determine_tier(state)
        pricing = TIER_PRICING[tier]
        
        # Build checkout summary
        checkout_card = self._build_checkout_card(state, tier, pricing)
        
        # Emit event to Brief Assembler
        if self.event_bus:
            event = self._build_cards_complete_event(
                state, tier, pricing, correlation_id
            )
            await self.event_bus.publish(event)
            self._logger.info("event_emitted", 
                            event_type="conversation.cards_complete",
                            correlation_id=correlation_id)
        
        return {
            "success": True,
            "checkout_card": checkout_card,
            "correlation_id": correlation_id,
            "tier": tier,
            "price_usd": pricing["price_usd"],
        }
    
    def _validate_cards(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all 4 cards are present and valid"""
        
        required_cards = ["persona_card", "competitor_card", "script_card", "roi_card"]
        missing = []
        
        for card in required_cards:
            if not state.get(card):
                missing.append(card.replace("_card", ""))
        
        if missing:
            return {
                "valid": False,
                "error": f"Missing cards: {', '.join(missing)}",
            }
        
        # Validate persona card has required fields
        persona = state.get("persona_card", {})
        if not persona.get("persona_name"):
            return {"valid": False, "error": "Persona card missing persona_name"}
        
        # Validate script card has content
        script = state.get("script_card", {})
        if not script.get("full_script") and not script.get("sections"):
            return {"valid": False, "error": "Script card missing content"}
        
        return {"valid": True, "error": None}
    
    def _determine_tier(self, state: Dict[str, Any]) -> VideoTier:
        """Determine pricing tier from script/ROI cards"""
        
        script = state.get("script_card", {})
        roi = state.get("roi_card", {})
        
        # Check duration from script
        duration = script.get("estimated_duration_seconds", 60)
        
        # Check budget from ROI
        budget = roi.get("investment_amount", 5000)
        
        # Tier logic
        if duration <= 30 and budget < 3500:
            return VideoTier.STARTER
        elif duration <= 60 or budget < 10000:
            return VideoTier.PROFESSIONAL
        else:
            return VideoTier.ENTERPRISE
    
    def _build_checkout_card(
        self,
        state: Dict[str, Any],
        tier: VideoTier,
        pricing: Dict[str, Any]
    ) -> CheckoutCard:
        """Build the checkout summary card"""
        
        persona = state.get("persona_card", {})
        competitor = state.get("competitor_card", {})
        script = state.get("script_card", {})
        roi = state.get("roi_card", {})
        
        # Build summary items
        summary_items = [
            CheckoutSummaryItem(
                label="Target Persona",
                value=persona.get("persona_name", "Your ideal customer"),
                icon="👤"
            ),
            CheckoutSummaryItem(
                label="Key Differentiator",
                value=competitor.get("kill_shot", {}).get("headline", "Your unique advantage"),
                icon="🎯"
            ),
            CheckoutSummaryItem(
                label="Video Format",
                value=f"{script.get('estimated_duration_seconds', 60)}s {script.get('tone', 'professional')}",
                icon="🎬"
            ),
            CheckoutSummaryItem(
                label="Projected ROI",
                value=f"{roi.get('roi_percentage', 1000)}%",
                icon="📈"
            ),
        ]
        
        return CheckoutCard(
            title="Your Commercial is Ready for Production!",
            subtitle=f"Based on your {tier.value} package selection",
            summary_items=summary_items,
            tier=tier,
            price_usd=pricing["price_usd"],
            features=pricing["features"],
            checkout_status="pending",
            session_id=state.get("session_id", ""),
            urgency_message="🔥 Limited slots available this week",
        )
    
    def _build_cards_complete_event(
        self,
        state: Dict[str, Any],
        tier: VideoTier,
        pricing: Dict[str, Any],
        correlation_id: str
    ) -> ConversationCardsCompleteEvent:
        """Build the cards_complete event"""
        
        lead = state.get("lead", {})
        collected = lead.get("collected_data", {})
        
        payload = CardsCompletePayload(
            session_id=state.get("session_id", ""),
            correlation_id=correlation_id,
            user_email=collected.get("email"),
            user_name=collected.get("name"),
            business_name=state.get("director", {}).get("persona_context", {}).get("company_type"),
            persona_card=state.get("persona_card", {}),
            competitor_card=state.get("competitor_card", {}),
            script_card=state.get("script_card", {}),
            roi_card=state.get("roi_card", {}),
            selected_tier=tier,
            price_usd=pricing["price_usd"],
            conversation_turns=state.get("turn_number", 0),
        )
        
        return ConversationCardsCompleteEvent(payload=payload)
    
    async def handle_checkout_session_created(
        self,
        session_id: str,
        checkout_url: str,
        checkout_session_id: str
    ) -> Dict[str, Any]:
        """
        Handle callback when Stripe checkout session is created.
        Updates the checkout card with the URL.
        """
        self._logger.info("checkout_session_created",
                         session_id=session_id,
                         checkout_session_id=checkout_session_id)
        
        return {
            "session_id": session_id,
            "checkout_url": checkout_url,
            "checkout_session_id": checkout_session_id,
            "checkout_status": "ready",
        }


# =============================================================================
# LANGGRAPH NODE FUNCTION
# =============================================================================

async def checkout_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node for checkout.
    
    Called when all 4 cards are complete.
    Emits event and returns checkout card.
    """
    from langchain_core.messages import AIMessage
    
    # Get event bus from context if available
    event_bus = state.get("_event_bus")
    
    # Initialize agent
    agent = CheckoutAgent(event_bus=event_bus)
    
    # Process checkout
    result = await agent.process(state)
    
    if not result["success"]:
        # Missing cards - shouldn't happen but handle gracefully
        return {
            "current_node": "checkout",
            "next_node": "creative_director",  # Go back to gather more info
            "messages": [AIMessage(content=f"Almost there! {result['error']}")],
            "hop_count": state.get("hop_count", 0) + 1,
        }
    
    # Build celebration message
    card = result["checkout_card"]
    
    message = f"""
🎉 **Your Commercial Brief is Complete!**

Here's what we've built together:

"""
    for item in card.summary_items:
        message += f"• **{item.label}:** {item.value}\n"
    
    message += f"""
**Package:** {card.tier.value.title()}
**Investment:** ${card.price_usd:,}

**What's Included:**
"""
    for feature in card.features[:5]:
        message += f"✓ {feature}\n"
    
    message += """
Click the button below to proceed to secure checkout. Once payment is confirmed, 
we'll start producing your video immediately!

_Expected delivery: 24-48 hours_
"""
    
    return {
        "current_node": "checkout",
        "next_node": "END",
        "messages": [AIMessage(content=message)],
        "render_card": card.model_dump(),
        "cards_ready": True,
        "checkout_initiated": True,
        "correlation_id": result["correlation_id"],
        "hop_count": state.get("hop_count", 0) + 1,
    }


# =============================================================================
# WEBHOOK HANDLERS
# =============================================================================

class CheckoutWebhookHandler:
    """Handles webhooks from Payment Gateway"""
    
    def __init__(self, session_store, websocket_manager=None):
        self.session_store = session_store
        self.ws_manager = websocket_manager
        self._logger = logger.bind(component="checkout_webhook_handler")
    
    async def handle_checkout_ready(
        self,
        session_id: str,
        checkout_url: str,
        checkout_session_id: str
    ):
        """
        Called when Stripe checkout session is created.
        Sends checkout URL to frontend via WebSocket.
        """
        self._logger.info("checkout_ready", session_id=session_id)
        
        # Update session store
        if self.session_store:
            state = self.session_store.get(session_id)
            if state:
                state["checkout_url"] = checkout_url
                state["checkout_session_id"] = checkout_session_id
                self.session_store[session_id] = state
        
        # Notify frontend via WebSocket
        if self.ws_manager:
            await self.ws_manager.send_to_session(session_id, {
                "type": "checkout_ready",
                "checkout_url": checkout_url,
                "checkout_session_id": checkout_session_id,
            })
    
    async def handle_payment_confirmed(
        self,
        session_id: str,
        order_id: str,
        amount_paid: int
    ):
        """
        Called when payment is confirmed.
        Triggers production tracking UI.
        """
        self._logger.info("payment_confirmed", 
                         session_id=session_id, 
                         order_id=order_id)
        
        # Update session
        if self.session_store:
            state = self.session_store.get(session_id)
            if state:
                state["order_id"] = order_id
                state["payment_confirmed"] = True
                state["production_status"] = "queued"
                self.session_store[session_id] = state
        
        # Notify frontend
        if self.ws_manager:
            await self.ws_manager.send_to_session(session_id, {
                "type": "payment_confirmed",
                "order_id": order_id,
                "amount_paid": amount_paid,
                "production_status": "queued",
                "message": "Payment received! Your video production is starting...",
            })
    
    async def handle_production_progress(
        self,
        session_id: str,
        phase_name: str,
        progress_percent: int,
        message: str
    ):
        """
        Called during video production.
        Streams progress to frontend.
        """
        self._logger.info("production_progress",
                         session_id=session_id,
                         phase=phase_name,
                         progress=progress_percent)
        
        if self.ws_manager:
            await self.ws_manager.send_to_session(session_id, {
                "type": "production_progress",
                "phase_name": phase_name,
                "progress_percent": progress_percent,
                "message": message,
            })
    
    async def handle_delivery_ready(
        self,
        session_id: str,
        video_url: str,
        portal_url: str,
        download_token: str
    ):
        """
        Called when video is ready for delivery.
        Sends download link to frontend.
        """
        self._logger.info("delivery_ready", session_id=session_id)
        
        if self.session_store:
            state = self.session_store.get(session_id)
            if state:
                state["video_url"] = video_url
                state["portal_url"] = portal_url
                state["production_status"] = "complete"
                self.session_store[session_id] = state
        
        if self.ws_manager:
            await self.ws_manager.send_to_session(session_id, {
                "type": "delivery_ready",
                "video_url": video_url,
                "portal_url": portal_url,
                "message": "🎉 Your video is ready! Click below to download.",
            })


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CheckoutAgent",
    "CheckoutCard",
    "VideoTier",
    "TIER_PRICING",
    "CardsCompletePayload",
    "ConversationCardsCompleteEvent",
    "checkout_node",
    "CheckoutWebhookHandler",
]


# =============================================================================
# DEMO
# =============================================================================

async def demo():
    """Demo the checkout agent"""
    
    print("=" * 70)
    print("CHECKOUT AGENT DEMO")
    print("=" * 70)
    
    # Simulate complete state
    state = {
        "session_id": "demo_session_123",
        "turn_number": 8,
        "lead": {
            "collected_data": {
                "email": "gary@barriosa2i.com",
                "name": "Gary Barrios",
            }
        },
        "director": {
            "persona_context": {
                "company_type": "AI Automation Consultancy"
            }
        },
        "persona_card": {
            "type": "persona",
            "persona_name": "Marketing Manager Maria",
            "title": "Director of Marketing",
            "company_type": "Mid-market SaaS",
            "pain_points": [
                {"title": "Lead Generation", "severity": "high"},
                {"title": "Video Content", "severity": "medium"},
            ],
            "goals": ["Increase MQLs by 50%", "Reduce CAC"],
        },
        "competitor_card": {
            "type": "competitor_analysis",
            "competitor_name": "HubSpot",
            "kill_shot": {
                "headline": "60% cheaper with better support",
                "detail": "Same features, fraction of the price",
            },
            "stats": [
                {"metric": "Price", "our_value": "$99/mo", "their_value": "$250/mo", "advantage": "us"},
            ],
        },
        "script_card": {
            "type": "script_preview",
            "title": "Barrios A2I Commercial",
            "format": "60s",
            "tone": "professional",
            "full_script": "In a world where AI automation...",
            "estimated_duration_seconds": 60,
            "sections": [
                {"section_type": "hook", "content": "What if AI could..."},
                {"section_type": "problem", "content": "Manual processes cost..."},
                {"section_type": "solution", "content": "Barrios A2I automates..."},
                {"section_type": "cta", "content": "Book your demo today!"},
            ],
        },
        "roi_card": {
            "type": "roi_calculator",
            "investment_amount": 5000,
            "projected_annual_savings": 50000,
            "roi_percentage": 900,
            "payback_period_months": 1.2,
        },
    }
    
    agent = CheckoutAgent()
    result = await agent.process(state)
    
    print(f"\nSuccess: {result['success']}")
    print(f"Tier: {result['tier'].value}")
    print(f"Price: ${result['price_usd']:,}")
    print(f"Correlation ID: {result['correlation_id']}")
    
    card = result['checkout_card']
    print(f"\n--- CHECKOUT CARD ---")
    print(f"Title: {card.title}")
    print(f"Status: {card.checkout_status}")
    print(f"\nSummary:")
    for item in card.summary_items:
        print(f"  {item.icon} {item.label}: {item.value}")
    print(f"\nFeatures:")
    for feature in card.features:
        print(f"  ✓ {feature}")
    
    # Demo the LangGraph node
    print("\n\n--- LANGGRAPH NODE OUTPUT ---")
    node_result = await checkout_node(state)
    print(f"Next node: {node_result['next_node']}")
    print(f"Checkout initiated: {node_result.get('checkout_initiated')}")
    print(f"Message preview: {node_result['messages'][0].content[:300]}...")


if __name__ == "__main__":
    asyncio.run(demo())
