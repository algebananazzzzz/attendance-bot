"""python-telegram-bot runtime wiring for Lambda update processing."""

import asyncio

from telegram import Update
from telegram.ext import CommandHandler, PollAnswerHandler

from ..clients import build_telegram_application
from ..config import (
    get_google_sheet_id,
    get_google_sheet_name,
    get_telegram_bot_token,
    load_service_account_info,
)
from ..sheets.client import GoogleSheetsClient
from ..sheets.service import SheetsService
from .handlers import (
    BOT_DATA_SHEETS_SERVICE_KEY,
    handle_add_training,
    handle_cancel_training,
    handle_chase,
    handle_deregister,
    handle_help,
    handle_poll_answer,
    handle_poll,
    handle_repoll,
    handle_register,
    handle_register_chat,
)
_APP = None
_BOT = None
_APP_READY = False
_LOOP = None


def _build_application():
    sheets_info = load_service_account_info()
    sheets_client = GoogleSheetsClient.create_from_service_account_info(sheets_info)
    sheets_service = SheetsService(
        sheets_client,
        get_google_sheet_id(),
        get_google_sheet_name(),
    )
    app = build_telegram_application(get_telegram_bot_token())

    app.bot_data[BOT_DATA_SHEETS_SERVICE_KEY] = sheets_service

    app.add_handler(CommandHandler("register", handle_register))
    app.add_handler(CommandHandler("register_chat", handle_register_chat))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("deregister", handle_deregister))
    app.add_handler(CommandHandler("add_training", handle_add_training))
    app.add_handler(CommandHandler("cancel_training", handle_cancel_training))
    app.add_handler(CommandHandler("poll", handle_poll))
    app.add_handler(CommandHandler("repoll", handle_repoll))
    app.add_handler(CommandHandler("chase", handle_chase))
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    return app


def _get_event_loop():
    global _LOOP, _APP, _APP_READY, _BOT
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
        _APP = None
        _BOT = None
        _APP_READY = False
    return _LOOP


async def _get_application():
    global _APP, _APP_READY, _BOT
    if _APP is None:
        _APP = _build_application()
        _BOT = _APP.bot
    if not _APP_READY:
        await _APP.initialize()
        _APP_READY = True
    return _APP


async def process_update_async(update_payload):
    app = await _get_application()
    update = Update.de_json(update_payload, app.bot)
    await app.process_update(update)


def process_update_sync(update_payload):
    loop = _get_event_loop()
    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(process_update_async(update_payload), loop)
        return future.result()
    return loop.run_until_complete(process_update_async(update_payload))


async def get_bot():
    await _get_application()
    return _BOT


def run_polling():
    app = _build_application()
    app.run_polling()
