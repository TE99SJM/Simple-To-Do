from PyQt5.QtCore import QThread


class TaskWorker(QThread):
    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.action()
        except Exception as error:
            self.error = str(error) or type(error).__name__
