"""Reminder job for upcoming trainings."""

from ..common.util import build_mentions, build_training_summary, chunk_mentions


async def send_reminder_for_training(bot, sheets_service, training_date, chat_id):
    if not (sheets_service and sheets_service.spreadsheet_id):
        return False

    trainings = sheets_service.get_week_trainings(training_date, training_date)
    training = trainings[0] if trainings else None
    if not training:
        return False

    summary = build_training_summary(training)
    reminder_text = f"Reminder! There's training on {summary}."

    poll_meta = sheets_service.get_latest_poll_for_training(training_date)
    if poll_meta and poll_meta.get("message_link"):
        reminder_text += f" Poll: {poll_meta.get('message_link')}"

    if not chat_id:
        raise ValueError("Chat id is required for chase messages.")

    await bot.send_message(chat_id=chat_id, text=reminder_text)

    not_voted = sheets_service.find_members_missing_vote(training_date)
    if not_voted:
        mentions = build_mentions(not_voted)
        for chunk in chunk_mentions(mentions):
            await bot.send_message(
                chat_id=chat_id,
                text=f"Please update your attendance: {chunk}",
                parse_mode="HTML",
            )
    return True


# run_reminder_job removed (no scheduled execution)
