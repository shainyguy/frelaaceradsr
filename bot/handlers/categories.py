from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot.database import async_session
from bot.models import User
from bot.config import config

router = Router()


def categories_keyboard(selected: list = None) -> InlineKeyboardMarkup:
    if selected is None:
        selected = []

    buttons = []
    for key, cat_info in config.CATEGORIES.items():
        check = "✅" if key in selected else "⬜"
        buttons.append([
            InlineKeyboardButton(
                text=f"{check} {cat_info['name']}",
                callback_data=f"toggle_cat:{key}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="✅ Выбрать все", callback_data="select_all_cats"),
        InlineKeyboardButton(text="❌ Сбросить", callback_data="clear_all_cats")
    ])
    buttons.append([
        InlineKeyboardButton(text="💾 Сохранить", callback_data="save_categories"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "categories")
async def show_categories(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

    selected = user.categories if user and user.categories else []

    await callback.message.edit_text(
        "📂 <b>Выберите категории для мониторинга</b>\n\n"
        "Бот будет искать заказы по выбранным категориям на всех биржах.",
        reply_markup=categories_keyboard(selected),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_cat:"))
async def toggle_category(callback: CallbackQuery):
    cat_key = callback.data.split(":")[1]

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Нажмите /start")
            return

        cats = list(user.categories or [])
        if cat_key in cats:
            cats.remove(cat_key)
        else:
            cats.append(cat_key)
        user.categories = cats
        await session.commit()

    await callback.message.edit_reply_markup(
        reply_markup=categories_keyboard(cats)
    )
    await callback.answer()


@router.callback_query(F.data == "select_all_cats")
async def select_all(callback: CallbackQuery):
    all_cats = list(config.CATEGORIES.keys())

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.categories = all_cats
            await session.commit()

    await callback.message.edit_reply_markup(
        reply_markup=categories_keyboard(all_cats)
    )
    await callback.answer("Все категории выбраны!")


@router.callback_query(F.data == "clear_all_cats")
async def clear_all(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.categories = []
            await session.commit()

    await callback.message.edit_reply_markup(
        reply_markup=categories_keyboard([])
    )
    await callback.answer("Категории сброшены!")


@router.callback_query(F.data == "save_categories")
async def save_categories(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

    count = len(user.categories) if user and user.categories else 0
    await callback.answer(f"✅ Сохранено! Выбрано категорий: {count}", show_alert=True)