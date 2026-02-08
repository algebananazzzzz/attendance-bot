"""Telegram command and poll handlers (python-telegram-bot)."""

from ..jobs.weekly import send_chase_for_week, send_training_polls_for_week
from ..common.util import (
    build_training_summary,
    extract_handle,
    format_training_date_label,
    parse_human_date,
    parse_time_range,
)
from ..config import get_broadcast_chat_id, set_broadcast_chat_id
from ..sheets.client import SheetsRetryableError


BOT_DATA_SHEETS_SERVICE_KEY = "sheets_service"
YES_OPTION_ID = 0


def _context_data(context):
    return context.application.bot_data[BOT_DATA_SHEETS_SERVICE_KEY]


async def handle_register(update, context):
    if not await _ensure_admin(update, context):
        return
    sheets_service = _context_data(context)
    target_chat_id = await _get_broadcast_chat_id_or_warn(update, context)
    if target_chat_id is None:
        return

    question = "Want to register as a member?"
    poll_message = await context.bot.send_poll(
        chat_id=target_chat_id,
        question=question,
        options=["Yes", "No"],
        is_anonymous=False,
    )

    try:
        sheets_service.append_poll_metadata(
            poll_id=poll_message.poll.id,
            poll_type="register",
            chat_id=target_chat_id,
            message_id=poll_message.message_id,
        )
    except SheetsRetryableError:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Google Sheets is unavailable. Please try again later.",
        )


async def handle_register_chat(update, context):
    if not await _ensure_admin(update, context):
        return
    chat_id = update.effective_chat.id
    try:
        set_broadcast_chat_id(chat_id)
    except ValueError as exc:
        await context.bot.send_message(chat_id=chat_id, text=str(exc))
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Broadcast chat registered: {chat_id}",
    )


async def handle_deregister(update, context):
    if not await _ensure_admin(update, context):
        return
    handle = extract_handle(update.effective_message.text if update.effective_message else "")
    chat_id = update.effective_chat.id
    if not handle:
        await context.bot.send_message(
            chat_id=chat_id, text="Usage: /deregister @username"
        )
        return

    sheets_service = _context_data(context)
    try:
        removed = sheets_service.remove_member(handle)
    except SheetsRetryableError:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Google Sheets is unavailable. Please try again later.",
        )
        return
    message = (
        f"Member deregistered: {handle}"
        if removed
        else f"Could not find {handle} in the roster."
    )
    await context.bot.send_message(chat_id=chat_id, text=message)


async def handle_add_training(update, context):
    if not await _ensure_admin(update, context):
        return
    chat_id = update.effective_chat.id
    if len(context.args) < 2:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Usage: /add_training <date> <start-end> [description]",
        )
        return

    try:
        date_text, timing_text, description = _split_add_training_args(context.args)
        training_date = parse_human_date(date_text).isoformat()
        _, _, normalized_timing = parse_time_range(timing_text)
    except ValueError:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Usage: /add_training <date> <start-end> [description]",
        )
        return

    sheets_service = _context_data(context)
    try:
        sheets_service.add_training(training_date, normalized_timing, description)
    except SheetsRetryableError:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Google Sheets is unavailable. Please try again later.",
        )
        return

    summary = build_training_summary(
        {"date": training_date, "timing": normalized_timing, "description": description}
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Training added: {summary}".strip(),
    )


async def handle_cancel_training(update, context):
    if not await _ensure_admin(update, context):
        return
    chat_id = update.effective_chat.id
    if not context.args:
        await context.bot.send_message(
            chat_id=chat_id, text="Usage: /cancel_training <date>"
        )
        return

    try:
        training_date = parse_human_date(" ".join(context.args)).isoformat()
    except ValueError:
        await context.bot.send_message(
            chat_id=chat_id, text="Usage: /cancel_training <date>"
        )
        return

    sheets_service = _context_data(context)
    try:
        deleted = sheets_service.cancel_training(training_date)
    except SheetsRetryableError:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Google Sheets is unavailable. Please try again later.",
        )
        return
    formatted_date = format_training_date_label(training_date)
    message = (
        f"Training cancelled: {formatted_date}"
        if deleted
        else f"No training found for {formatted_date}."
    )
    await context.bot.send_message(chat_id=chat_id, text=message)


async def handle_poll_answer(update, context):
    poll_answer = update.poll_answer

    sheets_service = _context_data(context)
    try:
        poll_meta = sheets_service.get_poll_metadata(poll_answer.poll_id) or {}
    except SheetsRetryableError:
        return

    if poll_meta.get("poll_type") == "register":
        await _apply_register_poll(poll_answer, poll_meta, context)
        return

    if poll_meta.get("poll_type") == "training":
        try:
            await _apply_training_poll(poll_answer, poll_meta, context)
        except SheetsRetryableError:
            return


async def _apply_register_poll(poll_answer, poll_meta, context):
    if YES_OPTION_ID not in poll_answer.option_ids:
        return

    sheets_service = _context_data(context)
    member_item = sheets_service.register_member(poll_answer.user)

    chat_id = poll_meta.get("chat_id")
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Welcome aboard: {member_item.get('handle') or member_item.get('name')}",
        )


