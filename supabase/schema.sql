-- SiteSense AI — Supabase Database Schema
-- Run this in the Supabase SQL Editor once.

-- 1. EXTENSIONS
-- Enable UUID-v4 generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. TRIGGER FUNCTIONS
-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';


-- 3. TABLES

-- TENANTS TABLE
-- Each tenant is an AI chatbot bot belonging to a user (owner).
CREATE TABLE tenants (
    id                  UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id             UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    bot_id              TEXT UNIQUE NOT NULL, -- 8-char random public ID
    bot_name            TEXT NOT NULL DEFAULT 'AI Assistant',
    welcome_message    TEXT DEFAULT 'Hi! How can I help you?',
    fallback_message   TEXT DEFAULT 'I don''t have information on that topic.',
    primary_color      TEXT DEFAULT '#2563eb',
    system_prompt      TEXT DEFAULT '',
    allowed_origins    JSONB DEFAULT '[]'::jsonb,
    llm_provider       TEXT DEFAULT 'claude',
    llm_model          TEXT DEFAULT 'claude-haiku-4-5-20251001',
    suggested_questions JSONB DEFAULT '[]'::jsonb,
    is_active          BOOLEAN DEFAULT TRUE,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

-- SOURCES TABLE
-- Documents scraped or uploaded for 
CREATE TABLE sources (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type            TEXT NOT NULL, -- 'web', 'file', etc.
    name            TEXT NOT NULL,
    location        TEXT NOT NULL, -- URL or file path
    file_path       TEXT DEFAULT '',
    status          TEXT DEFAULT 'pending', -- 'pending', 'indexing', 'indexed', 'error'
    chunk_count     INTEGER DEFAULT 0,
    content_hash    TEXT DEFAULT '',
    error_message   TEXT DEFAULT '',
    last_indexed    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- CONVERSATIONS TABLE
-- Logs of Q&A interactions.
CREATE TABLE conversations (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    session_id      TEXT NOT NULL,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    sources_used    JSONB DEFAULT '[]'::jsonb,
    was_answered    BOOLEAN DEFAULT FALSE,
    confidence      TEXT DEFAULT 'low',
    response_type   TEXT DEFAULT 'fallback',
    tokens_used     INTEGER DEFAULT 0,
    llm_provider    TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- LEADS TABLE
-- Captured visitor contact information.
CREATE TABLE leads (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    session_id      TEXT NOT NULL,
    name            TEXT DEFAULT '',
    email           TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- USER_API_KEYS TABLE (NEW)
-- Stores encrypted keys for custom LLM providers.
CREATE TABLE user_api_keys (
    id            UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id       UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    provider      TEXT NOT NULL CHECK (provider IN ('anthropic','gemini','mistral','voyage','openai')),
    key_preview   TEXT NOT NULL, -- e.g., sk-proj...abcd
    key_encrypted TEXT NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);


-- 4. ROW LEVEL SECURITY (RLS)
-- All tables are private by default.

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_api_keys ENABLE ROW LEVEL SECURITY;

-- POLICIES

-- Tenants: users see only their own data
CREATE POLICY "Users can manage their own tenants" ON tenants
    FOR ALL USING (auth.uid() = user_id);

-- Sources, Conversations, Leads: linked to owned tenants
CREATE POLICY "Users can manage sources of their tenants" ON sources
    FOR ALL USING (tenant_id IN (SELECT id FROM tenants WHERE user_id = auth.uid()));

CREATE POLICY "Users can manage conversations of their tenants" ON conversations
    FOR ALL USING (tenant_id IN (SELECT id FROM tenants WHERE user_id = auth.uid()));

CREATE POLICY "Users can manage leads of their tenants" ON leads
    FOR ALL USING (tenant_id IN (SELECT id FROM tenants WHERE user_id = auth.uid()));

-- user_api_keys: users see only their own keys
CREATE POLICY "Users can manage their own API keys" ON user_api_keys
    FOR ALL USING (auth.uid() = user_id);


-- 5. INDEXES
-- Performance optimizations for common queries

CREATE INDEX idx_tenants_user_id ON tenants(user_id);
CREATE INDEX idx_tenants_bot_id ON tenants(bot_id);
CREATE INDEX idx_sources_tenant_id ON sources(tenant_id);
CREATE INDEX idx_sources_status ON sources(status);
CREATE INDEX idx_conversations_tenant_id ON conversations(tenant_id);
CREATE INDEX idx_conversations_session_id ON conversations(session_id);
CREATE INDEX idx_leads_tenant_id ON leads(tenant_id);
CREATE INDEX idx_user_api_keys_user_id ON user_api_keys(user_id);


-- 6. TRIGGERS
-- Auto-update updated_at for tenants
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
