"""handlers/faq.py — FAQ for regular users: browse and free-form Q&A."""
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database import db
from keyboards.kb import cancel_kb, main_menu_kb
from utils.states import FaqFlow

router = Router()


@router.callback_query(F.data == "faq")
async def cb_faq_entry(call: CallbackQuery, state: FSMContext) -> None:
    faqs = await db.get_all_faq()

    if not faqs:
        await call.answer("FAQ пока пуст.", show_alert=True)
        return

    # Show top-5 as quick reference, then invite free questions
    lines = []
    for i, f in enumerate(faqs[:5], 1):
        lines.append(f"<b>{i}. {f['question']}</b>\n{f['answer'][:200]}")

    text = "❓ <b>Часто задаваемые вопросы</b>\n\n" + "\n\n".join(lines)
    if len(faqs) > 5:
        text += f"\n\n…и ещё {len(faqs)-5} вопросов."

    text += "\n\n💬 Или напишите свой вопрос — я найду подходящий ответ:"

    await state.set_state(FaqFlow.asking)
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=cancel_kb())
    await call.answer()


@router.message(FaqFlow.asking)
async def faq_free_question(message: Message, state: FSMContext) -> None:
    query = message.text.strip()
    if len(query) < 3:
        await message.answer("⚠️ Вопрос слишком короткий.")
        return

    results = await db.search_faq(query)

    if not results:
        await message.answer(
            "😔 Не нашёл подходящего ответа в FAQ.\n"
            "Попробуйте переформулировать или обратитесь к администратору.",
            reply_markup=cancel_kb(),
        )
        return

    best = results[0]
    text = (
        f"❓ <b>{best['question']}</b>\n\n"
        f"{best['answer']}"
    )
    if len(results) > 1:
        text += "\n\n🔗 <i>Похожие вопросы:</i>\n"
        for r in results[1:3]:
            text += f"• {r['question']}\n"

    admin = await db.is_admin(message.from_user.id)
    club  = await db.is_club_member(message.from_user.id)

    await state.clear()
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_kb(is_admin=admin, is_club=club),
    )
