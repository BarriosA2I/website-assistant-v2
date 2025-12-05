"""
Agent Integrations - Event Bus Wiring
=====================================
Connects all 3 agents to the shared event bus.

Usage:
    # Start all agents with event bus
    from agent_integrations import start_pipeline
    await start_pipeline()
"""

import asyncio
from typing import Optional
import structlog

# Import event bus
from event_bus_adapter import (
    IEventBus,
    create_event_bus,
    EventType,
    BaseEvent,
    AgentWiring,
    # Events from Website Assistant
    ConversationCardsCompleteEvent,
    CardsCompletePayload,
    # Events from Brief Assembler
    BriefAssembledEvent,
    BriefAssembledPayload,
    BriefValidationFailedEvent,
    BriefValidationFailedPayload,
    # Events from Payment Gateway
    PaymentConfirmedEvent,
    PaymentConfirmedPayload,
    PaymentFailedEvent,
    PaymentFailedPayload,
    OrderQueuedEvent,
    OrderQueuedPayload,
    PaymentSessionCreatedEvent,
    PaymentSessionCreatedPayload,
    # Events from RAGNAROK
    ProductionStartedEvent,
    ProductionStartedPayload,
    ProductionCompletedEvent,
    ProductionCompletedPayload,
    ProductionFailedEvent,
    ProductionFailedPayload,
)

