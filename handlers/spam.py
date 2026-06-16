"""handlers/spam.py — channel spam reports + auto-detection."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import IS_MEMBER

from config import settings
from database import db
from keyboards.kb import report_reason_kb
from services.spam_detector import check_message_and_notify

router = Router()


# ─── "Spam / rules violation" button in channel ───────────────────────────────

@router.callback_query(F.data.startswith("report:"))
async def cb_report_entry(call: CallbackQuery) -> None:
    """User tapped the report button — show reason choice."""
    _, channel_id, message_id = call.data.split(":")
    channel_id = int(channel_id)
    message_id = int(message_id)

    await call.message.answer(
        "🚨 <b>Пожаловаться на сообщение</b>\n\nВыберите причину:",
        parse_mode="HTML",
        reply_markup=report_reason_kb(channel_id, message_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("report_reason:"))
async def cb_report_reason(call: CallbackQuery) -> None:
    """Store report and notify admins if threshold reached."""
    parts = call.data.split(":")
    # format: report_reason:{channel_id}:{message_id}:{reason}
    channel_id = int(parts[1])
    message_id = int(parts[2])
    reason     = parts[3]

    inserted = await db.add_spam_report(
        channel_id=channel_id,
        message_id=message_id,
        reported_by=call.from_user.id,
        reason=reason,
    )

    if not inserted:
        await call.answer("Вы уже отправляли жалобу на это сообщение.", show_alert=True)
        return

    await call.answer("✅ Жалоба отправлена. Спасибо!", show_alert=True)

    # Count total reports for this message
    reports = await db.get_spam_reports(channel_id, message_id)
    count   = len(reports)

    # Notify admin on first report and every N reports
    if count == 1 or count % settings.SPAM_REPORT_THRESHOLD == 0:
        reason_label = {
            "spam": "📢 Спам",
            "rules_violation": "⚠️ Нарушение правил",
        }.get(reason, reason)

        notify = (
            f"🚨 <b>Жалоба на сообщение</b>\n\n"
            f"Канал: <code>{channel_id}</code>\n"
            f"Сообщение: <code>{message_id}</code>\n"
            f"Ссылка: https://t.me/c/{str(channel_id).lstrip('-100')}/{message_id}\n\n"
            f"Причина: {reason_label}\n"
            f"Всего жалоб: <b>{count}</b>\n\n"
            f"От: {call.from_user.full_name} (<code>{call.from_user.id}</code>)"
        )
        for admin_id in settings.ADMIN_IDS:
            try:
                await call.bot.send_message(admin_id, notify, parse_mode="HTML")
            except Exception:
                pass

    # Try to delete the confirmation message quietly
    try:
        await call.message.delete()
    except Exception:
        pass


# ─── Auto-detection: messages posted in channels/groups ───────────────────────

@router.message(F.chat.type.in_({"channel", "group", "supergroup"}))
async def channel_message_handler(message: Message) -> None:
    """Check every channel/group message for spam heuristics."""
    await check_message_and_notify(message, settings.ADMIN_IDS)


# ─── Bot added to / removed from channel ─────────────────────────────────────

@router.my_chat_member()
async def on_bot_chat_member(event, bot) -> None:
    """Register or deactivate channels when bot is added/removed."""
    from aiogram.types import ChatMemberUpdated
    update: ChatMemberUpdated = event

    chat = update.chat
    new_status = update.new_chat_member.status

    if new_status in ("administrator", "member"):
        # Bot added — register channel (type 'general' by default; admin changes it)
        await db.register_channel(chat.id, chat.title or "", "general")
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"✅ Бот добавлен в канал/группу:\n"
                    f"<b>{chat.title}</b> (<code>{chat.id}</code>)\n\n"
                    f"Установите тип канала через /setchannel.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
    elif new_status in ("kicked", "left"):
        pool = await db.get_pool()
        await pool.execute(
            "UPDATE channels SET is_active=FALSE WHERE id=$1", chat.id
        )
