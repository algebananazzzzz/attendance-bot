import base64
import json
import logging

from .bot.application import process_update_sync


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _parse_api_gateway_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    if not body:
        return None
    return json.loads(body)


def handler(event, context):
    if "requestContext" in event:
        update = _parse_api_gateway_body(event) or {}
        process_update_sync(update)
        return {"statusCode": 200, "body": "ok"}

    return {"statusCode": 200, "body": "ok"}
