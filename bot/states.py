"""
FSM-состояния для ConversationHandler.
Определяют пошаговый диалог пользователя с ботом.
"""
from enum import IntEnum


class SearchStates(IntEnum):
    """
    Состояния конечного автомата (FSM) диалога поиска.

    Маршрут пользователя:
        MAIN_MENU → CATEGORY_SELECT → CONDITION_SELECT →
        PRICE_INPUT → PLATFORM_SELECT → SEARCHING → RESULTS
    """
    MAIN_MENU       = 0   # Главное меню
    CATEGORY_SELECT = 1   # Выбор категории (inline)
    CONDITION_SELECT = 2  # Выбор состояния: Новое / Б/у / Не важно
    PRICE_INPUT     = 3   # Ввод диапазона цены
    KEYWORD_INPUT   = 4   # Ввод ключевых слов (для прямого поиска)
    PLATFORM_SELECT = 5   # Выбор площадок (inline)
    CITY_SELECT     = 6   # Выбор города для TG-барахолок
    RESULTS         = 7   # Просмотр результатов с пагинацией
