"""services/publisher.py — format and send approved posts to Telegram channels."""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramRetryAfter
import asyncio

from database import db
from keyboards.kb import channel_report_kb
from config import settings


_TYPE_TO_CHANNEL = {
    "news": settings.CHANNEL_NEWS,
    "poll": settings.CHANNEL_POLL,
    "wish": settings.CHANNEL_WISH,
}

_TYPE_EMOJI = {"news": "📰", "poll": "📊", "wish": "💫"}


def _format_post(post: dict) -> str:
    emoji  = _TYPE_EMOJI.get(post["type"], "📄")
    title  = post.get("title", "").strip()
    body   = post.get("body", "").strip()
    tags   = post.get("tags") or []
    uid    = post["uid"]

    tag_line = " ".join(f"#{t.strip('#')}" for t in tags) if tags else ""

    parts = [f"{emoji} <b>{title}</b>"] if title else [f"{emoji} <b>Без заголовка</b>"]
    if body:
        parts.append(body)
    if tag_line:
        parts.append(f"\n🏷 {tag_line}")
    parts.append(f"\n🆔 <code>{uid}</code>")
    return "\n\n".join(parts)


async def publish_post(bot: Bot, uid: str) -> bool:
    """
    Publish an approved post to the appropriate channel.
    Returns True on success.
    """
    post = await db.get_post_by_uid(uid)
    if not post:
        return False

    channel_id = _TYPE_TO_CHANNEL.get(post["type"])
    if not channel_id:
        return False

    text    = _format_post(dict(post))
    report_kb = channel_report_kb(channel_id, 0)  # placeholder; updated after send

    for attempt in range(3):
        try:
            if post["type"] == "poll":
                # Build native Telegram poll from options
                options = await db.get_poll_options(post["id"])
                opt_texts = [o["option_text"] for o in options]
                sent = await bot.send_poll(
                    chat_id=channel_id,
                    question=post["title"] or "Опрос",
                    options=opt_texts,
                    is_anonymous=True,
                    allows_multiple_answers=False,
                )
                # Send caption with report button separately
                await bot.send_message(
                    channel_id,
                    f"🆔 <code>{uid}</code>\n\n🚨 Нашли нарушение? Нажмите ниже:",
                    parse_mode="HTML",
                    reply_markup=channel_report_kb(channel_id, sent.message_id),
                )
                msg_id = sent.message_id
            else:
                sent = await bot.send_message(
                    channel_id,
                    text,
                    parse_mode="HTML",
                    reply_markup=channel_report_kb(channel_id, 0),
                )
                # Edit markup with real message_id now known
                real_kb = channel_report_kb(channel_id, sent.message_id)
                await bot.edit_message_reply_markup(
                    channel_id, sent.message_id, reply_markup=real_kb
                )
                msg_id = sent.message_id

            await db.mark_published(uid, channel_id, msg_id)
            return True

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except Exception as exc:
            print(f"[publisher] error: {exc}")
            return False

    return False
