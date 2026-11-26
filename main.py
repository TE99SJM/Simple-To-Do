import argparse
import sys
from pathlib import Path

from PyQt5.QtCore import QStandardPaths
from PyQt5.QtWidgets import QApplication

from gui import ToDoListApp
from sheets import GoogleSheetsTasks
from tasks import LocalTasks


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Simple To-Do.")
    parser.add_argument("--sheets", action="store_true", help="Use Google Sheets for storage.")
    parser.add_argument("--sheet-id", help="Google spreadsheet ID. Defaults to the name ToDoApp.")
    parser.add_argument("--credentials", type=Path, default=Path("credentials.json"),
                        help="Path to the Google service-account JSON key.")
    options = parser.parse_args(argv)

    app = QApplication([sys.argv[0]])
    app.setApplicationName("Simple To-Do")
    if options.sheets or options.sheet_id:
        store = GoogleSheetsTasks(options.credentials, options.sheet_id)
        storage_label = "Google Sheets"
    else:
        app_data = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        store = LocalTasks(app_data / "tasks.sqlite3")
        storage_label = "Local storage"

    window = ToDoListApp(store, storage_label)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
