"""
Resurrection Loop - The Safety Net
===================================
Background task that finds stuck orders (paid but not delivered)
and re-triggers the delivery pipeline.

This ensures no customer ever falls through the cracks.

Features:
- Runs every 5 minutes
- Finds orders stuck >10 minutes
- Re-triggers delivery agent
- Logs all resurrection attempts
- Configurable thresholds
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import structlog

from database import (
    log_event,
    get_stuck_orders,
    update_order_status,
    Database,
)

# Configure logger
logger = structlog.get_logger().bind(component="resurrection")


# =============================================================================
# CONFIGURATION
# =============================================================================

class ResurrectionConfig:
    """Resurrection loop configuration"""

    # How often to check for stuck orders (seconds)
    CHECK_INTERVAL = int(os.getenv("RESURRECTION_INTERVAL", "300"))  # 5 minutes

    # How long before an order is considered "stuck" (minutes)
    STUCK_THRESHOLD = int(os.getenv("RESURRECTION_THRESHOLD", "10"))  # 10 minutes

    # Maximum orders to process per cycle
    MAX_ORDERS_PER_CYCLE = int(os.getenv("RESURRECTION_BATCH_SIZE", "10"))

    # Maximum resurrection attempts before alerting
    MAX_ATTEMPTS = int(os.getenv("RESURRECTION_MAX_ATTEMPTS", "3"))

    # Enable/disable the resurrection loop
    ENABLED = os.getenv("RESURRECTION_ENABLED", "true").lower() == "true"


config = ResurrectionConfig()


# =============================================================================
# RESURRECTION LOGIC
# =============================================================================

async def trigger_resurrection(order_id: str, session_id: str, video_url: Optional[str] = None) -> bool:
    """
    Re-trigger delivery for a stuck order.

    This publishes a delivery.retry event to the event bus,
    which the Delivery Agent picks up.

    Args:
        order_id: The stuck order's ID
        session_id: Session ID for logging
        video_url: Video URL if already generated

    Returns:
        True if resurrection was triggered successfully
    """
    try:
        # Log the resurrection attempt
        await log_event(
            session_id=session_id,
            event_type="RESURRECTION_TRIGGERED",
            payload={
                "order_id": order_id,
                "video_url": video_url,
                "trigger_time": datetime.utcnow().isoformat(),
            },
            agent="resurrection",
            severity="WARN"
        )

        # Try to import and use event bus
        try:
            from pipeline.event_bus_adapter import EventBusAdapter

            event_bus = EventBusAdapter()
            await event_bus.connect()

            await event_bus.publish(
                "delivery.retry",
                {
                    "order_id": order_id,
                    "session_id": session_id,
                    "video_url": video_url,
                    "attempt": "resurrection",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            await event_bus.close()

            logger.warning(
                "Resurrection triggered via event bus",
                order_id=order_id[:8],
                session_id=session_id[:8],
            )
            return True

        except ImportError:
            # Event bus not available, update order status directly
            logger.warning(
                "Event bus not available, marking order for retry",
                order_id=order_id[:8],
            )

            # Mark order as needing retry
            await update_order_status(order_id, "retry_pending")
            return True

    except Exception as e:
        logger.error(
            "Resurrection failed",
            order_id=order_id[:8],
            error=str(e),
        )

        await log_event(
            session_id=session_id,
            event_type="AGENT_ERROR",
            payload={
                "order_id": order_id,
                "error": str(e),
                "context": "resurrection",
            },
            agent="resurrection",
            severity="ERROR"
        )

        return False


async def resurrection_loop():
    """
    Background task that runs every 5 minutes.
    Finds stuck orders and re-triggers delivery.

    This is "The Safety Net" - ensures no paid customer is left waiting.
    """
    logger.info(
        "Resurrection loop started",
        interval=config.CHECK_INTERVAL,
        threshold=config.STUCK_THRESHOLD,
        enabled=config.ENABLED,
    )

    if not config.ENABLED:
        logger.info("Resurrection loop disabled via config")
        return

    while True:
        try:
            # Find stuck orders
            stuck_orders = await get_stuck_orders(
                minutes_threshold=config.STUCK_THRESHOLD,
                limit=config.MAX_ORDERS_PER_CYCLE
            )

            if stuck_orders:
                logger.warning(
                    "Found stuck orders",
                    count=len(stuck_orders),
                )

                for order in stuck_orders:
                    order_id = str(order["id"])
                    session_id = str(order["session_id"])
                    video_url = order.get("video_url")
                    stuck_minutes = order.get("stuck_minutes", 0)

                    logger.info(
                        "Processing stuck order",
                        order_id=order_id[:8],
                        stuck_minutes=stuck_minutes,
                    )

                    # Check resurrection attempt count
                    attempts = await _get_resurrection_attempts(order_id)

                    if attempts >= config.MAX_ATTEMPTS:
                        # Too many attempts, escalate
                        await log_event(
                            session_id=session_id,
                            event_type="AGENT_ERROR",
                            payload={
                                "order_id": order_id,
                                "error": f"Max resurrection attempts ({config.MAX_ATTEMPTS}) exceeded",
                                "stuck_minutes": stuck_minutes,
                                "requires_manual_intervention": True,
                            },
                            agent="resurrection",
                            severity="CRITICAL"
                        )

                        logger.error(
                            "Order requires manual intervention",
                            order_id=order_id[:8],
                            attempts=attempts,
                        )
                        continue

                    # Trigger resurrection
                    success = await trigger_resurrection(order_id, session_id, video_url)

                    if success:
                        logger.info(
                            "Resurrection successful",
                            order_id=order_id[:8],
                            attempt=attempts + 1,
                        )
                    else:
                        logger.error(
                            "Resurrection failed",
                            order_id=order_id[:8],
                            attempt=attempts + 1,
                        )

                logger.info(
                    "Resurrection cycle complete",
                    processed=len(stuck_orders),
                )

        except Exception as e:
            logger.error(
                "Resurrection loop error",
                error=str(e),
            )

        # Sleep until next check
        await asyncio.sleep(config.CHECK_INTERVAL)


async def _get_resurrection_attempts(order_id: str) -> int:
    """Get the number of resurrection attempts for an order"""
    try:
        rows = await Database.fetch_all(
            """
            SELECT COUNT(*) as count
            FROM system_events
            WHERE event_type = 'RESURRECTION_TRIGGERED'
              AND payload->>'order_id' = $1
            """,
            order_id
        )
        return rows[0]["count"] if rows else 0
    except Exception:
        return 0


# =============================================================================
# MANUAL RESURRECTION (for admin dashboard)
# =============================================================================

async def manual_resurrection(order_id: str) -> dict:
    """
    Manually trigger resurrection for an order.
    Called from the admin dashboard.

    Returns:
        Status dict with result
    """
    from database import get_order

    order = await get_order(order_id)

    if not order:
        return {
            "success": False,
            "error": "Order not found",
        }

    if order["status"] not in ["paid", "retry_pending"]:
        return {
            "success": False,
            "error": f"Order status is '{order['status']}', cannot resurrect",
        }

    session_id = str(order["session_id"])
    video_url = order.get("video_url")

    success = await trigger_resurrection(order_id, session_id, video_url)

    return {
        "success": success,
        "order_id": order_id,
        "session_id": session_id,
        "message": "Resurrection triggered" if success else "Resurrection failed",
    }


# =============================================================================
# HEALTH CHECK
# =============================================================================

async def get_resurrection_stats() -> dict:
    """Get resurrection statistics for monitoring"""
    try:
        # Count stuck orders
        stuck = await get_stuck_orders(minutes_threshold=config.STUCK_THRESHOLD)

        # Count resurrection events in last 24 hours
        resurrections = await Database.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM system_events
            WHERE event_type = 'RESURRECTION_TRIGGERED'
              AND timestamp >= NOW() - INTERVAL '24 hours'
            """
        )

        # Count failed resurrections (orders stuck >30 min)
        critical = await get_stuck_orders(minutes_threshold=30)

        return {
            "enabled": config.ENABLED,
            "interval_seconds": config.CHECK_INTERVAL,
            "threshold_minutes": config.STUCK_THRESHOLD,
            "currently_stuck": len(stuck),
            "resurrections_24h": resurrections["count"] if resurrections else 0,
            "critical_stuck": len(critical),
        }

    except Exception as e:
        return {
            "enabled": config.ENABLED,
            "error": str(e),
        }


if __name__ == "__main__":
    # Test the resurrection loop
    async def test():
        from database import init_database

        await init_database()

        # Get stats
        stats = await get_resurrection_stats()
        print(f"Resurrection stats: {stats}")

        # Don't run the full loop in test mode
        print("Resurrection module loaded successfully")

    asyncio.run(test())
