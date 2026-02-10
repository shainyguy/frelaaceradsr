from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot.database import async_session
from bot.models import User
from bot.parsers.manager import parser_manager
from bot.config import config
from bot.handlers.middleware import check_subscription, SUB_REQUIRED_KB, SUB_REQUIRED_TEXT

router = Router()


@router.callback_query(F.data == "parser_control")
async def parser_control(callback: CallbackQuery):
    user, has_sub = await check_subscription(callback.from_user.id)

    if not user:
        await callback.answer("Нажмите /start", show_alert=True)
        return

    if not has_sub:
        await callback.message.edit_text(
            SUB_REQUIRED_TEXT,
            reply_markup=SUB_REQUIRED_KB,
            parse_mode="HTML"
        )
        await callback.answer()
        return

    status = "🟢 Активен" if user.parser_active else "🔴 Выключен"
    cats = len(user.categories or [])

    toggle_text = "⏸ Остановить" if user.parser_active else "▶️ Запустить"
    toggle_data = "parser_stop" if user.parser_active else "parser_start"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
        [InlineKeyboardButton(text="🔍 Найти заказы сейчас", callback_data="parse_now")],
        [InlineKeyboardButton(text="📊 Статус парсеров", callback_data="parser_stats")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        f"🔍 <b>Управление парсером</b>\n\n"
        f"Статус: {status}\n"
        f"Категорий выбрано: {cats}\n"
        f"Интервал: {config.PARSE_INTERVAL} сек\n\n"
        f"{'⚠️ Выберите хотя бы одну категорию!' if cats == 0 else ''}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "parser_start")
async def parser_start(callback: CallbackQuery):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.answer("🔒 Нужна подписка!", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user.categories:
            await callback.answer("⚠️ Сначала выберите категории!", show_alert=True)
            return

        user.parser_active = True
        await session.commit()

    await callback.answer("🟢 Парсер запущен!", show_alert=True)
    await parser_control(callback)


@router.callback_query(F.data == "parser_stop")
async def parser_stop(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        user.parser_active = False
        await session.commit()

    await callback.answer("🔴 Парсер остановлен", show_alert=True)
    await parser_control(callback)


@router.callback_query(F.data == "parse_now")
async def parse_now(callback: CallbackQuery):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.answer("🔒 Нужна подписка!", show_alert=True)
        return

    if not user or not user.categories:
        await callback.answer("⚠️ Выберите категории!", show_alert=True)
        return

    await callback.answer("🔍 Ищу заказы... 10-20 секунд")

    keywords = []
    for cat in user.categories:
        cat_info = config.CATEGORIES.get(cat)
        if cat_info:
            keywords.extend(cat_info["keywords"])

    orders = await parser_manager.parse_all(keywords)

    if not orders:
        await callback.message.answer("😔 Новых заказов не найдено. Попробуйте позже.")
        return

    sent = 0
    for order in orders[:10]:
        if parser_manager.is_sent(callback.from_user.id, order.hash):
            continue

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✍️ Сгенерировать отклик",
                callback_data=f"generate_response:{order.hash[:32]}"
            )],
            [
                InlineKeyboardButton(
                    text="📥 В CRM",
                    callback_data=f"save_crm:{order.hash[:32]}"
                ),
                InlineKeyboardButton(
                    text="🔍 Проверить",
                    callback_data=f"check_client:{order.hash[:32]}"
                ),
            ],
            [InlineKeyboardButton(text="🔗 Открыть", url=order.url)] if order.url else []
        ])

        try:
            await callback.message.answer(
                order.to_message(),
                reply_markup=keyboard,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            parser_manager.mark_sent(callback.from_user.id, order.hash)
            sent += 1
        except Exception:
            continue

    await callback.message.answer(f"✅ Найдено: {sent} заказов")
