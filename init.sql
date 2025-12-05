-- =============================================================================
-- BARRIOS A2I - DATABASE INITIALIZATION
-- =============================================================================

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY,
    brief_id VARCHAR(50) NOT NULL,
    session_id VARCHAR(100),
    correlation_id UUID NOT NULL,
    
    -- Customer
    business_name VARCHAR(255),
    contact_email VARCHAR(255) NOT NULL,
    
    -- Payment
    payment_tier VARCHAR(50) NOT NULL,
    amount_paid INTEGER NOT NULL,
    stripe_session_id VARCHAR(100),
    stripe_payment_intent_id VARCHAR(100),
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    paid_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    
    -- Optimistic locking
    version INTEGER DEFAULT 1
);

CREATE INDEX idx_orders_brief_id ON orders(brief_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_email ON orders(contact_email);

-- Briefs table
CREATE TABLE IF NOT EXISTS briefs (
    id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(100),
    correlation_id UUID NOT NULL,
    
    -- Brief content
    business_name VARCHAR(255),
    contact_email VARCHAR(255),
    payment_tier VARCHAR(50),
    quoted_price INTEGER,
    duration_seconds INTEGER,
    
    -- Quality
    confidence_score FLOAT,
    quality_grade VARCHAR(5),
    
    -- Full brief JSON
    creative_brief JSONB,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_briefs_session ON briefs(session_id);
CREATE INDEX idx_briefs_status ON briefs(status);

-- Delivery tokens table
CREATE TABLE IF NOT EXISTS delivery_tokens (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    
    -- Token (hashed)
    token_hash VARCHAR(64) NOT NULL,
    
    -- Limits
    max_downloads INTEGER DEFAULT 10,
    download_count INTEGER DEFAULT 0,
    
    -- Expiration
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Status
    revoked BOOLEAN DEFAULT FALSE,
    revoked_reason VARCHAR(255),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tokens_order ON delivery_tokens(order_id);
CREATE INDEX idx_tokens_hash ON delivery_tokens(token_hash);

-- Download attempts table
CREATE TABLE IF NOT EXISTS download_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id UUID REFERENCES delivery_tokens(id),
    order_id UUID REFERENCES orders(id),
    
    -- Request info
    ip_address INET,
    user_agent TEXT,
    referer TEXT,
    
    -- Result
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(255),
    
    -- Timestamps
    attempted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_downloads_token ON download_attempts(token_id);
CREATE INDEX idx_downloads_order ON download_attempts(order_id);
CREATE INDEX idx_downloads_time ON download_attempts(attempted_at);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID,
    
    -- What changed
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    
    -- Change details
    old_value JSONB,
    new_value JSONB,
    
    -- Who/what made the change
    actor VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_correlation ON audit_log(correlation_id);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_time ON audit_log(created_at);

-- Idempotency keys table
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key VARCHAR(255) PRIMARY KEY,
    
    -- State
    status VARCHAR(20) NOT NULL DEFAULT 'processing',
    result JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_idempotency_status ON idempotency_keys(status);

-- Dead letter queue table
CREATE TABLE IF NOT EXISTS dead_letters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Event info
    event_type VARCHAR(100) NOT NULL,
    event_id UUID,
    correlation_id UUID,
    
    -- Failure info
    error_message TEXT,
    attempt_count INTEGER DEFAULT 0,
    
    -- Payload
    payload JSONB NOT NULL,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'failed',
    retried_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_dlq_status ON dead_letters(status);
CREATE INDEX idx_dlq_event_type ON dead_letters(event_type);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to relevant tables
CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_briefs_updated_at
    BEFORE UPDATE ON briefs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO barrios;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO barrios;
