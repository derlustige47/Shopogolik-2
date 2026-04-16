"""
Парсер Avito — крупнейшей площадки объявлений в России.
Поддерживает фильтры по цене, состоянию и городу.

NOTE: Avito активно борется со скрапингом. В продакшене
рекомендуется использовать Selenium/Playwright или API-партнёра.
Селекторы CSS могут меняться при обновлении вёрстки.
"""
import logging
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup

from .base import BaseParser, Listing, SearchFilters, Condition

logger = logging.getLogger(__name__)


class AvitoParser(BaseParser):
    """Парсер объявлений Avito (avito.ru)."""

    PLATFORM_NAME = "Avito"
    PLATFORM_URL = "https://www.avito.ru"

    # Маппинг городов → URL-слаги Avito
    CITY_SLUGS = {
        "москва": "moskva",
        "санкт-петербург": "sankt-peterburg",
        "екатеринбург": "ekaterinburg",
        "новосибирск": "novosibirsk",
        "казань": "kazan",
        "краснодар": "krasnodar",
        "челябинск": "chelyabinsk",
        "ростов-на-дону": "rostov-na-donu",
        "уфа": "ufa",
        "воронеж": "voronezh",
        "красноярск": "krasnoyarsk",
        "нижний новгород": "nizhniy_novgorod",
        "самара": "samara",
        "пермь": "perm",
        "волгоград": "volgograd",
    }

    async def search(self, filters: SearchFilters) -> List[Listing]:
        """
        Поиск объявлений на Avito.

        Args:
            filters: Фильтры поиска (запрос, цена, состояние, город).

        Returns:
            Список объектов Listing (до 10 результатов).
        """
        url = self._build_search_url(filters)
        headers = self._get_headers()

        logger.info(f"[Avito] Поиск: «{filters.query}» | URL: {url}")

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=20),
                    ssl=False,
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"[Avito] HTTP {resp.status} для {url}")
                        return []

                    html = await resp.text()
                    return self._parse_html(html)

        except aiohttp.ClientError as e:
            logger.error(f"[Avito] Ошибка сети: {e}")
            return []
        except Exception as e:
            logger.error(f"[Avito] Непредвиденная ошибка: {e}")
            return []

    def _build_search_url(self, filters: SearchFilters) -> str:
        """
        Формирует URL поиска Avito с учётом фильтров.

        Пример:
          https://www.avito.ru/moskva?q=iphone+15&price_min=50000&price_max=120000
        """
        query = filters.query.replace(" ", "+")
        params = [f"q={query}"]

        # Фильтр цены
        if filters.price_min is not None:
            params.append(f"pmin={int(filters.price_min)}")
        if filters.price_max is not None:
            params.append(f"pmax={int(filters.price_max)}")

        # Фильтр состояния
        if filters.condition == Condition.NEW:
            params.append("s_trg=3")  # Только новые на Avito
        elif filters.condition == Condition.USED:
            params.append("s_trg=1")  # Только б/у

        # Город
        city_slug = "all"
        if filters.city:
            city_slug = self.CITY_SLUGS.get(
                filters.city.lower(), "all"
            )

        return f"{self.PLATFORM_URL}/{city_slug}?{'&'.join(params)}"

    def _parse_html(self, html: str) -> List[Listing]:
        """
        Парсинг HTML-страницы результатов Avito.

        Avito использует data-marker атрибуты для разметки карточек.
        Извлекает: заголовок, цену, ссылку, изображение, локацию.
        """
        soup = BeautifulSoup(html, "html.parser")
        listings = []

        # Карточки объявлений — data-marker="item"
        items = soup.find_all("div", {"data-marker": "item"})[:10]

        for item in items:
            try:
                listing = self._parse_single_item(item)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[Avito] Ошибка парсинга элемента: {e}")
                continue

        logger.info(f"[Avito] Найдено объявлений: {len(listings)}")
        return listings

    def _parse_single_item(self, item) -> Optional[Listing]:
        """Парсинг одной карточки объявления Avito."""

        # === Заголовок ===
        title_tag = (
            item.find("a", {"data-marker": "item-title"})
            or item.find("h3")
            or item.find("a", class_="iva-item-sliderLink")
        )
        title = title_tag.get_text(strip=True) if title_tag else "Без названия"

        # === Цена ===
        price_tag = (
            item.find("span", {"data-marker": "item-price"})
            or item.find("meta", {"itemprop": "price"})
            or item.find("span", class_="price-text")
        )
        if price_tag:
            if price_tag.name == "meta":
                price_text = f"{price_tag.get('content', '')} ₽"
            else:
                price_text = price_tag.get_text(strip=True)
        else:
            price_text = "Цена не указана"

        price_numeric = self._parse_price(price_text)

        # === Ссылка ===
        link_tag = (
            item.find("a", {"data-marker": "item-title"})
            or item.find("a", href=True)
        )
        url = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            url = href if href.startswith("http") else self.PLATFORM_URL + href

        # === Изображение ===
        img_tag = item.find("img")
        image_url = img_tag.get("src", "") if img_tag else None

        # === Локация ===
        geo_tag = item.find("div", {"data-marker": "item-address"})
        location = geo_tag.get_text(strip=True) if geo_tag else ""

        # === Описание ===
        desc_tag = item.find("div", {"data-marker": "item-specific-params"})
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        return Listing(
            title=title,
            price=price_text,
            price_numeric=price_numeric,
            url=url,
            image_url=image_url,
            condition="",
            location=location,
            platform=self.PLATFORM_NAME,
            description=description,
        )

    @staticmethod
    def _parse_price(price_text: str) -> Optional[float]:
        """
        Извлечение числового значения из строки цены.
        Пример: "150 000 ₽" → 150000.0
        """
        try:
            clean = (
                price_text
                .replace("₽", "")
                .replace("\u2009", "")   # узкий пробел
                .replace("\u00a0", "")   # неразрывный пробел
                .replace(" ", "")
                .replace("руб.", "")
                .strip()
            )
            return float(clean)
        except (ValueError, TypeError):
            return None
