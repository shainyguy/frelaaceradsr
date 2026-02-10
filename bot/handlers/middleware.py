from sqlalchemy import select
from bot.database import async_session
from bot.models import User
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Клавиатура для неподписанных
SUB_REQUIRED_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⭐ Оформить подписку", callback_data="subscription")],
    [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
])

SUB_REQUIRED_TEXT = (
    "🔒 <b>Нужна активная подписка</b>\n\n"
    "Эта функция доступна только с подпиской.\n\n"
    "💰 Стоимость: <b>690 ₽/мес</b>\n"
    "🎯 Окупается с одного заказа!\n\n"
    "Первый день — бесплатно."
)


async def get_user(telegram_id: int) -> User | None:
    """Получить пользователя из БД"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def check_subscription(telegram_id: int) -> tuple[User | None, bool]:
    """
    Проверить подписку.
    Возвращает (user, has_subscription)
    """
    user = await get_user(telegram_id)
    if not user:
        return None, False
    return user, user.has_active_subscription
