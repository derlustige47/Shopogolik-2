"""
Парсер Юла (youla.ru) — вторая по величине площадка объявлений.

NOTE: Юла активно использует JavaScript-рендеринг (React SPA).
Для стабильного парсинга в продакшене рекомендуется:
  1. Selenium / Playwright для рендеринга страницы
  2. Перехват неофициального API Юлы через DevTools

Селекторы CSS могут устареть — периодически обновляйте.
"""
import logging
from typing import List, Optional

import aiohttp
from bs4 import BeautifulSoup

from .base import BaseParser, Listing, SearchFilters, Condition

logger = logging.getLogger(__name__)


class YulaParser(BaseParser):
    """Парсер объявлений Юла (youla.ru)."""

    PLATFORM_NAME = "Юла"
    PLATFORM_URL = "https://youla.ru"

    # Маппинг городов → URL-слаги Юлы
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
        Поиск объявлений на Юла.

        Args:
            filters: Фильтры поиска.

        Returns:
            Список объектов Listing.
        """
        url = self._build_search_url(filters)
        headers = self._get_headers()

        logger.info(f"[Юла] Поиск: «{filters.query}» | URL: {url}")

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=20),
                    ssl=False,
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"[Юла] HTTP {resp.status} для {url}")
                        return []

                    html = await resp.text()
                    return self._parse_html(html)

        except aiohttp.ClientError as e:
            logger.error(f"[Юла] Ошибка сети: {e}")
            return []
        except Exception as e:
            logger.error(f"[Юла] Непредвиденная ошибка: {e}")
            return []

    def _build_search_url(self, filters: SearchFilters) -> str:
        """
        Формирует URL поиска Юла.

        Пример:
          https://youla.ru/moskva?q=iphone+15&price_from=50000&price_to=120000
        """
        query = filters.query.replace(" ", "%20")
        params = [f"q={query}"]

        # Фильтр цены
        if filters.price_min is not None:
            params.append(f"price_from={int(filters.price_min)}")
        if filters.price_max is not None:
            params.append(f"price_to={int(filters.price_max)}")

        # Фильтр состояния
        if filters.condition == Condition.NEW:
            params.append("conditions[]=new")
        elif filters.condition == Condition.USED:
            params.append("conditions[]=used")

        # Город
        city_slug = "all"
        if filters.city:
            city_slug = self.CITY_SLUGS.get(
                filters.city.lower(), "all"
            )

        return f"{self.PLATFORM_URL}/{city_slug}?{'&'.join(params)}"

    def _parse_html(self, html: str) -> List[Listing]:
        """
        Парсинг HTML страницы Юла.

        Юла рендерит контент через React, поэтому основные данные
        могут быть в JSON внутри <script> тегов или в server-side HTML.
        Попробуем оба варианта.
        """
        soup = BeautifulSoup(html, "html.parser")
        listings: List[Listing] = []

        # --- Вариант 1: SSR-разметка (если доступна) ---
        items = (
            soup.find_all("div", {"data-test-component": "ProductCard"})
            or soup.find_all("a", {"data-test-block": "productCardLink"})
            or soup.select("[class*='product_card']")
            or soup.select("[class*='ProductCard']")
        )

        # --- Вариант 2: JSON в <script id="__NEXT_DATA__"> ---
        if not items:
            listings = self._try_parse_next_data(soup)
            if listings:
                return listings

        # --- Вариант 3: универсальный fallback ---
        if not items:
            items = soup.select("a[href*='/product/']")[:10]

        for item in items[:10]:
            try:
                listing = self._parse_single_item(item)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[Юла] Ошибка парсинга элемента: {e}")
                continue

        logger.info(f"[Юла] Найдено объявлений: {len(listings)}")
        return listings

    def _try_parse_next_data(self, soup) -> List[Listing]:
        """
        Попытка извлечь данные из JSON, внедрённого в страницу
        (Next.js __NEXT_DATA__ или подобный паттерн).
        """
        import json

        listings = []
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script_tag:
            return listings

        try:
            data = json.loads(script_tag.string)
            products = (
                data.get("props", {})
                .get("pageProps", {})
                .get("products", [])
            )

            for product in products[:10]:
                listings.append(Listing(
                    title=product.get("name", "Без названия"),
                    price=str(product.get("price", "Цена не указана")),
                    price_numeric=float(product.get("price", 0)),
                    url=product.get("url", ""),
                    image_url=product.get("image", ""),
                    location=product.get("location", ""),
                    platform=self.PLATFORM_NAME,
                    description=product.get("description", ""),
                ))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug(f"[Юла] Ошибка парсинга JSON: {e}")

        return listings

    def _parse_single_item(self, item) -> Optional[Listing]:
        """Парсинг одной карточки объявления Юла."""

        # === Заголовок ===
        title_tag = (
            item.find(["h3", "span", "div"], class_=lambda c: c and "title" in str(c).lower())
            or item.find("a", href=True)
        )
        title = title_tag.get_text(strip=True) if title_tag else "Без названия"

        # === Цена ===
        price_tag = item.find(
            ["span", "div", "p"],
            class_=lambda c: c and "price" in str(c).lower()
        )
        price_text = price_tag.get_text(strip=True) if price_tag else "Цена не указана"
        price_numeric = self._parse_price(price_text)

        # === Ссылка ===
        link_tag = item.find("a", href=True)
        url = ""
        if link_tag:
            href = link_tag["href"]
            url = href if href.startswith("http") else self.PLATFORM_URL + href

        # === Изображение ===
        img_tag = item.find("img")
        image_url = img_tag.get("src", "") if img_tag else None

        return Listing(
            title=title,
            price=price_text,
            price_numeric=price_numeric,
            url=url,
            image_url=image_url,
            platform=self.PLATFORM_NAME,
        )

    @staticmethod
    def _parse_price(price_text: str) -> Optional[float]:
        """
        Извлечение числа из строки цены.
        Пример: "150 000 руб." → 150000.0
        """
        try:
            clean = (
                price_text
                .replace("₽", "")
                .replace("руб.", "")
                .replace("руб", "")
                .replace("\u2009", "")
                .replace("\u00a0", "")
                .replace(" ", "")
                .strip()
            )
            return float(clean)
        except (ValueError, TypeError):
            return None
