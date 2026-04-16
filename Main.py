"""
Shopogolik Bot v2.0 — Мощный агрегатор объявлений и товаров.

Ищет по сайтам (Avito, Юла, AliExpress, Ozon, Wildberries…)
и по Telegram-группам барахолок 15+ городов России.

Архитектура:
  FastAPI + python-telegram-bot v21+
  Lifespan для инициализации
  ConversationHandler для FSM
  Модульные парсеры в parsers/
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

# --- Внутренние модули ---
from config import (
    BOT_TOKEN,
    WEBHOOK_URL,
    CATEGORY_KEYWORDS,
    RESULTS_PER_PAGE,
)
from states import SearchStates
from keyboards import (
    get_main_menu_keyboard,
    get_categories_keyboard,
    get_condition_keyboard,
    get_platforms_keyboard,
    get_cities_keyboard,
    get_results_navigation_keyboard,
)
from parsers import registry, init_parsers, SearchFilters, Condition

# ============================================================
#                       ЛОГГИРОВАНИЕ
# ============================================================
logging.basicConfig(
    format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("shopogolik")


# ============================================================
#              ХРАНИЛИЩЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ
# ============================================================
# В продакшене заменить на Redis / PostgreSQL
user_data_store: dict = {}


def get_user_data(user_id: int) -> dict:
    """
    Получить (или создать) данные сессии пользователя.

    Структура данных:
      category:     выбранная категория (str | None)
      condition:    состояние товара (Condition)
      price_min:    мин. цена (float | None)
      price_max:    макс. цена (float | None)
      platforms:    выбранные площадки (set)
      cities:       выбранные города (set)
      keywords:     ключевые слова (list[str])
      results:      результаты поиска (list[Listing])
      current_page: текущая страница (int)
    """
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "category": None,
            "condition": Condition.ANY,
            "price_min": None,
            "price_max": None,
            "platforms": set(),
            "cities": set(),
            "keywords": [],
            "results": [],
            "current_page": 0,
        }
    return user_data_store[user_id]


# ============================================================
#              ИНИЦИАЛИЗАЦИЯ ПАРСЕРОВ
# ============================================================
init_parsers()
logger.info(f"📡 Парсеры загружены: {registry.get_all_names()}")


# ============================================================
#                     ОБРАБОТЧИКИ (HANDLERS)
# ============================================================
# Каждый обработчик соответствует одному состоянию FSM.

async def cmd_start(update: Update, context) -> int:
    """
    /start — точка входа, приветствие + главное меню.
    """
    user = update.effective_user
    text = (
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        f"🛒 Я — <b>Шопоголик</b>, мощный агрегатор объявлений!\n"
        f"Ищу товары по сайтам и Telegram-барахолкам.\n\n"
        f"🌐 <b>Площадки:</b> Avito, Юла, AliExpress, Ozon, WB и др.\n"
        f"📱 <b>Telegram-барахолки:</b> 15+ городов России\n\n"
        f"👇 Выбери действие в меню:"
    )
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
    return SearchStates.MAIN_MENU


async def main_menu_handler(update: Update, context) -> int:
    """Обработчик кнопок главного меню."""
    text = update.message.text
    user_id = update.effective_user.id
    data = get_user_data(user_id)

    if text == "🔍 Поиск":
        await update.message.reply_text(
            "📝 <b>Введи ключевые слова для поиска:</b>\n"
            "(например: <i>iPhone 15 Pro Max 256GB</i>)\n\n"
            "💡 Или отправь /cancel для отмены.",
            parse_mode="HTML",
        )
        return SearchStates.KEYWORD_INPUT

    elif text == "📂 Категории":
        await update.message.reply_text(
            "📂 <b>Выбери категорию:</b>",
            parse_mode="HTML",
            reply_markup=get_categories_keyboard(),
        )
        return SearchStates.CATEGORY_SELECT

    elif text == "⚙️ Настройки":
        await update.message.reply_text(
            "⚙️ <b>Настройки поиска</b>\n\n"
            "Для настройки фильтров используйте:\n"
            "📂 <b>Категории</b> → выбор категории с авто-ключевыми словами\n"
            "🔍 <b>Поиск</b> → ручной ввод запроса\n\n"
            "В процессе поиска вы сможете уточнить:\n"
            "• Состояние товара (Новое / Б/у)\n"
            "• Диапазон цены\n"
            "• Площадки для поиска",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return SearchStates.MAIN_MENU

    elif text == "ℹ️ Помощь":
        help_text = (
            "ℹ️ <b>Помощь — Шопоголик v2.0</b>\n\n"
            "🔍 <b>Быстрый поиск</b> — введите запрос и бот найдёт "
            "товары по всем подключённым площадкам.\n\n"
            "📂 <b>Категории</b> — при выборе категории бот автоматически "
            "подберёт релевантные ключевые слова.\n\n"
            "🌐 <b>Площадки:</b>\n"
            "  • Avito, Юла, Дром, Auto.ru\n"
            "  • AliExpress, Ozon, Wildberries\n"
            "  • Telegram-барахолки 15+ городов\n\n"
            "🏷 <b>Фильтры:</b>\n"
            "  • Цена: от и до\n"
            "  • Состояние: Новое / Б/у / Не важно\n"
            "  • Город: для TG-групп\n\n"
            "📋 <b>Команды:</b>\n"
            "  /start — главное меню\n"
            "  /cancel — отменить текущий поиск"
        )
        await update.message.reply_text(
            help_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return SearchStates.MAIN_MENU

    else:
        # Нераспознанный текст → пробуем как поисковый запрос
        data["keywords"] = [text]
        data["category"] = None
        await _execute_search(update, context, user_id)
        return SearchStates.RESULTS


# -------------------------------------------------------
#                 ВВОД КЛЮЧЕВЫХ СЛОВ
# -------------------------------------------------------

async def keyword_input_handler(update: Update, context) -> int:
    """Обработчик ввода ключевых слов для поиска."""
    user_id = update.effective_user.id
    data = get_user_data(user_id)

    query = update.message.text.strip()
    data["keywords"] = [query]

    await update.message.reply_text(
        f"✅ Запрос: <b>{query}</b>\n\n"
        f"🏷 Выбери состояние товара:",
        parse_mode="HTML",
        reply_markup=get_condition_keyboard(),
    )
    return SearchStates.CONDITION_SELECT


# -------------------------------------------------------
#                  ВЫБОР КАТЕГОРИИ
# -------------------------------------------------------

async def category_callback(update: Update, context) -> int:
    """Обработчик inline-кнопок выбора категории."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = get_user_data(user_id)

    if query.data.startswith("cat:"):
        cat_idx = int(query.data.split(":")[1])
        categories = list(CATEGORY_KEYWORDS.keys())

        if 0 <= cat_idx < len(categories):
            selected_cat = categories[cat_idx]
            data["category"] = selected_cat
            data["keywords"] = CATEGORY_KEYWORDS[selected_cat]

            # Показываем первые 5 авто-ключевых слов
            kw_preview = ", ".join(CATEGORY_KEYWORDS[selected_cat][:5])

            await query.edit_message_text(
                f"✅ Категория: <b>{selected_cat}</b>\n"
                f"🔍 Авто-слова: <i>{kw_preview}…</i>\n\n"
                f"🏷 Выбери состояние товара:",
                parse_mode="HTML",
                reply_markup=get_condition_keyboard(),
            )
            return SearchStates.CONDITION_SELECT

    elif query.data == "back:menu":
        await query.edit_message_text("🏠 Возврат в главное меню.")
        await context.bot.send_message(
            chat_id=user_id,
            text="🏠 Выбери действие:",
            reply_markup=get_main_menu_keyboard(),
        )
        return SearchStates.MAIN_MENU

    return SearchStates.CATEGORY_SELECT


