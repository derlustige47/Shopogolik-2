"""
Базовый класс парсера и модели данных.
Все парсеры конкретных площадок наследуются от BaseParser.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ============================================================
#                     МОДЕЛИ ДАННЫХ
# ============================================================

class Condition(str, Enum):
    """Состояние товара."""
    NEW = "новое"
    USED = "б/у"
    ANY = "не важно"


@dataclass
class Listing:
    """
    Модель объявления / товара.

    Единый формат для всех парсеров — каждый парсер
    возвращает список объектов Listing.
    """
    title: str
    price: Optional[str] = None          # Человекочитаемая строка цены
    price_numeric: Optional[float] = None # Числовое значение для сортировки
    url: str = ""                         # Ссылка на объявление
    image_url: Optional[str] = None       # URL изображения
    condition: str = ""                   # Новое / Б/у
    location: str = ""                    # Город / район
    platform: str = ""                    # Название площадки
    description: str = ""                 # Краткое описание
    posted_at: Optional[str] = None       # Дата публикации


@dataclass
class SearchFilters:
    """Фильтры поиска, передаваемые в парсеры."""
    query: str = ""
    condition: Condition = Condition.ANY
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    city: Optional[str] = None
    keywords: List[str] = field(default_factory=list)


# ============================================================
#                   БАЗОВЫЙ КЛАСС ПАРСЕРА
# ============================================================

class BaseParser(ABC):
    """
    Абстрактный базовый класс для всех парсеров.

    Каждый парсер должен реализовать:
      - search(filters) -> List[Listing]
      - _build_search_url(filters) -> str  (опционально)

    Парсеры регистрируются в ParserRegistry (см. registry.py).
    """

    PLATFORM_NAME: str = "Unknown"
    PLATFORM_URL: str = ""

    @abstractmethod
    async def search(self, filters: SearchFilters) -> List[Listing]:
        """
        Выполнить поиск по платформе.

        Args:
            filters: Фильтры поиска (запрос, цена, состояние, город).

        Returns:
            Список найденных объявлений (Listing).
        """
        raise NotImplementedError

    def _build_search_url(self, filters: SearchFilters) -> str:
        """
        Построить URL для поиска.
        Переопределяется в наследниках при необходимости.
        """
        raise NotImplementedError

    def _get_headers(self) -> dict:
        """Стандартные HTTP-заголовки для имитации браузера."""
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
