from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import Mock

from sheets import GoogleSheetsTasks
from tasks import Task, task_due


class GoogleSheetsTests(unittest.TestCase):
    def setUp(self):
        self.store = GoogleSheetsTasks(Path("unused.json"), None)
        self.sheet = self.store.worksheet = Mock(col_count=26)
        self.header = ["Task", "Date", "Link", "Date Added", "Date Completed", "Status", "Archived"]
        self.later = ["Later task", "12-10-26", "Keep these notes", "2026-11-20", "", "Pending", "No"]
        self.earlier = ["Earlier task", "12-01-26", "", "2026-11-25", "", "Pending", "No"]

    def test_sorted_legacy_task_keeps_its_sheet_row_with_blank_rows(self):
        self.sheet.get_all_values.return_value = [self.header, self.later, [], self.earlier]
        earlier, _ = sorted(self.store.load(), key=task_due)

        self.store.update(earlier, replace(earlier, completed="2026-11-26 10:00:00"))

        self.sheet.batch_update.assert_called_once_with([
            {"range": "E4", "values": [["2026-11-26 10:00:00"]]},
            {"range": "F4", "values": [["Completed"]]},
        ], raw=True)

    def test_archive_relocates_a_legacy_task_moved_in_the_sheet(self):
        self.sheet.get_all_values.side_effect = [
            [self.header, self.later, self.earlier],
            [self.header, self.earlier, self.later],
        ]
        _, earlier = self.store.load()

        self.store.update(earlier, replace(earlier, archived=True))

        self.sheet.batch_update.assert_called_once_with([
            {"range": "G2", "values": [["Yes"]]},
        ], raw=True)

    def test_duplicate_legacy_rows_fail_without_writing(self):
        self.sheet.get_all_values.return_value = [self.header, self.later, self.later]
        later, _ = self.store.load()

        with self.assertRaisesRegex(ValueError, "duplicate rows"):
            self.store.update(later, replace(later, archived=True))

        self.sheet.batch_update.assert_not_called()

    def test_retry_after_append_keeps_one_task_with_separate_notes_and_link(self):
        task = Task.new("Update plans", "", "These are the notes", "https://example.org")
        self.sheet.get_all_values.return_value = [self.header]

        saved = self.store.add(task)

        self.sheet.update.assert_called_once_with([["Link", "Task ID"]], "H1:I1", raw=True)
        self.sheet.append_row.assert_called_once_with(
            [task.title, "", task.notes, task.added, "", "Pending", "No", task.link, task.id],
            value_input_option="RAW", table_range="A1:I",
        )
        saved_row = self.sheet.append_row.call_args.args[0]
        self.sheet.get_all_values.return_value = [self.header + ["Link", "Task ID"], saved_row]
        self.assertEqual(self.store.add(task), saved)
        self.sheet.append_row.assert_called_once()


if __name__ == "__main__":
    unittest.main()
