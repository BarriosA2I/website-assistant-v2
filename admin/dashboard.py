"""
The Watchtower - Admin Dashboard
================================
Streamlit-based admin dashboard for Website Assistant v3.

Features:
- Revenue metrics (today, week, conversion)
- Active/stuck orders monitoring
- Manual resurrection button
- Agent health status
- Event log viewer

Run: streamlit run admin/dashboard.py
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import streamlit as st
import pandas as pd

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import (
    Database,
    get_session,
    get_order,
    get_stuck_orders,
    get_revenue_stats,
    get_session_analytics,
    log_event,
)
from tasks.resurrection import manual_resurrection, get_resurrection_stats


# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Website Assistant - The Watchtower",
    page_icon="🗼",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# STYLING
# =============================================================================

st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 10px;
        padding: 20px;
        border: 1px solid #0f3460;
    }
    .status-healthy { color: #00ff88; }
    .status-warning { color: #ffaa00; }
    .status-critical { color: #ff4444; }
    .resurrection-btn {
        background-color: #ff6b35;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 5px;
        cursor: pointer;
    }
    .event-info { background-color: #1e3a5f; }
    .event-warn { background-color: #5f4a1e; }
    .event-error { background-color: #5f1e1e; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# ASYNC HELPERS
# =============================================================================

def run_async(coro):
    """Run async function in sync context for Streamlit."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# =============================================================================
# DATA FETCHING
# =============================================================================

@st.cache_data(ttl=30)
def fetch_revenue_stats():
    """Fetch revenue statistics with 30s cache."""
    try:
        return run_async(get_revenue_stats())
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=10)
def fetch_stuck_orders():
    """Fetch stuck orders with 10s cache."""
    try:
        return run_async(get_stuck_orders(minutes_threshold=10))
    except Exception as e:
        return []


@st.cache_data(ttl=30)
def fetch_session_analytics():
    """Fetch session analytics with 30s cache."""
    try:
        return run_async(get_session_analytics(days=7))
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=30)
def fetch_resurrection_stats():
    """Fetch resurrection statistics."""
    try:
        return run_async(get_resurrection_stats())
    except Exception as e:
        return {"error": str(e)}


def fetch_recent_events(limit: int = 50) -> List[Dict]:
    """Fetch recent system events."""
    try:
        return run_async(_get_recent_events(limit))
    except Exception as e:
        return []


async def _get_recent_events(limit: int) -> List[Dict]:
    """Get recent events from database."""
    rows = await Database.fetch_all(
        """
        SELECT id, session_id, event_type, agent, severity, payload, timestamp
        FROM system_events
        ORDER BY timestamp DESC
        LIMIT $1
        """,
        limit
    )
    return [dict(row) for row in rows] if rows else []


def fetch_active_orders() -> List[Dict]:
    """Fetch currently active orders."""
    try:
        return run_async(_get_active_orders())
    except Exception as e:
        return []


async def _get_active_orders() -> List[Dict]:
    """Get active orders from database."""
    rows = await Database.fetch_all(
        """
        SELECT
            id, session_id, status, amount,
            video_url, created_at, updated_at,
            EXTRACT(EPOCH FROM (NOW() - created_at))/60 as age_minutes
        FROM orders
        WHERE status NOT IN ('delivered', 'refunded', 'cancelled')
        ORDER BY created_at DESC
        LIMIT 100
        """
    )
    return [dict(row) for row in rows] if rows else []


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar():
    """Render sidebar with navigation and quick stats."""
    st.sidebar.title("🗼 The Watchtower")
    st.sidebar.markdown("---")

    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["📊 Revenue Dashboard", "📦 Active Orders", "🔄 Resurrection Queue", "💚 Agent Health", "📜 Event Log"],
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")

    # Quick Stats
    st.sidebar.subheader("Quick Stats")

    resurrection_stats = fetch_resurrection_stats()
    if "error" not in resurrection_stats:
        st.sidebar.metric("Currently Stuck", resurrection_stats.get("currently_stuck", 0))
        st.sidebar.metric("Resurrections (24h)", resurrection_stats.get("resurrections_24h", 0))
        if resurrection_stats.get("critical_stuck", 0) > 0:
            st.sidebar.error(f"⚠️ {resurrection_stats['critical_stuck']} critical orders!")

    st.sidebar.markdown("---")

    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)
    if auto_refresh:
        st.sidebar.info("Page will refresh every 30 seconds")

    return page, auto_refresh


