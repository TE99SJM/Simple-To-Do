import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    due: str
    notes: str
    link: str
    added: str
    completed: str = ""
    archived: bool = False
    sheet_values: tuple[str, ...] = ()

    @classmethod
    def new(cls, title, due, notes, link):
        return cls(uuid4().hex, title, due, notes, link, timestamp())


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_due(value, today=None):
    value = value.strip()
    if not value:
        return None

    today = today or date.today()
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    for separator in ("-", "/"):
        parts = value.split(separator)
        if len(parts) == 2 and all(part.isdecimal() for part in parts):
            month, day = map(int, parts)
            try:
                return date(today.year, month, day)
            except ValueError:
                break

    raise ValueError("Enter a valid due date, such as 12-05 or 2026-12-05.")


def task_due(task):
    try:
        return parse_due(task.due)
    except ValueError:
        return None


class LocalTasks:
    def __init__(self, path: Path):
        self.path = path

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, due TEXT NOT NULL,
                notes TEXT NOT NULL, link TEXT NOT NULL, added TEXT NOT NULL,
                completed TEXT NOT NULL, archived INTEGER NOT NULL
            )
            """
        )
        return connection

    def load(self):
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT id, title, due, notes, link, added, completed, archived FROM tasks"
            )
            return [Task(*row[:-1], archived=bool(row[-1])) for row in rows]

    def add(self, task):
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (task.id, task.title, task.due, task.notes, task.link,
                 task.added, task.completed, task.archived),
            )
        return task

    def update(self, original, revised):
        with closing(self.connect()) as connection, connection:
            result = connection.execute(
                """
                UPDATE tasks
                SET title = ?, due = ?, notes = ?, link = ?, completed = ?, archived = ?
                WHERE id = ? AND title = ? AND due = ? AND notes = ? AND link = ?
                    AND completed = ? AND archived = ?
                """,
                (revised.title, revised.due, revised.notes, revised.link, revised.completed,
                 revised.archived, original.id, original.title, original.due, original.notes,
                 original.link, original.completed, original.archived),
            )
            if result.rowcount == 0:
                raise ValueError("This task changed. Refresh the list and try again.")
        return revised
