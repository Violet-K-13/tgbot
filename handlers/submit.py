"""handlers/submit.py — multi-step FSM for submitting news / polls / wishes."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import settings
from database import db
from keyboards.kb import content_type_kb, cancel_kb, submit_form_kb
from utils.states import SubmitPost

router = Router()

_TYPE_LABELS = {"news": "новость", "poll": "опрос", "wish": "желание"}
_TYPE_EMOJI  = {"news": "📰", "poll": "📊", "wish": "💫"}


# ─── Step 0: choose type ─────────────────────────────────────────────────────

@router.callback_query(F.data == "add_content")
async def cb_add_content(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SubmitPost.choosing_type)
    await call.message.edit_text(
        "✏️ <b>Что хотите добавить?</b>",
        parse_mode="HTML",
        reply_markup=content_type_kb(),
    )
    await call.answer()


# ─── Step 1: enter title ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("new:"))
async def cb_choose_type(call: CallbackQuery, state: FSMContext) -> None:
    post_type = call.data.split(":")[1]
    await state.update_data(post_type=post_type)
    await state.set_state(SubmitPost.entering_title)
    await call.message.edit_text(
        f"{_TYPE_EMOJI[post_type]} <b>Новая {_TYPE_LABELS[post_type]}</b>\n\n"
        "📌 Введите <b>заголовок</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(SubmitPost.entering_title)
async def msg_enter_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("⚠️ Заголовок слишком короткий. Минимум 3 символа.")
        return
    if len(title) > 512:
        await message.answer("⚠️ Заголовок слишком длинный. Максимум 512 символов.")
        return
    await state.update_data(title=title)
    await state.set_state(SubmitPost.entering_body)
    await message.answer("📝 Введите <b>текст</b> (основной контент):", parse_mode="HTML", reply_markup=cancel_kb())


# ─── Step 2: enter body ──────────────────────────────────────────────────────

@router.message(SubmitPost.entering_body)
async def msg_enter_body(message: Message, state: FSMContext) -> None:
    body = message.text.strip()
    if len(body) < 10:
        await message.answer("⚠️ Текст слишком короткий. Минимум 10 символов.")
        return
    await state.update_data(body=body)
    data = await state.get_data()

    if data["post_type"] == "poll":
        await state.set_state(SubmitPost.entering_opts)
        await message.answer(
            "📋 Введите <b>варианты ответа</b> для опроса — каждый с новой строки (2–10 вариантов):",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )
    else:
        await state.set_state(SubmitPost.entering_tags)
        await message.answer(
            "🏷 Введите <b>теги</b> через запятую (или «-» чтобы пропустить):\n"
            "Пример: <code>технологии, ИИ, новости</code>",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )


# ─── Step 2b: poll options ───────────────────────────────────────────────────

@router.message(SubmitPost.entering_opts)
async def msg_enter_opts(message: Message, state: FSMContext) -> None:
    lines = [l.strip() for l in message.text.split("\n") if l.strip()]
    if len(lines) < 2:
        await message.answer("⚠️ Нужно минимум 2 варианта ответа.")
        return
    if len(lines) > 10:
        await message.answer("⚠️ Максимум 10 вариантов ответа.")
        return
    for opt in lines:
        if len(opt) > 100:
            await message.answer(f"⚠️ Вариант слишком длинный (макс. 100 символов): {opt[:60]}…")
            return
    await state.update_data(poll_options=lines)
    await state.set_state(SubmitPost.entering_tags)
    await message.answer(
        "🏷 Введите <b>теги</b> через запятую (или «-» пропустить):",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


# ─── Step 3: tags → confirm ──────────────────────────────────────────────────

@router.message(SubmitPost.entering_tags)
async def msg_enter_tags(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    tags = [] if raw == "-" else [t.strip().lstrip("#") for t in raw.split(",") if t.strip()]
    await state.update_data(tags=tags)
    await state.set_state(SubmitPost.confirming)

    data = await state.get_data()
    post_type = data["post_type"]

    preview = (
        f"{_TYPE_EMOJI[post_type]} <b>{data['title']}</b>\n\n"
        f"{data['body']}\n\n"
    )
    if tags:
        preview += "🏷 " + " ".join(f"#{t}" for t in tags) + "\n\n"
    if post_type == "poll" and data.get("poll_options"):
        opts = "\n".join(f"  {i+1}. {o}" for i, o in enumerate(data["poll_options"]))
        preview += f"📋 Варианты:\n{opts}\n\n"

    preview += "Нажмите <b>«Отправить на ревью»</b> или вернитесь назад."

    await message.answer(
        f"👀 <b>Предпросмотр:</b>\n\n{preview}",
        parse_mode="HTML",
        reply_markup=submit_form_kb(post_type),
    )


# ─── Final submit ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("submit:"), SubmitPost.confirming)
async def cb_submit(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    post_type  = data["post_type"]
    poll_options = data.get("poll_options")

    uid = await db.create_post(
        author_id=call.from_user.id,
        post_type=post_type,
        title=data["title"],
        body=data["body"],
        tags=data.get("tags", []),
        poll_options=poll_options,
    )
    await state.clear()

    # Notify all admins
    notify_text = (
        f"🆕 <b>Новый контент на ревью</b>\n"
        f"🆔 <code>{uid}</code>  |  Тип: {_TYPE_EMOJI[post_type]} {_TYPE_LABELS[post_type]}\n"
        f"Автор: {call.from_user.full_name} (<code>{call.from_user.id}</code>)\n\n"
        f"<b>{data['title']}</b>\n{data['body'][:300]}"
    )
    from keyboards.kb import admin_review_kb
    for admin_id in settings.ADMIN_IDS:
        try:
            await call.bot.send_message(
                admin_id,
                notify_text,
                parse_mode="HTML",
                reply_markup=admin_review_kb(uid),
            )
        except Exception:
            pass

    await call.message.edit_text(
        f"✅ <b>Отправлено на ревью!</b>\n\nВаш ID: <code>{uid}</code>\n"
        "Мы уведомим вас о результате.",
        parse_mode="HTML",
    )
    await call.answer("Отправлено!")
