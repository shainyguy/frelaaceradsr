from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo
)
from sqlalchemy import select

from bot.database import async_session
from bot.models import User
from bot.config import config

router = Router()


def main_menu_keyboard(user: User = None) -> InlineKeyboardMarkup:
    webapp_url = config.WEBAPP_URL

    buttons = [
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="📂 Категории", callback_data="categories")],
        [InlineKeyboardButton(text="🔍 Парсер заказов", callback_data="parser_control"),
         InlineKeyboardButton(text="📊 CRM", callback_data="crm_menu")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications"),
         InlineKeyboardButton(text="💰 Калькулятор цены", callback_data="calculator")],
        [InlineKeyboardButton(text="👁 Проверка заказчика", callback_data="client_check"),
         InlineKeyboardButton(text="⭐ Подписка", callback_data="subscription")],
        [InlineKeyboardButton(text="📈 Статистика парсеров", callback_data="parser_stats")],
    ]

    if webapp_url:
        buttons.append([
            InlineKeyboardButton(
                text="🌐 Открыть Mini App",
                web_app=WebAppInfo(url=f"{webapp_url}/webapp")
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
            )
            session.add(user)
            await session.commit()

            welcome_text = (
                f"👋 Привет, <b>{message.from_user.full_name}</b>!\n\n"
                f"🎯 Я — <b>Freelance Radar</b>, твой ловец жирных заказов.\n\n"
                f"Что я умею:\n"
                f"• 🔍 Мониторю <b>7+ бирж</b> в реальном времени\n"
                f"• ⚡ Уведомляю о заказах <b>мгновенно</b>\n"
                f"• ✍️ Генерирую <b>идеальные отклики</b> за секунду\n"
                f"• 📊 Веду <b>CRM</b> твоих заказов\n"
                f"• 👁 Проверяю <b>заказчиков</b>\n"
                f"• 💰 Рассчитываю <b>цену</b> задач\n\n"
                f"🆓 У тебя <b>1 день бесплатно</b>!\n"
                f"Начни с выбора категорий ⬇️"
            )
        else:
            welcome_text = (
                f"С возвращением, <b>{user.full_name or message.from_user.full_name}</b>! 🚀\n\n"
                f"📊 Статус: {user.subscription_status}\n"
                f"📂 Категории: {len(user.categories or [])} выбрано\n"
                f"🔍 Парсер: {'🟢 Активен' if user.parser_active else '🔴 Выключен'}\n\n"
                f"Выбери действие ⬇️"
            )

    await message.answer(
        welcome_text,
        reply_markup=main_menu_keyboard(user),
        parse_mode="HTML"
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    await message.answer(
        "📱 <b>Главное меню</b>",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "main_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📱 <b>Главное меню</b>",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "parser_stats")
async def parser_stats(callback: CallbackQuery):
    from bot.parsers.manager import parser_manager
    stats = parser_manager.get_stats()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        stats,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()