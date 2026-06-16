"""handlers/catalog.py — browse news/polls/wishes by category + club section."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from keyboards.kb import main_menu_kb, pagination_kb

router = Router()

_PAGE_SIZE = 5
_TYPE_EMOJI = {"news": "📰", "poll": "📊", "wish": "💫"}
_TYPE_LABEL = {"news": "Новости", "poll": "Опросы", "wish": "Желания"}


def _format_post(post) -> str:
    emoji = _TYPE_EMOJI.get(post["type"], "📄")
    tags  = post.get("tags") or []
    tag_line = " ".join(f"#{t}" for t in tags) if tags else ""
    return (
        f"{emoji} <b>{post['title'] or 'Без заголовка'}</b>\n"
        f"🆔 <code>{post['uid']}</code>\n\n"
        f"{(post['body'] or '')[:400]}"
        + (f"\n\n🏷 {tag_line}" if tag_line else "")
    )


# ─── Category view ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cat:"))
async def cb_category(call: CallbackQuery) -> None:
    post_type = call.data.split(":")[1]
    await _show_category_page(call, post_type, page=0)


@router.callback_query(F.data.startswith("cat_page:"))
async def cb_category_page(call: CallbackQuery) -> None:
    # format: cat_page:{type}:page:{n}
    parts = call.data.split(":")
    post_type = parts[1]
    page = int(parts[3])
    await _show_category_page(call, post_type, page)


async def _show_category_page(call: CallbackQuery, post_type: str, page: int) -> None:
    pool_result = await db.get_pool()
    import asyncpg
    pool = await db.get_pool()

    total_count = await pool.fetchval(
        "SELECT COUNT(*) FROM posts WHERE type=$1 AND status='published'", post_type
    )
    if total_count == 0:
        await call.answer(f"В разделе «{_TYPE_LABEL[post_type]}» пока пусто.", show_alert=True)
        return

    offset = page * _PAGE_SIZE
    rows = await pool.fetch(
        "SELECT * FROM posts WHERE type=$1 AND status='published' "
        "ORDER BY published_at DESC LIMIT $2 OFFSET $3",
        post_type, _PAGE_SIZE, offset,
    )

    total_pages = (total_count + _PAGE_SIZE - 1) // _PAGE_SIZE
    chunks = [_format_post(dict(r)) for r in rows]
    text = (
        f"{_TYPE_EMOJI[post_type]} <b>{_TYPE_LABEL[post_type]}</b> "
        f"(страница {page+1}/{total_pages})\n\n"
        + "\n\n─────────────────\n\n".join(chunks)
    )

    kb = pagination_kb(page, total_pages, f"cat_page:{post_type}")

    try:
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await call.message.answer(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


# ─── My wishes ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_wishes")
async def cb_my_wishes(call: CallbackQuery) -> None:
    pool = await db.get_pool()
    rows = await pool.fetch(
        "SELECT * FROM posts WHERE type='wish' AND author_id=$1 ORDER BY created_at DESC LIMIT 20",
        call.from_user.id,
    )

    admin = await db.is_admin(call.from_user.id)
    club  = await db.is_club_member(call.from_user.id)
    menu  = main_menu_kb(is_admin=admin, is_club=club)

    if not rows:
        await call.message.edit_text(
            "💫 У вас пока нет желаний.\n\nДобавьте первое через «✏️ Добавить информацию»!",
            reply_markup=menu,
        )
        await call.answer()
        return

    chunks = []
    for r in rows:
        status_icon = {"pending": "⏳", "approved": "✅", "rejected": "❌", "published": "📢"}.get(
            r["status"], "❓"
        )
        chunks.append(
            f"💫 <b>{r['title'] or 'Без заголовка'}</b>\n"
            f"🆔 <code>{r['uid']}</code>  {status_icon} {r['status']}"
        )

    await call.message.edit_text(
        "❤️ <b>Мои желания</b>\n\n" + "\n\n".join(chunks),
        parse_mode="HTML",
        reply_markup=menu,
    )
    await call.answer()


# ─── Club section ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "club")
async def cb_club(call: CallbackQuery) -> None:
    if not await db.is_club_member(call.from_user.id):
        await call.answer("🔒 Этот раздел доступен только участникам клуба.", show_alert=True)
        return

    videos = await db.get_club_videos()

    admin = await db.is_admin(call.from_user.id)
    menu  = main_menu_kb(is_admin=admin, is_club=True)

    if not videos:
        await call.message.edit_text(
            "🎬 <b>Клуб — видео</b>\n\nВидео пока не добавлены.",
            parse_mode="HTML",
            reply_markup=menu,
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"🔒 <b>Клуб — видео</b> ({len(videos)} шт.)\n\nОтправляю видео…",
        parse_mode="HTML",
    )

    for v in videos[:5]:  # limit to avoid flood
        caption = (
            f"🎬 <b>{v['title']}</b>\n\n{v['description'] or ''}\n\n"
            f"🆔 <code>{v['uid']}</code>"
        )
        try:
            await call.message.answer_video(
                v["file_id"],
                caption=caption,
                parse_mode="HTML",
            )
        except Exception:
            await call.message.answer(f"⚠️ Не удалось загрузить видео <code>{v['uid']}</code>", parse_mode="HTML")

    await call.message.answer("📋 Все видео отправлены.", reply_markup=menu)
    await call.answer()
