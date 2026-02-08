from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.profile import router as profile_router
from bot.handlers.categories import router as categories_router
from bot.handlers.parser_control import router as parser_router
from bot.handlers.crm import router as crm_router
from bot.handlers.calculator import router as calculator_router
from bot.handlers.notifications import router as notifications_router
from bot.handlers.subscription import router as subscription_router
from bot.handlers.client_check import router as client_check_router


def get_all_routers() -> list[Router]:
    return [
        start_router,
        profile_router,
        categories_router,
        parser_router,
        crm_router,
        calculator_router,
        notifications_router,
        subscription_router,
        client_check_router,
    ]