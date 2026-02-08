from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.database import async_session
from bot.models import User

router = Router()


class ProfileEdit(StatesGroup):
    edit_bio = State()
    edit_portfolio = State()
    edit_rate = State()
    edit_experience = State()
    edit_name = State()


def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Имя", callback_data="edit_name"),
         InlineKeyboardButton(text="📝 О себе", callback_data="edit_bio")],
        [InlineKeyboardButton(text="🔗 Портфолио", callback_data="edit_portfolio"),
         InlineKeyboardButton(text="💵 Ставка/час", callback_data="edit_rate")],
        [InlineKeyboardButton(text="📅 Опыт (лет)", callback_data="edit_experience")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
    ])


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

    if not user:
        await callback.answer("Профиль не найден. Нажмите /start")
        return

    categories_names = []
    from bot.config import config
    for cat in (user.categories or []):
        cat_info = config.CATEGORIES.get(cat)
        if cat_info:
            categories_names.append(cat_info["name"])

    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📛 Имя: <b>{user.full_name or 'Не указано'}</b>\n"
        f"🆔 Username: @{user.username or 'не указан'}\n"
        f"📝 О себе: {user.bio or 'Не заполнено'}\n"
        f"🔗 Портфолио: {user.portfolio_url or 'Не указано'}\n"
        f"💵 Ставка: {user.hourly_rate or 'Не указана'} ₽/час\n"
        f"📅 Опыт: {user.experience_years} лет\n\n"
        f"📂 Категории: {', '.join(categories_names) if categories_names else 'Не выбраны'}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👀 Просмотрено заказов: {user.orders_viewed}\n"
        f"✉️ Откликов отправлено: {user.responses_sent}\n"
        f"✅ Заказов выиграно: {user.orders_won}\n"
        f"💰 Всего заработано: {user.total_earned:,.0f} ₽\n\n"
        f"⭐ {user.subscription_status}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "edit_name")
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✏️ Введите ваше имя (отображается в профиле):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="profile")]
        ])
    )
    await state.set_state(ProfileEdit.edit_name)
    await callback.answer()


@router.message(ProfileEdit.edit_name)
async def edit_name_save(message: Message, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.full_name = message.text[:200]
            await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Имя обновлено: <b>{message.text[:200]}</b>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "edit_bio")
async def edit_bio_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Расскажите о себе (будет использоваться для генерации откликов):\n\n"
        "Пример: «Fullstack-разработчик, 5 лет опыта. Специализация: Python, Django, React. "
        "Делал проекты для Сбера, Яндекса.»",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="profile")]
        ])
    )
    await state.set_state(ProfileEdit.edit_bio)
    await callback.answer()


@router.message(ProfileEdit.edit_bio)
async def edit_bio_save(message: Message, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.bio = message.text[:1000]
            await session.commit()

    await state.clear()
    await message.answer(
        "✅ Описание обновлено!",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "edit_portfolio")
async def edit_portfolio_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔗 Отправьте ссылку на портфолио (Behance, GitHub, сайт):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="profile")]
        ])
    )
    await state.set_state(ProfileEdit.edit_portfolio)
    await callback.answer()


@router.message(ProfileEdit.edit_portfolio)
async def edit_portfolio_save(message: Message, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.portfolio_url = message.text[:500]
            await session.commit()

    await state.clear()
    await message.answer(
        "✅ Портфолио обновлено!",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "edit_rate")
async def edit_rate_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💵 Укажите вашу ставку в рублях за час:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="profile")]
        ])
    )
    await state.set_state(ProfileEdit.edit_rate)
    await callback.answer()


@router.message(ProfileEdit.edit_rate)
async def edit_rate_save(message: Message, state: FSMContext):
    try:
        rate = float(message.text.replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число. Пример: 2500")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.hourly_rate = rate
            await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Ставка обновлена: <b>{rate:,.0f} ₽/час</b>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "edit_experience")
async def edit_exp_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📅 Сколько лет опыта?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="profile")]
        ])
    )
    await state.set_state(ProfileEdit.edit_experience)
    await callback.answer()


@router.message(ProfileEdit.edit_experience)
async def edit_exp_save(message: Message, state: FSMContext):
    try:
        exp = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число. Пример: 3")
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.experience_years = exp
            await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Опыт обновлён: <b>{exp} лет</b>",
        reply_markup=profile_keyboard(),
        parse_mode="HTML"
    )