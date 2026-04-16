"""
Реестр парсеров — единая точка доступа ко всем парсерам.
Позволяет запускать поиск параллельно по нескольким площадкам.
"""
import asyncio
import logging
from typing import Dict, List, Optional

from .base import BaseParser, Listing, SearchFilters

logger = logging.getLogger(__name__)


class ParserRegistry:
    """
    Реестр всех доступных парсеров.

    Особенности:
      - Регистрация парсеров по имени
      - Параллельный запуск через asyncio.gather()
      - Обработка ошибок каждого парсера отдельно
      - Сортировка результатов по цене
    """

    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {}

    # ---- Управление парсерами ----

    def register(self, name: str, parser: BaseParser) -> None:
        """Зарегистрировать парсер по имени."""
        key = name.lower().strip()
        self._parsers[key] = parser
        logger.info(f"[Registry] ✅ Зарегистрирован: {name} ({key})")

    def unregister(self, name: str) -> None:
        """Удалить парсер из реестра."""
        key = name.lower().strip()
        if key in self._parsers:
            del self._parsers[key]
            logger.info(f"[Registry] ❌ Удалён: {name}")

    def get(self, name: str) -> Optional[BaseParser]:
        """Получить парсер по имени."""
        return self._parsers.get(name.lower().strip())

    def get_all_names(self) -> List[str]:
        """Список имён всех зарегистрированных парсеров."""
        return list(self._parsers.keys())

    # ---- Поиск ----

    async def search_all(
        self,
        filters: SearchFilters,
        platforms: Optional[List[str]] = None,
    ) -> List[Listing]:
        """
        Параллельный поиск по всем (или выбранным) площадкам.

        Args:
            filters:  Фильтры поиска
            platforms: Список площадок (None = все зарегистрированные)

        Returns:
            Объединённый список Listing, отсортированный по цене.
        """
        # Определяем какие парсеры использовать
        if platforms:
            target_keys = {p.lower().strip() for p in platforms}
            parsers_to_use = {
                k: v for k, v in self._parsers.items() if k in target_keys
            }
        else:
            parsers_to_use = dict(self._parsers)

        if not parsers_to_use:
            logger.warning("[Registry] ⚠️ Нет доступных парсеров для поиска")
            return []

        logger.info(
            f"[Registry] 🚀 Запуск поиска по {len(parsers_to_use)} "
            f"площадкам: {list(parsers_to_use.keys())}"
        )

        # Запускаем все парсеры параллельно
        tasks = [
            self._safe_search(name, parser, filters)
            for name, parser in parsers_to_use.items()
        ]
        results: List[List[Listing]] = await asyncio.gather(*tasks)

        # Объединяем результаты
        all_listings: List[Listing] = []
        for listing_list in results:
            all_listings.extend(listing_list)

        # Сортируем по цене (None → бесконечность, будут в конце)
        all_listings.sort(
            key=lambda x: x.price_numeric if x.price_numeric is not None else float("inf")
        )

        logger.info(
            f"[Registry] 📊 Всего найдено: {len(all_listings)} объявлений"
        )
        return all_listings

    async def _safe_search(
        self,
        name: str,
        parser: BaseParser,
        filters: SearchFilters,
    ) -> List[Listing]:
        """Безопасный вызов парсера с перехватом любых ошибок."""
        try:
            return await parser.search(filters)
        except Exception as e:
            logger.error(f"[Registry] ❌ Ошибка парсера '{name}': {e}")
            return []


# ============================================================
#            Глобальный синглтон реестра
# ============================================================
registry = ParserRegistry()
