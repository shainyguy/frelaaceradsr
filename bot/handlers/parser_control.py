from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot.database import async_session
from bot.models import User
from bot.parsers.manager import parser_manager
from bot.config import config

router = Router()


@router.callback_query(F.data == "parser_control")
async def parser_control(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await callback.answer("Нажмите /start")
        return

    if not user.has_active_subscription:
        await callback.message.edit_text(
            "⚠️ Для использования парсера нужна активная подписка.\n\n"
            "Оформите подписку или активируйте пробный период.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ Подписка", callback_data="subscription")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
            ]),
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
        f"Интервал проверки: {config.PARSE_INTERVAL} сек\n\n"
        f"{'⚠️ Выберите хотя бы одну категорию!' if cats == 0 else ''}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "parser_start")
async def parser_start(callback: CallbackQuery):
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

    await callback.answer("🟢 Парсер запущен! Заказы начнут приходить.", show_alert=True)
    # Перерисовываем меню
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

    await callback.answer("🔴 Парсер остановлен.", show_alert=True)
    await parser_control(callback)


@router.callback_query(F.data == "parse_now")
async def parse_now(callback: CallbackQuery):
    await callback.answer("🔍 Ищу заказы... Это может занять 10-20 секунд.")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user or not user.categories:
        await callback.message.answer("⚠️ Выберите хотя бы одну категорию!")
        return

    # Собираем ключевые слова
    keywords = []
    for cat in user.categories:
        cat_info = config.CATEGORIES.get(cat)
        if cat_info:
            keywords.extend(cat_info["keywords"])

    # Парсим
    orders = await parser_manager.parse_all(keywords)

    if not orders:
        await callback.message.answer(
            "😔 Новых заказов не найдено. Попробуйте позже или расширьте категории."
        )
        return

    # Отправляем первые 10
    sent = 0
    for order in orders[:10]:
        if parser_manager.is_sent(callback.from_user.id, order.hash):
            continue

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Сгенерировать отклик",
                    callback_data=f"generate_response:{order.hash[:32]}"
                ),
            ],
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
            [
                InlineKeyboardButton(text="🔗 Открыть", url=order.url)
            ] if order.url else []
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

    await callback.message.answer(f"✅ Найдено и отправлено: {sent} заказов")