# -------------------------------------------------------
#                  ВЫБОР СОСТОЯНИЯ
# -------------------------------------------------------

async def condition_callback(update: Update, context) -> int:
    """Обработчик выбора состояния товара (Новое / Б/у / Не важно)."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = get_user_data(user_id)

    if query.data.startswith("cond:"):
        cond_idx = int(query.data.split(":")[1])
        conditions = ["Новое", "Б/у", "Не важно"]

        if 0 <= cond_idx < len(conditions):
            cond_map = {
                "Новое": Condition.NEW,
                "Б/у": Condition.USED,
                "Не важно": Condition.ANY,
            }
            data["condition"] = cond_map[conditions[cond_idx]]

            await query.edit_message_text(
                f"✅ Состояние: <b>{conditions[cond_idx]}</b>\n\n"
                f"💰 Введи диапазон цены:\n"
                f"Формат: <code>от-до</code> (например: <code>1000-50000</code>)\n"
                f"Или отправь <code>-</code> чтобы пропустить.",
                parse_mode="HTML",
            )
            return SearchStates.PRICE_INPUT

    elif query.data == "back:cat":
        await query.edit_message_text(
            "📂 Выбери категорию:",
            reply_markup=get_categories_keyboard(),
        )
        return SearchStates.CATEGORY_SELECT

    return SearchStates.CONDITION_SELECT


# -------------------------------------------------------
#                   ВВОД ЦЕНЫ
# -------------------------------------------------------

async def price_input_handler(update: Update, context) -> int:
    """Обработчик ввода диапазона цены."""
    user_id = update.effective_user.id
    data = get_user_data(user_id)

    text = update.message.text.strip()

    if text != "-":
        try:
            # Поддерживаем форматы: "1000-50000", "1000 - 50000", "50000"
            parts = text.replace(" ", "").split("-")

            if len(parts) == 2:
                data["price_min"] = float(parts[0]) if parts[0] else None
                data["price_max"] = float(parts[1]) if parts[1] else None
            elif len(parts) == 1 and parts[0]:
                price = float(parts[0])
                data["price_min"] = price
                data["price_max"] = None
            else:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат!\n"
                "Введите: <code>1000-50000</code>\n"
                "Или отправьте <code>-</code> чтобы пропустить.",
                parse_mode="HTML",
            )
            return SearchStates.PRICE_INPUT

    # Формируем информацию о цене
    price_info = "Не ограничена"
    if data.get("price_min") or data.get("price_max"):
        pmin = int(data["price_min"]) if data.get("price_min") else "0"
        pmax = int(data["price_max"]) if data.get("price_max") else "∞"
        price_info = f"{pmin} — {pmax} ₽"

    await update.message.reply_text(
        f"✅ Цена: <b>{price_info}</b>\n\n"
        f"🌐 Выбери площадки для поиска:",
        parse_mode="HTML",
        reply_markup=get_platforms_keyboard(data.get("platforms", set())),
    )
    return SearchStates.PLATFORM_SELECT


# -------------------------------------------------------
#                  ВЫБОР ПЛОЩАДОК
# -------------------------------------------------------

async def platform_callback(update: Update, context) -> int:
    """Обработчик inline-кнопок выбора площадок."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = get_user_data(user_id)
    platforms = data.get("platforms", set())

    if query.data == "plat:all":
        # Выбрать все площадки
        data["platforms"] = {"all"}
        await query.edit_message_text(
            "✅ Выбраны <b>все площадки</b>!\n\n🚀 Запускаю поиск…",
            parse_mode="HTML",
        )
        await _execute_search_callback(context, user_id)
        return SearchStates.RESULTS

    elif query.data == "plat:search":
        await query.edit_message_text("🚀 Запускаю поиск…")
        await _execute_search_callback(context, user_id)
        return SearchStates.RESULTS

    elif query.data.startswith("plat:"):
        # Toggle конкретной площадки
        plat_name = query.data.split(":", 1)[1]
        if plat_name in platforms:
            platforms.discard(plat_name)
        else:
            platforms.add(plat_name)
        data["platforms"] = platforms

        await query.edit_message_text(
            "🌐 Выбери площадки для поиска:\n"
            "(нажми на площадку чтобы выбрать/убрать)",
            reply_markup=get_platforms_keyboard(platforms),
        )
        return SearchStates.PLATFORM_SELECT

    elif query.data == "back:price":
        await query.edit_message_text(
            "💰 Введи диапазон цены:\n"
            "Формат: <code>от-до</code> (например: <code>1000-50000</code>)\n"
            "Или <code>-</code> чтобы пропустить.",
            parse_mode="HTML",
        )
        return SearchStates.PRICE_INPUT

    return SearchStates.PLATFORM_SELECT


