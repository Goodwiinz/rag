-- Migration 001: Create core user and organization tables
-- Multi-tenant foundation for the Multimodal Enterprise RAG System

BEGIN;

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Organizations table for multi-tenancy
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,

    -- Subscription and limits
    subscription_tier VARCHAR(50) DEFAULT 'starter' CHECK (subscription_tier IN ('starter', 'professional', 'enterprise')),
    storage_limit_gb INTEGER DEFAULT 5 CHECK (storage_limit_gb >= 0),
    max_users INTEGER DEFAULT 10 CHECK (max_users >= 0),
    max_documents_per_user INTEGER DEFAULT 100 CHECK (max_documents_per_user >= 0),

    -- Feature flags
    features_enabled JSONB DEFAULT '{}',

    -- Billing and usage
    current_storage_gb DECIMAL(10,2) DEFAULT 0,
    current_user_count INTEGER DEFAULT 0,
    current_document_count INTEGER DEFAULT 0,

    -- Metadata
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,

    CONSTRAINT org_storage_check CHECK (current_storage_gb <= storage_limit_gb)
);

-- Users table with organization-based multi-tenancy
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Basic information
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,

    -- Roles and permissions
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'content_manager', 'user', 'analyst')),
    permissions JSONB DEFAULT '[]',

    -- Status and activity
    is_active BOOLEAN DEFAULT TRUE,
    is_email_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    login_count INTEGER DEFAULT 0,

    -- Storage quota
    personal_storage_gb DECIMAL(10,2) DEFAULT 0,
    document_count INTEGER DEFAULT 0,

    -- Preferences
    preferences JSONB DEFAULT '{}',
    ui_settings JSONB DEFAULT '{}',

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,

    UNIQUE(organization_id, email)
);

-- User sessions for tracking and WebSocket management
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Session identifiers
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,

    -- Connection info
    ip_address INET,
    user_agent TEXT,
    device_fingerprint VARCHAR(255),

    -- Session data
    session_data JSONB DEFAULT '{}',
    websocket_connections JSONB DEFAULT '[]',

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    CONSTRAINT valid_expires_at CHECK (expires_at > created_at)
);

-- Create indexes for efficient querying
CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_tier ON organizations(subscription_tier);
CREATE INDEX idx_organizations_active ON organizations(is_deleted, created_at);

CREATE INDEX idx_users_organization ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(organization_id, role);
CREATE INDEX idx_users_active ON users(is_active, last_login_at);

CREATE INDEX idx_sessions_user ON user_sessions(user_id, last_activity DESC);
CREATE INDEX idx_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_sessions_active ON user_sessions(is_active, expires_at);
CREATE INDEX idx_sessions_organization ON user_sessions(organization_id, last_activity DESC);

-- Enable Row Level Security for multi-tenant isolation
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;

-- Create default organization for system initialization
INSERT INTO organizations (name, slug, subscription_tier, settings)
VALUES (
    'System Default Organization',
    'system-default',
    'enterprise',
    '{"is_system": true, "auto_approve_users": true}'
);

-- Create system admin user
INSERT INTO users (
    organization_id,
    email,
    password_hash,
    first_name,
    last_name,
    role,
    is_active,
    is_email_verified
)
SELECT
    id,
    'admin@system.local',
    crypt('change_me_immediately', gen_salt('bf')),
    'System',
    'Administrator',
    'admin',
    TRUE,
    TRUE
FROM organizations
WHERE slug = 'system-default';

COMMIT;