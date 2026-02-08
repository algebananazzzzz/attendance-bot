"""Weekly job and poll sender."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..common.util import (
    SINGAPORE_TZ,
    build_greeting_message,
    build_message_link,
    build_training_question,
)
from .reminder import send_reminder_for_training


async def send_training_polls_for_week(
    bot,
    sheets_service,
    chat_id,
    announce=False,
    only_missing=False,
):
    timezone = SINGAPORE_TZ
    tz = ZoneInfo(timezone)
    today = datetime.now(tz).date()
    end_date = today + timedelta(days=6)

    trainings = []
    if sheets_service and sheets_service.spreadsheet_id:
        trainings = sheets_service.get_week_trainings(
            today.isoformat(),
            end_date.isoformat(),
        )

    if announce:
        await bot.send_message(chat_id=chat_id, text=build_greeting_message(trainings))

    if sheets_service and sheets_service.spreadsheet_id:
        sheets_service.ensure_attendance_columns()

    sent_count = 0
    for training in trainings:
        if only_missing and sheets_service and sheets_service.spreadsheet_id:
            existing_poll = sheets_service.get_latest_poll_for_training(
                training.get("date", "")
            )
            if existing_poll:
                continue

        poll_message = await bot.send_poll(
            chat_id=chat_id,
            question=build_training_question(training),
            options=["Yes", "No"],
            is_anonymous=False,
        )
        sent_count += 1
        message_link = build_message_link(chat_id=chat_id, message_id=poll_message.message_id)

        if sheets_service and sheets_service.spreadsheet_id:
            sheets_service.append_poll_metadata(
                poll_id=poll_message.poll.id,
                poll_type="training",
                chat_id=chat_id,
                message_id=poll_message.message_id,
                training_date=training.get("date"),
                message_link=message_link,
            )

    return sent_count


async def send_chase_for_week(bot, sheets_service, chat_id):
    timezone = SINGAPORE_TZ
    tz = ZoneInfo(timezone)
    today = datetime.now(tz).date()
    end_date = today + timedelta(days=6)

    trainings = []
    if sheets_service and sheets_service.spreadsheet_id:
        trainings = sheets_service.get_week_trainings(
            today.isoformat(),
            end_date.isoformat(),
        )

    sent_count = 0
    for training in trainings:
        training_date = training.get("date", "")
        if not training_date:
            continue

        existing_poll = sheets_service.get_latest_poll_for_training(training_date)
        if not existing_poll:
            continue

        sent = await send_reminder_for_training(
            bot,
            sheets_service,
            training_date,
            chat_id,
        )
        if sent:
            sent_count += 1

    return sent_count
