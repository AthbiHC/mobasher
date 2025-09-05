-- Mobasher Database Schema
-- PostgreSQL with TimescaleDB and pgvector extensions

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Channels table - Configuration for TV channels
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    headers JSONB DEFAULT '{}',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Recordings table - Track recording sessions per channel
CREATE TABLE IF NOT EXISTS recordings (
    id UUID DEFAULT uuid_generate_v4(),
    channel_id TEXT NOT NULL REFERENCES channels(id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'stopped')),
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, started_at)
);

-- Create hypertable for recordings (partitioned by started_at)
SELECT create_hypertable('recordings', 'started_at', if_not_exists => TRUE);

-- Segments table - Individual audio/video segments from recordings
-- Note: No foreign key to recordings hypertable due to TimescaleDB limitations
CREATE TABLE IF NOT EXISTS segments (
    id UUID DEFAULT uuid_generate_v4(),
    recording_id UUID NOT NULL, -- Reference to recordings.id (not enforced by FK)
    channel_id TEXT NOT NULL REFERENCES channels(id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    duration_seconds REAL GENERATED ALWAYS AS (EXTRACT(EPOCH FROM (ended_at - started_at))) STORED,
    audio_path TEXT NOT NULL,
    video_path TEXT,
    file_size_bytes BIGINT,
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN ('created', 'processing', 'completed', 'failed')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, started_at)
);

-- Create hypertable for segments (partitioned by started_at)
SELECT create_hypertable('segments', 'started_at', if_not_exists => TRUE);

-- Transcripts table - ASR results for segments
-- Regular table (not hypertable) to allow foreign keys
CREATE TABLE IF NOT EXISTS transcripts (
    segment_id UUID NOT NULL,
    segment_started_at TIMESTAMPTZ NOT NULL,
    language TEXT NOT NULL DEFAULT 'ar',
    text TEXT NOT NULL,
    words JSONB, -- Array of word-level timestamps and confidence
    confidence REAL,
    model_name TEXT NOT NULL,
    model_version TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (segment_id, segment_started_at)
    -- Note: Cannot use FK to hypertable, will enforce in application code
);

-- Embeddings table - Vector representations of transcript content
CREATE TABLE IF NOT EXISTS segment_embeddings (
    segment_id UUID NOT NULL,
    segment_started_at TIMESTAMPTZ NOT NULL,
    model_name TEXT NOT NULL,
    vector VECTOR(384), -- Adjust dimension based on model
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (segment_id, segment_started_at)
    -- Note: Cannot use FK to hypertable, will enforce in application code
);

-- Visual events table - Computer vision analysis results
CREATE TABLE IF NOT EXISTS visual_events (
    id UUID DEFAULT uuid_generate_v4(),
    segment_id UUID NOT NULL, -- Reference to segments.id
    segment_started_at TIMESTAMPTZ NOT NULL, -- Reference to segments.started_at
    channel_id TEXT NOT NULL REFERENCES channels(id),
    timestamp_offset REAL NOT NULL, -- Seconds from segment start
    event_type TEXT NOT NULL CHECK (event_type IN ('object', 'face', 'ocr', 'logo', 'scene_change')),
    bbox INTEGER[], -- [x, y, width, height] bounding box
    confidence REAL,
    data JSONB NOT NULL, -- Event-specific data (label, text, face_id, etc.)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
);

-- Create hypertable for visual_events
SELECT create_hypertable('visual_events', 'created_at', if_not_exists => TRUE);

-- System metrics table - For monitoring and health checks
CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    tags JSONB DEFAULT '{}',
    channel_id TEXT REFERENCES channels(id),
    PRIMARY KEY (id, timestamp)
);

-- Create hypertable for system_metrics
SELECT create_hypertable('system_metrics', 'timestamp', if_not_exists => TRUE);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_recordings_channel_time ON recordings(channel_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_segments_channel_time ON segments(channel_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_segments_recording ON segments(recording_id, started_at);
CREATE INDEX IF NOT EXISTS idx_transcripts_language ON transcripts(language);
CREATE INDEX IF NOT EXISTS idx_transcripts_segment ON transcripts(segment_id, segment_started_at);
CREATE INDEX IF NOT EXISTS idx_embeddings_segment ON segment_embeddings(segment_id, segment_started_at);
CREATE INDEX IF NOT EXISTS idx_visual_events_segment ON visual_events(segment_id, segment_started_at);
CREATE INDEX IF NOT EXISTS idx_visual_events_type ON visual_events(event_type);
CREATE INDEX IF NOT EXISTS idx_system_metrics_name ON system_metrics(metric_name, timestamp DESC);

-- Full-text search index for transcripts
CREATE INDEX IF NOT EXISTS idx_transcripts_text_search ON transcripts USING GIN(to_tsvector('arabic', text));

-- Vector similarity index for embeddings (create after inserting data)
-- CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON segment_embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);

-- Data retention policies (keep raw data for 30 days, compressed for 1 year)
SELECT add_retention_policy('recordings', INTERVAL '1 year');
SELECT add_retention_policy('segments', INTERVAL '1 year');
SELECT add_retention_policy('visual_events', INTERVAL '6 months');
SELECT add_retention_policy('system_metrics', INTERVAL '90 days');

-- Compression policies (compress data older than 7 days)
SELECT add_compression_policy('recordings', INTERVAL '7 days');
SELECT add_compression_policy('segments', INTERVAL '7 days');
SELECT add_compression_policy('visual_events', INTERVAL '3 days');
SELECT add_compression_policy('system_metrics', INTERVAL '1 day');

-- Insert default Kuwait TV channel
INSERT INTO channels (id, name, description, url, headers) VALUES (
    'kuwait1',
    'Kuwait TV 1',
    'Official Kuwait Television Channel 1',
    'https://kwtktv1ta.cdn.mangomolo.com/ktv1/smil:ktv1.stream.smil/chunklist.m3u8',
    '{"Referer": "https://www.elahmad.com/", "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}'
) ON CONFLICT (id) DO UPDATE SET
    url = EXCLUDED.url,
    headers = EXCLUDED.headers,
    updated_at = NOW();

-- Create views for common queries
CREATE OR REPLACE VIEW recent_segments AS
SELECT 
    s.id,
    s.channel_id,
    c.name as channel_name,
    s.started_at,
    s.ended_at,
    s.duration_seconds,
    s.status,
    t.text as transcript,
    t.confidence as transcript_confidence
FROM segments s
JOIN channels c ON s.channel_id = c.id
LEFT JOIN transcripts t ON s.id = t.segment_id AND s.started_at = t.segment_started_at
WHERE s.started_at >= NOW() - INTERVAL '24 hours'
ORDER BY s.started_at DESC;

CREATE OR REPLACE VIEW channel_stats AS
SELECT 
    c.id,
    c.name,
    COUNT(s.id) as total_segments,
    COUNT(t.segment_id) as transcribed_segments,
    AVG(t.confidence) as avg_confidence,
    MAX(s.started_at) as last_segment_time
FROM channels c
LEFT JOIN segments s ON c.id = s.channel_id AND s.started_at >= NOW() - INTERVAL '24 hours'
LEFT JOIN transcripts t ON s.id = t.segment_id AND s.started_at = t.segment_started_at
GROUP BY c.id, c.name;

-- Test the database setup
SELECT 'Database setup completed successfully' as status;
