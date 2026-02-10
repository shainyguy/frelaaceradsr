from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.gigachat import gigachat_service
from bot.handlers.middleware import check_subscription, SUB_REQUIRED_KB, SUB_REQUIRED_TEXT

router = Router()


class CalculatorStates(StatesGroup):
    waiting_description = State()
    waiting_hours = State()


@router.callback_query(F.data == "calculator")
async def calculator_menu(callback: CallbackQuery):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.message.edit_text(
            SUB_REQUIRED_TEXT,
            reply_markup=SUB_REQUIRED_KB,
            parse_mode="HTML"
        )
        await callback.answer()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 AI-оценка задачи", callback_data="calc_ai")],
        [InlineKeyboardButton(text="⏱ Калькулятор по часам", callback_data="calc_hours")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "💰 <b>Калькулятор цены</b>\n\nВыберите способ расчёта:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "calc_ai")
async def calc_ai_start(callback: CallbackQuery, state: FSMContext):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.answer("🔒 Нужна подписка!", show_alert=True)
        return

    await callback.message.edit_text(
        "🤖 <b>AI-оценка стоимости</b>\n\n"
        "Опишите задачу подробно:\n\n"
        "<b>Пример:</b>\n"
        "«Telegram-бот для магазина: каталог из БД, корзина, "
        "оплата через ЮKassa, админ-панель, уведомления»",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="calculator")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(CalculatorStates.waiting_description)
    await callback.answer()


@router.message(CalculatorStates.waiting_description)
async def calc_ai_process(message: Message, state: FSMContext):
    await state.clear()

    user, has_sub = await check_subscription(message.from_user.id)
    if not has_sub:
        await message.answer(SUB_REQUIRED_TEXT, reply_markup=SUB_REQUIRED_KB, parse_mode="HTML")
        return

    if len(message.text.strip()) < 10:
        await message.answer("⚠️ Опишите задачу подробнее (минимум 10 символов)")
        return

    processing_msg = await message.answer("⏳ AI анализирует задачу... (5-10 сек)")

    try:
        result = await gigachat_service.calculate_price(message.text, "general")
        await processing_msg.delete()
        await message.answer(
            f"💰 <b>AI-оценка стоимости</b>\n\n{result}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Оценить другую", callback_data="calc_ai")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await processing_msg.delete()
        await message.answer(
            f"❌ <b>Ошибка:</b> {str(e)[:300]}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="calc_ai")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
            ]),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "calc_hours")
async def calc_hours_start(callback: CallbackQuery, state: FSMContext):
    user, has_sub = await check_subscription(callback.from_user.id)
    if not has_sub:
        await callback.answer("🔒 Нужна подписка!", show_alert=True)
        return

    await callback.message.edit_text(
        "⏱ <b>Калькулятор по часам</b>\n\nВведите количество часов:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="calculator")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(CalculatorStates.waiting_hours)
    await callback.answer()


@router.message(CalculatorStates.waiting_hours)
async def calc_hours_process(message: Message, state: FSMContext):
    await state.clear()

    user, has_sub = await check_subscription(message.from_user.id)
    if not has_sub:
        await message.answer(SUB_REQUIRED_TEXT, reply_markup=SUB_REQUIRED_KB, parse_mode="HTML")
        return

    try:
        hours = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("❌ Введите число. Пример: 20")
        return

    rates = {
        "👶 Junior": 800,
        "👨‍💻 Middle": 1800,
        "👨‍🔬 Senior": 3000,
        "🏆 Expert": 5000,
    }

    text = f"⏱ <b>Расчёт: {hours} часов</b>\n\n"
    for level, rate in rates.items():
        total = hours * rate
        risk = total * 1.25
        text += f"{level} ({rate} ₽/ч): <b>{total:,.0f} ₽</b> (с рисками: {risk:,.0f} ₽)\n"

    text += "\n💡 Закладывайте +25-30% на правки и риски"

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤖 AI-оценка", callback_data="calc_ai")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
        ]),
        parse_mode="HTML"
    )
