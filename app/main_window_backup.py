from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.logs_window import LogsWindow
from app.settings_window import SettingsWindow
from app.users_window import UsersWindow

from bot.commands import CommandHandler
from bot.manager import IMVUManager

from config.settings import load_settings

from database.users import UserManager

from music.controller import MusicController
from music.radio import RadioStreamManager


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "IMVU Music Bot"
        )

        self.setMinimumSize(
            1100,
            900
        )

        self.logs = []

        self.settings = load_settings()

        self.user_manager = UserManager()

        self.music_controller = MusicController()

        self.radio_manager = RadioStreamManager()

        self.command_handler = CommandHandler(
            self.music_controller,
            self.user_manager,
            self.settings.get(
                "prefix",
                "!"
            )
        )

        self.imvu_manager = IMVUManager()

        self.create_test_users()

        self.setup_ui()

        self.connect_signals()

        self.refresh_users()

        self.refresh_queue()

        self.update_now_playing(None)

        self.update_imvu_information()

        self.update_connection_buttons()

        self.add_log(
            "Application started."
        )

    # =========================================================
    # UI
    # =========================================================

    def setup_ui(self):

        central_widget = QWidget()

        self.setCentralWidget(
            central_widget
        )

        main_layout = QVBoxLayout(
            central_widget
        )

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        title = QLabel(
            "IMVU Music Bot"
        )

        title.setStyleSheet(
            """
            font-size: 28px;
            font-weight: bold;
            """
        )

        subtitle = QLabel(
            "Music queue, commands, radio streaming and IMVU connection"
        )

        main_layout.addWidget(
            title
        )

        main_layout.addWidget(
            subtitle
        )

        # -----------------------------------------------------
        # IMVU Connection
        # -----------------------------------------------------

        connection_group = QGroupBox(
            "IMVU Connection"
        )

        connection_layout = QVBoxLayout(
            connection_group
        )

        connection_form = QFormLayout()

        self.imvu_username_input = QLineEdit()

        self.imvu_username_input.setPlaceholderText(
            "IMVU bot username"
        )

        self.imvu_room_input = QLineEdit()

        self.imvu_room_input.setPlaceholderText(
            "IMVU room"
        )

        self.imvu_status_label = QLabel(
            "Disconnected"
        )

        connection_form.addRow(
            "Username:",
            self.imvu_username_input
        )

        connection_form.addRow(
            "Room:",
            self.imvu_room_input
        )

        connection_form.addRow(
            "Status:",
            self.imvu_status_label
        )

        connection_layout.addLayout(
            connection_form
        )

        connection_buttons = QHBoxLayout()

        self.connect_button = QPushButton(
            "Connect"
        )

        self.disconnect_button = QPushButton(
            "Disconnect"
        )

        self.connect_button.clicked.connect(
            self.connect_imvu
        )

        self.disconnect_button.clicked.connect(
            self.disconnect_imvu
        )

        connection_buttons.addWidget(
            self.connect_button
        )

        connection_buttons.addWidget(
            self.disconnect_button
        )

        connection_buttons.addStretch()

        connection_layout.addLayout(
            connection_buttons
        )

        main_layout.addWidget(
            connection_group
        )

        # -----------------------------------------------------
        # Radio Stream
        # -----------------------------------------------------

        radio_group = QGroupBox(
            "IMVU Radio Stream"
        )

        radio_layout = QVBoxLayout(
            radio_group
        )

        radio_form = QFormLayout()

        self.radio_url_input = QLineEdit()

        self.radio_url_input.setPlaceholderText(
            "https://example.com/radio.mp3"
        )

        self.radio_status_label = QLabel(
            "Stopped"
        )

        self.radio_current_url_label = QLabel(
            "No stream selected."
        )

        self.radio_current_url_label.setWordWrap(
            True
        )

        radio_form.addRow(
            "Stream URL:",
            self.radio_url_input
        )

        radio_form.addRow(
            "Status:",
            self.radio_status_label
        )

        radio_form.addRow(
            "Current:",
            self.radio_current_url_label
        )

        radio_layout.addLayout(
            radio_form
        )

        radio_buttons = QHBoxLayout()

        self.radio_start_button = QPushButton(
            "Start Radio"
        )

        self.radio_stop_button = QPushButton(
            "Stop Radio"
        )

        self.radio_test_button = QPushButton(
            "Test URL"
        )

        self.radio_start_button.clicked.connect(
            self.start_radio
        )

        self.radio_stop_button.clicked.connect(
            self.stop_radio
        )

        self.radio_test_button.clicked.connect(
            self.test_radio_url
        )

        radio_buttons.addWidget(
            self.radio_start_button
        )

        radio_buttons.addWidget(
            self.radio_stop_button
        )

        radio_buttons.addWidget(
            self.radio_test_button
        )

        radio_buttons.addStretch()

        radio_layout.addLayout(
            radio_buttons
        )

        radio_volume_layout = QHBoxLayout()

        radio_volume_label = QLabel(
            "Radio Volume:"
        )

        self.radio_volume_slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.radio_volume_slider.setMinimum(
            0
        )

        self.radio_volume_slider.setMaximum(
            100
        )

        self.radio_volume_slider.setValue(
            80
        )

        self.radio_volume_slider.valueChanged.connect(
            self.change_radio_volume
        )

        radio_volume_layout.addWidget(
            radio_volume_label
        )

        radio_volume_layout.addWidget(
            self.radio_volume_slider
        )

        radio_layout.addLayout(
            radio_volume_layout
        )

        radio_note = QLabel(
            "Use a direct HTTPS audio stream URL. "
            "The URL must play the audio stream directly."
        )

        radio_note.setWordWrap(
            True
        )

        radio_note.setStyleSheet(
            """
            color: gray;
            """
        )

        radio_layout.addWidget(
            radio_note
        )

        main_layout.addWidget(
            radio_group
        )

        # -----------------------------------------------------
        # Music
        # -----------------------------------------------------

        music_group = QGroupBox(
            "Music"
        )

        music_layout = QVBoxLayout(
            music_group
        )

        now_playing_label = QLabel(
            "Now Playing"
        )

        now_playing_label.setStyleSheet(
            """
            font-weight: bold;
            """
        )

        self.now_playing = QLabel(
            "Nothing is playing."
        )

        self.now_playing.setWordWrap(
            True
        )

        music_layout.addWidget(
            now_playing_label
        )

        music_layout.addWidget(
            self.now_playing
        )

        controls = QHBoxLayout()

        self.play_button = QPushButton(
            "Play"
        )

        self.pause_button = QPushButton(
            "Pause"
        )

        self.resume_button = QPushButton(
            "Resume"
        )

        self.skip_button = QPushButton(
            "Skip"
        )

        self.stop_button = QPushButton(
            "Stop"
        )

        self.play_button.clicked.connect(
            self.play_music
        )

        self.pause_button.clicked.connect(
            self.pause_music
        )

        self.resume_button.clicked.connect(
            self.resume_music
        )

        self.skip_button.clicked.connect(
            self.skip_music
        )

        self.stop_button.clicked.connect(
            self.stop_music
        )

        controls.addWidget(
            self.play_button
        )

        controls.addWidget(
            self.pause_button
        )

        controls.addWidget(
            self.resume_button
        )

        controls.addWidget(
            self.skip_button
        )

        controls.addWidget(
            self.stop_button
        )

        music_layout.addLayout(
            controls
        )

        volume_layout = QHBoxLayout()

        volume_label = QLabel(
            "Volume:"
        )

        self.volume_slider = QSlider(
            Qt.Orientation.Horizontal
        )

        self.volume_slider.setMinimum(
            0
        )

        self.volume_slider.setMaximum(
            100
        )

        self.volume_slider.setValue(
            80
        )

        self.volume_slider.valueChanged.connect(
            self.change_volume
        )

        volume_layout.addWidget(
            volume_label
        )

        volume_layout.addWidget(
            self.volume_slider
        )

        music_layout.addLayout(
            volume_layout
        )

        main_layout.addWidget(
            music_group
        )

        # -----------------------------------------------------
        # Queue
        # -----------------------------------------------------

        queue_group = QGroupBox(
            "Music Queue"
        )

        queue_layout = QVBoxLayout(
            queue_group
        )

        self.queue_list = QListWidget()

        queue_layout.addWidget(
            self.queue_list
        )

        queue_buttons = QHBoxLayout()

        self.remove_button = QPushButton(
            "Remove Selected"
        )

        self.clear_button = QPushButton(
            "Clear Queue"
        )

        self.remove_button.clicked.connect(
            self.remove_selected_song
        )

        self.clear_button.clicked.connect(
            self.clear_queue
        )

        queue_buttons.addWidget(
            self.remove_button
        )

        queue_buttons.addWidget(
            self.clear_button
        )

        queue_buttons.addStretch()

        queue_layout.addLayout(
            queue_buttons
        )

        main_layout.addWidget(
            queue_group
        )

        # -----------------------------------------------------
        # Command Console
        # -----------------------------------------------------

        command_group = QGroupBox(
            "Command Console"
        )

        command_layout = QVBoxLayout(
            command_group
        )

        command_form = QFormLayout()

        self.command_user = QComboBox()

        self.command_input = QLineEdit()

        self.command_input.setPlaceholderText(
            "Example: !help"
        )

        command_form.addRow(
            "User:",
            self.command_user
        )

        command_form.addRow(
            "Command:",
            self.command_input
        )

        command_layout.addLayout(
            command_form
        )

        command_buttons = QHBoxLayout()

        self.execute_button = QPushButton(
            "Execute Command"
        )

        self.clear_console_button = QPushButton(
            "Clear Console"
        )

        self.execute_button.clicked.connect(
            self.execute_command
        )

        self.clear_console_button.clicked.connect(
            self.clear_console
        )

        command_buttons.addWidget(
            self.execute_button
        )

        command_buttons.addWidget(
            self.clear_console_button
        )

        command_buttons.addStretch()

        command_layout.addLayout(
            command_buttons
        )

        self.command_output = QTextEdit()

        self.command_output.setReadOnly(
            True
        )

        command_layout.addWidget(
            self.command_output
        )

        main_layout.addWidget(
            command_group
        )

        # -----------------------------------------------------
        # Bottom Buttons
        # -----------------------------------------------------

        bottom_buttons = QHBoxLayout()

        self.settings_button = QPushButton(
            "Settings"
        )

        self.users_button = QPushButton(
            "Users"
        )

        self.logs_button = QPushButton(
            "Logs"
        )

        self.settings_button.clicked.connect(
            self.open_settings
        )

        self.users_button.clicked.connect(
            self.open_users
        )

        self.logs_button.clicked.connect(
            self.open_logs
        )

        bottom_buttons.addWidget(
            self.settings_button
        )

        bottom_buttons.addWidget(
            self.users_button
        )

        bottom_buttons.addWidget(
            self.logs_button
        )

        bottom_buttons.addStretch()

        main_layout.addLayout(
            bottom_buttons
        )

    # =========================================================
    # Signals
    # =========================================================

    def connect_signals(self):

        self.music_controller.now_playing_changed.connect(
            self.update_now_playing
        )

        self.music_controller.queue_changed.connect(
            self.refresh_queue
        )

        self.music_controller.status_changed.connect(
            self.handle_music_status
        )

        self.music_controller.error_occurred.connect(
            self.handle_error
        )

        self.radio_manager.stream_started.connect(
            self.handle_radio_started
        )

        self.radio_manager.stream_stopped.connect(
            self.handle_radio_stopped
        )

        self.radio_manager.status_changed.connect(
            self.handle_radio_status
        )

        self.radio_manager.stream_error.connect(
            self.handle_radio_error
        )

        self.imvu_manager.connection_changed.connect(
            self.handle_connection_changed
        )

        self.imvu_manager.connection_error.connect(
            self.handle_imvu_error
        )

        self.imvu_manager.chat_received.connect(
            self.handle_imvu_chat
        )

        self.imvu_manager.status_changed.connect(
            self.handle_imvu_status
        )

    # =========================================================
    # Test Users
    # =========================================================

    def create_test_users(self):

        if self.user_manager.get_user(
            "TestUser"
        ) is None:

            self.user_manager.add_user(
                "TestUser",
                "User"
            )

        if self.user_manager.get_user(
            "TestDJ"
        ) is None:

            self.user_manager.add_user(
                "TestDJ",
                "DJ"
            )

        if self.user_manager.get_user(
            "TestModerator"
        ) is None:

            self.user_manager.add_user(
                "TestModerator",
                "Moderator"
            )

        if self.user_manager.get_user(
            "TestOwner"
        ) is None:

            self.user_manager.add_user(
                "TestOwner",
                "Owner"
            )

    # =========================================================
    # IMVU
    # =========================================================

    def update_imvu_information(self):

        settings = load_settings()

        self.imvu_username_input.setText(
            settings.get(
                "username",
                ""
            )
        )

        self.imvu_room_input.setText(
            settings.get(
                "room",
                ""
            )
        )

        self.imvu_manager.configure(
            settings.get(
                "username",
                ""
            ),
            settings.get(
                "room",
                ""
            )
        )

    def connect_imvu(self):

        username = (
            self.imvu_username_input
            .text()
            .strip()
        )

        room = (
            self.imvu_room_input
            .text()
            .strip()
        )

        self.imvu_manager.configure(
            username,
            room
        )

        self.add_log(
            f"IMVU connection requested for "
            f"{username} in room {room}."
        )

        self.imvu_manager.connect_bot()

        self.update_connection_buttons()

    def disconnect_imvu(self):

        self.imvu_manager.disconnect()

        self.add_log(
            "IMVU disconnected."
        )

        self.update_connection_buttons()

    def update_connection_buttons(self):

        connected = (
            self.imvu_manager.is_connected()
        )

        self.connect_button.setEnabled(
            not connected
        )

        self.disconnect_button.setEnabled(
            connected
        )

    def handle_connection_changed(
        self,
        connected,
        status
    ):

        self.imvu_status_label.setText(
            status
        )

        self.update_connection_buttons()

        self.add_log(
            f"IMVU connection status: "
            f"{status}"
        )

    def handle_imvu_status(
        self,
        status
    ):

        self.imvu_status_label.setText(
            status
        )

        self.add_log(
            f"IMVU status: {status}"
        )

        self.update_connection_buttons()

    def handle_imvu_error(
        self,
        message
    ):

        self.imvu_status_label.setText(
            "Error"
        )

        self.add_log(
            f"IMVU error: {message}"
        )

        self.update_connection_buttons()

    # =========================================================
    # IMVU Chat Bridge
    # =========================================================

    def handle_imvu_chat(
        self,
        username,
        message
    ):

        if not username or not message:
            return

        self.command_output.append(
            f"[IMVU] {username}: {message}"
        )

        self.add_log(
            f"[IMVU] {username}: {message}"
        )

        response = (
            self.command_handler.handle(
                message,
                username
            )
        )

        if response is None:
            return

        self.command_output.append(
            f"[BOT] {response}"
        )

        self.command_output.append(
            ""
        )

        self.add_log(
            f"[BOT] {response}"
        )

        sent = (
            self.imvu_manager.send_message(
                response
            )
        )

        if sent:

            self.add_log(
                "Bot response sent to IMVU."
            )

        else:

            self.add_log(
                "Bot response could not be sent "
                "because IMVU is not connected."
            )

    # =========================================================
    # Radio Stream
    # =========================================================

    def start_radio(self):

        url = (
            self.radio_url_input
            .text()
            .strip()
        )

        if not url:

            self.add_log(
                "Radio start failed: URL is empty."
            )

            self.radio_status_label.setText(
                "URL required"
            )

            return

        if not self.radio_manager.is_valid_url(
            url
        ):

            self.radio_status_label.setText(
                "Invalid URL"
            )

            self.add_log(
                "Radio start failed: invalid URL."
            )

            return

        started = (
            self.radio_manager.start(
                url
            )
        )

        if started:

            self.radio_current_url_label.setText(
                url
            )

            self.add_log(
                f"Radio stream started: {url}"
            )

    def stop_radio(self):

        self.radio_manager.stop()

        self.add_log(
            "Radio stream stopped."
        )

    def test_radio_url(self):

        url = (
            self.radio_url_input
            .text()
            .strip()
        )

        if not url:

            self.radio_status_label.setText(
                "URL required"
            )

            return

        if self.radio_manager.is_valid_url(
            url
        ):

            self.radio_status_label.setText(
                "Valid URL"
            )

            self.add_log(
                f"Radio URL validated: {url}"
            )

        else:

            self.radio_status_label.setText(
                "Invalid URL"
            )

            self.add_log(
                f"Invalid radio URL: {url}"
            )

    def change_radio_volume(
        self,
        value
    ):

        volume = value / 100.0

        self.radio_manager.set_volume(
            volume
        )

    def handle_radio_started(
        self,
        url
    ):

        self.radio_status_label.setText(
            "Playing"
        )

        self.radio_current_url_label.setText(
            url
        )

    def handle_radio_stopped(self):

        self.radio_status_label.setText(
            "Stopped"
        )

    def handle_radio_status(
        self,
        status
    ):

        self.radio_status_label.setText(
            status
        )

        self.add_log(
            f"Radio: {status}"
        )

    def handle_radio_error(
        self,
        message
    ):

        self.radio_status_label.setText(
            "Error"
        )

        self.add_log(
            f"Radio error: {message}"
        )

    # =========================================================
    # Command Console
    # =========================================================

    def execute_command(self):

        message = (
            self.command_input
            .text()
            .strip()
        )

        if not message:
            return

        username = (
            self.command_user
            .currentData()
        )

        if not username:
            username = "TestOwner"

        self.command_output.append(
            f"[{username}] {message}"
        )

        self.add_log(
            f"[CONSOLE] {username}: {message}"
        )

        response = (
            self.command_handler.handle(
                message,
                username
            )
        )

        if response is None:

            self.command_output.append(
                "Not a command."
            )

            return

        self.command_output.append(
            response
        )

        self.command_output.append(
            ""
        )

        self.add_log(
            f"[COMMAND] {response}"
        )

        self.command_input.clear()

    def clear_console(self):

        self.command_output.clear()

    # =========================================================
    # Users
    # =========================================================

    def refresh_users(self):

        current_username = (
            self.command_user
            .currentData()
        )

        self.command_user.clear()

        users = (
            self.user_manager.get_users()
        )

        for user in users:

            username = user["username"]
            role = user["role"]

            item_text = (
                f"{username} ({role})"
            )

            self.command_user.addItem(
                item_text,
                username
            )

        if current_username:

            index = (
                self.command_user
                .findData(
                    current_username
                )
            )

            if index >= 0:

                self.command_user.setCurrentIndex(
                    index
                )

        if self.command_user.count() == 0:

            self.command_user.addItem(
                "TestOwner (Owner)",
                "TestOwner"
            )

    # =========================================================
    # Music Controls
    # =========================================================

    def play_music(self):

        if self.music_controller.play():

            self.add_log(
                "Play/resume requested."
            )

        else:

            self.add_log(
                "Nothing available to play."
            )

    def pause_music(self):

        if self.music_controller.pause():

            self.add_log(
                "Pause requested."
            )

    def resume_music(self):

        if self.music_controller.resume():

            self.add_log(
                "Resume requested."
            )

    def skip_music(self):

        if self.music_controller.skip():

            self.add_log(
                "Skip requested."
            )

    def stop_music(self):

        self.music_controller.stop()

        self.add_log(
            "Music stopped."
        )

    def change_volume(
        self,
        value
    ):

        volume = value / 100.0

        self.music_controller.set_volume(
            volume
        )

    # =========================================================
    # Queue
    # =========================================================

    def refresh_queue(self):

        self.queue_list.clear()

        queue = (
            self.music_controller.get_queue()
        )

        if not queue:

            self.queue_list.addItem(
                "Queue is empty."
            )

            return

        for number, song in enumerate(
            queue,
            start=1
        ):

            title = song.get(
                "title",
                "Unknown"
            )

            requester = song.get(
                "requested_by",
                "Unknown"
            )

            item = QListWidgetItem(
                f"{number}. {title} "
                f"(requested by {requester})"
            )

            self.queue_list.addItem(
                item
            )

    def remove_selected_song(self):

        selected = (
            self.queue_list
            .currentRow()
        )

        if selected < 0:
            return

        queue = (
            self.music_controller.get_queue()
        )

        if not queue:
            return

        if selected >= len(queue):
            return

        song = (
            self.music_controller
            .remove_song(selected)
        )

        if song:

            title = song.get(
                "title",
                "Unknown"
            )

            self.add_log(
                f"Removed from queue: {title}"
            )

    def clear_queue(self):

        self.music_controller.clear_queue()

        self.add_log(
            "Queue cleared."
        )

    # =========================================================
    # Now Playing
    # =========================================================

    def update_now_playing(
        self,
        song
    ):

        if not song:

            self.now_playing.setText(
                "Nothing is playing."
            )

            return

        title = song.get(
            "title",
            "Unknown"
        )

        requester = song.get(
            "requested_by",
            "Unknown"
        )

        self.now_playing.setText(
            f"{title} "
            f"(requested by {requester})"
        )

    # =========================================================
    # Status / Errors
    # =========================================================

    def handle_music_status(
        self,
        status
    ):

        self.add_log(
            f"Music: {status}"
        )

    def handle_error(
        self,
        message
    ):

        self.add_log(
            f"Error: {message}"
        )

    # =========================================================
    # Settings
    # =========================================================

    def open_settings(self):

        dialog = SettingsWindow(
            self
        )

        result = dialog.exec()

        if result:

            self.settings = load_settings()

            self.command_handler.set_prefix(
                self.settings.get(
                    "prefix",
                    "!"
                )
            )

            self.update_imvu_information()

            self.add_log(
                "Settings updated."
            )

    # =========================================================
    # Users Window
    # =========================================================

    def open_users(self):

        dialog = UsersWindow(
            self.user_manager,
            self
        )

        dialog.users_changed.connect(
            self.refresh_users
        )

        dialog.exec()

        self.refresh_users()

    # =========================================================
    # Logs Window
    # =========================================================

    def open_logs(self):

        dialog = LogsWindow(
            self.logs,
            self
        )

        dialog.exec()

    # =========================================================
    # Logging
    # =========================================================

    def add_log(
        self,
        message
    ):

        if not message:
            return

        self.logs.append(
            str(message)
        )

        if len(self.logs) > 1000:

            self.logs = self.logs[-1000:]