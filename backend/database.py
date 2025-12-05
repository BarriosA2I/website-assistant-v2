"""
Database Module - The Black Box
================================
Unified persistence layer with centralized event logging.

This module provides:
- AsyncPG connection pool for PostgreSQL
- The Black Box (system_events) for unified logging
- Session CRUD operations
- Order CRUD operations
- Knowledge Base queries

pip install asyncpg
"""

import os
import json
import asyncio
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Literal
from contextlib import asynccontextmanager

import structlog
import asyncpg
from pydantic import BaseModel, Field

# Configure logger
logger = structlog.get_logger().bind(component="database")


# =============================================================================
# CONFIGURATION
# =============================================================================

class DatabaseConfig:
    """Database configuration from environment"""

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/website_assistant"
    )
    MIN_POOL_SIZE = int(os.getenv("DB_MIN_POOL_SIZE", "5"))
    MAX_POOL_SIZE = int(os.getenv("DB_MAX_POOL_SIZE", "20"))


config = DatabaseConfig()


# =============================================================================
# EVENT TYPES (The Black Box)
# =============================================================================

EventType = Literal[
    # Conversation Events
    "CONVERSATION_STARTED",
    "CONVERSATION_MESSAGE",
    "CARD_GENERATED",
    "CARD_APPROVED",
    "CARD_REJECTED",

    # Brief Events
    "BRIEF_CREATED",
    "BRIEF_VALIDATED",
    "BRIEF_FAILED",
    "USP_CONFLICT_DETECTED",

    # Checkout Events
    "CHECKOUT_INITIATED",
    "PAYMENT_INTENT_CREATED",
    "PAYMENT_PENDING",
    "PAYMENT_CONFIRMED",
    "PAYMENT_FAILED",

    # Production Events
    "PRODUCTION_QUEUED",
    "RAGNAROK_STARTED",
    "RAGNAROK_PROGRESS",
    "VIDEO_GENERATED",

    # Delivery Events
    "DELIVERY_STARTED",
    "DELIVERY_TOKEN_CREATED",
    "DELIVERY_EMAIL_SENT",
    "DELIVERY_COMPLETE",
    "DOWNLOAD_REQUESTED",

    # System Events
    "AGENT_ERROR",
    "RETRY_SCHEDULED",
    "RESURRECTION_TRIGGERED",
    "SYSTEM_HEALTH_CHECK",

    # Learning Events (DSPy hook)
    "BRIEF_CONVERSION_SUCCESS",
    "BRIEF_CONVERSION_FAILURE",
]

Severity = Literal["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"]


# =============================================================================
# CONNECTION POOL
# =============================================================================

