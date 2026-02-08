"""Shared parsing and formatting helpers."""

import re
from datetime import date, datetime, time

SINGAPORE_TZ = "Asia/Singapore"

TIME_PATTERN = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*([ap]m)?$")
HANDLE_PATTERN = re.compile(r"@([A-Za-z0-9_]{1,64})")
DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d %b",
    "%d %B",
    "%b %d",
    "%B %d",
)


def parse_human_date(value):
    value = (value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt).date()
            if "%Y" not in fmt:
                parsed = parsed.replace(year=date.today().year)
            return parsed
        except ValueError:
            continue
    raise ValueError("Date must be like 2026-02-03 or 3 Feb 2026.")


def parse_time_range(value):
    value = (value or "").strip().lower().replace("to", "-")
    if "-" in value:
        parts = [part.strip() for part in value.split("-", 1)]
    else:
        parts = [part.strip() for part in value.split()]

    if len(parts) != 2:
        raise ValueError(
            "Timing must be start-end, e.g. 1230-1400, 12:30-14:00, or 10pm-11pm."
        )

    start = _parse_time_token(parts[0])
    end = _parse_time_token(parts[1])
    normalized = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    return start, end, normalized


def _parse_time_token(token):
    token = token.strip().lower()
    if token.isdigit() and len(token) in (3, 4):
        token = token.zfill(4)
        return time(hour=int(token[:2]), minute=int(token[2:]))
    match = TIME_PATTERN.match(token)
    if not match:
        raise ValueError(
            "Timing must be start-end, e.g. 1230-1400, 12:30-14:00, or 10pm-11pm."
        )

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem:
        hour = hour % 12
        if meridiem == "pm":
            hour += 12
    return time(hour=hour, minute=minute)


def extract_handle(text):
    match = HANDLE_PATTERN.search(text or "")
    if not match:
        return None
    return f"@{match.group(1)}"


def build_training_question(training):
    summary = build_training_summary(training)
    return f"Training {summary}".strip()


def build_training_summary(training):
    date_label = format_training_date_label(training.get("date", ""))
    time_label = format_training_time_label(training.get("timing", ""))
    description = training.get("description", "")

    parts = [part for part in [date_label, time_label] if part]
    base = " ".join(parts).strip()
    if description:
        return f"{base} - {description}".strip()
    return base


def format_training_date_label(date_value):
    try:
        parsed_date = parse_human_date(date_value)
        return f"{parsed_date.day} {parsed_date.strftime('%b')} ({parsed_date.strftime('%A')})"
    except ValueError:
        return (date_value or "").strip()


def format_training_time_label(timing):
    timing = (timing or "").strip()
    if not timing:
        return ""
    try:
        start, end, _ = parse_time_range(timing)
        return f"{_format_time_12h(start)}-{_format_time_12h(end)}"
    except ValueError:
        return timing


def _format_time_12h(value):
    hour = value.hour
    minute = value.minute
    suffix = "am" if hour < 12 else "pm"
    hour = hour % 12 or 12
    return f"{hour}:{minute:02d}{suffix}"


def build_greeting_message(training_items):
    if not training_items:
        return "Heads up! No trainings scheduled for the coming week. Enjoy the break."
    return "Good morning! Please tap in for this week's trainings."


def build_message_link(chat_id, message_id, chat_username=None):
    if chat_username:
        return f"https://t.me/{chat_username}/{message_id}"
    chat_id_str = str(chat_id)
    if chat_id_str.startswith("-100"):
        internal_id = chat_id_str[4:]
        return f"https://t.me/c/{internal_id}/{message_id}"
    return ""


def build_mentions(members):
    mentions = []
    for member in members:
        member_id = member.get("member_id")
        name = member.get("name") or member.get("handle") or "member"
        if member_id:
            mentions.append(f'<a href="tg://user?id={member_id}">{name}</a>')
        elif member.get("handle"):
            mentions.append(member["handle"])
        else:
            mentions.append(name)
    return mentions


def chunk_mentions(mentions, max_length=3500):
    chunks = []
    current = []
    current_length = 0
    for mention in mentions:
        mention_length = len(mention) + 1
        if current and current_length + mention_length > max_length:
            chunks.append(" ".join(current))
            current = []
            current_length = 0
        current.append(mention)
        current_length += mention_length
    if current:
        chunks.append(" ".join(current))
    return chunks
