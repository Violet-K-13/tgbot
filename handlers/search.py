"""handlers/search.py — search posts by UID or keywords."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from keyboards.kb import search_type_kb, cancel_kb, main_menu_kb
from utils.states import SearchFlow

router = Router()

_TYPE_EMOJI = {"news": "📰", "poll": "📊", "wish": "💫"}


def _format_result(post) -> str:
    emoji = _TYPE_EMOJI.get(post["type"], "📄")
    tags  = post.get("tags") or []
    tag_line = " ".join(f"#{t}" for t in tags) if tags else ""
    return (
        f"{emoji} <b>{post['title'] or 'Без заголовка'}</b>\n"
        f"🆔 <code>{post['uid']}</code>\n"
        f"{(post['body'] or '')[:300]}\n"
        + (f"🏷 {tag_line}" if tag_line else "")
    )


@router.callback_query(F.data == "search")
async def cb_search_entry(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchFlow.choosing_mode)
    await call.message.edit_text(
        "🔍 <b>Поиск</b>\n\nВыберите способ поиска:",
        parse_mode="HTML",
        reply_markup=search_type_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("search:"))
async def cb_search_mode(call: CallbackQuery, state: FSMContext) -> None:
    mode = call.data.split(":")[1]
    await state.update_data(search_mode=mode)
    await state.set_state(SearchFlow.entering_query)

    if mode == "id":
        prompt = "🆔 Введите <b>ID</b> поста (например: <code>NEWS-0001</code>):"
    else:
        prompt = "🔍 Введите <b>ключевые слова</b> для поиска:"

    await call.message.edit_text(prompt, parse_mode="HTML", reply_markup=cancel_kb())
    await call.answer()


@router.message(SearchFlow.entering_query)
async def search_query(message: Message, state: FSMContext) -> None:
    query = message.text.strip()
    data  = await state.get_data()
    mode  = data.get("search_mode", "keyword")

    await state.clear()

    admin = await db.is_admin(message.from_user.id)
    club  = await db.is_club_member(message.from_user.id)
    menu  = main_menu_kb(is_admin=admin, is_club=club)

    if mode == "id":
        post = await db.get_post_by_uid(query)
        if not post:
            await message.answer(
                f"😔 Пост с ID <code>{query}</code> не найден.",
                parse_mode="HTML",
                reply_markup=menu,
            )
            return
        await message.answer(_format_result(dict(post)), parse_mode="HTML", reply_markup=menu)

    else:
        results = await db.search_posts(query)
        if not results:
            await message.answer(
                "😔 Ничего не найдено. Попробуйте другие слова.",
                reply_markup=menu,
            )
            return
        header = f"🔍 Найдено результатов: <b>{len(results)}</b>\n\n"
        chunks = [_format_result(dict(r)) for r in results]
        await message.answer(
            header + "\n\n─────────────────\n\n".join(chunks),
            parse_mode="HTML",
            reply_markup=menu,
        )
