"""
Все клавиатуры бота: Reply (основное меню) и Inline (навигация).
Каждая функция возвращает готовый объект разметки.
"""
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from config import (
    ALL_CATEGORIES,
    CONDITIONS,
    CITY_TELEGRAM_GROUPS,
    ALL_CITIES,
    SITES_PLATFORMS,
)


# ============================================================
#                     REPLY-КЛАВИАТУРЫ
# ============================================================

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота — всегда доступно."""
    keyboard = [
        [KeyboardButton("🔍 Поиск"), KeyboardButton("📂 Категории")],
        [KeyboardButton("⚙️ Настройки"), KeyboardButton("ℹ️ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ============================================================
#                   INLINE-КЛАВИАТУРЫ
# ============================================================

def get_categories_keyboard() -> InlineKeyboardMarkup:
    """
    Инлайн-клавиатура выбора категории.
    По 2 кнопки в ряд для компактности.
    """
    buttons = []
    categories = ALL_CATEGORIES

    for i in range(0, len(categories), 2):
        row = [InlineKeyboardButton(categories[i], callback_data=f"cat:{i}")]
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(
                categories[i + 1], callback_data=f"cat:{i + 1}"
            ))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back:menu")])
    return InlineKeyboardMarkup(buttons)


def get_condition_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора состояния товара."""
    buttons = []
    for i, cond in enumerate(CONDITIONS):
        buttons.append([InlineKeyboardButton(cond, callback_data=f"cond:{i}")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back:cat")])
    return InlineKeyboardMarkup(buttons)


def get_platforms_keyboard(selected: set | None = None) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора площадок для поиска.
    Поддерживает множественный выбор (toggle).
    """
    if selected is None:
        selected = set()

    buttons = []

    # Telegram-группы барахолок
    buttons.append([InlineKeyboardButton(
        "📱 Telegram-барахолки" + (" ✅" if "telegram" in selected else ""),
        callback_data="plat:telegram",
    )])

    # Сайты — по 2 в ряд
    for i in range(0, len(SITES_PLATFORMS), 2):
        row = []
        plat_key = SITES_PLATFORMS[i].lower()
        row.append(InlineKeyboardButton(
            SITES_PLATFORMS[i] + (" ✅" if plat_key in selected else ""),
            callback_data=f"plat:{plat_key}",
        ))
        if i + 1 < len(SITES_PLATFORMS):
            plat_key2 = SITES_PLATFORMS[i + 1].lower()
            row.append(InlineKeyboardButton(
                SITES_PLATFORMS[i + 1] + (" ✅" if plat_key2 in selected else ""),
                callback_data=f"plat:{plat_key2}",
            ))
        buttons.append(row)

    # Управляющие кнопки
    buttons.append([
        InlineKeyboardButton("✅ Все площадки", callback_data="plat:all"),
    ])
    buttons.append([
        InlineKeyboardButton("🚀 Искать!", callback_data="plat:search"),
    ])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back:price")])
    return InlineKeyboardMarkup(buttons)


def get_cities_keyboard(selected: set | None = None) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора городов для Telegram-барахолок.
    Поддерживает множественный выбор.
    """
    if selected is None:
        selected = set()

    buttons = []

    for i in range(0, len(ALL_CITIES), 2):
        row = []
        city_key = ALL_CITIES[i].lower()
        row.append(InlineKeyboardButton(
            ALL_CITIES[i] + (" ✅" if city_key in selected else ""),
            callback_data=f"city:{city_key}",
        ))
        if i + 1 < len(ALL_CITIES):
            city_key2 = ALL_CITIES[i + 1].lower()
            row.append(InlineKeyboardButton(
                ALL_CITIES[i + 1] + (" ✅" if city_key2 in selected else ""),
                callback_data=f"city:{city_key2}",
            ))
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("✅ Все города", callback_data="city:all"),
        InlineKeyboardButton("🚀 Искать!", callback_data="city:search"),
    ])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back:plat")])
    return InlineKeyboardMarkup(buttons)


def get_results_navigation_keyboard(
    page: int = 0,
    total_pages: int = 1,
    query_id: str = "",
) -> InlineKeyboardMarkup:
    """Навигация по страницам результатов поиска."""
    buttons = []

    # Стрелки навигации
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            "⬅️ Назад", callback_data=f"page:{query_id}:{page - 1}"
        ))
    nav_row.append(InlineKeyboardButton(
        f"📄 {page + 1}/{total_pages}", callback_data="noop"
    ))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            "Вперёд ➡️", callback_data=f"page:{query_id}:{page + 1}"
        ))
    buttons.append(nav_row)

    # Действия
    buttons.append([
        InlineKeyboardButton("🔄 Новый поиск", callback_data="action:new_search"),
        InlineKeyboardButton("🏠 Меню", callback_data="action:home"),
    ])
    return InlineKeyboardMarkup(buttons)