# =============================================================================
# REVENUE DASHBOARD
# =============================================================================

def render_revenue_dashboard():
    """Render the revenue dashboard page."""
    st.title("📊 Revenue Dashboard")
    st.markdown("Real-time revenue and conversion metrics")

    stats = fetch_revenue_stats()

    if "error" in stats:
        st.error(f"Error fetching stats: {stats['error']}")
        return

    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "💰 Today's Revenue",
            f"${stats.get('today_revenue', 0):,.2f}",
            delta=f"{stats.get('today_orders', 0)} orders"
        )

    with col2:
        st.metric(
            "📅 This Week",
            f"${stats.get('week_revenue', 0):,.2f}",
            delta=f"{stats.get('week_orders', 0)} orders"
        )

    with col3:
        conversion = stats.get('conversion_rate', 0)
        st.metric(
            "🎯 Conversion Rate",
            f"{conversion:.1f}%",
            delta="Good" if conversion > 5 else "Needs work"
        )

    with col4:
        aov = stats.get('average_order_value', 0)
        st.metric(
            "💵 Avg Order Value",
            f"${aov:,.2f}"
        )

    st.markdown("---")

    # Session analytics
    st.subheader("📈 Session Analytics (7 days)")

    session_stats = fetch_session_analytics()

    if "error" not in session_stats:
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Sessions", session_stats.get("total_sessions", 0))

        with col2:
            st.metric("Completed Sessions", session_stats.get("completed_sessions", 0))

        with col3:
            st.metric("Avg Duration", f"{session_stats.get('avg_duration_minutes', 0):.1f} min")

        # Show funnel
        st.subheader("🔄 Conversion Funnel")
        funnel_data = session_stats.get("stage_breakdown", {})
        if funnel_data:
            df = pd.DataFrame(list(funnel_data.items()), columns=["Stage", "Count"])
            st.bar_chart(df.set_index("Stage"))
    else:
        st.warning("Session analytics unavailable")


# =============================================================================
# ACTIVE ORDERS
# =============================================================================

def render_active_orders():
    """Render the active orders page."""
    st.title("📦 Active Orders")
    st.markdown("Currently processing orders")

    orders = fetch_active_orders()

    if not orders:
        st.info("No active orders at the moment")
        return

    # Status breakdown
    status_counts = {}
    for order in orders:
        status = order.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    cols = st.columns(len(status_counts))
    for i, (status, count) in enumerate(status_counts.items()):
        with cols[i]:
            emoji = {
                "pending": "⏳",
                "paid": "💳",
                "processing": "⚙️",
                "generating": "🎬",
                "delivering": "📬",
            }.get(status, "📦")
            st.metric(f"{emoji} {status.title()}", count)

    st.markdown("---")

    # Orders table
    df = pd.DataFrame(orders)
    df["age_minutes"] = df["age_minutes"].round(1)
    df["amount"] = df["amount"].apply(lambda x: f"${x:,.2f}" if x else "-")
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")

    # Highlight stuck orders
    def highlight_stuck(row):
        if row["age_minutes"] > 10 and row["status"] in ["paid", "processing"]:
            return ["background-color: #5f1e1e"] * len(row)
        return [""] * len(row)

    display_cols = ["id", "status", "amount", "age_minutes", "created_at"]
    st.dataframe(
        df[display_cols].style.apply(highlight_stuck, axis=1),
        use_container_width=True,
        hide_index=True
    )


# =============================================================================
# RESURRECTION QUEUE
# =============================================================================

