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

# Импорты
from config import BOT_TOKEN, WEBHOOK_URL, CATEGORY_KEYWORDS, RESULTS_PER_PAGE
from states import SearchStates
from keyboards import (
    get_main_menu_keyboard,
    get_categories_keyboard,
    get_condition_keyboard,
    get_platforms_keyboard,
)
from parsers.registry import registry, init_parsers
from parsers.base import Condition

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shopogolik")

# Инициализация парсеров
init_parsers()
logger.info(f"Парсеры загружены: {registry.get_all_names()}")

user_data_store =
def get_user_data(user_id: int) -> dict:
    if user_id not in user_data_store:
        user_data_store = {
            "category": None,
            "condition": Condition.ANY,
            "price_min": None,
            "price_max": None,
            "platforms": set(),
            "keywords": [ ],
            "current_page": 0,
        }
    return user_data_store # ================== ОБРАБОТЧИКИ ==================

async def cmd_start(update: Update, context):
    await update.message.reply_text(
        "👋 Привет! Добро пожаловать в Шопоголик v2.0\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu_keyboard()
    )
    return SearchStates.MAIN_MENU

async def main_menu_handler(update: Update, context):
    text = update.message.text
    if text == "🔍 Поиск":
        await update.message.reply_text("Введите запрос для поиска:")
        return SearchStates.KEYWORD_INPUT
    elif text == "📂 Категории":
        await update.message.reply_text(
            "Выберите категорию:",
            reply_markup=get_categories_keyboard()
        )
        return SearchStates.CATEGORY_SELECT
    return SearchStates.MAIN_MENU

# ConversationHandler
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", cmd_start) MessageHandler(filters.TEXT & \~filters.COMMAND, main_menu_handler) MessageHandler(filters.TEXT & \~filters.COMMAND, lambda u,c: u.message.reply_text("Поиск пока в разработке...")) CallbackQueryHandler(lambda u,c: u.callback_query.answer()) CommandHandler("cancel", lambda u,c: u.message.reply_text("Поиск отменён."))],
)

# FastAPI + Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(conv_handler)
    await application.initialize()
    await application.start()
    logger.info("✅ Бот запущен")
    yield
    await application.stop()
    await application.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {"status": "online", "bot": "Shopogolik v2"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
