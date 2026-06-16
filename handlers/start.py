"""handlers/start.py — /start command + main menu callbacks."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from database import db
from keyboards.kb import main_menu_kb

router = Router()


async def _send_main_menu(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()

    user_id = target.from_user.id
    admin   = await db.is_admin(user_id)
    club    = await db.is_club_member(user_id)

    text = (
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Выберите раздел или добавьте контент:"
    )
    kb = main_menu_kb(is_admin=admin, is_club=club)

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await target.answer()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await _send_main_menu(message, state)


@router.callback_query(F.data == "back:main")
async def cb_back_main(call: CallbackQuery, state: FSMContext) -> None:
    await _send_main_menu(call, state)
