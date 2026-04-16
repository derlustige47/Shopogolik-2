"""
Заглушка парсера Telegram-групп барахолок.

Для реального чтения сообщений из групп необходим Telethon
(userbot) — бот Telegram API не может читать чужие группы.

Требования:
  - TG_API_ID и TG_API_HASH от my.telegram.org
  - Активная Telegram-сессия (первый запуск требует ввода кода)
  - Telethon установлен: pip install telethon
"""
import logging
from typing import List

from .base import BaseParser, Listing, SearchFilters
from config import CITY_TELEGRAM_GROUPS

logger = logging.getLogger(__name__)


class TelegramGroupsParser(BaseParser):
    """
    Парсер Telegram-барахолок.

    Читает последние сообщения из заданных групп
    и фильтрует по ключевым словам.
    """

    PLATFORM_NAME = "Telegram-барахолки"
    PLATFORM_URL = "https://t.me"

    def __init__(self):
        self._client = None
        self._initialized = False

    async def _ensure_client(self):
        """
        Ленивая инициализация Telethon-клиента.

        Для запуска в production:
          1. Получите API ключи на https://my.telegram.org
          2. Установите TG_API_ID и TG_API_HASH
          3. При первом запуске введите код подтверждения
        """
        if self._initialized:
            return

        try:
            from telethon import TelegramClient
            from config import TG_API_ID, TG_API_HASH, TG_SESSION_NAME

            if not TG_API_ID or not TG_API_HASH:
                logger.warning(
                    "[TG Groups] TG_API_ID/TG_API_HASH не настроены. "
                    "Парсер Telegram-групп недоступен."
                )
                self._initialized = True
                return

            self._client = TelegramClient(
                TG_SESSION_NAME, TG_API_ID, TG_API_HASH
            )
            await self._client.start()
            self._initialized = True
            logger.info("[TG Groups] ✅ Telethon-клиент инициализирован")

        except ImportError:
            logger.warning(
                "[TG Groups] Telethon не установлен. "
                "Установите: pip install telethon"
            )
            self._initialized = True
        except Exception as e:
            logger.error(f"[TG Groups] Ошибка инициализации: {e}")
            self._initialized = True

    async def search(self, filters: SearchFilters) -> List[Listing]:
        """
        Поиск по Telegram-группам барахолок.

        Ищет последние ~100 сообщений в каждой группе
        и фильтрует по ключевым словам запроса.
        """
        await self._ensure_client()

        if not self._client:
            logger.warning("[TG Groups] Клиент не инициализирован")
            return []

        listings: List[Listing] = []
        query_words = set(filters.query.lower().split())

        # Собираем группы для поиска
        target_groups = self._get_target_groups(filters.city)

        for group_username in target_groups:
            try:
                group_results = await self._search_group(
                    group_username, query_words
                )
                listings.extend(group_results)
            except Exception as e:
                logger.error(
                    f"[TG Groups] Ошибка в группе {group_username}: {e}"
                )

        logger.info(
            f"[TG Groups] Найдено объявлений: {len(listings)}"
        )
        return listings

    def _get_target_groups(self, city: str | None = None) -> List[str]:
        """Получить список групп для поиска (все или по городу)."""
        if city:
            city_lower = city.lower()
            for city_name, groups in CITY_TELEGRAM_GROUPS.items():
                if city_lower in city_name.lower():
                    return groups
            return []

        # Все группы всех городов
        all_groups = []
        for groups in CITY_TELEGRAM_GROUPS.values():
            all_groups.extend(groups)
        return all_groups

    async def _search_group(
        self,
        group_username: str,
        query_words: set,
        limit: int = 50,
    ) -> List[Listing]:
        """
        Поиск в одной Telegram-группе.

        Читает последние `limit` сообщений и фильтрует
        по совпадению ключевых слов.
        """
        listings: List[Listing] = []

        try:
            async for message in self._client.iter_messages(
                group_username, limit=limit
            ):
                if not message.text:
                    continue

                text = message.text.lower()
                # Проверяем вхождение хотя бы одного слова из запроса
                if not query_words or any(
                    word in text for word in query_words
                ):
                    # Пытаемся извлечь цену из текста
                    price, price_numeric = self._extract_price(message.text)

                    listings.append(Listing(
                        title=message.text[:100].replace("\n", " "),
                        price=price,
                        price_numeric=price_numeric,
                        url=f"{self.PLATFORM_URL}/{group_username.lstrip('@')}/{message.id}",
                        platform=f"TG: {group_username}",
                        description=message.text[:300],
                        posted_at=str(message.date) if message.date else None,
                    ))

        except Exception as e:
            logger.error(
                f"[TG Groups] Ошибка чтения {group_username}: {e}"
            )

        return listings

    @staticmethod
    def _extract_price(text: str) -> tuple:
        """
        Попытка извлечь цену из текста сообщения.
        Ищет паттерны: "5000₽", "5000 руб", "цене 5000", "5000 р."
        """
        import re

        patterns = [
            r"(\d[\d\s]*)\s*₽",
            r"(\d[\d\s]*)\s*руб",
            r"(\d[\d\s]*)\s*р\.",
            r"цен[аеы]?\s*:?\s*(\d[\d\s]*)",
            r"(\d{3,})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(" ", "")
                try:
                    price = float(price_str)
                    return f"{int(price)} ₽", price
                except ValueError:
                    continue

        return "Цена не указана", None
