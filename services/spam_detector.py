"""services/spam_detector.py — heuristic spam detection for channel messages."""
from __future__ import annotations
import re
from aiogram.types import Message


# Patterns that often indicate spam
_URL_RE       = re.compile(r"https?://|t\.me/|@\w{5,}", re.I)
_CAPS_RATIO   = 0.6   # fraction of uppercase letters
_MAX_URLS     = 3
_MAX_MENTIONS = 2
_SPAM_WORDS   = {
    "заработок", "казино", "крипта", "инвест", "схема", "100%", "гарантия",
    "быстро", "легко", "бесплатно", "нажми", "переходи", "подписывайся",
    "earn", "casino", "crypto", "invest", "click here", "free money",
}


def detect_spam(text: str) -> tuple[bool, str]:
    """
    Returns (is_spam, reason).
    Heuristic only — final decision always goes to admin.
    """
    if not text:
        return False, ""

    text_lower = text.lower()

    # 1. Too many URLs
    urls = _URL_RE.findall(text)
    if len(urls) > _MAX_URLS:
        return True, f"Слишком много ссылок ({len(urls)})"

    # 2. Spam keywords
    hits = [w for w in _SPAM_WORDS if w in text_lower]
    if len(hits) >= 3:
        return True, f"Спам-слова: {', '.join(hits[:5])}"

    # 3. High CAPS ratio (min 20 chars to measure)
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 20:
        caps = sum(1 for c in letters if c.isupper())
        if caps / len(letters) > _CAPS_RATIO:
            return True, "Слишком много заглавных букв"

    # 4. Very short message with only a link
    stripped = _URL_RE.sub("", text).strip()
    if len(stripped) < 10 and urls:
        return True, "Сообщение состоит только из ссылки"

    return False, ""


async def check_message_and_notify(message: Message, admin_ids: list[int]) -> None:
    """Check incoming channel/group message and DM admins if spam suspected."""
    from aiogram.exceptions import TelegramForbiddenError

    text = message.text or message.caption or ""
    is_spam, reason = detect_spam(text)
    if not is_spam:
        return

    info = (
        f"🤖 <b>Подозрение на спам</b>\n"
        f"Чат: {message.chat.title} (<code>{message.chat.id}</code>)\n"
        f"От: {message.from_user.full_name if message.from_user else 'unknown'}\n"
        f"Причина: {reason}\n"
        f"Текст:\n<blockquote>{text[:400]}</blockquote>"
    )
    for admin_id in admin_ids:
        try:
            await message.bot.send_message(admin_id, info, parse_mode="HTML")
        except TelegramForbiddenError:
            pass
