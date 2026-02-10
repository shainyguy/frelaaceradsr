from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.database import async_session
from bot.models import User, Client, ParsedOrder
from bot.services.gigachat import gigachat_service
from bot.handlers.middleware import check_subscription, SUB_REQUIRED_KB, SUB_REQUIRED_TEXT

router = Router()


class ClientCheckStates(StatesGroup):
    waiting_client_info = State()


@router.callback_query(F.data == "client_check")
async def client_check_menu(callback: CallbackQuery):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.message.edit_text(
            SUB_REQUIRED_TEXT, reply_markup=SUB_REQUIRED_KB, parse_mode="HTML"
        )
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить заказчика", callback_data="check_new_client")],
        [InlineKeyboardButton(text="📋 Мои проверки", callback_data="my_clients")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "👁 <b>Проверка заказчиков</b>\n\n"
        "AI проанализирует надёжность заказчика.\n"
        "Отправьте любую информацию о нём.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_new_client")
async def check_new_client(callback: CallbackQuery, state: FSMContext):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.answer("🔒 Нужна подписка!", show_alert=True)
        return

    await callback.message.edit_text(
        "🔍 Отправьте информацию о заказчике:\n"
        "• Имя/ник\n• Ссылку на профиль\n• Текст заказа\n• Условия",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="client_check")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(ClientCheckStates.waiting_client_info)
    await callback.answer()


@router.message(ClientCheckStates.waiting_client_info)
async def process_client_check(message: Message, state: FSMContext):
    await state.clear()

    user, has_sub = await check_subscription(message.from_user.id)
    if not has_sub:
        await message.answer(SUB_REQUIRED_TEXT, reply_markup=SUB_REQUIRED_KB, parse_mode="HTML")
        return

    if len(message.text.strip()) < 10:
        await message.answer("⚠️ Напишите подробнее")
        return

    processing_msg = await message.answer("⏳ Анализирую через AI... (5-10 сек)")

    try:
        analysis = await gigachat_service.analyze_client("Заказчик", message.text)

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            u = result.scalar_one_or_none()
            if u:
                client = Client(
                    user_id=u.id, name=message.text[:100],
                    notes=analysis[:500], trust_score=50
                )
                session.add(client)
                await session.commit()

        await processing_msg.delete()
        await message.answer(
            f"👁 <b>Анализ заказчика</b>\n\n{analysis}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Проверить другого", callback_data="check_new_client")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="client_check")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await processing_msg.delete()
        await message.answer(f"❌ Ошибка: {str(e)[:300]}", parse_mode="HTML")


@router.callback_query(F.data.startswith("check_client:"))
async def check_client_from_order(callback: CallbackQuery):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.answer("🔒 Нужна подписка!", show_alert=True)
        return

    order_hash = callback.data.split(":")[1]

    async with async_session() as session:
        parsed_result = await session.execute(
            select(ParsedOrder).where(ParsedOrder.hash.startswith(order_hash))
        )
        parsed = parsed_result.scalar_one_or_none()

    if not parsed:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await callback.answer("⏳ Анализирую... 5-10 сек")

    client_info = f"Источник: {parsed.source}\nЗаказ: {parsed.title}\n"
    client_info += f"Описание: {parsed.description[:1000]}\n"
    if parsed.client_name:
        client_info += f"Имя: {parsed.client_name}\n"
    if parsed.budget:
        client_info += f"Бюджет: {parsed.budget}\n"

    try:
        analysis = await gigachat_service.analyze_client(
            parsed.client_name or "Неизвестный", client_info
        )
        await callback.message.answer(
            f"👁 <b>Анализ заказчика</b>\n\n{analysis}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)[:300]}", parse_mode="HTML")


@router.callback_query(F.data.startswith("generate_response:"))
async def generate_response(callback: CallbackQuery):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.answer("🔒 Нужна подписка!", show_alert=True)
        return

    order_hash = callback.data.split(":")[1]

    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()

        parsed_result = await session.execute(
            select(ParsedOrder).where(ParsedOrder.hash.startswith(order_hash))
        )
        parsed = parsed_result.scalar_one_or_none()

    if not parsed:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await callback.answer("⏳ Генерирую отклик... 5-10 сек")

    try:
        response = await gigachat_service.generate_response(
            order_title=parsed.title,
            order_description=parsed.description or "",
            user_bio=user.bio or "",
            user_experience=user.experience_years or 0
        )

        await callback.message.answer(
            f"✍️ <b>Отклик на заказ:</b>\n"
            f"📋 <i>{parsed.title[:100]}</i>\n\n"
            f"{'━' * 25}\n\n{response}\n\n{'━' * 25}\n\n"
            f"💡 <i>Скопируйте и отредактируйте под себя</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Другой вариант",
                    callback_data=f"generate_response:{order_hash}")],
                [InlineKeyboardButton(text="📥 В CRM",
                    callback_data=f"save_crm:{order_hash}")],
            ]),
            parse_mode="HTML"
        )

        async with async_session() as session:
            r = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            u = r.scalar_one_or_none()
            if u:
                u.responses_sent += 1
                await session.commit()

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)[:300]}", parse_mode="HTML")


@router.callback_query(F.data == "my_clients")
async def my_clients(callback: CallbackQuery):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.answer("🔒 Нужна подписка!", show_alert=True)
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        clients_result = await session.execute(
            select(Client).where(Client.user_id == user.id)
            .order_by(Client.created_at.desc()).limit(5)
        )
        clients = clients_result.scalars().all()

    if not clients:
        await callback.answer("Нет проверок", show_alert=True)
        return

    text = "📋 <b>Проверки:</b>\n\n"
    for c in clients:
        text += f"👤 <b>{c.name[:50]}</b>\n📝 {(c.notes or '')[:100]}\n\n"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
