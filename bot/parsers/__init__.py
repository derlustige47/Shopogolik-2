"""
Инициализация модуля парсеров.
Регистрирует все доступные парсеры в глобальном реестре.
"""
from .registry import registry
from .base import BaseParser, Listing, SearchFilters, Condition

# Импортируем конкретные парсеры
from .avito import AvitoParser
from .yula import YulaParser
from .telegram_groups import TelegramGroupsParser


def init_parsers() -> None:
    """
    Регистрирует все парсеры в реестре.

    Вызывается один раз при старте бота (в lifespan).
    Для добавления нового парсера:
      1. Создайте файл parsers/my_site.py
      2. Унаследуйте от BaseParser
      3. Добавьте registry.register() здесь
    """
    registry.register("Avito", AvitoParser())
    registry.register("Юла", YulaParser())
    registry.register("Telegram", TelegramGroupsParser())

    # --- Заглушки для будущих парсеров ---
    # registry.register("Ozon", OzonParser())
    # registry.register("Wildberries", WildberriesParser())
    # registry.register("AliExpress", AliExpressParser())
    # registry.register("Дром", DromParser())
    # registry.register("Auto.ru", AutoRuParser())


__all__ = [
    "registry", "init_parsers",
    "BaseParser", "Listing", "SearchFilters", "Condition",
    "AvitoParser", "YulaParser", "TelegramGroupsParser",
]
