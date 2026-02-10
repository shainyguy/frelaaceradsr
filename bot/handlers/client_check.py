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


@router.callback_query(F.data == "client_check")
async def client_check_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить заказчика", callback_data="check_new_client")],
        [InlineKeyboardButton(text="📋 Мои проверки", callback_data="my_clients")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "👁 <b>Проверка заказчиков</b>\n\n"
        "AI проанализирует заказчика и даст рекомендацию:\n"
        "• Надёжность\n"
        "• Красные флаги\n"
        "• Как защититься\n"
        "• Стоит ли работать\n\n"
        "Отправьте любую информацию: ник, ссылку на профиль, "
        "описание заказа, переписку.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "check_new_client")
async def check_new_client(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 <b>Проверка заказчика</b>\n\n"
        "Отправьте информацию о заказчике:\n\n"
        "• Имя / никнейм\n"
        "• Ссылку на профиль\n"
        "• Текст заказа\n"
        "• Что он пишет в переписке\n"
        "• Условия которые предлагает\n\n"
        "Чем больше информации — тем точнее анализ.",
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

    if len(message.text.strip()) < 10:
        await message.answer(
            "⚠️ Слишком мало информации. Напишите подробнее.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="check_new_client")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="client_check")]
            ])
        )
        return

    processing_msg = await message.answer("⏳ Анализирую заказчика через AI... (5-10 секунд)")

    try:
        analysis = await gigachat_service.analyze_client(
            "Заказчик",
            message.text
        )

        # Сохраняем
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()

            if user:
                client = Client(
                    user_id=user.id,
                    name=message.text[:100],
                    notes=analysis[:500],
                    trust_score=50,
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
        await message.answer(
            f"❌ <b>Ошибка AI:</b> {str(e)[:300]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="check_new_client")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="client_check")]
            ]),
            parse_mode="HTML"
        )


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

    await callback.answer("⏳ Анализирую... (5-10 сек)")

    client_info = (
        f"Источник: {parsed.source}\n"
        f"Заказ: {parsed.title}\n"
        f"Описание: {parsed.description[:1000]}\n"
    )
    if parsed.client_name:
        client_info += f"Имя заказчика: {parsed.client_name}\n"
    if parsed.budget:
        client_info += f"Бюджет: {parsed.budget}\n"

    try:
        analysis = await gigachat_service.analyze_client(
            parsed.client_name or "Неизвестный",
            client_info
        )

        await callback.message.answer(
            f"👁 <b>Анализ заказчика</b>\n\n{analysis}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(
            f"❌ <b>Ошибка AI:</b> {str(e)[:300]}",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("generate_response:"))
async def generate_response(callback: CallbackQuery):
    order_hash = callback.data.split(":")[1]

    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = user_result.scalar_one_or_none()

        if not user or not user.has_active_subscription:
            await callback.answer("⚠️ Нужна активная подписка!", show_alert=True)
            return

        parsed_result = await session.execute(
            select(ParsedOrder).where(ParsedOrder.hash.startswith(order_hash))
        )
        parsed = parsed_result.scalar_one_or_none()

    if not parsed:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await callback.answer("⏳ Генерирую отклик через AI... (5-10 сек)")

    try:
        response = await gigachat_service.generate_response(
            order_title=parsed.title,
            order_description=parsed.description or "",
            user_bio=user.bio or "",
            user_experience=user.experience_years or 0
        )

        text = (
            f"✍️ <b>Отклик на заказ:</b>\n"
            f"📋 <i>{parsed.title[:100]}</i>\n\n"
            f"{'━' * 25}\n\n"
            f"{response}\n\n"
            f"{'━' * 25}\n\n"
            f"💡 <i>Скопируйте, отредактируйте под себя и отправьте заказчику</i>"
        )

        await callback.message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Другой вариант",
                    callback_data=f"generate_response:{order_hash}"
                )],
                [InlineKeyboardButton(
                    text="📥 Сохранить в CRM",
                    callback_data=f"save_crm:{order_hash}"
                )],
            ]),
            parse_mode="HTML"
        )

        # Обновляем статистику
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            u = result.scalar_one_or_none()
            if u:
                u.responses_sent += 1
                await session.commit()

    except Exception as e:
        await callback.message.answer(
            f"❌ <b>Ошибка генерации:</b> {str(e)[:300]}\n\n"
            f"Убедитесь что GIGACHAT_SECRET задан правильно.",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "my_clients")
async def my_clients(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Нажмите /start")
            return

        clients_result = await session.execute(
            select(Client).where(Client.user_id == user.id)
            .order_by(Client.created_at.desc()).limit(10)
        )
        clients = clients_result.scalars().all()

    if not clients:
        await callback.answer("Нет сохранённых проверок", show_alert=True)
        return

    text = "📋 <b>Последние проверки:</b>\n\n"
    for c in clients[:5]:
        text += (
            f"👤 <b>{c.name[:50]}</b>\n"
            f"📝 {(c.notes or 'Нет данных')[:150]}\n\n"
        )

    await callback.message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Новая проверка", callback_data="check_new_client")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="client_check")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()
