from dataclasses import replace
from datetime import date
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QKeySequence
from PyQt5.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPlainTextEdit, QPushButton, QScrollArea, QShortcut,
    QSizePolicy, QVBoxLayout, QWidget,
)

from tasks import Task, parse_due, task_due, timestamp
from workers import TaskWorker


VIEWS = ("Open", "Completed", "Archived", "All tasks")
STYLE = """
QMainWindow { background: #f4f5ef; }
QWidget { color: #1d3128; font-size: 14px; }
QFrame[panel="true"] { background: #fff; border: 1px solid #d9e1d8; border-radius: 14px; }
QLabel#appTitle { color: #173a2b; font-size: 34px; font-weight: 700; }
QLabel#heading { font-size: 20px; font-weight: 700; }
QLabel#taskTitle { font-size: 16px; font-weight: 650; }
QLabel#muted { color: #51685a; }
QLabel#feedback { color: #365647; }
QLabel#feedback[error="true"] { color: #9b3026; }
QLabel#due { color: #315e4b; background: #eaf2eb; border-radius: 7px; padding: 4px 8px; }
QLabel#due[overdue="true"] { color: #923027; background: #f9e9e5; }
QLineEdit, QPlainTextEdit {
    color: #1d3128; background: #fafcf9; border: 1px solid #c6d3c7;
    border-radius: 8px; padding: 7px 10px; selection-background-color: #29624b;
}
QLineEdit:focus, QPlainTextEdit:focus { border-color: #2a7959; }
QPushButton {
    color: #244638; background: #f6f9f5; border: 1px solid #cfdbd0;
    border-radius: 8px; padding: 7px 11px; min-height: 20px;
}
QPushButton:hover { background: #e7f0e7; }
QPushButton:focus { border-color: #2a7959; }
QPushButton:disabled { color: #52675b; background: #eef1ec; }
QPushButton#primary, QPushButton[view="true"]:checked {
    color: #fff; background: #20593f; border-color: #20593f; font-weight: 600;
}
QPushButton#primary:hover, QPushButton[view="true"]:checked:hover { background: #164632; }
QPushButton#primary:focus, QPushButton[view="true"]:checked:focus { border: 2px solid #60b995; }
QPushButton#primary:disabled { color: #475d50; background: #e5eee5; border-color: #cfdbd0; }
QScrollArea { border: 0; }
QWidget#taskContainer { background: #f4f5ef; }
"""


