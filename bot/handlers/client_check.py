from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.database import async_session
from bot.models import User, Client, ParsedOrder
from bot.services.gigachat import gigachat_service

router = Router()


class ClientCheckStates(StatesGroup):
    waiting_client_info = State()
    add_client_name = State()
    add_client_notes = State()


@router.callback_query(F.data == "client_check")
async def client_check_menu(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        clients_result = await session.execute(
            select(Client).where(Client.user_id == user.id).order_by(Client.created_at.desc()).limit(10)
        )
        clients = clients_result.scalars().all()

    text = (
        "👁 <b>Проверка заказчиков</b>\n\n"
        "Проверьте надёжность заказчика перед тем, как браться за работу.\n\n"
    )

    if clients:
        text += "<b>Последние проверки:</b>\n"
        for c in clients[:5]:
            trust_emoji = "🟢" if c.trust_score >= 70 else "🟡" if c.trust_score >= 40 else "🔴"
            text += f"{trust_emoji} {c.name} — {c.trust_score}/100\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить нового", callback_data="check_new_client")],
        [InlineKeyboardButton(text="📋 Мои заказчики", callback_data="my_clients")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "check_new_client")
async def check_new_client(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 <b>Проверка заказчика</b>\n\n"
        "Отправьте информацию о заказчике:\n"
        "• Имя/никнейм\n"
        "• Ссылку на профиль\n"
        "• Описание заказа\n"
        "• Любую известную информацию\n\n"
        "AI проанализирует и даст рекомендацию.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="client_check")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(ClientCheckStates.waiting_client_info)
    await callback.answer()


@router.message(ClientCheckStates.waiting_client_info)
async def process_client_check(message: Message, state: FSMContext):
    await message.answer("⏳ Анализирую заказчика...")

    try:
        analysis = await gigachat_service.analyze_client(
            "Заказчик",
            message.text
        )

        # Сохраняем в базу
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()

            client = Client(
                user_id=user.id,
                name=message.text[:100],
                notes=message.text[:500],
                trust_score=50,  # Дефолтный
            )
            session.add(client)
            await session.commit()

        await message.answer(
            f"👁 <b>Результат проверки:</b>\n\n{analysis}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Проверить другого", callback_data="check_new_client")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="client_check")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка анализа: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="client_check")]
            ])
        )

    await state.clear()


@router.callback_query(F.data.startswith("check_client:"))
async def check_client_from_order(callback: CallbackQuery):
    order_hash = callback.data.split(":")[1]

    async with async_session() as session:
        parsed_result = await session.execute(
            select(ParsedOrder).where(ParsedOrder.hash.startswith(order_hash))
        )
        parsed = parsed_result.scalar_one_or_none()

    if not parsed:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await callback.answer("⏳ Анализирую заказчика...")

    client_info = f"Источник: {parsed.source}\nЗаказ: {parsed.title}\n"
    if parsed.client_name:
        client_info += f"Имя: {parsed.client_name}\n"
    client_info += f"Описание: {parsed.description[:500]}"

    try:
        analysis = await gigachat_service.analyze_client(
            parsed.client_name or "Неизвестный",
            client_info
        )

        await callback.message.answer(
            f"👁 <b>Анализ заказчика:</b>\n\n{analysis}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)[:200]}")


@router.callback_query(F.data == "my_clients")
async def my_clients(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        clients_result = await session.execute(
            select(Client).where(Client.user_id == user.id).order_by(Client.created_at.desc()).limit(20)
        )
        clients = clients_result.scalars().all()

    if not clients:
        await callback.answer("У вас пока нет сохранённых заказчиков", show_alert=True)
        return

    for client in clients[:10]:
        trust_emoji = "🟢" if client.trust_score >= 70 else "🟡" if client.trust_score >= 40 else "🔴"
        text = (
            f"{trust_emoji} <b>{client.name}</b>\n"
            f"📊 Доверие: {client.trust_score}/100\n"
            f"📝 {client.notes[:200] if client.notes else 'Нет заметок'}\n"
        )
        await callback.message.answer(text, parse_mode="HTML")

    await callback.answer()


# Обработчик генерации отклика
@router.callback_query(F.data.startswith("generate_response:"))
async def generate_response(callback: CallbackQuery):
    order_hash = callback.data.split(":")[1]

    async with async_session() as session:
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()

        if not user or not user.has_active_subscription:
            await callback.answer("⚠️ Нужна активная подписка!", show_alert=True)
            return

        # Получаем заказ
        parsed_result = await session.execute(
            select(ParsedOrder).where(ParsedOrder.hash.startswith(order_hash))
        )
        parsed = parsed_result.scalar_one_or_none()

    if not parsed:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await callback.answer("⏳ Генерирую отклик... (3-5 сек)")

    try:
        response = await gigachat_service.generate_response(
            order_title=parsed.title,
            order_description=parsed.description or "",
            user_bio=user.bio or "",
            user_experience=user.experience_years or 0
        )

        text = (
            f"✍️ <b>Отклик на заказ:</b>\n"
            f"📋 {parsed.title[:100]}\n\n"
            f"{'─' * 30}\n\n"
            f"{response}\n\n"
            f"{'─' * 30}\n\n"
            f"💡 <i>Скопируйте и отправьте заказчику. Можно отредактировать.</i>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data=f"generate_response:{order_hash}")],
            [InlineKeyboardButton(text="📥 Сохранить в CRM", callback_data=f"save_crm:{order_hash}")],
        ])

        await callback.message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        # Обновляем статистику
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.responses_sent += 1
                await session.commit()

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка генерации: {str(e)[:200]}")