# -------------------------------------------------------
#              НАВИГАЦИЯ ПО РЕЗУЛЬТАТАМ
# -------------------------------------------------------

async def results_callback(update: Update, context) -> int:
    """Обработчик навигации по страницам результатов."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = get_user_data(user_id)

    if query.data.startswith("page:"):
        parts = query.data.split(":")
        page = int(parts[-1])
        data["current_page"] = page
        await _send_results_page(context, user_id, page)
        return SearchStates.RESULTS

    elif query.data == "action:new_search":
        await context.bot.send_message(
            chat_id=user_id,
            text="📝 Введи ключевые слова для нового поиска:",
        )
        return SearchStates.KEYWORD_INPUT

    elif query.data == "action:home":
        await context.bot.send_message(
            chat_id=user_id,
            text="🏠 Главное меню",
            reply_markup=get_main_menu_keyboard(),
        )
        return SearchStates.MAIN_MENU

    return SearchStates.RESULTS


# -------------------------------------------------------
#                  ОТМЕНА
# -------------------------------------------------------

async def cancel_handler(update: Update, context) -> int:
    """Обработчик /cancel — возврат в главное меню."""
    user_id = update.effective_user.id
    # Очищаем данные пользователя
    if user_id in user_data_store:
        del user_data_store[user_id]

    await update.message.reply_text(
        "❌ Поиск отменён.\n🏠 Выбери действие в меню:",
        reply_markup=get_main_menu_keyboard(),
    )
    return SearchStates.MAIN_MENU


# ============================================================
#                  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

async def _execute_search(update: Update, context, user_id: int) -> None:
    """Выполнить поиск и отправить результаты (через message)."""
    data = get_user_data(user_id)

    query_text = " ".join(data.get("keywords", []))
    if not query_text:
        await update.message.reply_text("❌ Пустой запрос. Попробуйте снова.")
        return

    await update.message.reply_text(
        f"🔍 Ищу: <b>{query_text}</b>…\n"
        f"⏳ Это может занять несколько секунд.",
        parse_mode="HTML",
    )

    # Формируем фильтры
    search_filters = SearchFilters(
        query=query_text,
        condition=data.get("condition", Condition.ANY),
        price_min=data.get("price_min"),
        price_max=data.get("price_max"),
    )

    # Определяем площадки
    platforms = data.get("platforms")
    if not platforms or "all" in platforms:
        results = await registry.search_all(search_filters)
    else:
        results = await registry.search_all(search_filters, list(platforms))

    data["results"] = results
    data["current_page"] = 0

    if not results:
        await update.message.reply_text(
            "😔 <b>Ничего не найдено.</b>\n"
            "Попробуйте изменить запрос или фильтры.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    await _send_results_page_msg(update, context, user_id, 0)


async def _execute_search_callback(context, user_id: int) -> None:
    """Выполнить поиск из callback (inline-кнопки)."""
    data = get_user_data(user_id)

    query_text = " ".join(data.get("keywords", []))
    if not query_text:
        await context.bot.send_message(
            chat_id=user_id, text="❌ Пустой запрос."
        )
        return

    search_filters = SearchFilters(
        query=query_text,
        condition=data.get("condition", Condition.ANY),
        price_min=data.get("price_min"),
        price_max=data.get("price_max"),
    )

    platforms = data.get("platforms")
    if not platforms or "all" in platforms:
        results = await registry.search_all(search_filters)
    else:
        results = await registry.search_all(search_filters, list(platforms))

    data["results"] = results
    data["current_page"] = 0

    if not results:
        await context.bot.send_message(
            chat_id=user_id,
            text="😔 <b>Ничего не найдено.</b>\n"
                 "Попробуйте изменить запрос или фильтры.",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    await _send_results_page(context, user_id, 0)


def _format_listing(listing) -> str:
    """Форматирование одного объявления для отправки в чат."""
    lines = [
        f"📦 <b>{listing.title}</b>",
    ]
    if listing.price:
        lines.append(f"💰 {listing.price}")
    if listing.location:
        lines.append(f"📍 {listing.location}")
    if listing.condition:
        lines.append(f"🏷 {listing.condition}")
    lines.append(f"🏪 {listing.platform}")
    if listing.url:
        lines.append(f"🔗 <a href=\"{listing.url}\">Открыть объявление</a>")

    return "\n".join(lines)


async def _send_results_page_msg(update, context, user_id: int, page: int) -> None:
    """Отправить страницу результатов через update.message."""
    data = get_user_data(user_id)
    results = data.get("results", [])
    total_pages = max(1, -(-len(results) // RESULTS_PER_PAGE))

    start = page * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    page_results = results[start:end]

    # Шапка
    await update.message.reply_text(
        f"📊 <b>Результаты поиска</b> (стр. {page + 1}/{total_pages}, "
        f"всего: {len(results)})",
        parse_mode="HTML",
    )

    # Объявления
    for listing in page_results:
        await update.message.reply_text(
            _format_listing(listing), parse_mode="HTML"
        )

    # Навигация
    nav = get_results_navigation_keyboard(page, total_pages, str(user_id))
    await update.message.reply_text(
        f"📄 Страница {page + 1} из {total_pages}",
        reply_markup=nav,
    )


async def _send_results_page(context, user_id: int, page: int) -> None:
    """Отправить страницу результатов через bot.send_message."""
    data = get_user_data(user_id)
    results = data.get("results", [])
    total_pages = max(1, -(-len(results) // RESULTS_PER_PAGE))

    start = page * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    page_results = results[start:end]

    # Шапка
    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"📊 <b>Результаты поиска</b> (стр. {page + 1}/{total_pages}, "
            f"всего: {len(results)})"
        ),
        parse_mode="HTML",
    )

    # Объявления
    for listing in page_results:
        await context.bot.send_message(
            chat_id=user_id,
            text=_format_listing(listing),
            parse_mode="HTML",
        )

    # Навигация
    nav = get_results_navigation_keyboard(page, total_pages, str(user_id))
    await context.bot.send_message(
        chat_id=user_id,
        text=f"📄 Страница {page + 1} из {total_pages}",
        reply_markup=nav,
    )


# ============================================================
#            CONVERSATION HANDLER (FSM)
# ============================================================

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", cmd_start)],

    states={
        # Главное меню
        SearchStates.MAIN_MENU: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler),
        ],
        # Ввод ключевых слов
        SearchStates.KEYWORD_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, keyword_input_handler),
        ],
        # Выбор категории (inline)
        SearchStates.CATEGORY_SELECT: [
            CallbackQueryHandler(category_callback),
        ],
        # Выбор состояния товара (inline)
        SearchStates.CONDITION_SELECT: [
            CallbackQueryHandler(condition_callback),
        ],
        # Ввод цены
        SearchStates.PRICE_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, price_input_handler),
        ],
        # Выбор площадок (inline)
        SearchStates.PLATFORM_SELECT: [
            CallbackQueryHandler(platform_callback),
        ],
        # Просмотр результатов с пагинацией
        SearchStates.RESULTS: [
            CallbackQueryHandler(results_callback),
        ],
    },

    fallbacks=[CommandHandler("cancel", cancel_handler)],
    allow_reentry=True,
)


# ============================================================
#                  TELEGRAM APPLICATION
# ============================================================

tg_app = Application.builder().token(BOT_TOKEN).build()
tg_app.add_handler(conv_handler)

# Также добавляем /start как fallback на случай потери состояния
tg_app.add_handler(CommandHandler("start", cmd_start))

logger.info("✅ Обработчики зарегистрированы")


# ============================================================
#               FASTAPI + LIFESPAN + WEBHOOK
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan FastAPI: инициализация и очистка Telegram Application.

    STARTUP:
      1. Инициализация tg_app
      2. Запуск polling / установка webhook
    SHUTDOWN:
      1. Остановка tg_app
      2. Очистка ресурсов
    """
    # --- STARTUP ---
    await tg_app.initialize()
    await tg_app.start()

    if WEBHOOK_URL:
        await tg_app.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"🔗 Webhook установлен: {WEBHOOK_URL}")
    else:
        logger.info("📡 Режим polling (WEBHOOK_URL не задан)")

    logger.info("✅ Бот «Шопоголик v2.0» запущен!")

    yield  # Приложение работает

    # --- SHUTDOWN ---
    await tg_app.stop()
    await tg_app.shutdown()
    logger.info("🛑 Бот остановлен")


