"""database/db.py — asyncpg pool + all query helpers."""
from __future__ import annotations

import asyncpg
from typing import Optional, List, Dict, Any
from config import settings


_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ─── Users ────────────────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: str | None, full_name: str) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO users (id, username, full_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (id) DO UPDATE
          SET username = EXCLUDED.username,
              full_name = EXCLUDED.full_name,
              updated_at = NOW()
        """,
        user_id, username, full_name,
    )


async def get_user(user_id: int) -> asyncpg.Record | None:
    pool = await get_pool()
    return await pool.fetchrow("SELECT * FROM users WHERE id = $1", user_id)


async def set_admin(user_id: int, value: bool = True) -> None:
    pool = await get_pool()
    await pool.execute("UPDATE users SET is_admin=$1 WHERE id=$2", value, user_id)


async def set_club_member(user_id: int, value: bool = True) -> None:
    pool = await get_pool()
    await pool.execute("UPDATE users SET is_club_member=$1 WHERE id=$2", value, user_id)


async def is_admin(user_id: int) -> bool:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT is_admin FROM users WHERE id=$1", user_id)
    return bool(row and row["is_admin"])


async def is_club_member(user_id: int) -> bool:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT is_club_member FROM users WHERE id=$1", user_id)
    return bool(row and row["is_club_member"])


# ─── Posts ────────────────────────────────────────────────────────────────────

_TYPE_PREFIX = {"news": "NEWS", "poll": "POLL", "wish": "WISH"}
_TYPE_SEQ    = {"news": "seq_news", "poll": "seq_poll", "wish": "seq_wish"}


async def create_post(
    author_id: int,
    post_type: str,
    title: str,
    body: str,
    tags: list[str],
    poll_options: list[str] | None = None,
    is_club_only: bool = False,
) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        seq = await conn.fetchval(f"SELECT nextval('{_TYPE_SEQ[post_type]}')")
        uid = f"{_TYPE_PREFIX[post_type]}-{seq:04d}"
        comments_enabled = post_type != "poll"
        post_id = await conn.fetchval(
            """
            INSERT INTO posts
              (uid, type, author_id, title, body, tags, comments_enabled, is_club_only)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            RETURNING id
            """,
            uid, post_type, author_id, title, body, tags, comments_enabled, is_club_only,
        )
        if post_type == "poll" and poll_options:
            for pos, opt in enumerate(poll_options, 1):
                await conn.execute(
                    "INSERT INTO poll_options (post_id, option_text, position) VALUES ($1,$2,$3)",
                    post_id, opt, pos,
                )
    return uid


async def get_post_by_uid(uid: str) -> asyncpg.Record | None:
    pool = await get_pool()
    return await pool.fetchrow("SELECT * FROM posts WHERE uid=$1", uid.upper())


async def get_pending_posts() -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM posts WHERE status='pending' ORDER BY created_at"
    )


async def approve_post(uid: str, admin_id: int) -> asyncpg.Record | None:
    pool = await get_pool()
    return await pool.fetchrow(
        """
        UPDATE posts SET status='approved', reviewed_at=NOW(), reviewed_by=$2
        WHERE uid=$1 RETURNING *
        """,
        uid.upper(), admin_id,
    )


async def reject_post(uid: str, admin_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE posts SET status='rejected', reviewed_at=NOW(), reviewed_by=$2
        WHERE uid=$1
        """,
        uid.upper(), admin_id,
    )


