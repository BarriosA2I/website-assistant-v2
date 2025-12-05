-- ============================================================================
-- Website Assistant v3 - Database Schema
-- ============================================================================
-- The Black Box - Unified persistence for all agents and events
-- Run this script to initialize a fresh database:
--   psql -U postgres -d website_assistant -f init.sql
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- SESSIONS TABLE
-- ============================================================================
-- Tracks all user chat sessions
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    stage VARCHAR(50) DEFAULT 'welcome',
    metadata JSONB DEFAULT '{}',

    -- Session state
    is_active BOOLEAN DEFAULT TRUE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Index for active sessions
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_sessions_stage ON sessions(stage);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);

-- ============================================================================
-- ORDERS TABLE
-- ============================================================================
-- Tracks all orders through the pipeline
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Order status
    status VARCHAR(50) DEFAULT 'pending',
    -- pending -> paid -> processing -> generating -> delivering -> delivered
    -- or: pending -> cancelled, paid -> refunded

    -- Payment info
    amount DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',
    stripe_payment_intent VARCHAR(255),
    stripe_customer_id VARCHAR(255),

    -- Product info
    video_url TEXT,
    video_duration_seconds INTEGER,

    -- Delivery info
    delivery_email VARCHAR(255),
    delivered_at TIMESTAMP WITH TIME ZONE,

    -- Error tracking
    last_error TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Indexes for orders
CREATE INDEX IF NOT EXISTS idx_orders_session ON orders(session_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_stripe_pi ON orders(stripe_payment_intent);

-- Index for stuck orders query
CREATE INDEX IF NOT EXISTS idx_orders_stuck ON orders(status, updated_at)
    WHERE status IN ('paid', 'processing', 'generating');

-- ============================================================================
-- SYSTEM_EVENTS TABLE (THE BLACK BOX)
-- ============================================================================
-- Unified event logging for all agents and system components
CREATE TABLE IF NOT EXISTS system_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Event identification
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    event_type VARCHAR(100) NOT NULL,

    -- Source
    agent VARCHAR(50),  -- agent1, agent2, agent3, resurrection, director, system

    -- Severity levels: DEBUG, INFO, WARN, ERROR, CRITICAL
    severity VARCHAR(20) DEFAULT 'INFO',

    -- Event payload (flexible JSON)
    payload JSONB DEFAULT '{}',

    -- Performance tracking
    duration_ms INTEGER,

    -- Correlation
    correlation_id UUID,
    parent_event_id UUID REFERENCES system_events(id)
);

-- Indexes for event queries
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON system_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_session ON system_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON system_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_agent ON system_events(agent);
CREATE INDEX IF NOT EXISTS idx_events_severity ON system_events(severity);
CREATE INDEX IF NOT EXISTS idx_events_correlation ON system_events(correlation_id);

-- Partial index for recent events (most common query)
CREATE INDEX IF NOT EXISTS idx_events_recent ON system_events(timestamp DESC)
    WHERE timestamp > NOW() - INTERVAL '24 hours';

-- ============================================================================
-- BRIEFS TABLE
-- ============================================================================
-- Stores video briefs created by Agent 1
CREATE TABLE IF NOT EXISTS briefs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Brief content
    company_name VARCHAR(255),
    tagline TEXT,
    usp TEXT,
    tone VARCHAR(50),
    target_audience TEXT,

    -- Validation
    is_validated BOOLEAN DEFAULT FALSE,
    validation_score DECIMAL(3, 2),
    validation_notes TEXT,

    -- Full brief JSON
    brief_data JSONB NOT NULL,

    -- Versioning
    version INTEGER DEFAULT 1,
    parent_brief_id UUID REFERENCES briefs(id)
);

CREATE INDEX IF NOT EXISTS idx_briefs_session ON briefs(session_id);
CREATE INDEX IF NOT EXISTS idx_briefs_order ON briefs(order_id);

