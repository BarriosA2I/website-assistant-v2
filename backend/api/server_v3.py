"""
Website Assistant Server v3.0 - REMASTERED
===========================================
Production-ready FastAPI server with:
- REST API for chat
- WebSocket for real-time progress
- Event bus integration for pipeline handoff
- Redis session management
- Health monitoring

pip install fastapi uvicorn pydantic redis aio-pika structlog
"""

import logging
import os
import time
import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import structlog

# Local imports
from api.website_graph_v3 import (
    process_message,
    format_response,
    WebsiteAssistantState,
    get_card_progress,
    CardStatus,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

logger = structlog.get_logger().bind(component="server")


# =============================================================================
# CONFIGURATION
# =============================================================================

class ServerConfig:
    """Server configuration from environment"""
    
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    ENV = os.getenv("ENV", "development")
    DEBUG = ENV == "development"
    
    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Redis (for session management)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    SESSION_TTL = int(os.getenv("SESSION_TTL", "3600"))  # 1 hour
    
    # RabbitMQ (for event bus)
    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    
    # API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


config = ServerConfig()


# =============================================================================
# SESSION STORAGE (Redis-backed or in-memory)
# =============================================================================

class SessionStore:
    """Session state storage with Redis backend"""
    
    def __init__(self):
        self._local_cache: Dict[str, WebsiteAssistantState] = {}
        self._redis = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis connection"""
        try:
            import redis.asyncio as redis
            self._redis = await redis.from_url(config.REDIS_URL)
            await self._redis.ping()
            self._initialized = True
            logger.info("redis_connected", url=config.REDIS_URL[:20] + "...")
        except Exception as e:
            logger.warning("redis_unavailable", error=str(e), fallback="in_memory")
            self._initialized = False
    
    async def get(self, session_id: str) -> Optional[WebsiteAssistantState]:
        """Get session state"""
        # Try local cache first
        if session_id in self._local_cache:
            return self._local_cache[session_id]
        
        # Try Redis
        if self._redis:
            try:
                data = await self._redis.get(f"session:{session_id}")
                if data:
                    state = json.loads(data)
                    self._local_cache[session_id] = state
                    return state
            except Exception as e:
                logger.error("redis_get_error", session_id=session_id[:8], error=str(e))
        
        return None
    
    async def set(self, session_id: str, state: WebsiteAssistantState):
        """Store session state"""
        # Update local cache
        self._local_cache[session_id] = state
        
        # Persist to Redis
        if self._redis:
            try:
                # Serialize state (handle non-JSON types)
                serializable = self._serialize_state(state)
                await self._redis.setex(
                    f"session:{session_id}",
                    config.SESSION_TTL,
                    json.dumps(serializable)
                )
            except Exception as e:
                logger.error("redis_set_error", session_id=session_id[:8], error=str(e))
    
    async def delete(self, session_id: str):
        """Delete session state"""
        if session_id in self._local_cache:
            del self._local_cache[session_id]
        
        if self._redis:
            try:
                await self._redis.delete(f"session:{session_id}")
            except Exception as e:
                logger.error("redis_delete_error", session_id=session_id[:8], error=str(e))
    
    def _serialize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Convert state to JSON-serializable format"""
        serializable = {}
        for key, value in state.items():
            if key == "messages":
                # Serialize LangChain messages
                serializable[key] = [
                    {"role": getattr(msg, 'type', 'unknown'), "content": msg.content}
                    for msg in value
                ]
            elif hasattr(value, 'model_dump'):
                serializable[key] = value.model_dump()
            elif isinstance(value, datetime):
                serializable[key] = value.isoformat()
            else:
                serializable[key] = value
        return serializable
    
    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
        self._local_cache.clear()


session_store = SessionStore()


# =============================================================================
# EVENT BUS CLIENT
# =============================================================================

class EventBusClient:
    """Client for publishing events to pipeline"""
    
    def __init__(self):
        self._connection = None
        self._channel = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize RabbitMQ connection"""
        try:
            import aio_pika
            self._connection = await aio_pika.connect_robust(config.RABBITMQ_URL)
            self._channel = await self._connection.channel()
            
            # Declare exchange
            await self._channel.declare_exchange(
                "barrios_pipeline",
                aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            
            self._initialized = True
            logger.info("rabbitmq_connected")
        except Exception as e:
            logger.warning("rabbitmq_unavailable", error=str(e))
            self._initialized = False
    
    async def publish(self, event_type: str, payload: Dict[str, Any]):
        """Publish event to pipeline"""
        if not self._initialized:
            logger.warning("event_not_published", reason="rabbitmq_not_connected", event_type=event_type)
            return False
        
        try:
            import aio_pika
            
            message = aio_pika.Message(
                body=json.dumps({
                    "event_type": event_type,
                    "payload": payload,
                    "timestamp": datetime.utcnow().isoformat(),
                }).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            
            exchange = await self._channel.get_exchange("barrios_pipeline")
            await exchange.publish(message, routing_key=event_type)
            
            logger.info("event_published", event_type=event_type)
            return True
        except Exception as e:
            logger.error("event_publish_error", event_type=event_type, error=str(e))
            return False
    
    async def close(self):
        """Close RabbitMQ connection"""
        if self._connection:
            await self._connection.close()


event_bus = EventBusClient()


# =============================================================================
# WEBSOCKET CONNECTION MANAGER
# =============================================================================

class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self._connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept and register connection"""
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(websocket)
        logger.info("websocket_connected", session_id=session_id[:8])
    
    def disconnect(self, session_id: str, websocket: WebSocket):
        """Remove connection"""
        if session_id in self._connections:
            if websocket in self._connections[session_id]:
                self._connections[session_id].remove(websocket)
            if not self._connections[session_id]:
                del self._connections[session_id]
        logger.info("websocket_disconnected", session_id=session_id[:8])
    
    async def send_progress(self, session_id: str, data: Dict[str, Any]):
        """Send progress update to all connections for session"""
        if session_id not in self._connections:
            return
        
        for websocket in self._connections[session_id][:]:  # Copy list to avoid mutation
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error("websocket_send_error", session_id=session_id[:8], error=str(e))
                self.disconnect(session_id, websocket)
    
    async def broadcast(self, data: Dict[str, Any]):
        """Send to all connected clients"""
        for session_id, connections in self._connections.items():
            for websocket in connections[:]:
                try:
                    await websocket.send_json(data)
                except:
                    self.disconnect(session_id, websocket)


ws_manager = WebSocketManager()


# =============================================================================
# LIFESPAN MANAGEMENT
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic"""
    logger.info("server_starting", version="3.0.0", env=config.ENV)
    
    # Initialize session store
    await session_store.initialize()
    
    # Initialize event bus
    await event_bus.initialize()
    
    # Initialize other services
    try:
        from agents.trinity_bridge import get_trinity_bridge
        await get_trinity_bridge()
        logger.info("trinity_bridge_initialized")
    except Exception as e:
        logger.warning("trinity_bridge_unavailable", error=str(e))
    
    yield
    
    # Cleanup
    logger.info("server_shutting_down")
    await session_store.close()
    await event_bus.close()


# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    title="Barrios A2I Website Assistant",
    description="AI-powered commercial video creation assistant with Generative UI",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    """Incoming chat request"""
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(default=None)
    tenant_id: str = Field(default="demo")
    site_id: str = Field(default="demo")
    user_tier: str = Field(default="starter", pattern="^(starter|pro|elite)$")


class CardProgressResponse(BaseModel):
    """Card completion progress"""
    persona: str
    competitor: str
    script: str
    roi: str
    complete_count: int
    all_complete: bool


class ChatResponse(BaseModel):
    """Chat response with optional Generative UI card"""
    content: str
    render_card: Optional[Dict[str, Any]] = None
    intent: str
    confidence: float
    model_used: str
    latency_ms: float
    cost_usd: float
    trace_id: str
    session_id: str
    turn_number: int
    cards_ready: bool = False
    card_progress: Optional[CardProgressResponse] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    uptime_seconds: float
    active_sessions: int
    redis_connected: bool
    rabbitmq_connected: bool


class CheckoutRequest(BaseModel):
    """Request to initiate checkout"""
    session_id: str
    email: str
    name: Optional[str] = None


class CheckoutResponse(BaseModel):
    """Checkout initiation response"""
    checkout_url: str
    brief_id: str
    session_id: str


# =============================================================================
# STARTUP TIME
# =============================================================================

START_TIME = datetime.utcnow()


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    """Add response timing and request ID headers"""
    request_id = str(uuid4())[:8]
    start = time.perf_counter()
    
    response = await call_next(request)
    
    duration = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{duration:.2f}"
    response.headers["X-Request-ID"] = request_id
    
    return response


# =============================================================================
# HEALTH ENDPOINTS
# =============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    uptime = (datetime.utcnow() - START_TIME).total_seconds()
    return HealthResponse(
        status="healthy",
        version="3.0.0",
        uptime_seconds=uptime,
        active_sessions=len(session_store._local_cache),
        redis_connected=session_store._initialized,
        rabbitmq_connected=event_bus._initialized,
    )


@app.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe"""
    return {"ready": True}


@app.get("/live")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"live": True}


