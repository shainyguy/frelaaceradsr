from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.database import async_session
from bot.models import User

router = Router()


class NotificationStates(StatesGroup):
    set_min_budget = State()
    set_quiet_start = State()
    set_quiet_end = State()


@router.callback_query(F.data == "notifications")
async def notifications_menu(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await callback.answer("Нажмите /start")
        return

    notif_status = "🟢 Включены" if user.notifications_enabled else "🔴 Выключены"
    instant_status = "⚡ Мгновенные" if user.instant_notify else "📦 Сводкой"

    text = (
        f"🔔 <b>Настройки уведомлений</b>\n\n"
        f"Статус: {notif_status}\n"
        f"Режим: {instant_status}\n"
        f"💰 Минимальный бюджет: {user.min_budget:,} ₽\n"
        f"🌙 Тихие часы: {user.quiet_hours_start}:00 — {user.quiet_hours_end}:00 (МСК)\n"
    )

    toggle_text = "🔴 Выключить" if user.notifications_enabled else "🟢 Включить"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="toggle_notifications")],
        [InlineKeyboardButton(
            text="⚡ Мгновенные" if not user.instant_notify else "📦 Сводкой",
            callback_data="toggle_instant"
        )],
        [InlineKeyboardButton(text="💰 Мин. бюджет", callback_data="set_min_budget")],
        [InlineKeyboardButton(text="🌙 Тихие часы", callback_data="set_quiet_hours")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        user.notifications_enabled = not user.notifications_enabled
        await session.commit()

    status = "включены" if user.notifications_enabled else "выключены"
    await callback.answer(f"Уведомления {status}!", show_alert=True)
    await notifications_menu(callback)


@router.callback_query(F.data == "toggle_instant")
async def toggle_instant(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        user.instant_notify = not user.instant_notify
        await session.commit()

    mode = "мгновенные" if user.instant_notify else "сводкой"
    await callback.answer(f"Режим: {mode}", show_alert=True)
    await notifications_menu(callback)


@router.callback_query(F.data == "set_min_budget")
async def set_min_budget_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💰 Введите минимальный бюджет заказа (₽).\n"
        "Заказы с бюджетом ниже этой суммы не будут приходить.\n\n"
        "Введите 0 чтобы получать все заказы.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="notifications")]
        ])
    )
    await state.set_state(NotificationStates.set_min_budget)
    await callback.answer()


@router.message(NotificationStates.set_min_budget)
async def set_min_budget_save(message: Message, state: FSMContext):
    try:
        budget = int(message.text.replace(" ", "").strip())
    except ValueError:
        await message.answer("❌ Введите число. Пример: 5000")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.min_budget = max(0, budget)
            await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Минимальный бюджет: <b>{budget:,} ₽</b>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "set_quiet_hours")
async def set_quiet_hours(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌙 22:00-07:00", callback_data="quiet:22:7"),
            InlineKeyboardButton(text="🌙 23:00-08:00", callback_data="quiet:23:8"),
        ],
        [
            InlineKeyboardButton(text="🌙 00:00-09:00", callback_data="quiet:0:9"),
            InlineKeyboardButton(text="🔔 Без тихих часов", callback_data="quiet:0:0"),
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="notifications")]
    ])

    await callback.message.edit_text(
        "🌙 Выберите тихие часы (МСК).\n"
        "В это время уведомления не приходят.",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quiet:"))
async def set_quiet(callback: CallbackQuery):
    parts = callback.data.split(":")
    start = int(parts[1])
    end = int(parts[2])

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.quiet_hours_start = start
            user.quiet_hours_end = end
            await session.commit()

    if start == 0 and end == 0:
        await callback.answer("🔔 Тихие часы отключены!", show_alert=True)
    else:
        await callback.answer(f"🌙 Тихие часы: {start}:00-{end}:00", show_alert=True)

    await notifications_menu(callback)