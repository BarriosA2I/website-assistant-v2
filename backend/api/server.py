# api/server.py
# ============================================================================
# BARRIOS A2I WEBSITE ASSISTANT v2.0 — FASTAPI SERVER
# ============================================================================
# Production-ready FastAPI server with CORS, health checks, and metrics
# ============================================================================

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from api.website_graph import (
    process_message,
    format_response,
    WebsiteAssistantState,
)
from schemas.event_definitions import AssistantMessage

# Storage imports (optional - graceful fallback if not configured)
try:
    from services import (
        get_drive_storage,
        store_conversation,
        store_card,
        on_conversation_complete,
        on_lead_captured,
    )
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("BarriosA2I.Server")


# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

# Session state storage (in production, use Redis)
session_states: Dict[str, WebsiteAssistantState] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("🚀 Starting Website Assistant v2.0...")

    # Initialize Trinity Bridge
    try:
        from agents.trinity_bridge import get_trinity_bridge
        await get_trinity_bridge()
        logger.info("✅ Trinity Bridge initialized")
    except Exception as e:
        logger.warning(f"⚠️ Trinity Bridge init failed (will use fallback): {e}")

    # Initialize Google Drive Storage
    if STORAGE_AVAILABLE:
        try:
            storage = await get_drive_storage()
            if storage._initialized:
                logger.info(f"✅ Google Drive storage initialized ({len(storage.folder_ids)} folders)")
            else:
                logger.warning("⚠️ Google Drive storage not configured (running without persistence)")
        except Exception as e:
            logger.warning(f"⚠️ Storage init failed (running without persistence): {e}")
    else:
        logger.info("ℹ️ Storage module not available")

    yield

    logger.info("👋 Shutting down Website Assistant...")
    session_states.clear()


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Barrios A2I Website Assistant",
    description="AI-powered website assistant with Generative UI",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ChatRequest(BaseModel):
    """Incoming chat request."""
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: str = Field(..., min_length=1)
    tenant_id: str = Field(default="demo")
    site_id: str = Field(default="demo")
    user_tier: str = Field(default="starter", pattern="^(starter|pro|elite)$")


class ChatResponse(BaseModel):
    """Chat response with optional Generative UI card."""
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


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    uptime_seconds: float
    active_sessions: int


# ============================================================================
# STARTUP TIME
# ============================================================================

START_TIME = datetime.utcnow()


# ============================================================================
# MIDDLEWARE
# ============================================================================

@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    """Add response timing header."""
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{duration:.2f}"
    return response


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = (datetime.utcnow() - START_TIME).total_seconds()
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        uptime_seconds=uptime,
        active_sessions=len(session_states)
    )


@app.post("/api/v2/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    
    Processes user message through the LangGraph and returns
    response with optional Generative UI card.
    """
    start_time = time.perf_counter()
    
    try:
        # Get existing state for multi-turn
        existing_state = session_states.get(request.session_id)
        
        # Process message
        final_state = await process_message(
            message=request.message,
            tenant_id=request.tenant_id,
            site_id=request.site_id,
            session_id=request.session_id,
            user_tier=request.user_tier,
            existing_state=existing_state
        )
        
        # Store state for next turn
        session_states[request.session_id] = final_state
        
        # Format response
        response = format_response(final_state)
        
        # Calculate total latency
        total_latency = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"Chat processed | session={request.session_id[:8]}... | "
            f"intent={response.intent} | latency={total_latency:.0f}ms | "
            f"cost=${response.cost_usd:.4f}"
        )

        # Persist to Google Drive (non-blocking)
        if STORAGE_AVAILABLE:
            try:
                # Store conversation
                await store_conversation(
                    session_id=request.session_id,
                    user_message=request.message,
                    assistant_response=response.content,
                    card_type=response.render_card.get("type") if response.render_card else None,
                    metadata={"intent": response.intent, "confidence": response.confidence}
                )

                # Store card if generated
                if response.render_card:
                    card_type = response.render_card.get("type", "unknown")
                    await store_card(
                        card_type=card_type,
                        card_data=response.render_card,
                        session_id=request.session_id
                    )

                # Trigger conversation complete hook
                await on_conversation_complete(
                    session_id=request.session_id,
                    messages=[
                        {"role": "user", "content": request.message},
                        {"role": "assistant", "content": response.content}
                    ],
                    card_shown=response.render_card
                )
            except Exception as storage_error:
                logger.warning(f"Storage persistence failed (non-fatal): {storage_error}")

        return ChatResponse(
            content=response.content,
            render_card=response.render_card.model_dump() if hasattr(response.render_card, 'model_dump') else response.render_card,
            intent=response.intent,
            confidence=response.confidence,
            model_used=response.model_used,
            latency_ms=total_latency,
            cost_usd=response.cost_usd,
            trace_id=response.trace_id,
            session_id=response.session_id,
            turn_number=response.turn_number
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        
        # Return graceful fallback
        return ChatResponse(
            content="I apologize, but I'm having trouble processing your request. Please try again.",
            render_card=None,
            intent="error",
            confidence=0.0,
            model_used="fallback",
            latency_ms=(time.perf_counter() - start_time) * 1000,
            cost_usd=0.0,
            trace_id="error",
            session_id=request.session_id,
            turn_number=0
        )


@app.delete("/api/v2/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear session state."""
    if session_id in session_states:
        del session_states[session_id]
        return {"status": "cleared", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


@app.get("/api/v2/sessions")
async def list_sessions():
    """List active sessions (debug endpoint)."""
    return {
        "count": len(session_states),
        "sessions": [
            {
                "session_id": sid[:8] + "...",
                "turn_number": state.get("turn_number", 0),
                "intent": state.get("detected_intent", "unknown")
            }
            for sid, state in list(session_states.items())[:20]
        ]
    }


class LeadCaptureRequest(BaseModel):
    """Lead capture request."""
    email: str
    name: Optional[str] = None
    company: Optional[str] = None
    session_id: Optional[str] = None


@app.post("/api/v2/capture-lead")
async def capture_lead(request: LeadCaptureRequest):
    """
    Capture and persist a lead to Google Drive.

    Returns lead_id on success.
    """
    if not STORAGE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Storage not available - lead capture disabled"
        )

    try:
        from uuid import uuid4
        session_id = request.session_id or str(uuid4())

        lead_id = await on_lead_captured(
            session_id=session_id,
            email=request.email,
            name=request.name,
            company=request.company,
            source="website_assistant_v2"
        )

        logger.info(f"Lead captured: {request.email}")

        return {
            "success": True,
            "lead_id": lead_id,
            "session_id": session_id
        }

    except Exception as e:
        logger.error(f"Lead capture failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/storage/status")
async def storage_status():
    """Check Google Drive storage status."""
    if not STORAGE_AVAILABLE:
        return {
            "available": False,
            "reason": "Storage module not imported"
        }

    try:
        storage = await get_drive_storage()
        return {
            "available": storage._initialized,
            "folders": list(storage.folder_ids.keys()) if storage._initialized else [],
            "root_folder_id": storage.root_folder_id
        }
    except Exception as e:
        return {
            "available": False,
            "reason": str(e)
        }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "development") == "development",
        log_level="info"
    )
