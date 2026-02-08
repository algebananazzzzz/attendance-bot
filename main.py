#!/usr/bin/env python3
import argparse
import json

from src.app import handler
from src.bot.application import run_polling


class _LocalContext:
    invoked_function_arn = "local"


def _invoke_weekly():
    return handler({"kind": "weekly"}, _LocalContext())


def _invoke_reminder(training_date):
    return handler({"kind": "reminder", "training_date": training_date}, _LocalContext())


def _invoke_update(path):
    with open(path, "r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)
    event = {
        "body": json.dumps(payload),
        "isBase64Encoded": False,
        "requestContext": {"http": {"method": "POST", "path": "/webhook"}},
    }
    return handler(event, _LocalContext())


def main():
    parser = argparse.ArgumentParser(description="Run the bot locally.")
    parser.add_argument("--polling", action="store_true", help="Run Telegram polling loop.")
    parser.add_argument("--weekly", action="store_true", help="Trigger weekly job once.")
    parser.add_argument("--reminder", help="Trigger reminder job for YYYY-MM-DD.")
    parser.add_argument("--update", help="Process a Telegram update JSON file.")
    args = parser.parse_args()

    if args.weekly:
        _invoke_weekly()
        return
    if args.reminder:
        _invoke_reminder(args.reminder)
        return
    if args.update:
        _invoke_update(args.update)
        return

    if args.polling:
        run_polling()
        return

    raise SystemExit("No action specified. Use --polling, --weekly, --reminder, or --update.")


if __name__ == "__main__":
    main()
