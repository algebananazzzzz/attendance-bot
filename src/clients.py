"""Shared external clients."""

import boto3
from telegram.ext import Application


SSM_CLIENT = boto3.client("ssm")


def build_telegram_application(token):
    return Application.builder().token(token).build()
