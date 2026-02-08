from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot.database import async_session
from bot.models import User, Payment
from bot.services.payment import payment_service
from bot.config import config

router = Router()


@router.callback_query(F.data == "subscription")
async def subscription_menu(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await callback.answer("Нажмите /start")
        return

    text = (
        f"⭐ <b>Подписка Freelance Radar</b>\n\n"
        f"Текущий статус: {user.subscription_status}\n\n"
        f"<b>Что входит в подписку:</b>\n"
        f"✅ Мониторинг 7+ бирж в реальном времени\n"
        f"✅ Мгновенные уведомления о новых заказах\n"
        f"✅ AI-генерация откликов (GigaChat)\n"
        f"✅ CRM для управления заказами\n"
        f"✅ Проверка заказчиков\n"
        f"✅ Калькулятор цен\n"
        f"✅ Mini App\n\n"
        f"💰 Стоимость: <b>{config.SUBSCRIPTION_PRICE} ₽/мес</b>\n"
        f"🎯 Окупается с одного заказа!"
    )

    buttons = []
    if not user.has_active_subscription:
        buttons.append([
            InlineKeyboardButton(
                text=f"💳 Оплатить {config.SUBSCRIPTION_PRICE} ₽",
                callback_data="pay_subscription"
            )
        ])

    # Кнопка проверки оплаты
    buttons.append([
        InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_payment")
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


@router.callback_query(F.data == "pay_subscription")
async def pay_subscription(callback: CallbackQuery):
    try:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()

            # Создаём платёж
            payment_data = await payment_service.create_payment(
                user_id=user.id,
                amount=config.SUBSCRIPTION_PRICE
            )

            # Сохраняем в БД
            payment = Payment(
                user_id=user.id,
                yookassa_id=payment_data["id"],
                amount=config.SUBSCRIPTION_PRICE,
                status="pending",
                payment_url=payment_data["url"]
            )
            session.add(payment)
            await session.commit()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_data["url"])],
            [InlineKeyboardButton(text="🔄 Я оплатил — проверить", callback_data="check_payment")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
        ])

        await callback.message.edit_text(
            f"💳 <b>Оплата подписки</b>\n\n"
            f"Сумма: <b>{config.SUBSCRIPTION_PRICE} ₽</b>\n"
            f"Период: {config.SUBSCRIPTION_DAYS} дней\n\n"
            f"Нажмите кнопку ниже для оплаты через ЮKassa.\n"
            f"После оплаты нажмите «Проверить».",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка создания платежа: {str(e)[:200]}\n\n"
            f"Попробуйте позже или обратитесь в поддержку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="subscription")]
            ])
        )

    await callback.answer()


@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        # Находим последний pending платёж
        payment_result = await session.execute(
            select(Payment).where(
                Payment.user_id == user.id,
                Payment.status == "pending"
            ).order_by(Payment.created_at.desc()).limit(1)
        )
        payment = payment_result.scalar_one_or_none()

        if not payment:
            await callback.answer("Нет ожидающих платежей", show_alert=True)
            return

        try:
            payment_info = await payment_service.check_payment(payment.yookassa_id)

            if payment_info["status"] == "succeeded":
                payment.status = "succeeded"
                user.is_trial = False
                user.subscription_end = datetime.utcnow() + timedelta(days=config.SUBSCRIPTION_DAYS)
                await session.commit()

                await callback.message.edit_text(
                    "🎉 <b>Оплата прошла успешно!</b>\n\n"
                    f"Подписка активирована на {config.SUBSCRIPTION_DAYS} дней.\n"
                    f"Статус: {user.subscription_status}\n\n"
                    f"Теперь запустите парсер и получайте заказы! 🚀",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔍 Запустить парсер", callback_data="parser_control")],
                        [InlineKeyboardButton(text="◀️ Меню", callback_data="main_menu")]
                    ]),
                    parse_mode="HTML"
                )
            elif payment_info["status"] == "canceled":
                payment.status = "cancelled"
                await session.commit()
                await callback.answer("❌ Платёж отменён", show_alert=True)
            else:
                await callback.answer("⏳ Платёж ещё обрабатывается. Подождите.", show_alert=True)

        except Exception as e:
            await callback.answer(f"Ошибка проверки: {str(e)[:100]}", show_alert=True)