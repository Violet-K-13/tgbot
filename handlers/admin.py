"""handlers/admin.py — admin panel: review, FAQ management, club videos, user management."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Filter

from config import settings
from database import db
from keyboards.kb import (
    admin_panel_kb, admin_review_kb, faq_edit_kb, cancel_kb, main_menu_kb
)
from services.publisher import publish_post
from utils.states import AdminFaq, AdminClub, AdminMisc

router = Router()


# ─── Admin filter ─────────────────────────────────────────────────────────────

class IsAdmin(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        return user_id in settings.ADMIN_IDS or await db.is_admin(user_id)


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ─── Admin panel entry ────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin")
async def cb_admin_panel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text(
        "⚙️ <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )
    await call.answer()


# ─── Pending review list ──────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:pending")
async def cb_pending(call: CallbackQuery) -> None:
    posts = await db.get_pending_posts()
    if not posts:
        await call.answer("Нет постов на ревью.", show_alert=True)
        return

    for post in posts[:10]:  # show max 10
        emoji = {"news": "📰", "poll": "📊", "wish": "💫"}.get(post["type"], "📄")
        text = (
            f"{emoji} <b>{post['title'] or 'Без заголовка'}</b>\n"
            f"🆔 <code>{post['uid']}</code>\n"
            f"Автор: <code>{post['author_id']}</code>\n\n"
            f"{(post['body'] or '')[:400]}"
        )
        await call.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=admin_review_kb(post["uid"]),
        )
    await call.answer()


# ─── Approve ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("review:approve:"))
async def cb_approve(call: CallbackQuery) -> None:
    uid = call.data.split(":", 2)[2]
    post = await db.approve_post(uid, call.from_user.id)
    if not post:
        await call.answer("Пост не найден.", show_alert=True)
        return

    success = await publish_post(call.bot, uid)
    if success:
        await call.message.edit_text(
            f"✅ <b>{uid}</b> одобрен и опубликован в канале.",
            parse_mode="HTML",
        )
        # Notify author
        try:
            await call.bot.send_message(
                post["author_id"],
                f"🎉 Ваш пост <code>{uid}</code> одобрен и опубликован!",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await call.message.edit_text(
            f"⚠️ <b>{uid}</b> одобрен, но публикация не удалась. Проверьте каналы.",
            parse_mode="HTML",
        )
    await call.answer()


# ─── Reject ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("review:reject:"))
async def cb_reject(call: CallbackQuery) -> None:
    uid = call.data.split(":", 2)[2]
    post = await db.get_post_by_uid(uid)
    if not post:
        await call.answer("Пост не найден.", show_alert=True)
        return
    await db.reject_post(uid, call.from_user.id)
    await call.message.edit_text(
        f"❌ <b>{uid}</b> отклонён.",
        parse_mode="HTML",
    )
    try:
        await call.bot.send_message(
            post["author_id"],
            f"😔 Ваш пост <code>{uid}</code> не прошёл модерацию.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await call.answer()


# ─── FAQ: list ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:faq_list")
async def cb_faq_list(call: CallbackQuery) -> None:
    faqs = await db.get_all_faq()
    if not faqs:
        await call.answer("FAQ пуст.", show_alert=True)
        return
    for faq in faqs:
        text = f"❓ <b>{faq['question']}</b>\n\n{faq['answer'][:300]}"
        await call.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=faq_edit_kb(faq["id"]),
        )
    await call.answer()


# ─── FAQ: add ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:faq_add")
async def cb_faq_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFaq.entering_question)
    await call.message.edit_text(
        "➕ <b>Новый FAQ</b>\n\nВведите <b>вопрос</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AdminFaq.entering_question)
async def faq_enter_question(message: Message, state: FSMContext) -> None:
    await state.update_data(question=message.text.strip())
    await state.set_state(AdminFaq.entering_answer)
    await message.answer("📝 Введите <b>ответ</b>:", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(AdminFaq.entering_answer)
async def faq_enter_answer(message: Message, state: FSMContext) -> None:
    await state.update_data(answer=message.text.strip())
    await state.set_state(AdminFaq.entering_keywords)
    await message.answer(
        "🔑 Введите <b>ключевые слова</b> через запятую (или «-» пропустить):",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(AdminFaq.entering_keywords)
async def faq_enter_keywords(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    kws = [] if raw == "-" else [k.strip() for k in raw.split(",") if k.strip()]
    data = await state.get_data()
    faq_id = await db.add_faq(data["question"], data["answer"], kws)
    await state.clear()
    await message.answer(
        f"✅ FAQ #{faq_id} добавлен!",
        reply_markup=admin_panel_kb(),
    )


# ─── FAQ: edit ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:faq_edit:"))
async def cb_faq_edit(call: CallbackQuery, state: FSMContext) -> None:
    faq_id = int(call.data.split(":")[-1])
    await state.update_data(editing_id=faq_id)
    await state.set_state(AdminFaq.editing_question)
    await call.message.edit_text(
        f"✏️ Редактирование FAQ #{faq_id}\n\nВведите новый <b>вопрос</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AdminFaq.editing_question)
async def faq_edit_question(message: Message, state: FSMContext) -> None:
    await state.update_data(question=message.text.strip())
    await state.set_state(AdminFaq.editing_answer)
    await message.answer("📝 Введите новый <b>ответ</b>:", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(AdminFaq.editing_answer)
async def faq_edit_answer(message: Message, state: FSMContext) -> None:
    await state.update_data(answer=message.text.strip())
    await state.set_state(AdminFaq.editing_keywords)
    await message.answer(
        "🔑 Введите новые <b>ключевые слова</b> через запятую (или «-» пропустить):",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(AdminFaq.editing_keywords)
async def faq_edit_keywords(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    kws = [] if raw == "-" else [k.strip() for k in raw.split(",") if k.strip()]
    data = await state.get_data()
    await db.update_faq(data["editing_id"], data["question"], data["answer"], kws)
    await state.clear()
    await message.answer("✅ FAQ обновлён!", reply_markup=admin_panel_kb())


# ─── FAQ: delete ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin:faq_del:"))
async def cb_faq_del(call: CallbackQuery) -> None:
    faq_id = int(call.data.split(":")[-1])
    await db.delete_faq(faq_id)
    await call.message.edit_text(f"🗑 FAQ #{faq_id} удалён.")
    await call.answer()


# ─── Club video: add ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:club_add")
async def cb_club_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminClub.waiting_video)
    await call.message.edit_text(
        "🎬 <b>Загрузка видео в клуб</b>\n\nОтправьте видеофайл:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AdminClub.waiting_video, F.video)
async def club_got_video(message: Message, state: FSMContext) -> None:
    await state.update_data(file_id=message.video.file_id)
    await state.set_state(AdminClub.entering_title)
    await message.answer("📌 Введите <b>заголовок</b> видео:", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(AdminClub.entering_title)
async def club_enter_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminClub.entering_desc)
    await message.answer("📝 Введите <b>описание</b>:", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(AdminClub.entering_desc)
async def club_enter_desc(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminClub.entering_tags)
    await message.answer("🏷 Введите <b>теги</b> через запятую (или «-»):", parse_mode="HTML", reply_markup=cancel_kb())


@router.message(AdminClub.entering_tags)
async def club_enter_tags(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    tags = [] if raw == "-" else [t.strip() for t in raw.split(",") if t.strip()]
    data = await state.get_data()
    uid = await db.add_club_video(
        title=data["title"],
        description=data["description"],
        file_id=data["file_id"],
        tags=tags,
        added_by=message.from_user.id,
    )
    await state.clear()
    await message.answer(
        f"✅ Видео добавлено в клуб!\n🆔 <code>{uid}</code>",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )


# ─── User management ──────────────────────────────────────────────────────────

@router.callback_query(F.data.in_({"admin:set_admin", "admin:set_club"}))
async def cb_set_user_role(call: CallbackQuery, state: FSMContext) -> None:
    action = call.data.split(":")[-1]
    await state.update_data(role_action=action)
    await state.set_state(AdminMisc.entering_user_id)
    label = "администратором" if action == "set_admin" else "участником клуба"
    await call.message.edit_text(
        f"👤 Введите <b>Telegram ID</b> пользователя, которого хотите сделать {label}:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AdminMisc.entering_user_id)
async def misc_set_role(message: Message, state: FSMContext) -> None:
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Введите корректный числовой ID.")
        return

    data = await state.get_data()
    action = data["role_action"]
    if action == "set_admin":
        await db.set_admin(target_id, True)
        label = "администратором"
    else:
        await db.set_club_member(target_id, True)
        label = "участником клуба"

    await state.clear()
    await message.answer(
        f"✅ Пользователь <code>{target_id}</code> теперь {label}.",
        parse_mode="HTML",
        reply_markup=admin_panel_kb(),
    )
