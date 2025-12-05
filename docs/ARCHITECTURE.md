# Website Assistant v3.0 Architecture

## Overview

Website Assistant v3.0 is a conversational AI system that guides users through creating AI-powered video commercials. It uses a hybrid architecture combining real-time conversation with asynchronous production pipelines.

## Design Decision: Hybrid Orchestration

This system uses a **hybrid architecture** that separates conversational AI from production workflows.

See [ADR-001: Hybrid Orchestration Design](./ADR-001-HYBRID-ORCHESTRATION.md) for the full rationale.

### Why Not Monolithic LangGraph?

1. **Temporal Mismatch**: Conversation requires <500ms latency. Video production takes 243 seconds.
2. **RAGNAROK Integration**: RAGNAROK v7.0 is an external system with its own orchestration.
3. **Failure Isolation**: A production failure shouldn't kill the conversation.
4. **Independent Scaling**: Conversation and production have different scaling needs.

## System Architecture

```
+------------------+     +-------------------+     +------------------+
|                  |     |                   |     |                  |
|  Next.js Frontend|---->|  FastAPI Backend  |---->|   LangGraph      |
|  (Generative UI) |     |  (API Layer)      |     |   (Orchestrator) |
|                  |     |                   |     |                  |
+------------------+     +-------------------+     +------------------+
                                  |
                                  | conversation.cards_complete
                                  v
+-------------------------------------------------------------------------+
|                          Event Bus (RabbitMQ)                           |
+-------------------------------------------------------------------------+
        |                    |                    |                    |
        v                    v                    v                    v
+---------------+    +---------------+    +---------------+    +---------------+
| Brief         |    | Payment       |    | RAGNAROK      |    | Delivery      |
| Assembler     |--->| Gateway       |--->| (Video Gen)   |--->| Agent         |
| (Trinity USP) |    | (Stripe)      |    | (7 agents)    |    | (JIT tokens)  |
+---------------+    +---------------+    +---------------+    +---------------+
```

## System Boundaries

### Website Assistant (LangGraph)
- Persona generation
- Competitor analysis
- Script creation
- ROI calculation
- Creative Direction
- Checkout initiation

### Production Pipeline (Event-Driven)
- Brief validation (Trinity-powered USP validation)
- Payment processing (Stripe)
- Video generation (RAGNAROK)
- Secure delivery (JIT tokens)

## Communication Pattern

Systems communicate via typed events over RabbitMQ:

```
conversation.cards_complete -> Brief Assembler
brief.assembled -> Payment Gateway
payment.confirmed -> RAGNAROK
production.complete -> Delivery Agent
delivery.ready -> WebSocket -> Frontend
```

This enables retry, audit logging, and system independence.

## Generative UI Cards

The frontend renders dynamic cards based on backend responses:

| Card Type | Purpose |
|-----------|---------|
| CompetitorAnalysisCard | Vs. Mode comparison |
| PersonaCard | Buyer persona visualization |
| ScriptPreviewCard | Script editor with approve/reject |
| ROICalculatorCard | Interactive ROI sliders |
| CheckoutCard | Stripe payment integration |
| ProductionTracker | Real-time video generation status |
| BriefReviewCard | Edit brief before payment |
| OrderTrackingCard | Post-payment order status |

## Key Technologies

- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python 3.11, Pydantic v2
- **Orchestration**: LangGraph, LangChain
- **Event Bus**: RabbitMQ
- **Database**: PostgreSQL, Redis (cache)
- **Payments**: Stripe
- **Video Generation**: RAGNAROK v7.0

## Revenue Pipeline

```
Conversation -> 4 Cards -> Checkout -> RAGNAROK -> Video -> Delivery
              (LangGraph)  (Stripe)    (243s)     ($2.60)  (JIT Token)
```

## Pricing Tiers

- **Starter**: $2,500 (30-second video)
- **Professional**: $5,000 (60-second video)
- **Enterprise**: $15,000 (90+ second video)

---

*Last Updated: December 5, 2024*
*Architecture: Hybrid (LangGraph + Event-Driven)*
