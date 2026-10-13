from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from config.settings import (
    load_settings,
    save_settings,
)


class SettingsWindow(QDialog):

    def __init__(
        self,
        parent=None
    ):
        super().__init__(
            parent
        )

        self.setWindowTitle(
            "IMVU Music Bot - Settings"
        )

        self.setMinimumWidth(
            450
        )

        # =====================================================
        # CROWBOT SETTINGS THEME
        # =====================================================

        self.setStyleSheet(
            """
            QDialog {
                background: #f7faf8;
                color: #17211b;
                font-family: "Segoe UI";
                font-size: 14px;
            }

            QLabel {
                color: #26352c;
                background: transparent;
                font-size: 14px;
                font-weight: 600;
            }

            QLineEdit,
            QComboBox {
                min-height: 40px;
                background: #ffffff;
                color: #17211b;
                border: 2px solid #d7e2db;
                border-radius: 9px;
                padding: 0 10px;
                selection-background-color: #16a34a;
                selection-color: #ffffff;
            }

            QLineEdit:focus,
            QComboBox:focus {
                border: 2px solid #16a34a;
            }

            QLineEdit:disabled,
            QComboBox:disabled {
                background: #edf1ef;
                color: #718078;
            }

            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #17211b;
                selection-background-color: #dcfce7;
                selection-color: #166534;
                border: 1px solid #d7e2db;
            }

            QPushButton {
                min-height: 42px;
                border-radius: 9px;
                border: 1px solid #cbd8d0;
                background: #ffffff;
                color: #26352c;
                font-weight: 700;
                padding: 0 16px;
            }

            QPushButton:hover {
                background: #ecf8f0;
                border-color: #16a34a;
            }

            QPushButton:pressed {
                background: #dcfce7;
            }
            """
        )

        settings = load_settings()

        layout = QVBoxLayout(
            self
        )

        # =====================================================
        # TITLE
        # =====================================================

        title = QLabel(
            "Bot Settings"
        )

        title.setStyleSheet(
            """
            color: #15803d;
            font-size: 24px;
            font-weight: 800;
            """
        )

        layout.addWidget(
            title
        )

        # =====================================================
        # FORM
        # =====================================================

        form = QFormLayout()

        # -----------------------------------------------------
        # IMVU BOT USERNAME
        # -----------------------------------------------------

        self.username = QLineEdit()

        self.username.setPlaceholderText(
            "Enter IMVU bot username"
        )

        self.username.setText(
            settings.get(
                "username",
                ""
            )
        )

        # -----------------------------------------------------
        # ROOM ID
        # -----------------------------------------------------

        self.room_id = QLineEdit()

        self.room_id.setPlaceholderText(
            "Enter IMVU Room ID"
        )

        self.room_id.setText(
            settings.get(
                "room_id",
                ""
            )
        )

        # -----------------------------------------------------
        # BOT NAME
        # -----------------------------------------------------

        self.bot_name = QLineEdit()

        self.bot_name.setPlaceholderText(
            "Example: My Music Bot"
        )

        self.bot_name.setText(
            settings.get(
                "bot_name",
                ""
            )
        )

        # -----------------------------------------------------
        # COMMAND PREFIX
        # -----------------------------------------------------

        self.prefix = QLineEdit()

        self.prefix.setText(
            settings.get(
                "prefix",
                "!"
            )
        )

        # -----------------------------------------------------
        # IMVU CLIENT
        # -----------------------------------------------------

        self.imvu_client = QComboBox()

        self.imvu_client.addItems(
            [
                "Auto Detect",
                "IMVU Web (Chrome)",
                "IMVU Desktop",
                "IMVU Classic",
            ]
        )

        saved_client = settings.get(
            "imvu_client",
            "Auto Detect"
        )

        client_index = (
            self.imvu_client.findText(
                saved_client
            )
        )

        if client_index >= 0:
            self.imvu_client.setCurrentIndex(
                client_index
            )
        else:
            self.imvu_client.setCurrentText(
                "Auto Detect"
            )

        # -----------------------------------------------------
        # MUSIC MODE
        # -----------------------------------------------------

        self.music_mode = QComboBox()

        self.music_mode.addItems(
            [
                "Radio Stream",
                "Music Queue",
            ]
        )

        saved_mode = settings.get(
            "music_mode",
            "Radio Stream"
        )

        mode_index = (
            self.music_mode.findText(
                saved_mode
            )
        )

        if mode_index >= 0:
            self.music_mode.setCurrentIndex(
                mode_index
            )

        # =====================================================
        # FORM ROWS
        # =====================================================

        form.addRow(
            "IMVU Bot Username:",
            self.username
        )

        form.addRow(
            "Room ID:",
            self.room_id
        )

        form.addRow(
            "Bot Name:",
            self.bot_name
        )

        form.addRow(
            "Command Prefix:",
            self.prefix
        )

        form.addRow(
            "IMVU Client:",
            self.imvu_client
        )

        form.addRow(
            "Music Mode:",
            self.music_mode
        )

        layout.addLayout(
            form
        )

        # =====================================================
        # BUTTONS
        # =====================================================

        save_button = QPushButton(
            "Save Settings"
        )

        save_button.clicked.connect(
            self.save_settings
        )

        cancel_button = QPushButton(
            "Cancel"
        )

        cancel_button.clicked.connect(
            self.reject
        )

        layout.addWidget(
            save_button
        )

        layout.addWidget(
            cancel_button
        )

    # =========================================================
    # SAVE SETTINGS
    # =========================================================

    def save_settings(self):

        settings = {
            "username": (
                self.username
                .text()
                .strip()
            ),

            "room_id": (
                self.room_id
                .text()
                .strip()
            ),

            "bot_name": (
                self.bot_name
                .text()
                .strip()
            ),

            "prefix": (
                self.prefix
                .text()
                .strip()
                or "!"
            ),

            "imvu_client": (
                self.imvu_client
                .currentText()
            ),

            "music_mode": (
                self.music_mode
                .currentText()
            ),
        }

        save_settings(
            settings
        )

        print(
            "Settings saved successfully."
        )

        print(
            settings
        )

        self.accept()