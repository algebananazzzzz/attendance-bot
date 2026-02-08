"""Google Sheets service for attendance, trainings, and polls."""

from datetime import datetime
import re

from ..constants import (
    DATA_START_ROW,
    MEMBER_COLUMNS,
    MEMBER_INFO_LABEL,
    TOTAL_LABEL,
    TRAINING_DATES_LABEL,
)
from ..data.members import build_member_identity_key, normalize_telegram_handle
from .client import convert_column_index_to_letter


ATTENDANCE_SHEET = "Attendance"
TRAININGS_SHEET = "Trainings"
POLLS_SHEET = "Polls"
ADMINS_SHEET = "Admins"

TRAININGS_HEADERS = ["Date", "Timing", "Description"]
POLLS_HEADERS = [
    "PollId",
    "Type",
    "TrainingDate",
    "ChatId",
    "MessageId",
    "MessageLink",
    "TargetUserId",
    "CreatedAt",
]
ADMINS_HEADERS = ["Username"]

DATE_HEADER_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DISPLAY_DATE_FORMATS = ("%d %b %Y (%A)", "%d %B %Y (%A)")


class SheetsService:
    def __init__(self, client, spreadsheet_id, sheet_name=None):
        self.client = client
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name or ATTENDANCE_SHEET
        self._conditional_formats_cleared = False

    def register_member(self, user):
        trainings = self._load_trainings_from_sheet()
        layout_info = self._ensure_training_columns(trainings)

        member_item = {
            "name": " ".join(part for part in [user.first_name, user.last_name] if part),
            "handle": f"@{user.username}" if user.username else "",
        }
        member_for_sheet = self._normalize_member_for_sheet(member_item)
        self._ensure_member_row(member_for_sheet, layout_info)
        return member_item

    def remove_member(self, handle):
        member_rows = self.client.get_values(
            self.spreadsheet_id,
            f"{self.sheet_name}!A{DATA_START_ROW}:B",
        )
        for index, row in enumerate(member_rows):
            row_handle = row[1] if len(row) > 1 else ""
            if row_handle == handle:
                sheet_id = self.client.get_worksheet_properties_by_title(
                    self.spreadsheet_id,
                    self.sheet_name,
                ).get("sheetId")
                row_index = DATA_START_ROW + index
                self.client.batch_update_spreadsheet(
                    self.spreadsheet_id,
                    [
                        {
                            "deleteDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": row_index - 1,
                                    "endIndex": row_index,
                                }
                            }
                        }
                    ],
                )
                return True
        return False

    def add_training(self, training_date, timing, description):
        self._upsert_training_row(
            {"date": training_date, "timing": timing, "description": description},
        )
        trainings = self._load_trainings_from_sheet()
        self._ensure_training_columns(trainings)

    def cancel_training(self, training_date):
        deleted = self._delete_training_row(training_date)
        self._remove_training_column(training_date)
        return deleted

    def record_poll_answer(self, user, training_date, status):
        trainings = self._load_trainings_from_sheet()
        layout_info = self._ensure_training_columns(trainings)

        member_item = {
            "name": " ".join(part for part in [user.first_name, user.last_name] if part),
            "handle": f"@{user.username}" if user.username else "",
        }
        member_for_sheet = self._normalize_member_for_sheet(member_item)
        row_index, _ = self._ensure_member_row(member_for_sheet, layout_info)

        column_index = layout_info["date_columns"].get(training_date)
        if column_index is None:
            return

        self._update_attendance_cell(row_index, column_index, status)

    def get_week_trainings(self, start_date, end_date):
        trainings = self._load_trainings_from_sheet()
        return [
            training
            for training in trainings
            if start_date <= training.get("date", "") <= end_date
        ]

    def find_members_missing_vote(self, training_date):
        member_rows = self.client.get_values(
            self.spreadsheet_id,
            f"{self.sheet_name}!A{DATA_START_ROW}:B",
        )
        trainings = self._load_trainings_from_sheet()
        layout_info = self._ensure_training_columns(trainings)
        column_index = layout_info["date_columns"].get(training_date)
        if column_index is None:
            return []

        column_letter = chr(65 + column_index)
        attendance_column = self.client.get_values(
            self.spreadsheet_id,
            f"{self.sheet_name}!{column_letter}{DATA_START_ROW}:{column_letter}",
        )

        missing = []
        for idx, row in enumerate(member_rows):
            handle_value = row[1] if len(row) > 1 else ""
            voted_value = (
                attendance_column[idx][0]
                if idx < len(attendance_column) and attendance_column[idx]
                else ""
            )
            if not voted_value and handle_value:
                missing.append({"handle": handle_value, "name": row[0] if row else ""})
        return missing

    def append_poll_metadata(self, **kwargs):
        self._append_poll_meta(**kwargs)

    def get_poll_metadata(self, poll_id):
        return self._get_poll_meta(poll_id)

    def get_latest_poll_for_training(self, training_date):
        return self._get_latest_training_poll_meta(training_date)

    def ensure_attendance_columns(self):
        trainings = self._load_trainings_from_sheet()
        self._ensure_training_columns(trainings)

    def is_admin(self, username):
        if not username:
            return False
        normalized = self._normalize_admin_username(username)
        if not normalized:
            return False
        self._ensure_sheet_exists(ADMINS_SHEET, ADMINS_HEADERS)
        rows = self.client.get_values(self.spreadsheet_id, f"{ADMINS_SHEET}!A2:A")
        for row in rows:
            if not row:
                continue
            candidate = self._normalize_admin_username(row[0])
            if candidate and candidate == normalized:
                return True
        return False

    def _ensure_sheet_exists(self, sheet_name, headers=None):
        properties = self.client.get_worksheet_properties_by_title(
            self.spreadsheet_id,
            sheet_name,
        )
        if not properties:
            properties = self.client.create_worksheet(self.spreadsheet_id, sheet_name)

        if headers:
            header_range = f"{sheet_name}!A1:{chr(64 + len(headers))}1"
            existing_headers = self.client.get_values(self.spreadsheet_id, header_range)
            if not existing_headers or not existing_headers[0]:
                self.client.update_values(self.spreadsheet_id, header_range, [headers])

        return properties

    def _load_trainings_from_sheet(self):
        self._ensure_sheet_exists(TRAININGS_SHEET, TRAININGS_HEADERS)
        rows = self.client.get_values(self.spreadsheet_id, f"{TRAININGS_SHEET}!A2:C")
        trainings = []
        for row in rows:
            date_value = row[0].strip() if len(row) > 0 else ""
            if not date_value:
                continue
            trainings.append(
                {
                    "date": date_value,
                    "timing": row[1].strip() if len(row) > 1 else "",
                    "description": row[2].strip() if len(row) > 2 else "",
                }
            )
        return trainings

    def _normalize_admin_username(self, value):
        if not value:
            return ""
        value = str(value).strip()
        if value.startswith("@"):
            value = value[1:]
        return value.lower()

    def _upsert_training_row(self, training):
        self._ensure_sheet_exists(TRAININGS_SHEET, TRAININGS_HEADERS)
        rows = self.client.get_values(self.spreadsheet_id, f"{TRAININGS_SHEET}!A2:C")
        target_date = training.get("date")
        for idx, row in enumerate(rows, start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            if row_date == target_date:
                self.client.update_values(
                    self.spreadsheet_id,
                    f"{TRAININGS_SHEET}!A{idx}:C{idx}",
                    [[target_date, training.get("timing", ""), training.get("description", "")]],
                )
                return
        insert_idx = None
        for idx, row in enumerate(rows, start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            if row_date and target_date and row_date > target_date:
                insert_idx = idx
                break

        if insert_idx is None:
            self.client.append_values(
                self.spreadsheet_id,
                f"{TRAININGS_SHEET}!A:C",
                [[target_date, training.get("timing", ""), training.get("description", "")]],
            )
            return

        sheet_id = self.client.get_worksheet_properties_by_title(
            self.spreadsheet_id, TRAININGS_SHEET
        ).get("sheetId")
        self.client.batch_update_spreadsheet(
            self.spreadsheet_id,
            [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": insert_idx - 1,
                            "endIndex": insert_idx,
                        },
                        "inheritFromBefore": True,
                    }
                }
            ],
        )
        self.client.update_values(
            self.spreadsheet_id,
            f"{TRAININGS_SHEET}!A{insert_idx}:C{insert_idx}",
            [[target_date, training.get("timing", ""), training.get("description", "")]],
        )

    def _delete_training_row(self, training_date):
        self._ensure_sheet_exists(TRAININGS_SHEET, TRAININGS_HEADERS)
        rows = self.client.get_values(self.spreadsheet_id, f"{TRAININGS_SHEET}!A2:C")
        for idx, row in enumerate(rows, start=2):
            row_date = row[0].strip() if len(row) > 0 else ""
            if row_date == training_date:
                sheet_id = self.client.get_worksheet_properties_by_title(
                    self.spreadsheet_id, TRAININGS_SHEET
                ).get("sheetId")
                self.client.batch_update_spreadsheet(
                    self.spreadsheet_id,
                    [
                        {
                            "deleteDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": idx - 1,
                                    "endIndex": idx,
                                }
                            }
                        }
                    ],
                )
                return True
        return False

    def _append_poll_meta(
        self,
        poll_id,
        poll_type,
        chat_id,
        message_id,
        training_date=None,
        target_user_id=None,
        message_link=None,
    ):
        self._ensure_sheet_exists(POLLS_SHEET, POLLS_HEADERS)
        created_at = datetime.utcnow().isoformat()
        self.client.append_values(
            self.spreadsheet_id,
            f"{POLLS_SHEET}!A:H",
            [
                [
                    poll_id,
                    poll_type,
                    training_date or "",
                    str(chat_id or ""),
                    str(message_id or ""),
                    message_link or "",
                    str(target_user_id or ""),
                    created_at,
                ]
            ],
        )

    def _get_poll_meta(self, poll_id):
        self._ensure_sheet_exists(POLLS_SHEET, POLLS_HEADERS)
        rows = self.client.get_values(self.spreadsheet_id, f"{POLLS_SHEET}!A2:H")
        for row in rows:
            if len(row) > 0 and row[0] == poll_id:
                return {
                    "poll_id": row[0],
                    "poll_type": row[1] if len(row) > 1 else "",
                    "training_date": row[2] if len(row) > 2 else "",
                    "chat_id": row[3] if len(row) > 3 else "",
                    "message_id": row[4] if len(row) > 4 else "",
                    "message_link": row[5] if len(row) > 5 else "",
                    "target_user_id": row[6] if len(row) > 6 else "",
                    "created_at": row[7] if len(row) > 7 else "",
                }
        return None

    def _get_latest_training_poll_meta(self, training_date):
        self._ensure_sheet_exists(POLLS_SHEET, POLLS_HEADERS)
        rows = self.client.get_values(self.spreadsheet_id, f"{POLLS_SHEET}!A2:H")
        for row in reversed(rows):
            if len(row) > 2 and row[2] == training_date and row[1] == "training":
                return {
                    "poll_id": row[0],
                    "poll_type": row[1],
                    "training_date": row[2],
                    "chat_id": row[3] if len(row) > 3 else "",
                    "message_id": row[4] if len(row) > 4 else "",
                    "message_link": row[5] if len(row) > 5 else "",
                    "target_user_id": row[6] if len(row) > 6 else "",
                    "created_at": row[7] if len(row) > 7 else "",
                }
        return None

    def _ensure_sheet_properties(self):
        properties = self.client.get_worksheet_properties_by_title(
            self.spreadsheet_id, self.sheet_name
        )
        if properties:
            return properties
        return self.client.create_worksheet(self.spreadsheet_id, self.sheet_name)

    def _clear_conditional_formatting(self, sheet_id):
        if self._conditional_formats_cleared:
            return
        spreadsheet = self.client.get_spreadsheet(
            self.spreadsheet_id,
            fields="sheets(properties.sheetId,properties.title,conditionalFormats)",
        )
        target_sheet = None
        for sheet in spreadsheet.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("sheetId") == sheet_id:
                target_sheet = sheet
                break

        conditional_formats = (target_sheet or {}).get("conditionalFormats", [])
        if not conditional_formats:
            self._conditional_formats_cleared = True
            return

        requests = [
            {
                "deleteConditionalFormatRule": {
                    "sheetId": sheet_id,
                    "index": index,
                }
            }
            for index in reversed(range(len(conditional_formats)))
        ]
        self.client.batch_update_spreadsheet(self.spreadsheet_id, requests)
        self._conditional_formats_cleared = True

    def _normalize_member_for_sheet(self, member):
        name = (member.get("name") or "").strip()
        handle = normalize_telegram_handle(member.get("handle") or member.get("telegram"))
        if not name and handle:
            name = handle.lstrip("@")
        return {"name": name, "telegram": handle}

    def _build_member_identity_key_from_sheet_row(self, row_values):
        if not row_values:
            return None

        member_name = str(row_values[0]).strip() if len(row_values) > 0 else ""
        member_telegram = ""
        if len(row_values) > 1:
            member_telegram = normalize_telegram_handle(row_values[1])

        if not member_name and not member_telegram:
            return None

        if not member_name and member_telegram:
            member_name = member_telegram.lstrip("@")

        member = {"name": member_name, "telegram": member_telegram}
        return build_member_identity_key(member)

    def _get_sheet_member_rows(self):
        member_range = f"{self.sheet_name}!A{DATA_START_ROW}:B"
        return self.client.get_values(self.spreadsheet_id, member_range)

    def _build_training_days_from_items(self, training_items):
        days = []
        for item in training_items:
            date_value = item.get("date")
            if date_value:
                days.append({"date": date_value, "label": item.get("description") or None})
        return sorted(days, key=lambda item: item["date"])

    def _ensure_training_columns(self, training_items):
        training_days = self._build_training_days_from_items(training_items)
        sheet_properties = self._ensure_sheet_properties()
        sheet_id = sheet_properties.get("sheetId")
        column_count = sheet_properties.get("gridProperties", {}).get("columnCount", 26)
        if sheet_id is None:
            raise ValueError("Unable to resolve target sheet id.")

        layout_info = self._ensure_sheet_layout(sheet_id, column_count, training_days)
        self._ensure_total_formulas(
            layout_info.get("total_column_index"),
            layout_info.get("date_columns", {}),
        )
        return layout_info

    def _get_member_row_index(self, member):
        member_rows = self._get_sheet_member_rows()
        member_key = build_member_identity_key(member)
        for index, row in enumerate(member_rows):
            row_key = self._build_member_identity_key_from_sheet_row(row)
            if row_key and row_key == member_key:
                return DATA_START_ROW + index
        return None

    def _append_member_row(self, member):
        member_rows = self._get_sheet_member_rows()
        self.client.append_values(
            self.spreadsheet_id,
            f"{self.sheet_name}!A:B",
            [[member["name"], member["telegram"]]],
            value_input_option="RAW",
            insert_data_option="INSERT_ROWS",
        )
        return DATA_START_ROW + len(member_rows)

    def _ensure_member_row(self, member, layout_info=None):
        row_index = self._get_member_row_index(member)
        if row_index is not None:
            return row_index, False
        row_index = self._append_member_row(member)
        if layout_info:
            self._set_total_formula_for_row(
                row_index,
                layout_info.get("total_column_index"),
                layout_info.get("date_columns", {}),
            )
        return row_index, True

    def _update_attendance_cell(self, row_index, column_index, status):
        column_letter = convert_column_index_to_letter(column_index)
        range_name = f"{self.sheet_name}!{column_letter}{row_index}"
        self.client.update_values(self.spreadsheet_id, range_name, [[status]], value_input_option="RAW")

    def _build_total_formula(self, row_index, date_columns):
        if not date_columns:
            return None
        first_index = min(date_columns.values())
        last_index = max(date_columns.values())
        first_col = convert_column_index_to_letter(first_index)
        last_col = convert_column_index_to_letter(last_index)
        return f"=SUM({first_col}{row_index}:{last_col}{row_index})"

    def _set_total_formula_for_row(self, row_index, total_column_index, date_columns):
        if total_column_index is None:
            return
        formula = self._build_total_formula(row_index, date_columns)
        if not formula:
            return
        column_letter = convert_column_index_to_letter(total_column_index)
        range_name = f"{self.sheet_name}!{column_letter}{row_index}"
        self.client.update_values(
            self.spreadsheet_id,
            range_name,
            [[formula]],
            value_input_option="USER_ENTERED",
        )

    def _ensure_total_formulas(self, total_column_index, date_columns):
        if total_column_index is None or not date_columns:
            return
        member_rows = self._get_sheet_member_rows()
        if not member_rows:
            return
        start_row = DATA_START_ROW
        end_row = DATA_START_ROW + len(member_rows) - 1
        column_letter = convert_column_index_to_letter(total_column_index)
        range_name = f"{self.sheet_name}!{column_letter}{start_row}:{column_letter}{end_row}"
        values = [
            [self._build_total_formula(row_index, date_columns)]
            for row_index in range(start_row, end_row + 1)
        ]
        self.client.update_values(
            self.spreadsheet_id,
            range_name,
            values,
            value_input_option="USER_ENTERED",
        )

    def _remove_training_column(self, training_date):
        sheet_properties = self._ensure_sheet_properties()
        sheet_id = sheet_properties.get("sheetId")
        column_count = sheet_properties.get("gridProperties", {}).get("columnCount", 26)
        if sheet_id is None:
            raise ValueError("Unable to resolve target sheet id.")

        header_row_one, header_row_two = self.client.get_header_rows(
            self.spreadsheet_id, self.sheet_name, column_count
        )
        _, date_columns, _ = self._parse_existing_layout(header_row_one, header_row_two)
        if training_date not in date_columns:
            return False

        column_index = date_columns[training_date]
        self.client.batch_update_spreadsheet(
            self.spreadsheet_id,
            [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": column_index,
                            "endIndex": column_index + 1,
                        }
                    }
                }
            ],
        )
        return True

    def _normalize_cell(self, value):
        if value is None:
            return ""
        return str(value).strip()

    def _format_training_date_for_header(self, date_value):
        parsed_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        return parsed_date.strftime("%d %b %Y (%A)").lstrip("0")

    def _parse_training_date_from_header(self, cell_value):
        if not cell_value:
            return None

        normalized_value = cell_value.strip()
        if DATE_HEADER_PATTERN.match(normalized_value):
            return normalized_value

        for display_format in DISPLAY_DATE_FORMATS:
            try:
                parsed_date = datetime.strptime(normalized_value, display_format).date()
                return parsed_date.isoformat()
            except ValueError:
                continue

        return None

    def _parse_existing_layout(self, header_row_one, header_row_two):
        normalized_row_one = [self._normalize_cell(value) for value in header_row_one]
        normalized_row_two = [self._normalize_cell(value) for value in header_row_two]

        member_column_count = len(MEMBER_COLUMNS)
        has_expected_table = (
            len(normalized_row_two) >= member_column_count
            and normalized_row_two[:member_column_count] == MEMBER_COLUMNS
        )

        date_columns = {}
        for column_index, cell_value in enumerate(normalized_row_two):
            parsed_date = self._parse_training_date_from_header(cell_value)
            if parsed_date:
                date_columns[parsed_date] = column_index

        total_column_index = None
        for column_index, cell_value in enumerate(normalized_row_one):
            if cell_value == TOTAL_LABEL:
                total_column_index = column_index
                break

        if total_column_index is None:
            for column_index, cell_value in enumerate(normalized_row_two):
                if cell_value == TOTAL_LABEL:
                    total_column_index = column_index
                    break

        return has_expected_table, date_columns, total_column_index

    def _shift_date_columns(self, date_columns, start_index):
        for date_value in list(date_columns.keys()):
            if date_columns[date_value] >= start_index:
                date_columns[date_value] += 1

    def _ensure_column_capacity(self, sheet_id, existing_count, required_count):
        if required_count <= existing_count:
            return

        self.client.batch_update_spreadsheet(
            self.spreadsheet_id,
            [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": existing_count,
                            "endIndex": required_count,
                        },
                        "inheritFromBefore": True,
                    }
                }
            ],
        )

    def _build_header_rows(self, date_columns, total_column_index):
        header_length = total_column_index + 1
        row_one = [""] * header_length
        row_two = [""] * header_length

        row_one[0] = MEMBER_INFO_LABEL
        member_column_count = len(MEMBER_COLUMNS)
        row_two[0:member_column_count] = MEMBER_COLUMNS

        for date_value, column_index in date_columns.items():
            if column_index < header_length:
                row_two[column_index] = self._format_training_date_for_header(date_value)

        if date_columns:
            first_date_column_index = min(date_columns.values())
            row_one[first_date_column_index] = TRAINING_DATES_LABEL

        row_one[total_column_index] = TOTAL_LABEL
        return [row_one, row_two]

    def _write_header_rows(self, date_columns, total_column_index):
        header_rows = self._build_header_rows(date_columns, total_column_index)
        last_column_letter = convert_column_index_to_letter(total_column_index)
        header_range = f"{self.sheet_name}!A1:{last_column_letter}2"
        self.client.update_values(self.spreadsheet_id, header_range, header_rows, value_input_option="RAW")

    def _ensure_sheet_layout(self, sheet_id, column_count, training_days):
        self._clear_conditional_formatting(sheet_id)
        header_row_one, header_row_two = self.client.get_header_rows(
            self.spreadsheet_id,
            self.sheet_name,
            column_count,
        )
        has_expected_table, date_columns, total_column_index = self._parse_existing_layout(
            header_row_one,
            header_row_two,
        )

        training_dates = [day.get("date") for day in training_days if day.get("date")]
        member_column_count = len(MEMBER_COLUMNS)

        if not has_expected_table:
            date_columns = {
                date_value: member_column_count + index
                for index, date_value in enumerate(training_dates)
            }
            total_column_index = member_column_count + len(date_columns)
            self._ensure_column_capacity(sheet_id, column_count, total_column_index + 1)
            self._write_header_rows(date_columns, total_column_index)
            return {"date_columns": date_columns, "total_column_index": total_column_index}

        missing_dates = [date_value for date_value in training_dates if date_value not in date_columns]
        insert_requests = []
        insert_index = (
            total_column_index
            if total_column_index is not None
            else (max(date_columns.values(), default=member_column_count - 1) + 1)
        )

        for date_value in missing_dates:
            insert_requests.append(
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": insert_index,
                            "endIndex": insert_index + 1,
                        },
                        "inheritFromBefore": True,
                    }
                }
            )
            self._shift_date_columns(date_columns, insert_index)
            if total_column_index is not None and total_column_index >= insert_index:
                total_column_index += 1
            date_columns[date_value] = insert_index
            insert_index += 1

        if total_column_index is None:
            total_column_index = max(date_columns.values(), default=member_column_count - 1) + 1
            insert_requests.append(
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": total_column_index,
                            "endIndex": total_column_index + 1,
                        },
                        "inheritFromBefore": True,
                    }
                }
            )

        if insert_requests:
            self.client.batch_update_spreadsheet(self.spreadsheet_id, insert_requests)

        self._ensure_column_capacity(sheet_id, column_count, total_column_index + 1)
        self._write_header_rows(date_columns, total_column_index)
        return {"date_columns": date_columns, "total_column_index": total_column_index}
