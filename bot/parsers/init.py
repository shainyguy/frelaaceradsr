from bot.parsers.base import BaseParser, FreelanceOrder
from bot.parsers.kwork import KworkParser
from bot.parsers.fl_ru import FLParser
from bot.parsers.habr_freelance import HabrFreelanceParser
from bot.parsers.hh_ru import HHParser
from bot.parsers.telegram_channels import TelegramChannelParser
from bot.parsers.freelance_ru import FreelanceRuParser
from bot.parsers.weblancer import WeblancerParser
from bot.parsers.manager import parser_manager

__all__ = [
    "BaseParser",
    "FreelanceOrder",
    "KworkParser",
    "FLParser",
    "HabrFreelanceParser",
    "HHParser",
    "TelegramChannelParser",
    "FreelanceRuParser",
    "WeblancerParser",
    "parser_manager",
]