def render_resurrection_queue():
    """Render the resurrection queue page."""
    st.title("🔄 Resurrection Queue")
    st.markdown("Orders stuck in limbo - ready for resurrection")

    # Resurrection stats
    stats = fetch_resurrection_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        enabled = stats.get("enabled", False)
        st.metric(
            "Loop Status",
            "🟢 Enabled" if enabled else "🔴 Disabled"
        )

    with col2:
        st.metric("Check Interval", f"{stats.get('interval_seconds', 300)}s")

    with col3:
        st.metric("Stuck Threshold", f"{stats.get('threshold_minutes', 10)} min")

    with col4:
        st.metric("Critical (>30min)", stats.get("critical_stuck", 0))

    st.markdown("---")

    # Stuck orders
    stuck_orders = fetch_stuck_orders()

    if not stuck_orders:
        st.success("✅ No stuck orders! Everything is flowing smoothly.")
        return

    st.warning(f"⚠️ {len(stuck_orders)} orders need attention")

    # Display each stuck order with resurrection button
    for order in stuck_orders:
        order_id = str(order.get("id", ""))[:8]
        stuck_minutes = order.get("stuck_minutes", 0)
        status = order.get("status", "unknown")

        with st.expander(f"Order {order_id}... - Stuck {stuck_minutes:.0f} min"):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.write(f"**Status:** {status}")
                st.write(f"**Session:** {str(order.get('session_id', ''))[:8]}...")
                st.write(f"**Video URL:** {order.get('video_url', 'Not generated')}")
                st.write(f"**Stuck Since:** {stuck_minutes:.1f} minutes")

            with col2:
                if st.button(f"🔄 Resurrect", key=f"resurrect_{order_id}"):
                    with st.spinner("Triggering resurrection..."):
                        result = run_async(manual_resurrection(str(order.get("id"))))
                        if result.get("success"):
                            st.success("Resurrection triggered!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"Failed: {result.get('error')}")


# =============================================================================
# AGENT HEALTH
# =============================================================================

def render_agent_health():
    """Render the agent health page."""
    st.title("💚 Agent Health")
    st.markdown("Status of all pipeline agents and services")

    # Define agents and their expected status
    agents = [
        {"name": "Brief Assembler", "id": "agent1", "emoji": "📋"},
        {"name": "Payment Gateway", "id": "agent2", "emoji": "💳"},
        {"name": "Delivery Agent", "id": "agent3", "emoji": "📬"},
        {"name": "Resurrection Loop", "id": "resurrection", "emoji": "🔄"},
        {"name": "Event Bus", "id": "event_bus", "emoji": "📡"},
        {"name": "Database", "id": "database", "emoji": "🗄️"},
    ]

    # Check each agent's recent activity
    for agent in agents:
        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            st.write(f"### {agent['emoji']}")

        with col2:
            st.write(f"**{agent['name']}**")

            # Check recent events for this agent
            recent = run_async(_check_agent_activity(agent["id"]))
            if recent.get("active"):
                st.write(f"🟢 Active - Last seen: {recent.get('last_seen', 'Unknown')}")
            elif recent.get("error"):
                st.write(f"🔴 Error - {recent.get('error')}")
            else:
                st.write("⚪ No recent activity")

        with col3:
            if recent.get("event_count", 0) > 0:
                st.metric("Events (1h)", recent["event_count"])

        st.markdown("---")

    # Service dependencies
    st.subheader("🔗 Service Dependencies")

    services = [
        {"name": "PostgreSQL", "check": "Database connection"},
        {"name": "Redis", "check": "Cache connection"},
        {"name": "RabbitMQ", "check": "Event bus connection"},
    ]

    for service in services:
        status = run_async(_check_service(service["name"]))
        icon = "🟢" if status["healthy"] else "🔴"
        st.write(f"{icon} **{service['name']}** - {status.get('message', 'Unknown')}")


async def _check_agent_activity(agent_id: str) -> Dict:
    """Check recent activity for an agent."""
    try:
        row = await Database.fetch_one(
            """
            SELECT
                COUNT(*) as event_count,
                MAX(timestamp) as last_event
            FROM system_events
            WHERE agent = $1
              AND timestamp >= NOW() - INTERVAL '1 hour'
            """,
            agent_id
        )

        if row and row["event_count"] > 0:
            return {
                "active": True,
                "event_count": row["event_count"],
                "last_seen": row["last_event"].strftime("%H:%M:%S") if row["last_event"] else "Unknown"
            }
        return {"active": False, "event_count": 0}
    except Exception as e:
        return {"error": str(e)}


async def _check_service(service_name: str) -> Dict:
    """Check if a service is healthy."""
    try:
        if service_name == "PostgreSQL":
            result = await Database.fetch_one("SELECT 1")
            return {"healthy": True, "message": "Connected"}
        elif service_name == "Redis":
            # Would check Redis connection here
            return {"healthy": True, "message": "Connected (assumed)"}
        elif service_name == "RabbitMQ":
            # Would check RabbitMQ connection here
            return {"healthy": True, "message": "Connected (assumed)"}
        return {"healthy": False, "message": "Unknown service"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


# =============================================================================
# EVENT LOG
# =============================================================================

def render_event_log():
    """Render the event log page."""
    st.title("📜 Event Log")
    st.markdown("Real-time system events from The Black Box")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        severity_filter = st.selectbox(
            "Severity",
            ["All", "INFO", "WARN", "ERROR", "CRITICAL"]
        )

    with col2:
        agent_filter = st.selectbox(
            "Agent",
            ["All", "agent1", "agent2", "agent3", "resurrection", "director", "system"]
        )

    with col3:
        limit = st.slider("Show last", 10, 200, 50)

    # Fetch events
    events = fetch_recent_events(limit)

    if not events:
        st.info("No events found")
        return

    # Filter events
    if severity_filter != "All":
        events = [e for e in events if e.get("severity") == severity_filter]
    if agent_filter != "All":
        events = [e for e in events if e.get("agent") == agent_filter]

    # Display events
    for event in events:
        severity = event.get("severity", "INFO")
        color_class = {
            "INFO": "event-info",
            "WARN": "event-warn",
            "ERROR": "event-error",
            "CRITICAL": "event-error"
        }.get(severity, "event-info")

        emoji = {
            "INFO": "ℹ️",
            "WARN": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }.get(severity, "📝")

        timestamp = event.get("timestamp")
        if timestamp:
            time_str = timestamp.strftime("%H:%M:%S")
        else:
            time_str = "Unknown"

        with st.container():
            col1, col2, col3, col4 = st.columns([1, 2, 2, 1])

            with col1:
                st.write(f"{emoji} {time_str}")

            with col2:
                st.write(f"**{event.get('event_type', 'UNKNOWN')}**")

            with col3:
                st.write(f"Agent: {event.get('agent', '-')}")

            with col4:
                session_id = event.get("session_id", "")
                if session_id:
                    st.write(f"Session: {str(session_id)[:8]}...")

            # Expandable payload
            payload = event.get("payload", {})
            if payload:
                with st.expander("View Payload"):
                    st.json(payload)

            st.markdown("---")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main dashboard entry point."""
    # Initialize database connection
    try:
        run_async(Database.connect())
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.info("Make sure PostgreSQL is running and DATABASE_URL is set")
        return

    # Render sidebar and get selected page
    page, auto_refresh = render_sidebar()

    # Render selected page
    if page == "📊 Revenue Dashboard":
        render_revenue_dashboard()
    elif page == "📦 Active Orders":
        render_active_orders()
    elif page == "🔄 Resurrection Queue":
        render_resurrection_queue()
    elif page == "💚 Agent Health":
        render_agent_health()
    elif page == "📜 Event Log":
        render_event_log()

    # Auto-refresh
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()


if __name__ == "__main__":
    main()
