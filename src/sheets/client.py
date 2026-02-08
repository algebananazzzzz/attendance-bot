import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..constants import HEADER_ROW_COUNT, SHEETS_SCOPE


class SheetsRetryableError(RuntimeError):
    pass


class GoogleSheetsClient:
    def __init__(self, service):
        self.service = service

    def _execute_with_retry(self, request):
        delay = 0.5
        last_exc = None
        for attempt in range(3):
            try:
                return request.execute()
            except HttpError as exc:
                last_exc = exc
            except Exception as exc:
                last_exc = exc

            if attempt < 2:
                time.sleep(delay)
                delay *= 2

        raise SheetsRetryableError(
            "Google Sheets is unavailable. Please try again later."
        ) from last_exc

    @classmethod
    def create_from_service_account_file(cls, service_account_file):
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=[SHEETS_SCOPE],
        )
        service = build("sheets", "v4", credentials=credentials)
        return cls(service)

    @classmethod
    def create_from_service_account_info(cls, service_account_info):
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[SHEETS_SCOPE],
        )
        service = build("sheets", "v4", credentials=credentials)
        return cls(service)

    def get_spreadsheet(self, spreadsheet_id, fields=None):
        request_params = {"spreadsheetId": spreadsheet_id}
        if fields:
            request_params["fields"] = fields
        return self._execute_with_retry(
            self.service.spreadsheets().get(**request_params)
        )

    def ensure_worksheet_exists(self, spreadsheet_id, sheet_name):
        existing_sheet_properties = self.get_worksheet_properties_by_title(spreadsheet_id, sheet_name)
        if existing_sheet_properties:
            return existing_sheet_properties
        return self.create_worksheet(spreadsheet_id, sheet_name)

    def get_worksheet_properties_by_title(self, spreadsheet_id, sheet_name):
        spreadsheet = self.get_spreadsheet(spreadsheet_id)
        for sheet in spreadsheet.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == sheet_name:
                return properties
        return None

    def create_worksheet(self, spreadsheet_id, sheet_name):
        response = self._execute_with_retry(
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
            )
        )
        replies = response.get("replies", [{}])
        add_sheet_reply = replies[0].get("addSheet", {})
        return add_sheet_reply.get("properties", {})

    def batch_update_spreadsheet(self, spreadsheet_id, requests):
        if not requests:
            return
        self._execute_with_retry(
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests},
            )
        )

    def update_values(self, spreadsheet_id, range_name, values, value_input_option="RAW"):
        self._execute_with_retry(
            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body={"values": values},
            )
        )

    def batch_update_values(self, spreadsheet_id, data, value_input_option="RAW"):
        if not data:
            return
        self._execute_with_retry(
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "valueInputOption": value_input_option,
                    "data": data,
                },
            )
        )

    def get_header_rows(self, spreadsheet_id, sheet_name, column_count):
        last_column_letter = convert_column_index_to_letter(max(0, column_count - 1))
        header_range = f"{sheet_name}!A1:{last_column_letter}{HEADER_ROW_COUNT}"
        response = self._execute_with_retry(
            self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=header_range,
                majorDimension="ROWS",
            )
        )
        values = response.get("values", [])
        first_row = values[0] if len(values) > 0 else []
        second_row = values[1] if len(values) > 1 else []
        return first_row, second_row

    def get_values(self, spreadsheet_id, range_name, major_dimension="ROWS"):
        response = self._execute_with_retry(
            self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                majorDimension=major_dimension,
            )
        )
        return response.get("values", [])

    def append_values(
        self,
        spreadsheet_id,
        range_name,
        values,
        value_input_option="RAW",
        insert_data_option="INSERT_ROWS",
    ):
        self._execute_with_retry(
            self.service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                insertDataOption=insert_data_option,
                body={"values": values},
            )
        )


def _is_retryable_http_error(exc):
    return True



def convert_column_index_to_letter(index):
    if index < 0:
        raise ValueError("column index must be non-negative")

    letters = []
    current_index = index
    while True:
        current_index, remainder = divmod(current_index, 26)
        letters.append(chr(65 + remainder))
        if current_index == 0:
            break
        current_index -= 1

    return "".join(reversed(letters))
