from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class LogsWindow(QDialog):

    def __init__(self, logs=None, parent=None):

        super().__init__(parent)

        self.setWindowTitle(
            "IMVU Music Bot - Logs"
        )

        self.setMinimumSize(
            750,
            500
        )

        self.logs = logs if logs is not None else []

        # ==========================
        # Main Layout
        # ==========================

        layout = QVBoxLayout(self)

        # ==========================
        # Title
        # ==========================

        title = QLabel(
            "Bot Logs"
        )

        title.setStyleSheet(
            """
            font-size: 24px;
            font-weight: bold;
            """
        )

        layout.addWidget(title)

        # ==========================
        # Log Output
        # ==========================

        self.log_output = QTextEdit()

        self.log_output.setReadOnly(
            True
        )

        layout.addWidget(
            self.log_output
        )

        # ==========================
        # Buttons
        # ==========================

        buttons = QHBoxLayout()

        refresh_button = QPushButton(
            "Refresh"
        )

        clear_button = QPushButton(
            "Clear"
        )

        close_button = QPushButton(
            "Close"
        )

        buttons.addWidget(
            refresh_button
        )

        buttons.addWidget(
            clear_button
        )

        buttons.addStretch()

        buttons.addWidget(
            close_button
        )

        layout.addLayout(
            buttons
        )

        # ==========================
        # Connections
        # ==========================

        refresh_button.clicked.connect(
            self.refresh_logs
        )

        clear_button.clicked.connect(
            self.clear_logs
        )

        close_button.clicked.connect(
            self.accept
        )

        # ==========================
        # Initial Display
        # ==========================

        self.refresh_logs()

    # ==========================
    # Refresh Logs
    # ==========================

    def refresh_logs(self):

        self.log_output.clear()

        for entry in self.logs:

            self.log_output.append(
                entry
            )

    # ==========================
    # Clear Logs
    # ==========================

    def clear_logs(self):

        self.logs.clear()

        self.log_output.clear()