-- ============================================================
-- TELEGRAM BOT DATABASE SCHEMA
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------
-- USERS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT PRIMARY KEY,          -- Telegram user_id
    username        VARCHAR(64),
    full_name       VARCHAR(256),
    is_admin        BOOLEAN DEFAULT FALSE,
    is_club_member  BOOLEAN DEFAULT FALSE,
    is_banned       BOOLEAN DEFAULT FALSE,
    joined_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ------------------------------------------------------------
-- POSTS  (news / polls / wishes)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posts (
    id              SERIAL PRIMARY KEY,
    uid             VARCHAR(12) UNIQUE NOT NULL,  -- human-readable ID e.g. NEWS-0001
    type            VARCHAR(16) NOT NULL CHECK (type IN ('news','poll','wish')),
    author_id       BIGINT REFERENCES users(id),
    title           VARCHAR(512),
    body            TEXT,
    tags            TEXT[],                        -- array of tags
    status          VARCHAR(16) DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','published')),
    channel_msg_id  BIGINT,                        -- message_id after publish
    channel_id      BIGINT,                        -- which channel published to
    comments_enabled BOOLEAN DEFAULT TRUE,
    is_club_only    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     BIGINT REFERENCES users(id),
    published_at    TIMESTAMPTZ
);

-- Full-text search index on title + body
CREATE INDEX IF NOT EXISTS posts_fts ON posts
    USING GIN (to_tsvector('russian', coalesce(title,'') || ' ' || coalesce(body,'')));
CREATE INDEX IF NOT EXISTS posts_uid  ON posts (uid);
CREATE INDEX IF NOT EXISTS posts_type ON posts (type);
CREATE INDEX IF NOT EXISTS posts_tags ON posts USING GIN (tags);

-- ------------------------------------------------------------
-- POLL OPTIONS  (for type='poll')
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS poll_options (
    id          SERIAL PRIMARY KEY,
    post_id     INT REFERENCES posts(id) ON DELETE CASCADE,
    option_text VARCHAR(100) NOT NULL,
    position    SMALLINT NOT NULL
);

-- ------------------------------------------------------------
-- SPAM REPORTS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS spam_reports (
    id              SERIAL PRIMARY KEY,
    channel_id      BIGINT NOT NULL,
    message_id      BIGINT NOT NULL,
    reported_by     BIGINT REFERENCES users(id),
    reason          VARCHAR(64) DEFAULT 'spam',   -- spam | rules_violation
    admin_notified  BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (channel_id, message_id, reported_by)  -- one report per user per msg
);

-- ------------------------------------------------------------
-- FAQ
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS faq (
    id          SERIAL PRIMARY KEY,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    keywords    TEXT[],         -- for keyword matching
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Full-text index on faq
CREATE INDEX IF NOT EXISTS faq_fts ON faq
    USING GIN (to_tsvector('russian', question || ' ' || answer));

-- ------------------------------------------------------------
-- CLUB VIDEOS  (private section)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS club_videos (
    id          SERIAL PRIMARY KEY,
    uid         VARCHAR(12) UNIQUE NOT NULL,
    title       VARCHAR(512),
    description TEXT,
    file_id     VARCHAR(256) NOT NULL,   -- Telegram file_id
    tags        TEXT[],
    added_by    BIGINT REFERENCES users(id),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ------------------------------------------------------------
-- BOT <-> CHANNEL REGISTRY
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS channels (
    id          BIGINT PRIMARY KEY,          -- Telegram chat_id (negative)
    title       VARCHAR(256),
    type        VARCHAR(16) CHECK (type IN ('news','poll','wish','club','general')),
    is_active   BOOLEAN DEFAULT TRUE,
    added_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ------------------------------------------------------------
-- SEQUENCE COUNTERS per type (for uid generation)
-- ------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS seq_news  START 1;
CREATE SEQUENCE IF NOT EXISTS seq_poll  START 1;
CREATE SEQUENCE IF NOT EXISTS seq_wish  START 1;
CREATE SEQUENCE IF NOT EXISTS seq_club  START 1;