# FastAPI приложение
api = FastAPI(
    title="Shopogolik Bot API",
    description="Мощный агрегатор объявлений и товаров",
    version="2.0.0",
    lifespan=lifespan,
)


@api.post("/webhook")
async def webhook(request: Request):
    """
    Webhook endpoint для получения обновлений от Telegram.

    Telegram отправляет POST-запросы с Update JSON
    каждый раз при новом событии (сообщение, кнопка и т.д.).
    """
    try:
        data = await request.json()
        update = Update.de_json(data, tg_app.bot)
        await tg_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@api.get("/")
async def health():
    """Health check — статус бота и список парсеров."""
    return {
        "status": "ok",
        "bot": "Shopogolik",
        "version": "2.0.0",
        "parsers": registry.get_all_names(),
    }


@api.get("/parsers")
async def list_parsers():
    """Список доступных парсеров."""
    return {
        "parsers": registry.get_all_names(),
        "count": len(registry.get_all_names()),
    }


# ============================================================
#                       ЗАПУСК
# ============================================================

if __name__ == "__main__":
    import uvicorn
    from config import FASTAPI_HOST, FASTAPI_PORT

    logger.info(f"🚀 Запуск сервера: http://{FASTAPI_HOST}:{FASTAPI_PORT}")
    uvicorn.run(
        "main:api",
        host=FASTAPI_HOST,
        port=FASTAPI_PORT,
        reload=False,
    )
