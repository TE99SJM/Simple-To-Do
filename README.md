# Simple To-Do

A desktop task list for Windows, macOS, and Linux. Add a due date, notes, or a web or local file link. Use the Open, Completed, and Archived views to finish, reopen, and restore tasks. Search matches titles, notes, links, and due dates.

## Run locally

1. Install Python 3.10 or later, then clone the repository.

   ```sh
   git clone https://github.com/TE99SJM/Simple-To-Do.git
   cd Simple-To-Do
   ```

2. Create a virtual environment, install the dependencies, and start the app.

   Windows PowerShell

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe main.py
   ```

   macOS or Linux

   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python main.py
   ```

3. Enter a task and press **Enter** or select **Add task**. A date like `12-05` uses the current year. You can also enter `2026-12-05` or `12-05-26`.

Local mode saves to `tasks.sqlite3` in your operating system's application data directory for **Simple To-Do**. Press **Ctrl+F** to search and **F5** to refresh.

## Use Google Sheets

1. Enable the Google Sheets API for your service account's Google Cloud project. Store the service-account JSON key outside the repository.
2. Share the spreadsheet with the service account's email address as an **Editor**. The app uses the spreadsheet's first worksheet.
3. Copy the spreadsheet ID from between `/d/` and `/edit` in its URL. Start the app with your ID and the path to your key.

   ```sh
   .venv/bin/python main.py --sheet-id YOUR_SPREADSHEET_ID --credentials "/path/to/service-account.json"
   ```

   On Windows, use `.\.venv\Scripts\python.exe` and the path to your JSON key.

   To connect by the original spreadsheet name, **ToDoApp**, enable the Google Drive API too and use `--sheets` in place of `--sheet-id YOUR_SPREADSHEET_ID`.

Use a blank worksheet or the original layout with headers in row 1 and task data in columns A–G. Existing notes remain in column C. The app uses columns H and I for links and task IDs on new entries. Keep those two columns available. Legacy rows with identical values need distinct titles or notes before the app can tell them apart. Refresh the app after editing in Sheets and wait for app saves to finish before sorting or moving rows in the sheet.

Local storage and Google Sheets are two separate task lists. Opening the app in Google Sheets mode loads tasks from that spreadsheet.
