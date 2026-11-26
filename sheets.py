from dataclasses import replace
from pathlib import Path

from tasks import Task


HEADERS = ("Task", "Date", "Notes", "Date Added", "Date Completed", "Status", "Archived")
EXTRA_HEADERS = ("Link", "Task ID")
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
LEGACY_COMPLETED = "Completed"


def row_values(row):
    return tuple((list(row) + [""] * 9)[:9])


def task_from_row(index, values):
    title, due, notes, added, completed, status, archived, link, task_id = values
    return Task(
        task_id or f"legacy:{index}", title, due, notes, link, added,
        (completed or LEGACY_COMPLETED) if status.strip().casefold() == "completed" else "",
        archived.strip().casefold() == "yes", values,
    )


class GoogleSheetsTasks:
    def __init__(self, credentials: Path, spreadsheet_id: str | None):
        self.credentials = credentials
        self.spreadsheet_id = spreadsheet_id
        self.worksheet = None

    def sheet(self):
        if self.worksheet is None:
            if not self.credentials.is_file():
                raise ValueError(f"Google Sheets credentials file is missing: {self.credentials}")
            import gspread

            scopes = [SHEETS_SCOPE]
            if not self.spreadsheet_id:
                scopes.append(DRIVE_SCOPE)
            client = gspread.service_account(filename=str(self.credentials), scopes=scopes)
            client.set_timeout(10)
            book = (client.open_by_key(self.spreadsheet_id)
                    if self.spreadsheet_id else client.open("ToDoApp"))
            self.worksheet = book.sheet1
        return self.worksheet

    def read_rows(self):
        sheet = self.sheet()
        rows = sheet.get_all_values()
        header = row_values(rows[0]) if rows else row_values([])
        records = [(index, row_values(row)) for index, row in enumerate(rows[1:], start=2)]

        for column, label in enumerate(EXTRA_HEADERS, start=7):
            heading = header[column].strip()
            if heading.casefold() == label.casefold():
                continue
            if heading or any(values[column] for _, values in records):
                raise ValueError(f"Column {'HI'[column - 7]} is already in use. "
                                 f"Simple To-Do needs that column for {label}.")
        return header, records

    def load(self):
        _, records = self.read_rows()
        tasks = [task_from_row(index, row) for index, row in records if row[0].strip()]
        if len({task.id for task in tasks}) != len(tasks):
            raise ValueError("Duplicate task IDs in Google Sheets. Clear the Task ID in the copied rows.")
        return tasks

    def prepare_columns(self, header):
        sheet = self.sheet()
        if sheet.col_count < 9:
            sheet.add_cols(9 - sheet.col_count)
        if not any(header):
            sheet.update([list(HEADERS + EXTRA_HEADERS)], "A1:I1", raw=True)
        elif not all(header[7:]):
            sheet.update([list(EXTRA_HEADERS)], "H1:I1", raw=True)

    def add(self, task):
        header, records = self.read_rows()
        values = (task.title, task.due, task.notes, task.added, "", "Pending", "No", task.link, task.id)
        matches = [(index, row) for index, row in records if row[8] == task.id]
        if len(matches) == 1:
            return task_from_row(*matches[0])
        if matches:
            raise ValueError("Duplicate task IDs in Google Sheets. Clear the Task ID in the copied rows.")
        self.prepare_columns(header)
        self.sheet().append_row(list(values), value_input_option="RAW", table_range="A1:I")
        return replace(task, sheet_values=values)

    def update(self, original, revised):
        header, records = self.read_rows()
        task_id = original.sheet_values[8]
        if task_id:
            matches = [(index, row) for index, row in records if row[8] == task_id]
        else:
            matches = [(index, row) for index, row in records if row == original.sheet_values]
        if len(matches) > 1:
            raise ValueError("This task has duplicate rows in Google Sheets. "
                             "Give the rows distinct titles or notes, then refresh.")
        if not matches or matches[0][1] != original.sheet_values:
            raise ValueError("This task changed in Google Sheets. Refresh the list and try again.")

        index, row = matches[0]
        changes = {
            column: new for column, old, new in (
                ("A", original.title, revised.title),
                ("B", original.due, revised.due),
                ("C", original.notes, revised.notes),
                ("H", original.link, revised.link),
            ) if old != new
        }
        if revised.completed != original.completed:
            changes["E"] = revised.completed
            changes["F"] = "Completed" if revised.completed else "Pending"
        if revised.archived != original.archived:
            changes["G"] = "Yes" if revised.archived else "No"

        if changes:
            if "H" in changes:
                self.prepare_columns(header)
            self.sheet().batch_update(
                [{"range": f"{column}{index}", "values": [[value]]}
                 for column, value in changes.items()],
                raw=True,
            )
            updated = list(row)
            for column, value in changes.items():
                updated[ord(column) - ord("A")] = value
            return replace(revised, sheet_values=tuple(updated))
        return original