-- ============================================================================
-- CARDS TABLE
-- ============================================================================
-- Stores generated video cards/previews
CREATE TABLE IF NOT EXISTS cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    brief_id UUID REFERENCES briefs(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Card content
    title VARCHAR(255),
    description TEXT,
    thumbnail_url TEXT,
    preview_url TEXT,

    -- User interaction
    is_approved BOOLEAN DEFAULT FALSE,
    approved_at TIMESTAMP WITH TIME ZONE,

    -- Generation metadata
    generation_params JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_cards_session ON cards(session_id);
CREATE INDEX IF NOT EXISTS idx_cards_brief ON cards(brief_id);

-- ============================================================================
-- DSPY_EXAMPLES TABLE
-- ============================================================================
-- Stores successful examples for DSPy learning
CREATE TABLE IF NOT EXISTS dspy_examples (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Example type
    example_type VARCHAR(50) NOT NULL,  -- brief_generation, card_approval, etc.

    -- Input/Output
    input_data JSONB NOT NULL,
    output_data JSONB NOT NULL,

    -- Quality metrics
    success_score DECIMAL(3, 2),
    was_edited BOOLEAN DEFAULT FALSE,

    -- Source
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    agent VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_dspy_type ON dspy_examples(example_type);
CREATE INDEX IF NOT EXISTS idx_dspy_score ON dspy_examples(success_score DESC);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to sessions
DROP TRIGGER IF EXISTS sessions_updated_at ON sessions;
CREATE TRIGGER sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Apply trigger to orders
DROP TRIGGER IF EXISTS orders_updated_at ON orders;
CREATE TRIGGER orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View for stuck orders (used by resurrection loop)
CREATE OR REPLACE VIEW stuck_orders AS
SELECT
    o.id,
    o.session_id,
    o.status,
    o.video_url,
    o.created_at,
    o.updated_at,
    EXTRACT(EPOCH FROM (NOW() - o.updated_at))/60 as stuck_minutes
FROM orders o
WHERE o.status IN ('paid', 'processing', 'generating')
  AND o.updated_at < NOW() - INTERVAL '10 minutes'
ORDER BY o.updated_at ASC;

-- View for revenue stats
CREATE OR REPLACE VIEW revenue_stats AS
SELECT
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE) as today_orders,
    COALESCE(SUM(amount) FILTER (WHERE created_at >= CURRENT_DATE), 0) as today_revenue,
    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days') as week_orders,
    COALESCE(SUM(amount) FILTER (WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'), 0) as week_revenue,
    COALESCE(AVG(amount) FILTER (WHERE status = 'delivered'), 0) as average_order_value
FROM orders
WHERE status IN ('paid', 'processing', 'generating', 'delivering', 'delivered');

-- View for session funnel
CREATE OR REPLACE VIEW session_funnel AS
SELECT
    stage,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as last_24h
FROM sessions
GROUP BY stage
ORDER BY
    CASE stage
        WHEN 'welcome' THEN 1
        WHEN 'discovery' THEN 2
        WHEN 'card_review' THEN 3
        WHEN 'checkout' THEN 4
        WHEN 'payment' THEN 5
        WHEN 'generating' THEN 6
        WHEN 'delivered' THEN 7
        WHEN 'completed' THEN 8
        ELSE 99
    END;

-- ============================================================================
-- INITIAL DATA (Optional)
-- ============================================================================

-- Insert a test session (commented out for production)
-- INSERT INTO sessions (stage, metadata) VALUES ('welcome', '{"source": "init_script"}');

-- ============================================================================
-- GRANTS (Adjust for your database user)
-- ============================================================================

-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO website_assistant;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO website_assistant;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO website_assistant;

-- ============================================================================
-- DONE
-- ============================================================================
-- Run: psql -U postgres -d website_assistant -f init.sql
-- Or in Python: await Database.execute(open('sql/init.sql').read())
