# Attendance Bot

Attendance bot for Telegram that uses **Google Sheets as the database**.

## Quick overview
- Telegram commands create polls and update attendance.
- Manual commands send training polls and reminders.
- All data lives in the Google Sheet (no DynamoDB).

## How it works
1. `/register` posts a poll. Anyone who votes **Yes** is added to the Attendance sheet.
2. `/add_training` writes a row in the `Trainings` sheet and creates a date column in the `Attendance` sheet.
3. `/poll` posts a poll for each training that week.
4. Poll answers update the attendance cell directly.
5. `/chase` pings members who have not responded (for all polls this week).

## Google Sheet layout
There are three worksheets used:
- `Attendance` (default sheet name)
  - Column A: Name
  - Column B: Telegram handle
  - Columns C..: one column per training date
- `Trainings`
  - `Date`, `Timing`, `Description`
- `Polls`
  - `PollId`, `Type`, `TrainingDate`, `ChatId`, `MessageId`, `MessageLink`, `TargetUserId`, `CreatedAt`
- `Admins`
  - `Username` (Telegram usernames, one per row)

## Commands
- `/help`
- `/register`
- `/register_chat` (set broadcast chat)
- `/deregister @username`
- `/add_training <date> <start-end> [description]`
- `/cancel_training <date>`
- `/poll` (send training polls for the current week)
- `/repoll` (send polls only for newly added trainings this week)
- `/chase` (send reminders for all polls this week)

Admins only: All commands are restricted to usernames listed in the `Admins` sheet.
Run `/register_chat` inside the broadcast channel to set where polls/reminders are sent.

Date examples: `2026-02-03`, `3 Feb`, `03/02/2026`  
Time examples: `1230-1400`, `12:30-14:00`

## Setup (local)
1. Create a Google Cloud project and enable **Google Sheets API**.
2. Create a **service account** and download the JSON key file.
3. Share your Google Sheet with the service account email.

Install:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:
```bash
TELEGRAM_BOT_TOKEN="your_bot_token"
GOOGLE_SHEET_ID="your_sheet_id_here"
GOOGLE_SERVICE_ACCOUNT_FILE="./service-account.json"
GOOGLE_SHEET_NAME="Attendance"
```

Dotenv is auto-loaded for local runs (skipped in Lambda).

Run locally (polling):
```bash
python main.py
```

Run locally (webhook update JSON):
```bash
python main.py --update path/to/update.json
```

## Setup (AWS Lambda)
Terraform provisions:
- Lambda (container image)
- SSM Parameter Store for Sheets credentials

Lambda VPC config (optional):
- `vpc_subnet_name_labels` and `vpc_security_group_name_labels` in `infra/config/*.tfvars`
- Use `$env` in names to substitute the environment (e.g. `$env-app-subnet-private-1a`)

Expected environment vars in Lambda:
- `TELEGRAM_BOT_TOKEN_PARAM` (SSM path)
- `GOOGLE_SHEET_ID_PARAM` (SSM path)
- `GOOGLE_SERVICE_ACCOUNT_PARAM` (SSM path)

SSM values can be updated manually using `aws ssm put-parameter --overwrite`.

## Secrets (SSM manual update)
Required SSM parameters:
- `/attendancebot/prd/google_sheet_id` (SecureString)
- `/attendancebot/prd/google_service_account_json` (SecureString)
- `/attendancebot/prd/telegram_bot_token` (SecureString)

Manual SSM update (example for `project_code = "attendancebot"` and `env = "prd"`):
```bash
aws ssm put-parameter \
  --name "/attendancebot/prd/google_sheet_id" \
  --type SecureString \
  --value "YOUR_SHEET_ID" \
  --overwrite

aws ssm put-parameter \
  --name "/attendancebot/prd/google_service_account_json" \
  --type SecureString \
  --value "$(jq -c . service-account.json)" \
  --overwrite

aws ssm put-parameter \
  --name "/attendancebot/prd/telegram_bot_token" \
  --type SecureString \
  --value "YOUR_TELEGRAM_BOT_TOKEN" \
  --overwrite
```

Note: locally you can keep using `TELEGRAM_BOT_TOKEN` in `.env`. In Lambda, the bot reads the token from SSM via `TELEGRAM_BOT_TOKEN_PARAM`.

Never commit `service-account.json`. If it was ever committed or shared, revoke and rotate the key in Google Cloud.

## Docker deploy script
Use `scripts/deploy-image.sh` for both local and CI deployments.

Local example:
```bash
export ECR_REPOSITORY_URL="123456789.dkr.ecr.ap-southeast-1.amazonaws.com/attendancebot"
export FUNCTION_NAME="prd-app-func-attendancebot"
export IMAGE_TAG="prd-$(git rev-parse --short HEAD)"
export AWS_REGION="ap-southeast-1"

# Login once, then deploy
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${ECR_REPOSITORY_URL%%/*}"

./scripts/deploy-image.sh
```

If you want the script to perform ECR login:
```bash
./scripts/deploy-image.sh --login
```

## Project structure
- `src/config.py`: environment/SSM config + dotenv loader.
- `src/clients.py`: AWS + Telegram clients.
- `src/bot/application.py`: python-telegram-bot application setup.
- `src/bot/handlers.py`: command + poll handlers (no direct Sheets logic).
- `src/jobs/`: poll and chase helpers (Lambda + bot commands).
- `src/sheets/service.py`: Sheets read/write operations.
- `src/sheets/`: Google Sheets API helpers and formatting.
- `src/common/`: shared utilities.
- `main.py`: local update processor entrypoint.
