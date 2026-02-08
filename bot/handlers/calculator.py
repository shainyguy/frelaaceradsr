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
        [InlineKeyboardButton(text="📊 Средние цены по рынку", callback_data="calc_market")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "💰 <b>Калькулятор цены</b>\n\n"
        "Оцените стоимость задачи с помощью AI или ручного расчёта.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "calc_ai")
async def calc_ai_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🤖 <b>AI-оценка задачи</b>\n\n"
        "Опишите задачу, и AI рассчитает рыночную стоимость:\n\n"
        "Пример: «Сделать Telegram-бота для интернет-магазина с каталогом, "
        "корзиной и оплатой через ЮKassa»",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="calculator")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(CalculatorStates.waiting_description)
    await callback.answer()


@router.message(CalculatorStates.waiting_description)
async def calc_ai_process(message: Message, state: FSMContext):
    await message.answer("⏳ Анализирую задачу...")

    try:
        result = await gigachat_service.calculate_price(
            message.text,
            "general"
        )
        await message.answer(
            f"💰 <b>AI-оценка стоимости:</b>\n\n{result}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Оценить другую", callback_data="calc_ai")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка: {str(e)[:200]}\n\nПопробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
            ])
        )

    await state.clear()


@router.callback_query(F.data == "calc_hours")
async def calc_hours_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "⏱ <b>Калькулятор по часам</b>\n\n"
        "Введите количество часов на выполнение задачи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="calculator")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(CalculatorStates.waiting_hours)
    await callback.answer()


@router.message(CalculatorStates.waiting_hours)
async def calc_hours_process(message: Message, state: FSMContext):
    try:
        hours = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("❌ Введите число часов. Пример: 20")
        return

    # Расценки по уровням
    rates = {
        "Junior": 800,
        "Middle": 1500,
        "Senior": 2500,
        "Lead/Expert": 4000,
    }

    text = f"⏱ <b>Расчёт стоимости ({hours} часов)</b>\n\n"
    for level, rate in rates.items():
        total = hours * rate
        text += f"👤 {level} ({rate} ₽/ч): <b>{total:,.0f} ₽</b>\n"

    text += f"\n💡 Не забудьте добавить 20-30% на риски и правки!"

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Другой расчёт", callback_data="calc_hours")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
        ]),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "calc_market")
async def calc_market(callback: CallbackQuery):
    text = (
        "📊 <b>Средние цены по рынку (2024)</b>\n\n"
        "🐍 <b>Python-разработка:</b>\n"
        "• Telegram-бот: 10,000 — 80,000 ₽\n"
        "• Парсер: 5,000 — 40,000 ₽\n"
        "• API/Backend: 30,000 — 200,000 ₽\n"
        "• Автоматизация: 10,000 — 60,000 ₽\n\n"
        "🌐 <b>Веб-разработка:</b>\n"
        "• Лендинг: 15,000 — 60,000 ₽\n"
        "• Корпоративный сайт: 50,000 — 300,000 ₽\n"
        "• Интернет-магазин: 80,000 — 500,000 ₽\n"
        "• Верстка макета: 5,000 — 30,000 ₽\n\n"
        "🎨 <b>Дизайн:</b>\n"
        "• Логотип: 5,000 — 50,000 ₽\n"
        "• Баннер: 1,000 — 10,000 ₽\n"
        "• UI/UX макет: 30,000 — 150,000 ₽\n"
        "• Фирменный стиль: 20,000 — 100,000 ₽\n\n"
        "✍️ <b>Копирайтинг:</b>\n"
        "• Статья (1000 слов): 1,000 — 5,000 ₽\n"
        "• SEO-текст: 500 — 3,000 ₽\n"
        "• Текст для лендинга: 5,000 — 20,000 ₽\n\n"
        "📱 <b>Мобильная разработка:</b>\n"
        "• Простое приложение: 100,000 — 500,000 ₽\n"
        "• Среднее приложение: 300,000 — 1,500,000 ₽\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤖 AI-оценка моей задачи", callback_data="calc_ai")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="calculator")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()