def label(text, style="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.PlainText)
    widget.setObjectName(style)
    widget.setWordWrap(wrap)
    if wrap:
        widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    return widget


def panel():
    widget = QFrame()
    widget.setProperty("panel", True)
    return widget


class ToDoListApp(QMainWindow):
    def __init__(self, store, storage_label):
        super().__init__()
        self.store = store
        self.tasks = {}
        self.view = "Open"
        self.editing = None
        self.pending_add = None
        self.worker = None
        self.loaded = False

        self.setWindowTitle("Simple To-Do")
        self.resize(950, 760)
        self.setMinimumSize(640, 540)
        self.setStyleSheet(STYLE)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 18, 24, 14)
        layout.setSpacing(12)
        self.setCentralWidget(body)

        header = QHBoxLayout()
        heading = label("Simple To-Do", "appTitle")
        header.addWidget(heading, 1)
        header.addWidget(label(storage_label, "muted"))
        self.refresh = QPushButton("Refresh")
        self.refresh.clicked.connect(self.reload)
        header.addWidget(self.refresh)
        layout.addLayout(header)

        composer = panel()
        layout.addWidget(composer)
        self.build_composer(composer)

        toolbar = QHBoxLayout()
        self.views = QButtonGroup(self)
        for name in VIEWS:
            button = QPushButton(name)
            button.setCheckable(True)
            button.setProperty("view", True)
            button.setChecked(name == self.view)
            button.clicked.connect(lambda checked, selected=name: self.select_view(selected))
            self.views.addButton(button)
            toolbar.addWidget(button)
        toolbar.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tasks")
        self.search.setAccessibleName("Search tasks")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.render_tasks)
        toolbar.addWidget(self.search, 1)
        layout.addLayout(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_container = QWidget()
        self.task_container.setObjectName("taskContainer")
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(8)
        self.task_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.task_container)
        layout.addWidget(self.scroll, 1)

        self.feedback = label("", "feedback", wrap=True)
        layout.addWidget(self.feedback)
        QShortcut(QKeySequence.Find, self, activated=self.search.setFocus)
        QShortcut(QKeySequence.Refresh, self, activated=self.reload)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.focus_title)

        self.reload()
        self.title_input.setFocus()

    def build_composer(self, composer):
        editor = QGridLayout(composer)
        editor.setContentsMargins(15, 10, 15, 12)
        editor.setHorizontalSpacing(12)
        editor.setVerticalSpacing(5)
        editor.setColumnStretch(0, 3)
        editor.setColumnStretch(1, 2)

        self.editor_heading = label("New task", "heading")
        editor.addWidget(self.editor_heading, 0, 0, 1, 2)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("What needs to get done?")
        self.due_input = QLineEdit()
        self.due_input.setPlaceholderText("MM-DD or YYYY-MM-DD")
        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Add details")
        self.notes_input.setFixedHeight(56)
        self.notes_input.setTabChangesFocus(True)
        self.link_input = QLineEdit()
        self.link_input.setPlaceholderText("Web address or file path")

        for name, widget, row, column in (
            ("Task", self.title_input, 1, 0),
            ("Due date", self.due_input, 1, 1),
            ("Notes", self.notes_input, 3, 0),
            ("Link", self.link_input, 3, 1),
        ):
            widget.setAccessibleName(name)
            editor.addWidget(label(name, "muted"), row, column)
            editor.addWidget(widget, row + 1, column, alignment=Qt.AlignTop)

        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel = QPushButton("Cancel edit")
        self.cancel.clicked.connect(self.clear_editor)
        self.cancel.hide()
        self.save = QPushButton("Add task")
        self.save.setObjectName("primary")
        self.save.clicked.connect(self.submit)
        actions.addWidget(self.cancel)
        actions.addWidget(self.save)
        editor.addLayout(actions, 5, 0, 1, 2)

        for entry in (self.title_input, self.due_input, self.link_input):
            entry.returnPressed.connect(self.submit)

    def focus_title(self):
        if self.editing is None:
            self.title_input.setFocus()

    def show_feedback(self, text, error=False):
        self.feedback.setText(text)
        self.feedback.setProperty("error", error)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

    def run_job(self, action, on_success, status):
        if self.worker is not None:
            return
        self.show_feedback(status)
        self.worker = TaskWorker(action, self)
        self.worker.finished.connect(lambda: self.job_finished(on_success))
        self.set_busy(True)
        self.worker.start()

    def set_busy(self, busy):
        for field in (self.title_input, self.due_input, self.notes_input, self.link_input):
            field.setReadOnly(busy)
        for control in (self.save, self.cancel, self.refresh, self.task_container):
            control.setEnabled(not busy)
        self.save.setEnabled(self.loaded and not busy)

    def job_finished(self, on_success):
        worker = self.worker
        self.worker = None
        self.set_busy(False)

        if worker.error is None:
            on_success(worker.result)
        else:
            self.show_feedback(worker.error, error=True)
        worker.deleteLater()

    def reload(self):
        self.run_job(self.store.load, self.apply_loaded_tasks, "Loading tasks…")

    def apply_loaded_tasks(self, tasks):
        self.loaded = True
        self.tasks = {task.id: task for task in tasks}
        self.set_busy(False)
        self.render_tasks()
        if self.editing and self.tasks.get(self.editing.id) != self.editing:
            self.show_feedback("The task you were editing changed. Cancel the edit and reopen the task.", True)
        else:
            self.show_feedback("Tasks loaded.")

    def select_view(self, name):
        self.view = name
        self.scroll.verticalScrollBar().setValue(0)
        self.render_tasks()

    def render_tasks(self):
        while self.task_layout.count():
            self.task_layout.takeAt(0).widget().deleteLater()

        active = [task for task in self.tasks.values() if not task.archived]
        groups = {
            "Open": [task for task in active if not task.completed],
            "Completed": [task for task in active if task.completed],
            "Archived": [task for task in self.tasks.values() if task.archived],
            "All tasks": list(self.tasks.values()),
        }
        for name, button in zip(VIEWS, self.views.buttons()):
            button.setText(f"{name}  {len(groups[name])}")

        query = self.search.text().strip().casefold()
        today = date.today()
        matches = (task for task in groups[self.view] if query in
                   " ".join((task.title, task.notes, task.link, task.due)).casefold())
        sorted_tasks = sorted(
            matches,
            key=lambda task: (task.archived, bool(task.completed), task_due(task) or date.max,
                              task.title.casefold(), task.added),
        )
        for task in sorted_tasks:
            self.task_layout.addWidget(self.task_card(task, today))

        if not sorted_tasks and self.loaded:
            message = "No tasks match your search." if query else {
                "Open": "No open tasks. Add a task above to get started.",
                "Completed": "No completed tasks yet.",
                "Archived": "No archived tasks yet.",
                "All tasks": "No tasks yet.",
            }[self.view]
            empty = label(message, "muted", wrap=True)
            empty.setAlignment(Qt.AlignCenter)
            empty.setMinimumHeight(80)
            self.task_layout.addWidget(empty)

    def task_card(self, task, today):
        card = panel()
        outer = QVBoxLayout(card)
        outer.setContentsMargins(13, 8, 13, 8)
        outer.setSpacing(4)

        row = QHBoxLayout()
        outer.addLayout(row)
        title = label(task.title, "taskTitle", wrap=True)
        if task.completed:
            font = title.font()
            font.setStrikeOut(True)
            title.setFont(font)
        row.addWidget(title, 1)

        due = task_due(task)
        if task.due:
            overdue = bool(due and due < today and not task.completed and not task.archived)
            due_label = label(due.strftime("%b %d, %Y") if due else task.due, "due")
            due_label.setProperty("overdue", overdue)
            due_label.setToolTip("Overdue" if overdue else "Due date")
            row.addWidget(due_label)

        if task.link:
            self.add_action(row, "Open link", lambda: self.open_link(task.link), task)
        if task.archived:
            self.add_action(row, "Restore", lambda: self.set_archived(task), task)
        else:
            self.add_action(row, "Edit", lambda: self.edit_task(task), task)
            self.add_action(row, "Reopen" if task.completed else "Complete",
                            lambda: self.set_completed(task), task)
            self.add_action(row, "Archive", lambda: self.set_archived(task), task)

        if task.archived or task.completed:
            status = "Archived" if task.archived else "Completed"
            outer.addWidget(label(status, "muted"))
        if task.notes:
            notes = label(task.notes, "muted", wrap=True)
            notes.setTextInteractionFlags(Qt.TextSelectableByMouse)
            outer.addWidget(notes)
        return card

    @staticmethod
    def add_action(layout, name, action, task):
        button = QPushButton(name)
        button.setAccessibleName(f"{name} for {task.title}")
        button.clicked.connect(action)
        layout.addWidget(button)

    def open_link(self, link):
        url = QUrl(link)
        if url.scheme().lower() not in ("https", "http"):
            path = Path(link).expanduser()
            if not path.exists():
                self.show_feedback("This link is neither a web address nor an existing path.", True)
                return
            url = QUrl.fromLocalFile(str(path.absolute()))
        if not QDesktopServices.openUrl(url):
            self.show_feedback("Could not open the link on this device.", True)

    def edit_task(self, task):
        self.editing = task
        self.editor_heading.setText("Edit task")
        self.title_input.setText(task.title)
        self.due_input.setText(task.due)
        self.notes_input.setPlainText(task.notes)
        self.link_input.setText(task.link)
        self.save.setText("Save changes")
        self.cancel.show()
        self.title_input.setFocus()
        self.title_input.selectAll()

    def clear_editor(self):
        self.editing = None
        for field in (self.title_input, self.due_input, self.notes_input, self.link_input):
            field.clear()
        self.cancel.hide()
        self.editor_heading.setText("New task")
        self.save.setText("Add task")
        self.title_input.setFocus()

    def submit(self):
        if self.worker is not None or not self.loaded:
            return
        title = self.title_input.text().strip()
        if not title:
            self.show_feedback("Enter a task title.", True)
            self.title_input.setFocus()
            return

        due_text = self.due_input.text().strip()
        original = self.editing
        due = original.due if original and due_text == original.due else ""
        if due_text != due:
            try:
                parsed = parse_due(due_text)
                due = parsed.isoformat() if parsed else ""
            except ValueError as error:
                self.show_feedback(str(error), True)
                self.due_input.setFocus()
                return

        notes = self.notes_input.toPlainText().strip()
        link = self.link_input.text().strip()
        if original:
            revised = replace(original, title=title, due=due, notes=notes, link=link)
            self.save_task(original, revised, "Changes saved.", clear_editor=True)
        else:
            draft = (title, due, notes, link)
            task = self.pending_add
            if task is None or draft != (task.title, task.due, task.notes, task.link):
                task = Task.new(*draft)
                self.pending_add = task
            self.run_job(lambda: self.store.add(task), self.task_added, "Adding task…")

    def task_added(self, task):
        self.pending_add = None
        self.clear_editor()
        self.views.buttons()[0].setChecked(True)
        self.search.clear()
        self.select_view("Open")
        self.apply_change(task, "Task added.")

    def apply_change(self, task, message):
        self.tasks[task.id] = task
        self.render_tasks()
        self.show_feedback(message)

    def save_task(self, original, revised, message, clear_editor=False):
        def on_success(task):
            if clear_editor:
                self.clear_editor()
            elif self.editing == original:
                self.editing = task
            self.apply_change(task, message)

        self.run_job(lambda: self.store.update(original, revised), on_success, "Saving task…")

    def set_completed(self, task):
        completed = "" if task.completed else timestamp()
        self.save_task(task, replace(task, completed=completed),
                       "Task completed." if completed else "Task reopened.")

    def set_archived(self, task):
        self.save_task(task, replace(task, archived=not task.archived),
                       "Task restored." if task.archived else "Task archived.")

    def closeEvent(self, event):
        if self.worker is not None:
            self.show_feedback("Wait for the current storage operation to finish.")
            event.ignore()
        else:
            super().closeEvent(event)
