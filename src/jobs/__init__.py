from ..config import (
    get_google_sheet_id,
    get_google_sheet_name,
    load_service_account_info,
)
from ..sheets.client import GoogleSheetsClient
from ..sheets.service import SheetsService


_SHEETS_SERVICE = None


def get_sheets_service():
    global _SHEETS_SERVICE
    if _SHEETS_SERVICE is None:
        sheets_info = load_service_account_info()
        sheets_client = GoogleSheetsClient.create_from_service_account_info(sheets_info)
        _SHEETS_SERVICE = SheetsService(
            sheets_client,
            get_google_sheet_id(),
            get_google_sheet_name(),
        )
    return _SHEETS_SERVICE