# =============================================================================
# CHAT ENDPOINTS
# =============================================================================

@app.post("/api/v3/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Main chat endpoint v3.
    
    Processes user message through LangGraph and returns
    response with optional Generative UI card and card progress.
    """
    start_time = time.perf_counter()
    
    # Generate session ID if not provided
    session_id = request.session_id or f"session_{uuid4().hex[:12]}"
    
    try:
        # Get existing state for multi-turn
        existing_state = await session_store.get(session_id)
        
        # Process message
        final_state = await process_message(
            message=request.message,
            tenant_id=request.tenant_id,
            site_id=request.site_id,
            session_id=session_id,
            user_tier=request.user_tier,
            existing_state=existing_state
        )
        
        # Store state for next turn
        await session_store.set(session_id, final_state)
        
        # Format response
        response = format_response(final_state)
        
        # Calculate total latency
        total_latency = (time.perf_counter() - start_time) * 1000
        
        # Check if checkout should be triggered
        if final_state.get("cards_ready") and final_state.get("checkout", {}).get("initiated"):
            # Publish event for Brief Assembler
            background_tasks.add_task(
                publish_cards_complete_event,
                session_id=session_id,
                state=final_state,
            )
        
        logger.info(
            "chat_processed",
            session_id=session_id[:8],
            intent=response.intent,
            latency_ms=round(total_latency),
            cost_usd=round(response.cost_usd, 4),
            cards_ready=response.cards_ready,
        )
        
        # Build card progress
        progress = response.card_progress
        card_progress_response = CardProgressResponse(
            persona=progress["persona"],
            competitor=progress["competitor"],
            script=progress["script"],
            roi=progress["roi"],
            complete_count=progress["complete_count"],
            all_complete=progress["all_complete"],
        ) if progress else None
        
        return ChatResponse(
            content=response.content,
            render_card=response.render_card,
            intent=response.intent,
            confidence=response.confidence,
            model_used=response.model_used,
            latency_ms=total_latency,
            cost_usd=response.cost_usd,
            trace_id=response.trace_id,
            session_id=session_id,
            turn_number=response.turn_number,
            cards_ready=response.cards_ready,
            card_progress=card_progress_response,
        )
        
    except Exception as e:
        logger.error("chat_error", error=str(e), session_id=session_id[:8])
        
        return ChatResponse(
            content="I apologize, but I'm having trouble processing your request. Please try again.",
            render_card=None,
            intent="error",
            confidence=0.0,
            model_used="fallback",
            latency_ms=(time.perf_counter() - start_time) * 1000,
            cost_usd=0.0,
            trace_id="error",
            session_id=session_id,
            turn_number=0,
            cards_ready=False,
            card_progress=None,
        )


async def publish_cards_complete_event(session_id: str, state: Dict[str, Any]):
    """Publish conversation.cards_complete event to pipeline"""
    
    payload = {
        "session_id": session_id,
        "user_email": state.get("lead", {}).get("collected_data", {}).get("email"),
        "persona_card": state.get("persona_card"),
        "competitor_card": state.get("competitor_card"),
        "script_card": state.get("script_card"),
        "roi_card": state.get("roi_card"),
        "checkout": state.get("checkout"),
    }
    
    await event_bus.publish("conversation.cards_complete", payload)


# =============================================================================
# CHECKOUT ENDPOINTS
# =============================================================================

@app.post("/api/v3/checkout", response_model=CheckoutResponse)
async def initiate_checkout(request: CheckoutRequest):
    """
    Initiate Stripe checkout for completed brief.
    
    Called by frontend when user clicks checkout button.
    """
    # Get session state
    state = await session_store.get(request.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Verify all cards complete
    progress = get_card_progress(state)
    if not progress["all_complete"]:
        raise HTTPException(
            status_code=400,
            detail=f"Brief incomplete: {progress['complete_count']}/4 cards complete"
        )
    
    # Get investment amount from ROI card
    roi_card = state.get("roi_card", {})
    amount = roi_card.get("investment_amount", 5000)
    
    try:
        # Create Stripe checkout session
        import stripe
        stripe.api_key = config.STRIPE_SECRET_KEY
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Commercial Video Production",
                        "description": f"{state.get('script_card', {}).get('format', '60s')} commercial",
                    },
                    "unit_amount": amount * 100,  # Stripe uses cents
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/success?session_id={request.session_id}",
            cancel_url=f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/checkout?session_id={request.session_id}",
            customer_email=request.email,
            metadata={
                "session_id": request.session_id,
                "brief_id": state.get("checkout", {}).get("brief_id"),
            },
        )
        
        # Update session state
        state["checkout"]["checkout_url"] = checkout_session.url
        await session_store.set(request.session_id, state)
        
        # Publish event
        await event_bus.publish("payment.session_created", {
            "session_id": request.session_id,
            "checkout_session_id": checkout_session.id,
            "amount": amount,
        })
        
        return CheckoutResponse(
            checkout_url=checkout_session.url,
            brief_id=state.get("checkout", {}).get("brief_id", ""),
            session_id=request.session_id,
        )
        
    except Exception as e:
        logger.error("checkout_error", error=str(e), session_id=request.session_id[:8])
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@app.post("/api/v3/webhook/stripe")
async def stripe_webhook(request: Request):
    """
    Stripe webhook handler for payment events.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        import stripe
        stripe.api_key = config.STRIPE_SECRET_KEY
        
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        logger.error("stripe_webhook_error", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session["metadata"].get("session_id")
        
        if session_id:
            # Update state
            state = await session_store.get(session_id)
            if state:
                state["checkout"]["payment_status"] = "completed"
                state["checkout"]["order_id"] = session.get("payment_intent")
                state["production"]["status"] = "queued"
                await session_store.set(session_id, state)
            
            # Publish payment confirmed event
            await event_bus.publish("payment.confirmed", {
                "session_id": session_id,
                "payment_intent": session.get("payment_intent"),
                "amount": session.get("amount_total", 0) / 100,
                "customer_email": session.get("customer_email"),
            })
            
            # Notify via WebSocket
            await ws_manager.send_progress(session_id, {
                "type": "payment_confirmed",
                "message": "Payment successful! Starting video production...",
            })
            
            logger.info("payment_confirmed", session_id=session_id[:8])
    
    elif event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        session_id = session["metadata"].get("session_id")
        
        if session_id:
            state = await session_store.get(session_id)
            if state:
                state["checkout"]["payment_status"] = "failed"
                await session_store.set(session_id, state)
            
            await event_bus.publish("payment.failed", {
                "session_id": session_id,
                "reason": "session_expired",
            })
    
    return {"received": True}


# =============================================================================
# WEBSOCKET ENDPOINTS
# =============================================================================

@app.websocket("/ws/progress/{session_id}")
async def progress_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time progress updates.
    
    Clients connect here to receive production progress notifications.
    """
    await ws_manager.connect(session_id, websocket)
    
    try:
        # Send initial state
        state = await session_store.get(session_id)
        if state:
            progress = get_card_progress(state)
            await websocket.send_json({
                "type": "connected",
                "session_id": session_id,
                "card_progress": progress,
                "production": state.get("production", {}),
            })
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for client messages (heartbeat, etc.)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
                
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
    except Exception as e:
        logger.error("websocket_error", session_id=session_id[:8], error=str(e))
        ws_manager.disconnect(session_id, websocket)


# =============================================================================
# SESSION MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/v3/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session state"""
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Return sanitized state
    return {
        "session_id": session_id,
        "turn_number": state.get("turn_number", 0),
        "card_progress": get_card_progress(state),
        "cards_ready": state.get("cards_ready", False),
        "checkout": state.get("checkout", {}),
        "production": state.get("production", {}),
    }


@app.delete("/api/v3/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear session state"""
    await session_store.delete(session_id)
    return {"status": "cleared", "session_id": session_id}


@app.get("/api/v3/sessions/{session_id}/progress")
async def get_card_progress_endpoint(session_id: str):
    """Get card completion progress"""
    state = await session_store.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    progress = get_card_progress(state)
    return CardProgressResponse(**progress)


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@app.get("/api/v3/admin/sessions")
async def list_sessions(limit: int = 20):
    """List active sessions (admin endpoint)"""
    sessions = []
    for sid, state in list(session_store._local_cache.items())[:limit]:
        progress = get_card_progress(state)
        sessions.append({
            "session_id": sid[:8] + "...",
            "turn_number": state.get("turn_number", 0),
            "cards_complete": progress["complete_count"],
            "cards_ready": state.get("cards_ready", False),
            "intent": state.get("detected_intent", "unknown"),
        })
    
    return {
        "count": len(session_store._local_cache),
        "sessions": sessions,
    }


@app.get("/api/v3/admin/metrics")
async def get_metrics():
    """Get server metrics"""
    return {
        "uptime_seconds": (datetime.utcnow() - START_TIME).total_seconds(),
        "active_sessions": len(session_store._local_cache),
        "websocket_connections": sum(
            len(conns) for conns in ws_manager._connections.values()
        ),
        "redis_connected": session_store._initialized,
        "rabbitmq_connected": event_bus._initialized,
    }


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

@app.post("/api/v2/chat")
async def chat_v2_compat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Backward compatible v2 endpoint"""
    return await chat(request, background_tasks)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "server_v3:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info",
    )
