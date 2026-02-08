from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.database import async_session
from bot.models import User, Order, ParsedOrder

router = Router()


class CRMStates(StatesGroup):
    add_note = State()
    set_price = State()
    set_earned = State()


STATUS_LABELS = {
    "new": "🆕 Новый",
    "responded": "✉️ Откликнулся",
    "in_progress": "⚙️ В работе",
    "completed": "✅ Завершён",
    "cancelled": "❌ Отменён",
}


@router.callback_query(F.data == "crm_menu")
async def crm_menu(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Нажмите /start")
            return

        orders_result = await session.execute(
            select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(50)
        )
        orders = orders_result.scalars().all()

    # Статистика
    stats = {}
    for status in STATUS_LABELS:
        stats[status] = len([o for o in orders if o.status == status])

    total_earned = sum(o.my_price or 0 for o in orders if o.status == "completed")

    text = (
        f"📊 <b>CRM — Ваши заказы</b>\n\n"
        f"🆕 Новые: {stats.get('new', 0)}\n"
        f"✉️ Откликнулся: {stats.get('responded', 0)}\n"
        f"⚙️ В работе: {stats.get('in_progress', 0)}\n"
        f"✅ Завершено: {stats.get('completed', 0)}\n"
        f"❌ Отменено: {stats.get('cancelled', 0)}\n\n"
        f"💰 Заработано: <b>{total_earned:,.0f} ₽</b>\n"
        f"📋 Всего заказов: {len(orders)}"
    )

    buttons = []
    for status_key, status_label in STATUS_LABELS.items():
        count = stats.get(status_key, 0)
        if count > 0:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{status_label} ({count})",
                    callback_data=f"crm_list:{status_key}"
                )
            ])

    buttons.append([
        InlineKeyboardButton(text="📋 Все заказы", callback_data="crm_list:all")
    ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")
    ])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("crm_list:"))
async def crm_list(callback: CallbackQuery):
    status_filter = callback.data.split(":")[1]

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        query = select(Order).where(Order.user_id == user.id)
        if status_filter != "all":
            query = query.where(Order.status == status_filter)
        query = query.order_by(Order.created_at.desc()).limit(10)

        orders_result = await session.execute(query)
        orders = orders_result.scalars().all()

    if not orders:
        await callback.answer("Нет заказов в этой категории", show_alert=True)
        return

    for order in orders:
        status_label = STATUS_LABELS.get(order.status, order.status)
        text = (
            f"{status_label}\n"
            f"📋 <b>{order.title[:100]}</b>\n"
            f"🏷 Источник: {order.source}\n"
            f"💰 Бюджет: {order.budget or 'Не указан'}\n"
            f"💵 Моя цена: {order.my_price or 'Не указана'}\n"
        )
        if order.notes:
            text += f"📝 Заметки: {order.notes[:100]}\n"

        buttons = [
            [
                InlineKeyboardButton(text="➡️ Сменить статус", callback_data=f"crm_status:{order.id}"),
                InlineKeyboardButton(text="💵 Моя цена", callback_data=f"crm_price:{order.id}"),
            ],
            [
                InlineKeyboardButton(text="📝 Заметка", callback_data=f"crm_note:{order.id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"crm_delete:{order.id}"),
            ],
        ]
        if order.url:
            buttons.append([
                InlineKeyboardButton(text="🔗 Открыть", url=order.url)
            ])

        await callback.message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )

    await callback.answer()


@router.callback_query(F.data.startswith("save_crm:"))
async def save_to_crm(callback: CallbackQuery):
    order_hash = callback.data.split(":")[1]

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        # Ищем заказ в спарсенных
        parsed_result = await session.execute(
            select(ParsedOrder).where(ParsedOrder.hash.startswith(order_hash))
        )
        parsed = parsed_result.scalar_one_or_none()

        if not parsed:
            await callback.answer("⚠️ Заказ не найден в базе", show_alert=True)
            return

        # Проверяем дубликат в CRM
        existing = await session.execute(
            select(Order).where(
                Order.user_id == user.id,
                Order.external_id == parsed.hash
            )
        )
        if existing.scalar_one_or_none():
            await callback.answer("ℹ️ Заказ уже в CRM!", show_alert=True)
            return

        # Сохраняем
        order = Order(
            user_id=user.id,
            external_id=parsed.hash,
            source=parsed.source,
            title=parsed.title,
            description=parsed.description,
            budget=parsed.budget,
            budget_value=parsed.budget_value,
            url=parsed.url,
            category=parsed.category,
            client_name=parsed.client_name,
            deadline=parsed.deadline,
            status="new",
        )
        session.add(order)
        await session.commit()

    await callback.answer("✅ Заказ сохранён в CRM!", show_alert=True)


@router.callback_query(F.data.startswith("crm_status:"))
async def change_status(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])

    buttons = []
    for key, label in STATUS_LABELS.items():
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"set_status:{order_id}:{key}")
        ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="crm_menu")
    ])

    await callback.message.edit_text(
        "Выберите новый статус:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_status:"))
async def set_status(callback: CallbackQuery):
    parts = callback.data.split(":")
    order_id = int(parts[1])
    new_status = parts[2]

    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order.status = new_status

            # Если завершён — обновляем статистику пользователя
            if new_status == "completed":
                user_result = await session.execute(
                    select(User).where(User.id == order.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    user.orders_won += 1
                    if order.my_price:
                        user.total_earned += order.my_price

            await session.commit()

    await callback.answer(f"✅ Статус изменён: {STATUS_LABELS.get(new_status, new_status)}", show_alert=True)


@router.callback_query(F.data.startswith("crm_price:"))
async def crm_price_start(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(crm_order_id=order_id)
    await state.set_state(CRMStates.set_price)

    await callback.message.answer("💵 Введите вашу цену за этот заказ (в рублях):")
    await callback.answer()


@router.message(CRMStates.set_price)
async def crm_price_save(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число")
        return

    data = await state.get_data()
    order_id = data.get("crm_order_id")

    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order.my_price = price
            await session.commit()

    await state.clear()
    await message.answer(f"✅ Цена установлена: <b>{price:,.0f} ₽</b>", parse_mode="HTML")


@router.callback_query(F.data.startswith("crm_note:"))
async def crm_note_start(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split(":")[1])
    await state.update_data(crm_order_id=order_id)
    await state.set_state(CRMStates.add_note)

    await callback.message.answer("📝 Введите заметку к заказу:")
    await callback.answer()


@router.message(CRMStates.add_note)
async def crm_note_save(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("crm_order_id")

    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order.notes = message.text[:1000]
            await session.commit()

    await state.clear()
    await message.answer("✅ Заметка сохранена!")


@router.callback_query(F.data.startswith("crm_delete:"))
async def crm_delete(callback: CallbackQuery):
    order_id = int(callback.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            await session.delete(order)
            await session.commit()

    await callback.answer("🗑 Заказ удалён из CRM", show_alert=True)