-- Initial database schema for production agent system
-- This migration creates all tables and indexes

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For full-text search

-- Try to enable TimescaleDB (optional, will fail gracefully if not available)
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'TimescaleDB extension not available, skipping';
END $$;

-- Try to enable pgvector (optional, for semantic search)
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector extension not available, skipping';
END $$;

-- Events table for agent processing queue
CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    visibility_timeout TIMESTAMPTZ,
    claimed_by VARCHAR(100),
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_visibility ON events(visibility_timeout);
CREATE INDEX idx_events_processing ON events(status, visibility_timeout);
CREATE INDEX idx_events_created_at ON events(created_at);

-- Slack users table
CREATE TABLE IF NOT EXISTS slack_users (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    real_name VARCHAR(100),
    email VARCHAR(255),
    is_bot BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    timezone VARCHAR(50),
    avatar_url TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_slack_users_name ON slack_users(name);
CREATE INDEX idx_slack_users_email ON slack_users(email);

-- Slack channels table
CREATE TABLE IF NOT EXISTS slack_channels (
    channel_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_private BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    topic TEXT,
    purpose TEXT,
    member_count INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_slack_channels_name ON slack_channels(name);
CREATE INDEX idx_slack_channels_archived ON slack_channels(is_archived);

-- Slack messages table
CREATE TABLE IF NOT EXISTS slack_messages (
    channel_id VARCHAR(50) NOT NULL REFERENCES slack_channels(channel_id),
    ts VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) REFERENCES slack_users(user_id),
    text TEXT,
    thread_ts VARCHAR(50),
    subtype VARCHAR(50),
    is_bot_message BOOLEAN DEFAULT FALSE,
    edited_ts VARCHAR(50),
    attachments JSONB,
    files JSONB,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (channel_id, ts)
);

CREATE INDEX idx_slack_messages_user_id ON slack_messages(user_id);
CREATE INDEX idx_slack_messages_thread_ts ON slack_messages(thread_ts);
CREATE INDEX idx_slack_messages_created_at ON slack_messages(created_at);
CREATE INDEX idx_slack_messages_text ON slack_messages USING gin(text gin_trgm_ops);

-- Convert slack_messages to hypertable if TimescaleDB is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable(
            'slack_messages',
            'created_at',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );

        -- Set up compression policy (compress chunks older than 45 days)
        PERFORM add_compression_policy(
            'slack_messages',
            INTERVAL '45 days',
            if_not_exists => TRUE
        );

        -- Enable compression
        ALTER TABLE slack_messages SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'channel_id'
        );

        RAISE NOTICE 'TimescaleDB hypertable created for slack_messages';
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Failed to create hypertable: %', SQLERRM;
END $$;

-- Slack reactions table
CREATE TABLE IF NOT EXISTS slack_reactions (
    id BIGSERIAL PRIMARY KEY,
    channel_id VARCHAR(50) NOT NULL,
    message_ts VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL REFERENCES slack_users(user_id),
    reaction VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_slack_reactions_message ON slack_reactions(channel_id, message_ts);
CREATE INDEX idx_slack_reactions_user ON slack_reactions(user_id);
CREATE UNIQUE INDEX idx_slack_reactions_unique ON slack_reactions(channel_id, message_ts, user_id, reaction);

-- Documentation embeddings table
CREATE TABLE IF NOT EXISTS documentation_embeddings (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    version VARCHAR(20),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT,
    embedding JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_documentation_embeddings_source ON documentation_embeddings(source, version);

-- If pgvector is available, add vector column and index
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        -- Add vector column if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'documentation_embeddings'
            AND column_name = 'embedding_vector'
        ) THEN
            ALTER TABLE documentation_embeddings ADD COLUMN embedding_vector vector(1536);

            -- Create IVFFlat index for fast vector similarity search
            CREATE INDEX idx_documentation_embeddings_vector
            ON documentation_embeddings
            USING ivfflat (embedding_vector vector_cosine_ops)
            WITH (lists = 100);

            RAISE NOTICE 'pgvector column and index created';
        END IF;
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Failed to add pgvector column: %', SQLERRM;
END $$;

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_slack_users_updated_at
    BEFORE UPDATE ON slack_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_slack_channels_updated_at
    BEFORE UPDATE ON slack_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_slack_messages_updated_at
    BEFORE UPDATE ON slack_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documentation_embeddings_updated_at
    BEFORE UPDATE ON documentation_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert system user for bot messages
INSERT INTO slack_users (user_id, name, real_name, is_bot, email)
VALUES ('SYSTEM', 'System', 'System Bot', TRUE, 'system@localhost')
ON CONFLICT (user_id) DO NOTHING;

COMMIT;
