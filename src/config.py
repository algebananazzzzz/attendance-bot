import json
import os

from dotenv import load_dotenv

from .clients import SSM_CLIENT

_ENV_LOADED = False


def _ensure_env_loaded():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if not os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        dotenv_path = os.getenv("DOTENV_PATH", ".env")
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
    _ENV_LOADED = True


def _get_ssm_parameter(name):
    response = SSM_CLIENT.get_parameter(Name=name, WithDecryption=True)
    return response.get("Parameter", {}).get("Value", "")


def _resolve_parameter(env_value_name, env_parameter_name):
    _ensure_env_loaded()
    param_name = os.getenv(env_parameter_name, "")
    if param_name:
        return _get_ssm_parameter(param_name)
    return os.getenv(env_value_name, "")


def _require(value, message):
    if not value:
        raise ValueError(f"Missing required config: {message}")
    return value


def get_telegram_bot_token():
    value = _resolve_parameter("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN_PARAM")
    return _require(value, "TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN_PARAM")


def get_google_sheet_id():
    value = _resolve_parameter("GOOGLE_SHEET_ID", "GOOGLE_SHEET_ID_PARAM")
    return _require(value, "GOOGLE_SHEET_ID or GOOGLE_SHEET_ID_PARAM")


def get_google_sheet_name():
    _ensure_env_loaded()
    return os.getenv("GOOGLE_SHEET_NAME", "Attendance")


def get_google_service_account_json():
    return _resolve_parameter("GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT_PARAM")


def get_google_service_account_file():
    _ensure_env_loaded()
    return os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")


def load_service_account_info():
    json_value = get_google_service_account_json()
    if json_value:
        return json.loads(json_value)
    file_path = get_google_service_account_file()
    if not file_path:
        raise ValueError(
            "Service account JSON is required. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON/GOOGLE_SERVICE_ACCOUNT_PARAM or GOOGLE_SERVICE_ACCOUNT_FILE."
        )
    with open(file_path, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def get_broadcast_chat_id():
    return _resolve_parameter("BROADCAST_CHAT_ID", "BROADCAST_CHAT_ID_PARAM")


def set_broadcast_chat_id(chat_id):
    _ensure_env_loaded()
    param_name = os.getenv("BROADCAST_CHAT_ID_PARAM", "")
    if not param_name:
        raise ValueError("BROADCAST_CHAT_ID_PARAM is required to store the chat id.")
    SSM_CLIENT.put_parameter(
        Name=param_name,
        Value=str(chat_id),
        Type="String",
        Overwrite=True,
    )