# Import agents (adjust paths as needed)
# from agent1_brief_assembler import BriefAssembler, CreativeBrief, BriefValidationError
# from agent2_payment_gateway import PaymentGateway, CreativeBrief as PGCreativeBrief
# from agent3_delivery_agent_legendary import DeliveryAgent, ProductionOrder

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(structlog.logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


# =============================================================================
# BRIEF ASSEMBLER INTEGRATION
# =============================================================================

class BriefAssemblerIntegration:
    """
    Wires Brief Assembler to Event Bus
    
    Subscribes to:
        - conversation.cards_complete
    
    Publishes:
        - brief.assembled (success)
        - brief.validation_failed (failure)
    """
    
    def __init__(self, event_bus: IEventBus, assembler=None):
        self.bus = event_bus
        # self.assembler = assembler or BriefAssembler()
        self.assembler = assembler  # Mock for now
        self._subscription_id: Optional[str] = None
        self._logger = structlog.get_logger().bind(agent="brief_assembler_integration")
    
    async def start(self):
        """Start listening for events"""
        config = AgentWiring.brief_assembler()
        self._subscription_id = await self.bus.subscribe(
            config.subscribes_to,
            self._handle_event,
            config.queue_name,
        )
        self._logger.info("started", subscription_id=self._subscription_id)
    
    async def stop(self):
        """Stop listening"""
        if self._subscription_id:
            await self.bus.unsubscribe(self._subscription_id)
            self._logger.info("stopped")
    
    async def _handle_event(self, event: BaseEvent):
        """Handle incoming events"""
        self._logger.info("event_received",
                        event_type=event.event_type.value,
                        correlation_id=event.correlation_id)
        
        if event.event_type == EventType.CONVERSATION_CARDS_COMPLETE:
            await self._process_cards(event)
    
    async def _process_cards(self, event: BaseEvent):
        """Process cards and emit result"""
        try:
            payload = event.payload
            
            # Call assembler (when real agent is imported)
            # result = await self.assembler.process_cards(
            #     persona_card=payload.get("persona_card"),
            #     competitor_card=payload.get("competitor_card"),
            #     script_card=payload.get("script_card"),
            #     roi_card=payload.get("roi_card"),
            #     session_id=payload.get("session_id"),
            #     user_email=payload.get("user_email"),
            #     business_name=payload.get("business_name"),
            #     trace_id=event.correlation_id,
            # )
            
            # Mock result for demo
            result = {
                "success": True,
                "brief_id": f"BRF-{event.correlation_id[:8].upper()}",
                "confidence_score": 0.92,
                "quality_grade": "A",
            }
            
            if result.get("success", True):
                # Emit success event
                success_event = BriefAssembledEvent(
                    correlation_id=event.correlation_id,
                    payload=BriefAssembledPayload(
                        brief_id=result.get("brief_id", ""),
                        session_id=payload.get("session_id", ""),
                        business_name=payload.get("business_name", ""),
                        contact_email=payload.get("user_email", ""),
                        payment_tier="professional",
                        quoted_price=5000,
                        duration_seconds=60,
                        confidence_score=result.get("confidence_score", 0.0),
                        quality_grade=result.get("quality_grade", ""),
                        is_ready_for_payment=True,
                        creative_brief=result,
                    ),
                )
                await self.bus.publish(success_event)
                self._logger.info("brief_assembled", brief_id=result.get("brief_id"))
            else:
                # Emit failure event
                failure_event = BriefValidationFailedEvent(
                    correlation_id=event.correlation_id,
                    payload=BriefValidationFailedPayload(
                        session_id=payload.get("session_id", ""),
                        issues=result.get("issues", []),
                        repairs_attempted=result.get("repairs", []),
                        confidence_score=result.get("confidence_score", 0.0),
                        suggestions=result.get("suggestions", []),
                    ),
                )
                await self.bus.publish(failure_event)
                self._logger.warning("brief_validation_failed")
                
        except Exception as e:
            self._logger.error("processing_error", error=str(e))
            raise


# =============================================================================
# PAYMENT GATEWAY INTEGRATION
# =============================================================================

class PaymentGatewayIntegration:
    """
    Wires Payment Gateway to Event Bus
    
    Subscribes to:
        - brief.assembled (auto-create checkout)
    
    Publishes:
        - payment.session_created
        - payment.confirmed
        - payment.failed
        - order.queued
    """
    
    def __init__(self, event_bus: IEventBus, gateway=None):
        self.bus = event_bus
        # self.gateway = gateway or PaymentGateway()
        self.gateway = gateway  # Mock for now
        self._subscription_id: Optional[str] = None
        self._logger = structlog.get_logger().bind(agent="payment_gateway_integration")
    
    async def start(self):
        """Start listening for events"""
        # Subscribe to brief.assembled
        self._subscription_id = await self.bus.subscribe(
            [EventType.BRIEF_ASSEMBLED],
            self._handle_event,
            "payment_gateway_queue",
        )
        self._logger.info("started", subscription_id=self._subscription_id)
    
    async def stop(self):
        """Stop listening"""
        if self._subscription_id:
            await self.bus.unsubscribe(self._subscription_id)
            self._logger.info("stopped")
    
    async def _handle_event(self, event: BaseEvent):
        """Handle incoming events"""
        self._logger.info("event_received",
                        event_type=event.event_type.value,
                        correlation_id=event.correlation_id)
        
        if event.event_type == EventType.BRIEF_ASSEMBLED:
            await self._create_checkout(event)
    
    async def _create_checkout(self, event: BaseEvent):
        """Create checkout session for brief"""
        try:
            payload = event.payload
            
            # Create brief object for gateway
            # brief = PGCreativeBrief(
            #     brief_id=payload.get("brief_id"),
            #     session_id=payload.get("session_id"),
            #     business_name=payload.get("business_name"),
            #     contact_email=payload.get("contact_email"),
            #     payment_tier=payload.get("payment_tier"),
            #     quoted_price=payload.get("quoted_price"),
            #     duration_seconds=payload.get("duration_seconds"),
            #     confidence_score=payload.get("confidence_score"),
            # )
            
            # result = await self.gateway.create_checkout(brief)
            
            # Mock checkout result
            checkout_result = {
                "checkout_url": f"https://checkout.stripe.com/demo/{event.correlation_id[:8]}",
                "stripe_session_id": f"cs_demo_{event.correlation_id[:8]}",
                "expires_at": "2025-12-05T12:00:00Z",
            }
            
            # Emit session created
            session_event = PaymentSessionCreatedEvent(
                correlation_id=event.correlation_id,
                payload=PaymentSessionCreatedPayload(
                    brief_id=payload.get("brief_id", ""),
                    checkout_url=checkout_result["checkout_url"],
                    stripe_session_id=checkout_result["stripe_session_id"],
                    expires_at=checkout_result["expires_at"],
                    amount=payload.get("quoted_price", 0),
                ),
            )
            await self.bus.publish(session_event)
            
            self._logger.info("checkout_created",
                            brief_id=payload.get("brief_id"),
                            session_id=checkout_result["stripe_session_id"])
            
        except Exception as e:
            self._logger.error("checkout_error", error=str(e))
            raise
    
    async def on_payment_confirmed(
        self,
        stripe_session_id: str,
        payment_intent_id: str,
        amount_paid: int,
        brief_id: str,
        correlation_id: str,
        contact_email: str,
        payment_tier: str,
        creative_brief: dict,
    ):
        """
        Called by webhook handler when payment confirmed.
        Emits payment.confirmed and order.queued events.
        """
        order_id = f"ORD-{brief_id[4:]}"  # Convert BRF-xxx to ORD-xxx
        
        # Emit payment confirmed
        confirm_event = PaymentConfirmedEvent(
            correlation_id=correlation_id,
            payload=PaymentConfirmedPayload(
                order_id=order_id,
                brief_id=brief_id,
                stripe_session_id=stripe_session_id,
                stripe_payment_intent_id=payment_intent_id,
                amount_paid=amount_paid,
                payment_tier=payment_tier,
                delivery_email=contact_email,
            ),
        )
        await self.bus.publish(confirm_event)
        
        # Emit order queued (to RAGNAROK)
        queue_event = OrderQueuedEvent(
            correlation_id=correlation_id,
            payload=OrderQueuedPayload(
                order_id=order_id,
                brief_id=brief_id,
                creative_brief=creative_brief,
                cost_ceiling=amount_paid * 0.05,  # 5% of price
                delivery_email=contact_email,
            ),
        )
        await self.bus.publish(queue_event)
        
        self._logger.info("payment_confirmed_and_queued",
                         order_id=order_id,
                         brief_id=brief_id)
    
    async def on_payment_failed(
        self,
        brief_id: str,
        correlation_id: str,
        error_code: str,
        message: str,
    ):
        """Called by webhook handler when payment fails"""
        fail_event = PaymentFailedEvent(
            correlation_id=correlation_id,
            payload=PaymentFailedPayload(
                brief_id=brief_id,
                error_code=error_code,
                message=message,
            ),
        )
        await self.bus.publish(fail_event)
        
        self._logger.warning("payment_failed_event_published",
                            brief_id=brief_id,
                            error_code=error_code)


# =============================================================================
# DELIVERY AGENT INTEGRATION
# =============================================================================

class DeliveryAgentIntegration:
    """
    Wires Delivery Agent to Event Bus
    
    Subscribes to:
        - payment.session_created → Send checkout reminder
        - payment.confirmed → Send receipt
        - payment.failed → Send failure notice
        - order.queued → Internal tracking
        - production.started → Send progress update
        - production.phase_complete → Send milestone (optional)
        - production.completed → Send final delivery
        - production.failed → Send failure + refund offer
    """
    
    def __init__(self, event_bus: IEventBus, agent=None):
        self.bus = event_bus
        # self.agent = agent or DeliveryAgent()
        self.agent = agent  # Mock for now
        self._subscription_id: Optional[str] = None
        self._logger = structlog.get_logger().bind(agent="delivery_agent_integration")
    
    async def start(self):
        """Start listening for events"""
        config = AgentWiring.delivery_agent()
        self._subscription_id = await self.bus.subscribe(
            config.subscribes_to,
            self._handle_event,
            config.queue_name,
        )
        self._logger.info("started",
                         subscription_id=self._subscription_id,
                         listening_to=len(config.subscribes_to))
    
    async def stop(self):
        """Stop listening"""
        if self._subscription_id:
            await self.bus.unsubscribe(self._subscription_id)
            self._logger.info("stopped")
    
    async def _handle_event(self, event: BaseEvent):
        """Route events to appropriate handlers"""
        self._logger.info("event_received",
                        event_type=event.event_type.value,
                        correlation_id=event.correlation_id)
        
        handlers = {
            EventType.PAYMENT_SESSION_CREATED: self._on_checkout_created,
            EventType.PAYMENT_CONFIRMED: self._on_payment_confirmed,
            EventType.PAYMENT_FAILED: self._on_payment_failed,
            EventType.PRODUCTION_STARTED: self._on_production_started,
            EventType.PRODUCTION_PHASE_COMPLETE: self._on_phase_complete,
            EventType.PRODUCTION_COMPLETED: self._on_production_completed,
            EventType.PRODUCTION_FAILED: self._on_production_failed,
        }
        
        handler = handlers.get(event.event_type)
        if handler:
            await handler(event)
        else:
            self._logger.debug("no_handler", event_type=event.event_type.value)
    
    async def _on_checkout_created(self, event: BaseEvent):
        """Send checkout reminder email"""
        payload = event.payload
        self._logger.info("sending_checkout_email",
                         brief_id=payload.get("brief_id"),
                         checkout_url=payload.get("checkout_url", "")[:50])
        
        # await self.agent.send_notification(...)
        # Mock for now
        self._logger.info("checkout_email_sent")
    
    async def _on_payment_confirmed(self, event: BaseEvent):
        """Send payment receipt"""
        payload = event.payload
        
        # Build ProductionOrder from event
        # order = ProductionOrder(
        #     order_id=payload.get("order_id"),
        #     brief_id=payload.get("brief_id"),
        #     correlation_id=event.correlation_id,
        #     delivery_email=payload.get("delivery_email"),
        #     payment_tier=payload.get("payment_tier"),
        #     amount_paid=payload.get("amount_paid"),
        # )
        # await self.agent.on_payment_confirmed(order)
        
        self._logger.info("payment_receipt_sent",
                         order_id=payload.get("order_id"),
                         delivery_email=payload.get("delivery_email"))
    
    async def _on_payment_failed(self, event: BaseEvent):
        """Send payment failure notice"""
        payload = event.payload
        self._logger.info("payment_failure_email_sent",
                         brief_id=payload.get("brief_id"),
                         error_code=payload.get("error_code"))
    
    async def _on_production_started(self, event: BaseEvent):
        """Send production started notification"""
        payload = event.payload
        self._logger.info("production_started_email_sent",
                         order_id=payload.get("order_id"))
    
    async def _on_phase_complete(self, event: BaseEvent):
        """Send milestone update (optional based on preferences)"""
        payload = event.payload
        self._logger.info("milestone_update_sent",
                         order_id=payload.get("order_id"),
                         phase=payload.get("phase_name"),
                         progress=payload.get("progress_percent"))
    
    async def _on_production_completed(self, event: BaseEvent):
        """Send final delivery with video"""
        payload = event.payload
        
        # This is the big one - creates secure token and sends email
        # order = ProductionOrder(...)
        # token, notif = await self.agent.on_production_completed(
        #     order,
        #     video_key=payload.get("video_key"),
        #     formats=payload.get("formats_available"),
        # )
        
        self._logger.info("final_delivery_sent",
                         order_id=payload.get("order_id"),
                         video_key=payload.get("video_key"))
    
    async def _on_production_failed(self, event: BaseEvent):
        """Send failure notification with refund offer"""
        payload = event.payload
        self._logger.info("production_failure_email_sent",
                         order_id=payload.get("order_id"),
                         phase_failed=payload.get("phase_failed"),
                         refund_recommended=payload.get("refund_recommended"))


# =============================================================================
# RAGNAROK INTEGRATION (Stub - connects to existing RAGNAROK)
# =============================================================================

class RAGNAROKIntegration:
    """
    Wires RAGNAROK to Event Bus
    
    Subscribes to:
        - order.queued
    
    Publishes:
        - production.started
        - production.phase_complete
        - production.completed
        - production.failed
    """
    
    def __init__(self, event_bus: IEventBus, ragnarok=None):
        self.bus = event_bus
        self.ragnarok = ragnarok  # Existing RAGNAROK orchestrator
        self._subscription_id: Optional[str] = None
        self._logger = structlog.get_logger().bind(agent="ragnarok_integration")
    
    async def start(self):
        """Start listening for orders"""
        config = AgentWiring.ragnarok()
        self._subscription_id = await self.bus.subscribe(
            config.subscribes_to,
            self._handle_event,
            config.queue_name,
        )
        self._logger.info("started", subscription_id=self._subscription_id)
    
    async def stop(self):
        if self._subscription_id:
            await self.bus.unsubscribe(self._subscription_id)
    
    async def _handle_event(self, event: BaseEvent):
        """Handle incoming orders"""
        if event.event_type == EventType.ORDER_QUEUED:
            await self._process_order(event)
    
    async def _process_order(self, event: BaseEvent):
        """Start production pipeline"""
        payload = event.payload
        order_id = payload.get("order_id")
        brief_id = payload.get("brief_id")
        
        self._logger.info("order_received",
                         order_id=order_id,
                         brief_id=brief_id)
        
        # Emit production started
        started_event = ProductionStartedEvent(
            correlation_id=event.correlation_id,
            payload=ProductionStartedPayload(
                order_id=order_id,
                brief_id=brief_id,
                assigned_agents=[
                    "biz_intel_rag",
                    "story_creator",
                    "video_prompt_eng",
                    "video_gen",
                    "voiceover",
                    "video_assembly",
                    "quality_checker",
                ],
            ),
        )
        await self.bus.publish(started_event)
        
        # In real implementation:
        # result = await self.ragnarok.process_order(payload)
        # Then emit completion or failure based on result
        
        # Mock: Simulate completion after "processing"
        self._logger.info("production_started", order_id=order_id)


# =============================================================================
# PIPELINE ORCHESTRATOR
# =============================================================================

class PipelineOrchestrator:
    """
    Manages all agent integrations.
    
    Usage:
        orchestrator = PipelineOrchestrator()
        await orchestrator.start()
        # ... pipeline runs ...
        await orchestrator.stop()
    """
    
    def __init__(self, event_bus: Optional[IEventBus] = None):
        self.bus = event_bus or create_event_bus(use_rabbitmq=True)
        
        self.brief_assembler = BriefAssemblerIntegration(self.bus)
        self.payment_gateway = PaymentGatewayIntegration(self.bus)
        self.delivery_agent = DeliveryAgentIntegration(self.bus)
        self.ragnarok = RAGNAROKIntegration(self.bus)
        
        self._logger = structlog.get_logger().bind(component="pipeline_orchestrator")
    
    async def start(self):
        """Start all integrations"""
        self._logger.info("starting_pipeline")
        
        # Connect event bus
        await self.bus.connect()
        
        # Start all agents
        await self.brief_assembler.start()
        await self.payment_gateway.start()
        await self.delivery_agent.start()
        await self.ragnarok.start()
        
        self._logger.info("pipeline_started")
    
    async def stop(self):
        """Stop all integrations gracefully"""
        self._logger.info("stopping_pipeline")
        
        await self.brief_assembler.stop()
        await self.payment_gateway.stop()
        await self.delivery_agent.stop()
        await self.ragnarok.stop()
        
        await self.bus.disconnect()
        
        self._logger.info("pipeline_stopped")
    
    async def health_check(self) -> dict:
        """Check health of all components"""
        return {
            "event_bus": await self.bus.health_check(),
            "brief_assembler": self.brief_assembler._subscription_id is not None,
            "payment_gateway": self.payment_gateway._subscription_id is not None,
            "delivery_agent": self.delivery_agent._subscription_id is not None,
            "ragnarok": self.ragnarok._subscription_id is not None,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def start_pipeline() -> PipelineOrchestrator:
    """Start the full pipeline"""
    orchestrator = PipelineOrchestrator()
    await orchestrator.start()
    return orchestrator


async def simulate_website_conversion(
    orchestrator: PipelineOrchestrator,
    session_id: str,
    user_email: str,
    business_name: str,
):
    """Simulate a complete website → video conversion"""
    
    # Publish cards complete event (simulates Website Assistant)
    event = ConversationCardsCompleteEvent(
        payload=CardsCompletePayload(
            session_id=session_id,
            user_email=user_email,
            business_name=business_name,
            persona_card={
                "persona_name": "Tech-Savvy Tim",
                "industry_vertical": "SaaS",
                "company_size": "11-50",
                "pain_points": ["High CAC", "Low conversion"],
                "goals": ["Reduce CAC by 30%"],
            },
            competitor_card={
                "primary_competitor_name": "SlowCorp",
                "competitor_weaknesses": ["Slow support"],
                "our_advantages": ["24/7 AI support", "50% cheaper"],
                "positioning_statement": "The smarter alternative",
            },
            script_card={
                "hook_line": "Stop losing customers",
                "problem_statement": "Every minute costs you",
                "solution_presentation": "AI responds instantly",
                "key_benefits": ["Instant response", "50% savings"],
                "call_to_action": "Start free trial",
                "estimated_duration_seconds": 60,
            },
            roi_card={
                "investment_amount": 5000,
                "payment_tier": "professional",
                "projected_revenue": 100000,
                "roi_percentage": 1900,
            },
        ),
    )
    
    await orchestrator.bus.publish(event)
    return event.correlation_id


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Demo the full pipeline"""
    
    print("=" * 70)
    print("WEBSITE ASSISTANT → RAGNAROK PIPELINE")
    print("=" * 70)
    
    # Use in-memory bus for demo
    from event_bus_adapter import InMemoryEventBus
    bus = InMemoryEventBus()
    
    orchestrator = PipelineOrchestrator(event_bus=bus)
    await orchestrator.start()
    
    print("\n✅ Pipeline started with all 4 integrations")
    
    # Health check
    health = await orchestrator.health_check()
    print(f"\n📊 Health: {health}")
    
    # Simulate conversion
    print("\n🌐 Simulating website conversion...")
    correlation_id = await simulate_website_conversion(
        orchestrator,
        session_id="demo-session-001",
        user_email="customer@example.com",
        business_name="Demo Corp",
    )
    
    # Give async handlers time
    await asyncio.sleep(0.2)
    
    # Check published events
    events = bus.get_published_events()
    print(f"\n📨 Events published: {len(events)}")
    for event in events:
        print(f"   • {event.event_type.value} (from: {event.source_agent})")
    
    # Simulate payment confirmation (normally from webhook)
    print("\n💳 Simulating payment webhook...")
    await orchestrator.payment_gateway.on_payment_confirmed(
        stripe_session_id="cs_demo_123",
        payment_intent_id="pi_demo_456",
        amount_paid=5000,
        brief_id="BRF-DEMO123",
        correlation_id=correlation_id,
        contact_email="customer@example.com",
        payment_tier="professional",
        creative_brief={"demo": True},
    )
    
    await asyncio.sleep(0.2)
    
    # Final event count
    events = bus.get_published_events()
    print(f"\n📨 Total events: {len(events)}")
    
    print("\n" + "=" * 70)
    print("PIPELINE FLOW COMPLETE")
    print("=" * 70)
    print("""
    Events triggered:
    1. conversation.cards_complete → Brief Assembler
    2. brief.assembled → Payment Gateway
    3. payment.session_created → Delivery Agent
    4. payment.confirmed → Delivery Agent + RAGNAROK
    5. order.queued → RAGNAROK
    6. production.started → Delivery Agent
    """)
    
    await orchestrator.stop()
    print("\n✅ Pipeline stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())