async def _apply_training_poll(poll_answer, poll_meta, context):
    training_date = poll_meta.get("training_date")
    if not training_date:
        return

    status = 1 if YES_OPTION_ID in poll_answer.option_ids else 0
    sheets_service = _context_data(context)
    sheets_service.record_poll_answer(poll_answer.user, training_date, status)


async def handle_help(update, context):
    if not await _ensure_admin(update, context):
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "Commands:\n"
            "/register - open registration poll\n"
            "/register_chat - set this chat as broadcast\n"
            "/deregister @user - remove a member\n"
            "/add_training <date> <start-end> [desc]\n"
            "/cancel_training <date>\n"
            "/poll - send polls for this week\n"
            "/repoll - send polls for newly added trainings this week\n"
            "/chase - remind members for all polls this week\n\n"
            "Note: Polls and reminders are always sent to the broadcast chat.\n"
            "Run /register_chat in the broadcast channel first.\n\n"
            "Examples:\n"
            "/add_training 6 Aug 1430-1800 Team training\n"
            "/add_training 12 Feb 10pm-11pm Evening session\n"
            "/add_training 2026-02-03 12:30-14:00 Morning session\n"
            "/cancel_training 03/02/2026\n"
            "/deregister @username\n\n"
            "Date examples: 2026-02-03, 3 Feb, 03/02/2026\n"
            "Time examples: 1230-1400, 12:30-14:00, 10pm-11pm"
        ),
    )


def _split_add_training_args(args):
    if len(args) < 2:
        raise ValueError("Not enough args.")

    # Detect time range position.
    for idx, token in enumerate(args):
        if _try_parse_time_range(token):
            date_text = " ".join(args[:idx]).strip()
            if not date_text:
                raise ValueError("Missing date.")
            return date_text, token, " ".join(args[idx + 1 :]).strip()

        if idx + 2 < len(args) and args[idx + 1] in ("-", "to", "–", "—"):
            candidate = f"{args[idx]} {args[idx + 1]} {args[idx + 2]}"
            if _try_parse_time_range(candidate):
                date_text = " ".join(args[:idx]).strip()
                if not date_text:
                    raise ValueError("Missing date.")
                return date_text, candidate, " ".join(args[idx + 3 :]).strip()

        if idx + 1 < len(args):
            candidate = f"{args[idx]}-{args[idx + 1]}"
            if _try_parse_time_range(candidate):
                date_text = " ".join(args[:idx]).strip()
                if not date_text:
                    raise ValueError("Missing date.")
                return date_text, candidate, " ".join(args[idx + 2 :]).strip()

    raise ValueError("No time range detected.")


def _try_parse_time_range(value):
    try:
        parse_time_range(value)
    except ValueError:
        return False
    return True


async def handle_repoll(update, context):
    if not await _ensure_admin(update, context):
        return
    target_chat_id = await _get_broadcast_chat_id_or_warn(update, context)
    if target_chat_id is None:
        return
    try:
        sent_count = await send_training_polls_for_week(
            bot=context.bot,
            sheets_service=_context_data(context),
            chat_id=target_chat_id,
            announce=True,
            only_missing=True,
        )
    except SheetsRetryableError:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Google Sheets is unavailable. Please try again later.",
        )
        return
    if sent_count == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="No other trainings to poll.",
        )


async def handle_poll(update, context):
    if not await _ensure_admin(update, context):
        return
    target_chat_id = await _get_broadcast_chat_id_or_warn(update, context)
    if target_chat_id is None:
        return
    try:
        sent_count = await send_training_polls_for_week(
            bot=context.bot,
            sheets_service=_context_data(context),
            chat_id=target_chat_id,
            announce=True,
            only_missing=False,
        )
    except SheetsRetryableError:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Google Sheets is unavailable. Please try again later.",
        )
        return
    if sent_count == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="No trainings scheduled for this week.",
        )


async def handle_chase(update, context):
    if not await _ensure_admin(update, context):
        return
    target_chat_id = await _get_broadcast_chat_id_or_warn(update, context)
    if target_chat_id is None:
        return
    try:
        sent_count = await send_chase_for_week(
            bot=context.bot,
            sheets_service=_context_data(context),
            chat_id=target_chat_id,
        )
    except SheetsRetryableError:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Google Sheets is unavailable. Please try again later.",
        )
        return
    if sent_count == 0:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="No trainings to chase today.",
        )


async def _get_broadcast_chat_id_or_warn(update, context):
    raw_value = get_broadcast_chat_id()
    if not raw_value:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Broadcast chat not set. Run /register_chat in the broadcast channel.",
        )
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Broadcast chat id is invalid. Run /register_chat again.",
        )
        return None


async def _ensure_admin(update, context):
    user = update.effective_user
    username = user.username if user else None
    if not username:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You need a Telegram username to use this bot.",
        )
        return False

    sheets_service = _context_data(context)
    try:
        is_admin = sheets_service.is_admin(username)
    except SheetsRetryableError:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Google Sheets is unavailable. Please try again later.",
        )
        return False

    if not is_admin:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Not authorized. Ask an admin to add your username to the Admins sheet.",
        )
        return False
    return True
