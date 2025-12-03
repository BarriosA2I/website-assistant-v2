// app/api/chat/route.ts
// ============================================================================
// BARRIOS A2I WEBSITE ASSISTANT v2.0 — CHAT API ROUTE
// ============================================================================
// Next.js API route that proxies to Python backend
// ============================================================================

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

interface ChatRequest {
  message: string;
  session_id: string;
  tenant_id: string;
  site_id: string;
  user_tier: "starter" | "pro" | "elite";
}

export async function POST(request: NextRequest) {
  try {
    const body: ChatRequest = await request.json();

    // Validate required fields
    if (!body.message?.trim()) {
      return NextResponse.json(
        { error: "Message is required" },
        { status: 400 }
      );
    }

    // Forward to Python backend
    const response = await fetch(`${BACKEND_URL}/api/v2/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: body.message,
        session_id: body.session_id || `session_${Date.now()}`,
        tenant_id: body.tenant_id || "demo",
        site_id: body.site_id || "demo",
        user_tier: body.user_tier || "starter",
      }),
    });

    if (!response.ok) {
      const errorData = await response.text();
      console.error("Backend error:", errorData);
      return NextResponse.json(
        { error: "Backend error", details: errorData },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error("Chat API error:", error);
    
    // Return graceful fallback
    return NextResponse.json({
      content: "I'm having trouble connecting to my brain right now. Please try again in a moment!",
      render_card: null,
      intent: "error",
      confidence: 0,
      model_used: "fallback",
      latency_ms: 0,
      cost_usd: 0,
      trace_id: "error",
      session_id: "error",
      turn_number: 0,
    });
  }
}

// Health check
export async function GET() {
  return NextResponse.json({ status: "ok", version: "2.0.0" });
}
