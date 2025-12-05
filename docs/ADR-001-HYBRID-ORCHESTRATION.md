# ADR-001: Hybrid Orchestration Design

**Status:** Accepted
**Date:** 2024-12-05
**Decision Makers:** Claude Opus 4.5, Gary (Barrios A2I)

## Context

Website Assistant v3.0 needs to handle both:
1. **Conversational AI** (real-time, <500ms latency)
2. **Video Production** (long-running, ~243 seconds via RAGNAROK)

The question: Should we use monolithic LangGraph for everything, or a hybrid approach?

## Decision

We use a **Hybrid Architecture**:
- **LangGraph** for conversation orchestration (fast, stateful)
- **Event-Driven Pipeline** for production workflows (async, resilient)

## Rationale

### Why Not Monolithic LangGraph?

1. **Temporal Mismatch**
   - Conversation: Requires <500ms response time
   - Production: Takes 243 seconds average
   - A single graph can't optimize for both

2. **RAGNAROK Integration**
   - RAGNAROK v7.0 is an external system with its own orchestration
   - It has 7 specialized agents already
   - Wrapping it in LangGraph adds latency with no benefit

3. **Failure Isolation**
   - A production failure shouldn't kill the conversation
   - Payment webhook timeouts shouldn't affect chat UX
   - Each domain needs independent retry policies

4. **Scaling Characteristics**
   - Conversation: Many concurrent, short-lived sessions
   - Production: Fewer, long-running, GPU-intensive jobs
   - Different scaling strategies needed

### The Hybrid Design

```
Website Assistant (LangGraph)     Production Pipeline (Event-Driven)
------------------------------    --------------------------------
- Persona generation              - Brief validation (Trinity-powered)
- Competitor analysis             - Payment processing
- Script creation                 - Video generation (RAGNAROK)
- ROI calculation                 - Secure delivery
- Creative Direction
- Checkout initiation
                    |
                    v
           Event Bus (RabbitMQ)
                    |
                    v
           Pipeline Agents
```

### Communication Pattern

Systems communicate via typed events over RabbitMQ:

1. `conversation.cards_complete` -> Brief Assembler
2. `brief.assembled` -> Payment Gateway
3. `payment.confirmed` -> RAGNAROK
4. `production.complete` -> Delivery Agent
5. `delivery.ready` -> WebSocket -> Frontend

This enables:
- Retry without re-running conversation
- Audit logging of all state transitions
- System independence (one can fail without affecting others)

## Consequences

### Positive
- Clear separation of concerns
- Each system optimized for its use case
- Easier debugging (follow the events)
- Can replace components independently

### Negative
- Two orchestration paradigms to understand
- More infrastructure (RabbitMQ)
- Event schema versioning needed

### Neutral
- Development team needs to understand both patterns
- Monitoring needs to span both systems

## Alternatives Considered

### Alternative 1: Monolithic LangGraph
- Rejected: Would force conversation to wait for production

### Alternative 2: Pure Event-Driven
- Rejected: LangGraph's state management is valuable for conversation

### Alternative 3: Temporal.io
- Rejected: Over-engineering for current scale

## References

- LangGraph Documentation
- RAGNAROK v7.0 Architecture
- RabbitMQ Patterns Guide

---

*This ADR explains the "why" behind Website Assistant v3.0's architecture.*