async def mark_published(uid: str, channel_id: int, channel_msg_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE posts
        SET status='published', channel_id=$2, channel_msg_id=$3, published_at=NOW()
        WHERE uid=$1
        """,
        uid.upper(), channel_id, channel_msg_id,
    )


async def search_posts(query: str, post_type: str | None = None) -> list[asyncpg.Record]:
    pool = await get_pool()
    base = """
        SELECT *, ts_rank(to_tsvector('russian', coalesce(title,'') || ' ' || coalesce(body,'')),
                          plainto_tsquery('russian',$1)) AS rank
        FROM posts
        WHERE status='published'
          AND to_tsvector('russian', coalesce(title,'') || ' ' || coalesce(body,''))
              @@ plainto_tsquery('russian',$1)
    """
    if post_type:
        return await pool.fetch(base + " AND type=$2 ORDER BY rank DESC LIMIT 10", query, post_type)
    return await pool.fetch(base + " ORDER BY rank DESC LIMIT 10", query)


async def get_poll_options(post_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM poll_options WHERE post_id=$1 ORDER BY position", post_id
    )


# ─── Spam reports ─────────────────────────────────────────────────────────────

async def add_spam_report(
    channel_id: int, message_id: int, reported_by: int, reason: str = "spam"
) -> bool:
    """Returns True if inserted (first report by this user), False if duplicate."""
    pool = await get_pool()
    try:
        await pool.execute(
            """
            INSERT INTO spam_reports (channel_id, message_id, reported_by, reason)
            VALUES ($1,$2,$3,$4)
            """,
            channel_id, message_id, reported_by, reason,
        )
        return True
    except asyncpg.UniqueViolationError:
        return False


async def get_spam_reports(channel_id: int, message_id: int) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        "SELECT * FROM spam_reports WHERE channel_id=$1 AND message_id=$2",
        channel_id, message_id,
    )


# ─── FAQ ──────────────────────────────────────────────────────────────────────

async def get_all_faq() -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch("SELECT * FROM faq WHERE is_active=TRUE ORDER BY id")


async def search_faq(query: str) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(
        """
        SELECT *, ts_rank(to_tsvector('russian', question || ' ' || answer),
                          plainto_tsquery('russian',$1)) AS rank
        FROM faq
        WHERE is_active=TRUE
          AND to_tsvector('russian', question || ' ' || answer)
              @@ plainto_tsquery('russian',$1)
        ORDER BY rank DESC LIMIT 5
        """,
        query,
    )


async def add_faq(question: str, answer: str, keywords: list[str]) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO faq (question,answer,keywords) VALUES ($1,$2,$3) RETURNING id",
        question, answer, keywords,
    )
    return row["id"]


async def update_faq(faq_id: int, question: str, answer: str, keywords: list[str]) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        UPDATE faq SET question=$2, answer=$3, keywords=$4, updated_at=NOW()
        WHERE id=$1
        """,
        faq_id, question, answer, keywords,
    )


async def delete_faq(faq_id: int) -> None:
    pool = await get_pool()
    await pool.execute("UPDATE faq SET is_active=FALSE WHERE id=$1", faq_id)


# ─── Club videos ──────────────────────────────────────────────────────────────

async def add_club_video(
    title: str, description: str, file_id: str, tags: list[str], added_by: int
) -> str:
    pool = await get_pool()
    seq = await pool.fetchval("SELECT nextval('seq_club')")
    uid = f"VID-{seq:04d}"
    await pool.execute(
        """
        INSERT INTO club_videos (uid, title, description, file_id, tags, added_by)
        VALUES ($1,$2,$3,$4,$5,$6)
        """,
        uid, title, description, file_id, tags, added_by,
    )
    return uid


async def get_club_videos() -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch("SELECT * FROM club_videos ORDER BY created_at DESC")


# ─── Channels ─────────────────────────────────────────────────────────────────

async def register_channel(channel_id: int, title: str, channel_type: str) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO channels (id, title, type)
        VALUES ($1,$2,$3)
        ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title, type=EXCLUDED.type
        """,
        channel_id, title, channel_type,
    )


async def get_channel_by_type(channel_type: str) -> asyncpg.Record | None:
    pool = await get_pool()
    return await pool.fetchrow(
        "SELECT * FROM channels WHERE type=$1 AND is_active=TRUE LIMIT 1", channel_type
    )