class Database:
    """Async database connection pool manager"""

    _pool: Optional[asyncpg.Pool] = None
    _initialized: bool = False

    @classmethod
    async def initialize(cls):
        """Initialize the connection pool"""
        if cls._initialized:
            return

        try:
            cls._pool = await asyncpg.create_pool(
                config.DATABASE_URL,
                min_size=config.MIN_POOL_SIZE,
                max_size=config.MAX_POOL_SIZE,
            )
            cls._initialized = True
            logger.info("Database connection pool initialized")

            # Run migrations on startup
            await cls._run_migrations()

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @classmethod
    async def close(cls):
        """Close the connection pool"""
        if cls._pool:
            await cls._pool.close()
            cls._initialized = False
            logger.info("Database connection pool closed")

    @classmethod
    @asynccontextmanager
    async def acquire(cls):
        """Acquire a connection from the pool"""
        if not cls._pool:
            await cls.initialize()

        async with cls._pool.acquire() as conn:
            yield conn

    @classmethod
    async def execute(cls, query: str, *args) -> str:
        """Execute a query"""
        async with cls.acquire() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def fetch_one(cls, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row"""
        async with cls.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def fetch_all(cls, query: str, *args) -> List[asyncpg.Record]:
        """Fetch all rows"""
        async with cls.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def _run_migrations(cls):
        """Run database migrations"""
        migrations = [
            # Sessions table
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID,
                state JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,

            # Orders table
            """
            CREATE TABLE IF NOT EXISTS orders (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID REFERENCES sessions(id),
                tier VARCHAR(20) NOT NULL,
                amount_cents INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                payment_intent_id VARCHAR(255),
                brief_data JSONB,
                video_url TEXT,
                delivery_token VARCHAR(255),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                paid_at TIMESTAMPTZ,
                delivered_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,

            # THE BLACK BOX: Unified event log
            """
            CREATE TABLE IF NOT EXISTS system_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID,
                timestamp TIMESTAMPTZ DEFAULT NOW(),
                event_type VARCHAR(50) NOT NULL,
                agent VARCHAR(50),
                payload JSONB NOT NULL DEFAULT '{}',
                severity VARCHAR(10) DEFAULT 'INFO'
            )
            """,

            # Create indexes
            "CREATE INDEX IF NOT EXISTS idx_events_session ON system_events(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_events_type ON system_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON system_events(timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_orders_session ON orders(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",

            # Knowledge Base index (for agent queries)
            """
            CREATE TABLE IF NOT EXISTS knowledge_index (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title TEXT NOT NULL,
                category VARCHAR(50) NOT NULL,
                tags TEXT[] DEFAULT '{}',
                gdrive_file_id VARCHAR(255),
                gdrive_url TEXT,
                summary TEXT,
                key_insights JSONB DEFAULT '[]',
                relevance_score FLOAT DEFAULT 0.8,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_index(category)",
        ]

        async with cls.acquire() as conn:
            for migration in migrations:
                try:
                    await conn.execute(migration)
                except Exception as e:
                    # Index might already exist, that's fine
                    if "already exists" not in str(e):
                        logger.warning(f"Migration warning: {e}")

        logger.info("Database migrations complete")


# =============================================================================
# THE BLACK BOX: Event Logging
# =============================================================================

async def log_event(
    session_id: Optional[str],
    event_type: str,
    payload: Dict[str, Any],
    agent: Optional[str] = None,
    severity: str = "INFO"
) -> str:
    """
    Unified event logging for all agents and system components.

    This is "The Black Box" - every significant event in the system
    flows through here, creating a complete audit trail.

    Args:
        session_id: Session this event belongs to (optional)
        event_type: One of the EventType literals
        payload: Event-specific data
        agent: Which agent generated this event
        severity: DEBUG, INFO, WARN, ERROR, CRITICAL

    Returns:
        Event ID
    """
    event_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat()

    # Log to console with context
    log_method = getattr(logger, severity.lower(), logger.info)
    log_method(
        event_type,
        event_id=event_id[:8],
        session_id=session_id[:8] if session_id else None,
        agent=agent,
        **{k: v for k, v in payload.items() if k not in ["brief_snapshot"]}  # Don't log full briefs
    )

    try:
        await Database.execute(
            """
            INSERT INTO system_events
            (id, session_id, timestamp, event_type, agent, payload, severity)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            event_id,
            session_id,
            timestamp,
            event_type,
            agent,
            json.dumps(payload),
            severity
        )
    except Exception as e:
        logger.error(f"Failed to log event to database: {e}")

    return event_id


async def get_session_events(
    session_id: str,
    event_types: Optional[List[str]] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get all events for a session"""

    if event_types:
        query = """
            SELECT * FROM system_events
            WHERE session_id = $1 AND event_type = ANY($2)
            ORDER BY timestamp DESC
            LIMIT $3
        """
        rows = await Database.fetch_all(query, session_id, event_types, limit)
    else:
        query = """
            SELECT * FROM system_events
            WHERE session_id = $1
            ORDER BY timestamp DESC
            LIMIT $2
        """
        rows = await Database.fetch_all(query, session_id, limit)

    return [dict(row) for row in rows]


async def get_recent_events(
    limit: int = 50,
    event_types: Optional[List[str]] = None,
    severity: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get recent events across all sessions"""

    conditions = []
    params = []
    param_num = 1

    if event_types:
        conditions.append(f"event_type = ANY(${param_num})")
        params.append(event_types)
        param_num += 1

    if severity:
        conditions.append(f"severity = ${param_num}")
        params.append(severity)
        param_num += 1

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT * FROM system_events
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ${param_num}
    """
    params.append(limit)

    rows = await Database.fetch_all(query, *params)
    return [dict(row) for row in rows]


# =============================================================================
# SESSION CRUD
# =============================================================================

async def create_session(
    user_id: Optional[str] = None,
    initial_state: Optional[Dict[str, Any]] = None
) -> str:
    """Create a new session"""
    session_id = str(uuid4())
    state = initial_state or {}

    await Database.execute(
        """
        INSERT INTO sessions (id, user_id, state)
        VALUES ($1, $2, $3)
        """,
        session_id,
        user_id,
        json.dumps(state)
    )

    await log_event(
        session_id=session_id,
        event_type="CONVERSATION_STARTED",
        payload={"user_id": user_id},
        agent="system"
    )

    return session_id


async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session by ID"""
    row = await Database.fetch_one(
        "SELECT * FROM sessions WHERE id = $1",
        session_id
    )

    if row:
        result = dict(row)
        result["state"] = json.loads(result["state"]) if isinstance(result["state"], str) else result["state"]
        return result

    return None


async def update_session_state(session_id: str, state: Dict[str, Any]) -> bool:
    """Update session state"""
    result = await Database.execute(
        """
        UPDATE sessions
        SET state = $1, updated_at = NOW()
        WHERE id = $2
        """,
        json.dumps(state),
        session_id
    )

    return "UPDATE 1" in result


# =============================================================================
# ORDER CRUD
# =============================================================================

async def create_order(
    session_id: str,
    tier: str,
    amount_cents: int,
    payment_intent_id: Optional[str] = None,
    brief_data: Optional[Dict[str, Any]] = None
) -> str:
    """Create a new order"""
    order_id = str(uuid4())

    await Database.execute(
        """
        INSERT INTO orders
        (id, session_id, tier, amount_cents, payment_intent_id, brief_data)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        order_id,
        session_id,
        tier,
        amount_cents,
        payment_intent_id,
        json.dumps(brief_data) if brief_data else None
    )

    await log_event(
        session_id=session_id,
        event_type="CHECKOUT_INITIATED",
        payload={
            "order_id": order_id,
            "tier": tier,
            "amount_cents": amount_cents
        },
        agent="system"
    )

    return order_id


async def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    """Get order by ID"""
    row = await Database.fetch_one(
        "SELECT * FROM orders WHERE id = $1",
        order_id
    )

    if row:
        result = dict(row)
        if result.get("brief_data") and isinstance(result["brief_data"], str):
            result["brief_data"] = json.loads(result["brief_data"])
        return result

    return None


async def get_order_by_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get order by session ID"""
    row = await Database.fetch_one(
        "SELECT * FROM orders WHERE session_id = $1 ORDER BY created_at DESC LIMIT 1",
        session_id
    )

    if row:
        result = dict(row)
        if result.get("brief_data") and isinstance(result["brief_data"], str):
            result["brief_data"] = json.loads(result["brief_data"])
        return result

    return None


async def update_order_status(
    order_id: str,
    status: str,
    **kwargs
) -> bool:
    """Update order status and optional fields"""

    set_clauses = ["status = $1", "updated_at = NOW()"]
    params = [status]
    param_num = 2

    for key, value in kwargs.items():
        if key in ["payment_intent_id", "video_url", "delivery_token"]:
            set_clauses.append(f"{key} = ${param_num}")
            params.append(value)
            param_num += 1
        elif key == "paid_at" and value:
            set_clauses.append(f"paid_at = ${param_num}")
            params.append(datetime.utcnow())
            param_num += 1
        elif key == "delivered_at" and value:
            set_clauses.append(f"delivered_at = ${param_num}")
            params.append(datetime.utcnow())
            param_num += 1
        elif key == "brief_data":
            set_clauses.append(f"brief_data = ${param_num}")
            params.append(json.dumps(value) if value else None)
            param_num += 1

    params.append(order_id)

    query = f"""
        UPDATE orders
        SET {', '.join(set_clauses)}
        WHERE id = ${param_num}
    """

    result = await Database.execute(query, *params)
    return "UPDATE 1" in result


async def get_stuck_orders(minutes_threshold: int = 10, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get orders that are paid but not delivered after threshold.
    Used by the Resurrection Loop.
    """
    rows = await Database.fetch_all(
        """
        SELECT id, session_id, brief_data, video_url, paid_at, updated_at
        FROM orders
        WHERE status = 'paid'
          AND delivered_at IS NULL
          AND updated_at < NOW() - INTERVAL '%s minutes'
        LIMIT $1
        """ % minutes_threshold,
        limit
    )

    results = []
    for row in rows:
        result = dict(row)
        if result.get("brief_data") and isinstance(result["brief_data"], str):
            result["brief_data"] = json.loads(result["brief_data"])
        # Calculate stuck duration
        if result.get("paid_at"):
            result["stuck_minutes"] = int(
                (datetime.utcnow() - result["paid_at"].replace(tzinfo=None)).total_seconds() / 60
            )
        results.append(result)

    return results


# =============================================================================
# ANALYTICS QUERIES
# =============================================================================

async def get_revenue_stats(days: int = 7) -> Dict[str, Any]:
    """Get revenue statistics"""

    # Today's revenue
    today_result = await Database.fetch_one(
        """
        SELECT COALESCE(SUM(amount_cents), 0) as total
        FROM orders
        WHERE status IN ('paid', 'delivered')
          AND paid_at >= CURRENT_DATE
        """
    )

    # This week's revenue
    week_result = await Database.fetch_one(
        """
        SELECT COALESCE(SUM(amount_cents), 0) as total
        FROM orders
        WHERE status IN ('paid', 'delivered')
          AND paid_at >= CURRENT_DATE - INTERVAL '%s days'
        """ % days
    )

    # Conversion rate (sessions with orders / total sessions)
    conversion_result = await Database.fetch_one(
        """
        SELECT
            COUNT(DISTINCT o.session_id)::float / NULLIF(COUNT(DISTINCT s.id), 0) as rate
        FROM sessions s
        LEFT JOIN orders o ON s.id = o.session_id AND o.status IN ('paid', 'delivered')
        WHERE s.created_at >= CURRENT_DATE - INTERVAL '%s days'
        """ % days
    )

    return {
        "today_cents": today_result["total"] if today_result else 0,
        "week_cents": week_result["total"] if week_result else 0,
        "conversion_rate": conversion_result["rate"] if conversion_result and conversion_result["rate"] else 0
    }


async def get_order_counts() -> Dict[str, int]:
    """Get order counts by status"""
    rows = await Database.fetch_all(
        """
        SELECT status, COUNT(*) as count
        FROM orders
        GROUP BY status
        """
    )

    return {row["status"]: row["count"] for row in rows}


async def get_agent_health_stats(hours: int = 24) -> Dict[str, Dict[str, Any]]:
    """Get error rates and latency for each agent"""

    agents = ["brief_assembler", "payment_gateway", "delivery_agent", "system"]
    stats = {}

    for agent in agents:
        # Error count
        error_result = await Database.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM system_events
            WHERE agent = $1
              AND severity IN ('ERROR', 'CRITICAL')
              AND timestamp >= NOW() - INTERVAL '%s hours'
            """ % hours,
            agent
        )

        # Total events
        total_result = await Database.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM system_events
            WHERE agent = $1
              AND timestamp >= NOW() - INTERVAL '%s hours'
            """ % hours,
            agent
        )

        total = total_result["count"] if total_result else 0
        errors = error_result["count"] if error_result else 0

        stats[agent] = {
            "total_events": total,
            "error_count": errors,
            "error_rate": errors / total if total > 0 else 0,
            "health_score": int((1 - (errors / total if total > 0 else 0)) * 100)
        }

    return stats


# =============================================================================
# DSPy LEARNING HOOK
# =============================================================================

async def on_payment_success(session_id: str, brief: Dict[str, Any]):
    """
    Called when payment succeeds - brief was "good enough" to convert.

    Phase 2: This will feed into DSPy optimizer to improve brief generation.
    """
    await log_event(
        session_id=session_id,
        event_type="BRIEF_CONVERSION_SUCCESS",
        payload={
            "brief_id": brief.get("id"),
            "tier": brief.get("tier"),
            "amount": brief.get("amount"),
            # Store for future training
            "brief_snapshot": brief
        },
        agent="system"
    )

    logger.info(
        "[LEARNING] Successful brief recorded",
        session_id=session_id[:8],
        tier=brief.get("tier")
    )

    # Phase 2: DSPy optimization
    # await train_brief_assembler_on_success(brief)


# =============================================================================
# INITIALIZATION
# =============================================================================

async def init_database():
    """Initialize database on app startup"""
    await Database.initialize()


async def close_database():
    """Close database on app shutdown"""
    await Database.close()


if __name__ == "__main__":
    # Test the module
    async def test():
        await init_database()

        # Create a test session
        session_id = await create_session()
        print(f"Created session: {session_id}")

        # Log an event
        event_id = await log_event(
            session_id=session_id,
            event_type="CARD_GENERATED",
            payload={"card_type": "persona", "confidence": 0.95},
            agent="brief_assembler"
        )
        print(f"Logged event: {event_id}")

        # Get session events
        events = await get_session_events(session_id)
        print(f"Session events: {len(events)}")

        await close_database()

    asyncio.run(test())
