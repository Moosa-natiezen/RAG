CREATE TABLE IF NOT EXISTS "user" (
    id text PRIMARY KEY,
    name text NOT NULL,
    email text NOT NULL UNIQUE,
    email_verified boolean NOT NULL DEFAULT false,
    image text,
    role text NOT NULL DEFAULT 'user',
    access_control_groups jsonb NOT NULL DEFAULT '["group_all"]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "session" (
    id text PRIMARY KEY,
    expires_at timestamptz NOT NULL,
    token text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    ip_address text,
    user_agent text,
    user_id text NOT NULL REFERENCES "user" (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS session_user_id_idx ON "session" (user_id);

CREATE TABLE IF NOT EXISTS "account" (
    id text PRIMARY KEY,
    account_id text NOT NULL,
    provider_id text NOT NULL,
    user_id text NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    access_token text,
    refresh_token text,
    id_token text,
    access_token_expires_at timestamptz,
    refresh_token_expires_at timestamptz,
    scope text,
    password text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS account_user_id_idx ON "account" (user_id);

CREATE TABLE IF NOT EXISTS verification (
    id text PRIMARY KEY,
    identifier text NOT NULL,
    value text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS verification_identifier_idx ON verification (identifier);

CREATE TABLE IF NOT EXISTS jwks (
    id text PRIMARY KEY,
    public_key text NOT NULL,
    private_key text NOT NULL,
    alg text NOT NULL,
    crv text,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz
);

CREATE TABLE IF NOT EXISTS auth_claim_audit (
    id uuid PRIMARY KEY,
    user_id text NOT NULL,
    session_id text,
    claims jsonb NOT NULL,
    method varchar(10) NOT NULL,
    path varchar(500) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_auth_claim_audit_user_created ON auth_claim_audit (user_id, created_at);

CREATE TABLE IF NOT EXISTS chat_conversations (
    id uuid PRIMARY KEY,
    user_id varchar(128) NOT NULL,
    session_id varchar(128),
    title varchar(300) NOT NULL DEFAULT 'New conversation',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_chat_conversations_user_id ON chat_conversations (user_id);
CREATE INDEX IF NOT EXISTS ix_chat_conversations_user_updated ON chat_conversations (user_id, updated_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    id uuid PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES chat_conversations (id) ON DELETE CASCADE,
    user_id varchar(128) NOT NULL,
    role varchar(16) NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    citations jsonb NOT NULL DEFAULT '[]'::jsonb,
    jwt_claims jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_chat_messages_conversation_created ON chat_messages (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS ix_chat_messages_user_created ON chat_messages (user_id, created_at);