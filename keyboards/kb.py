"""keyboards/kb.py — all InlineKeyboardMarkup / ReplyKeyboardMarkup factories."""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ─── Main menu ────────────────────────────────────────────────────────────────

def main_menu_kb(is_admin: bool = False, is_club: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📰 Новости",  callback_data="cat:news"),
        InlineKeyboardButton(text="📊 Опросы",   callback_data="cat:poll"),
    )
    builder.row(
        InlineKeyboardButton(text="💫 Желания",  callback_data="cat:wish"),
        InlineKeyboardButton(text="❤️ Мои желания", callback_data="my_wishes"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Добавить информацию", callback_data="add_content"),
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Поиск", callback_data="search"),
        InlineKeyboardButton(text="❓ FAQ",   callback_data="faq"),
    )
    if is_club:
        builder.row(
            InlineKeyboardButton(text="🔒 Клуб (видео)", callback_data="club"),
        )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="⚙️ Панель админа", callback_data="admin"),
        )
    return builder.as_markup()


# ─── Content type selection ───────────────────────────────────────────────────

def content_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📰 Новость", callback_data="new:news"),
        InlineKeyboardButton(text="📊 Опрос",   callback_data="new:poll"),
        InlineKeyboardButton(text="💫 Желание", callback_data="new:wish"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back:main"))
    return builder.as_markup()


# ─── Submission form ──────────────────────────────────────────────────────────

def submit_form_kb(post_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 Отправить на ревью", callback_data=f"submit:{post_type}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="add_content"))
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="back:main"))
    return builder.as_markup()


# ─── Admin review ─────────────────────────────────────────────────────────────

def admin_review_kb(uid: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"review:approve:{uid}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"review:reject:{uid}"),
    )
    return builder.as_markup()


def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Ожидают ревью", callback_data="admin:pending"))
    builder.row(
        InlineKeyboardButton(text="📝 FAQ — список",   callback_data="admin:faq_list"),
        InlineKeyboardButton(text="➕ Добавить FAQ",   callback_data="admin:faq_add"),
    )
    builder.row(
        InlineKeyboardButton(text="🎬 Добавить видео в клуб", callback_data="admin:club_add"),
    )
    builder.row(
        InlineKeyboardButton(text="👤 Сделать админом",    callback_data="admin:set_admin"),
        InlineKeyboardButton(text="🔒 Добавить в клуб",    callback_data="admin:set_club"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="back:main"))
    return builder.as_markup()


def faq_edit_kb(faq_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:faq_edit:{faq_id}"),
        InlineKeyboardButton(text="🗑 Удалить",        callback_data=f"admin:faq_del:{faq_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:faq_list"))
    return builder.as_markup()


# ─── Spam report button (posted IN channel) ───────────────────────────────────

def channel_report_kb(channel_id: int, message_id: int) -> InlineKeyboardMarkup:
    """Inline keyboard attached to every published post in channels."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🚨 Спам / нарушение правил",
            callback_data=f"report:{channel_id}:{message_id}",
        )
    )
    return builder.as_markup()


def report_reason_kb(channel_id: int, message_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📢 Спам",
            callback_data=f"report_reason:{channel_id}:{message_id}:spam",
        ),
        InlineKeyboardButton(
            text="⚠️ Нарушение правил",
            callback_data=f"report_reason:{channel_id}:{message_id}:rules_violation",
        ),
    )
    builder.row(InlineKeyboardButton(text="◀️ Отмена", callback_data="back:main"))
    return builder.as_markup()


# ─── Pagination ───────────────────────────────────────────────────────────────

def pagination_kb(page: int, total: int, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}:page:{page-1}"))
    row.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if page < total - 1:
        row.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}:page:{page+1}"))
    builder.row(*row)
    builder.row(InlineKeyboardButton(text="◀️ Меню", callback_data="back:main"))
    return builder.as_markup()


# ─── Search ───────────────────────────────────────────────────────────────────

def search_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔎 По ID",           callback_data="search:id"),
        InlineKeyboardButton(text="🔍 По ключевым словам", callback_data="search:keyword"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back:main"))
    return builder.as_markup()
