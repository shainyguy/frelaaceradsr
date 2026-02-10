from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.gigachat import gigachat_service

router = Router()


class CalculatorStates(StatesGroup):
    waiting_description = State()
    waiting_hours = State()


@router.callback_query(F.data == "calculator")
async def calculator_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 AI-оценка задачи", callback_data="calc_ai")],
        [InlineKeyboardButton(text="⏱ Калькулятор по часам", callback_data="calc_hours")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "💰 <b>Калькулятор цены</b>\n\n"
        "Выберите способ расчёта:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "calc_ai")
async def calc_ai_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🤖 <b>AI-оценка стоимости</b>\n\n"
        "Опишите задачу подробно. Чем больше деталей — тем точнее оценка.\n\n"
        "<b>Хороший пример:</b>\n"
        "«Telegram-бот для интернет-магазина: каталог товаров из БД, "
        "корзина, оформление заказа, оплата через ЮKassa, "
        "админ-панель для добавления товаров, уведомления менеджеру»\n\n"
        "<b>Плохой пример:</b>\n"
        "«Нужен бот»",
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

    if len(message.text.strip()) < 10:
        await message.answer(
            "⚠️ Слишком короткое описание. Опишите задачу подробнее.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="calc_ai")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
            ])
        )
        return

    processing_msg = await message.answer("⏳ Анализирую задачу через AI... (5-10 секунд)")

    try:
        result = await gigachat_service.calculate_price(
            message.text,
            "general"
        )

        await processing_msg.delete()
        await message.answer(
            f"💰 <b>AI-оценка стоимости</b>\n\n{result}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Оценить другую задачу", callback_data="calc_ai")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await processing_msg.delete()
        await message.answer(
            f"❌ <b>Ошибка AI:</b> {str(e)[:300]}\n\n"
            f"Проверьте что GIGACHAT_SECRET задан правильно.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="calc_ai")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
            ]),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "calc_hours")
async def calc_hours_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⏱ <b>Калькулятор по часам</b>\n\n"
        "Введите количество часов на задачу:",
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

    try:
        hours = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("❌ Введите число. Пример: 20")
        return

    rates = {
        "👶 Junior (0-1 год)": 800,
        "👨‍💻 Middle (2-4 года)": 1800,
        "👨‍🔬 Senior (5+ лет)": 3000,
        "🏆 Lead/Expert": 5000,
    }

    text = f"⏱ <b>Расчёт: {hours} часов работы</b>\n\n"

    for level, rate in rates.items():
        total = hours * rate
        with_risks = total * 1.25  # +25% на риски
        text += (
            f"{level}\n"
            f"  Ставка: {rate:,} ₽/час\n"
            f"  Базовая: <b>{total:,.0f} ₽</b>\n"
            f"  С рисками (+25%): <b>{with_risks:,.0f} ₽</b>\n\n"
        )

    text += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 <b>Советы:</b>\n"
        f"• Всегда закладывайте +25-30% на правки\n"
        f"• Первый заказ у клиента — цена выше\n"
        f"• Срочность: +30-50% к цене\n"
        f"• Сложный ТЗ без чёткости: +20%"
    )

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤖 AI-оценка задачи", callback_data="calc_ai")],
            [InlineKeyboardButton(text="🔄 Другой расчёт", callback_data="calc_hours")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
        ]),
        parse_mode="HTML"
    )
