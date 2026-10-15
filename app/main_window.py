from PySide6.QtCore import QTimer
import os
import socket
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal







from PySide6.QtGui import QGuiApplication







from PySide6.QtWidgets import (







    QGroupBox,







    QHBoxLayout,







    QLabel,







    QLineEdit,







    QListWidget,







    QMainWindow,







    QMessageBox,







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



from bot.imvu_client_detector import IMVUClientDetector



from bot.imvu_web_controller import IMVUWebController















from config.settings import load_settings















from database.users import UserManager















from music.controller import MusicController







from music.radio import RadioStreamManager















from radio_server.server import RadioStreamServer







from radio_server.cloudflare import CloudflareTunnel
























class IMVURadioUpdateWorker(QThread):







    succeeded = Signal(str, str)



    failed = Signal(str)







    def __init__(self, stream_url, parent=None):



        super().__init__(parent)



        self.stream_url = stream_url







    def run(self):



        controller = IMVUWebController()







        try:



            print("IMVU: Connecting to Chrome on port 9222...")



            controller.connect()







            page = controller.find_imvu_room()



            if not page:



                raise RuntimeError(



                    "No IMVU room tab was found in the bot Chrome session."



                )







            print(f"IMVU: Room found: {controller.get_room_url()}")







            print(
                "IMVU: Ensuring Radio Streaming is enabled..."
            )

            controller.ensure_radio_streaming_on(
                timeout_ms=15000
            )

            print(
                "IMVU: Radio Streaming is ON and controls are ready."
            )







            previous_url = controller.get_current_stream_url()



            print(f"IMVU: Previous stream URL: {previous_url or '(empty)'}")



            print(f"IMVU: Loading new stream URL: {self.stream_url}")







            result = controller.load_stream(self.stream_url)







            if not result.get("loaded"):



                raise RuntimeError("IMVU did not confirm the LOAD action.")







            print("IMVU: Stream URL entered and LOAD clicked.")



            self.succeeded.emit(self.stream_url, previous_url)







        except Exception as error:



            print(f"IMVU RADIO UPDATE ERROR: {error}")



            self.failed.emit(str(error))







        finally:



            controller.disconnect()











class IMVUJoinWorker(QThread):



    succeeded = Signal(str, bool)



    failed = Signal(str)







    def __init__(self, parent=None):



        super().__init__(parent)







    def run(self):



        import time



        last_error = None







        # Give the newly opened IMVU room time to appear in Chrome.



        for _ in range(15):



            controller = IMVUWebController()







            try:



                controller.connect()







                page = controller.find_imvu_room()



                if not page:



                    last_error = RuntimeError(



                        "No IMVU room tab was found in the dedicated bot Chrome session."



                    )



                    time.sleep(1)



                    continue







                result = controller.ensure_joined(timeout_ms=30000)







                self.succeeded.emit(



                    controller.get_room_url(),



                    bool(result.get("clicked"))



                )



                return







            except Exception as error:



                last_error = error







            finally:



                controller.disconnect()







            time.sleep(1)







        self.failed.emit(



            str(last_error or "Unable to join the IMVU room automatically.")



        )











class IMVUChatWorker(QThread):

    """Long-lived live IMVU room chat listener."""



    message_received = Signal(str, str)

    started_listening = Signal(int)

    failed = Signal(str)



    def __init__(self, parent=None):

        super().__init__(parent)

        self._stop_requested = False



    def stop(self):

        self._stop_requested = True



    def run(self):

        controller = IMVUWebController()



        try:

            print("IMVU CHAT: Connecting to Chrome on port 9222...")

            controller.connect()



            page = controller.find_imvu_room()

            if not page:

                raise RuntimeError(

                    "No IMVU room tab was found in the dedicated bot Chrome session."

                )



            controller.ensure_joined(timeout_ms=30000)

            existing_count = controller.prime_chat_listener()

            self.started_listening.emit(existing_count)



            while not self._stop_requested:

                messages = controller.wait_for_new_chat_messages(
                    timeout_ms=500,
                    poll_interval_ms=100,
                )



                for message in messages:

                    if self._stop_requested:

                        break

                    username = (message.get("username") or "").strip()

                    chat_text = (message.get("message") or "").strip()

                    if username and chat_text:

                        self.message_received.emit(username, chat_text)



        except Exception as error:

            if not self._stop_requested:

                print(f"IMVU CHAT LISTENER ERROR: {error}")

                self.failed.emit(str(error))

        finally:

            controller.disconnect()





class SecondaryRoomWorker(QThread):
    """Room-specific monitor. No shared games or music state yet."""
    message_received = Signal(str, str, str)
    failed = Signal(str, str)
    ready = Signal(str)

    def __init__(self, room_url, parent=None):
        super().__init__(parent)
        self.room_url = room_url
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        controller = IMVUWebController()
        try:
            controller.connect()
            if not controller.find_imvu_room(self.room_url):
                raise RuntimeError("Room tab is no longer open")
            controller.ensure_joined(timeout_ms=30000)
            controller.prime_chat_listener()
            self.ready.emit(self.room_url)
            while not self._stop_requested:
                for event in controller.wait_for_new_chat_messages(timeout_ms=400):
                    if self._stop_requested:
                        break
                    self.message_received.emit(
                        self.room_url,
                        (event.get("username") or "").strip(),
                        (event.get("message") or "").strip(),
                    )
        except Exception as error:
            self.failed.emit(self.room_url, str(error))
        finally:
            controller.disconnect()


class IMVUChatSendWorker(QThread):
    """Send one generated bot response into the active IMVU Web room."""

    succeeded = Signal(str)
    failed = Signal(str, str)

    def __init__(self, message, parent=None, room_url=None):
        super().__init__(parent)
        self.message = str(message or "").strip()
        self.room_url = room_url

    def run(self):
        controller = IMVUWebController()

        try:
            if not self.message:
                raise ValueError("Cannot send an empty IMVU chat message.")

            print("IMVU CHAT SEND: Connecting to Chrome on port 9222...")
            controller.connect()

            page = controller.find_imvu_room(self.room_url)
            if not page:
                raise RuntimeError(
                    "Requested IMVU room tab was not found."
                )

            controller.ensure_joined(timeout_ms=30000)
            controller.send_chat_message(self.message)

            print(f"IMVU CHAT SEND: {self.message}")
            self.succeeded.emit(self.message)

        except Exception as error:
            print(f"IMVU CHAT SEND ERROR: {error}")
            self.failed.emit(self.message, str(error))

        finally:
            controller.disconnect()


class MainWindow(QMainWindow):















    def __init__(self):







        super().__init__()















        self.setWindowTitle("IMVU Music Bot")







        self.setMinimumSize(1100, 900)















        self.settings = load_settings()







        self.logs = []

        # Users welcomed during this CrowBot application session.
        self._welcomed_users = set()
        # Random collectibles appear only while IMVU chat is connected.
        self.collectible_timer = QTimer(self)
        self.collectible_timer.setSingleShot(True)
        self.collectible_timer.timeout.connect(self._spawn_collectible)
















        # =====================================================







        # USER MANAGEMENT







        # =====================================================















        self.user_manager = UserManager()















        # =====================================================







        # MUSIC SYSTEM







        # =====================================================















        self.music_controller = MusicController()















        # =====================================================







        # COMMAND SYSTEM







        # =====================================================















        self.command_handler = CommandHandler(







            self.music_controller,







            self.user_manager,







            self.settings.get("prefix", "!")







        )















        # =====================================================







        # IMVU MANAGER







        # =====================================================















        self.imvu_manager = IMVUManager(







            self.music_controller,







            self.user_manager,







            self.settings.get("prefix", "!")







        )

        # Use the exact same CommandHandler instance for both the local
        # command console and real IMVU chat. This keeps Jamendo resolution,
        # permissions, prefix handling, and music state on one command path.
        self.imvu_manager.set_command_handler(self.command_handler)







        self.imvu_client_detector = IMVUClientDetector()















        # =====================================================







        # RADIO MANAGER







        # =====================================================















        self.radio_manager = RadioStreamManager()















        # =====================================================







        # LOCAL RADIO SERVER







        # =====================================================















        self.radio_server = RadioStreamServer()















        self.music_controller.attach_radio_server(







            self.radio_server







        )















        # =====================================================







        # CLOUDFLARE TUNNEL







        # =====================================================















        self.cloudflare_tunnel = CloudflareTunnel()















        self.public_stream_url = ""







        # Keep active QThreads referenced until they finish.



        self.imvu_radio_workers = []



        self.imvu_join_workers = []















        self.imvu_chat_worker = None
        self.imvu_chat_send_workers = []
        self.secondary_room_workers = []
        self._secondary_room_url_set = set()
        self._outgoing_chat_queue = []
        self._outgoing_chat_active = False
        self._processing_live_imvu_chat = False

        # =====================================================







        # UI







        # =====================================================















        self.setup_ui()







        self.connect_signals()







        self.load_settings_into_ui()















        self.log("Application started.")

        # First-run configuration.
        # Delay until the main window has completed setup.
        QTimer.singleShot(
            500,
            self.check_first_run_setup
        )















    # =========================================================







    # UI SETUP







    # =========================================================















    def setup_ui(self):
        """
        CrowBot production dashboard.

        The visible interface is intentionally minimal.
        Legacy widgets that are still referenced by runtime methods/signals
        are retained inside a hidden compatibility container.
        """

        # =====================================================
        # WINDOW
        # =====================================================

        self.setWindowTitle("CrowBot - IMVU Music Bot")
        self.setMinimumSize(760, 620)
        self.resize(980, 760)

        central = QWidget()
        central.setObjectName("crowbotRoot")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(18)

        # =====================================================
        # GLOBAL THEME
        # =====================================================

        self.setStyleSheet(
            """

            /* ================================================
               CROWBOT - NEON NIGHT
               ================================================ */

            QMainWindow {
                background: #060a11;
            }

            QWidget#crowbotRoot {
                background: #060a11;
                color: #e5edf7;
                font-family: "Segoe UI";
                font-size: 14px;
            }

            QLabel {
                color: #e5edf7;
                background: transparent;
            }

            /* ================================================
               BRAND
               ================================================ */

            QLabel#appTitle {
                color: #f8fafc;
                font-size: 30px;
                font-weight: 900;
            }

            QLabel#appSubtitle {
                color: #4ade80;
                font-size: 12px;
                font-weight: 800;
            }

            QLabel#connectionStatus {
                color: #86efac;
                background: #102019;
                border: 1px solid #22c55e;
                border-radius: 16px;
                padding: 7px 15px;
                font-size: 12px;
                font-weight: 800;
            }

            QLabel#sectionTitle {
                color: #4ade80;
                font-size: 11px;
                font-weight: 800;
            }

            QLabel#nowPlaying {
                color: #f8fafc;
                font-size: 23px;
                font-weight: 800;
            }

            QLabel#secondaryText {
                color: #a5b4c7;
                font-size: 13px;
            }

            /* ================================================
               CARDS
               ================================================ */

            QGroupBox {
                color: #86efac;
                background: #0d1420;
                border: 1px solid #243247;
                border-radius: 16px;
                margin-top: 10px;
                padding: 18px;
                font-size: 12px;
                font-weight: 800;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 17px;
                padding: 0 7px;
                color: #4ade80;
                background: #0d1420;
            }

            /* ================================================
               NORMAL BUTTONS
               ================================================ */

            QPushButton {
                min-height: 38px;
                color: #e2e8f0;
                background: #121c2b;
                border: 1px solid #2b3a50;
                border-radius: 10px;
                padding: 0 17px;
                font-weight: 700;
            }

            QPushButton:hover {
                color: #ecfdf5;
                background: #17283a;
                border: 1px solid #4ade80;
            }

            QPushButton:pressed {
                color: #ffffff;
                background: #123020;
                border: 1px solid #22c55e;
            }

            QPushButton:disabled {
                color: #64748b;
                background: #111827;
                border: 1px solid #1e293b;
            }

            /* ================================================
               CONNECT BOT
               ================================================ */

            QPushButton#connectButton {
                min-height: 56px;
                color: #03130a;
                background: #4ade80;
                border: 1px solid #86efac;
                border-radius: 14px;
                padding: 0 24px;
                font-size: 16px;
                font-weight: 900;
            }

            QPushButton#connectButton:hover {
                color: #022c16;
                background: #86efac;
                border: 1px solid #bbf7d0;
            }

            QPushButton#connectButton:pressed {
                color: #02160a;
                background: #22c55e;
                border: 1px solid #4ade80;
            }

            QPushButton#connectButton:disabled {
                color: #94a3b8;
                background: #172033;
                border: 1px solid #26344a;
            }

            /* ================================================
               SETTINGS / LOGS
               ================================================ */

            QPushButton#secondaryButton {
                min-height: 38px;
                color: #dbeafe;
                background: #101827;
                border: 1px solid #304159;
                border-radius: 10px;
            }

            QPushButton#secondaryButton:hover {
                color: #86efac;
                background: #13231d;
                border: 1px solid #4ade80;
            }

            /* ================================================
               QUEUE
               ================================================ */

            QListWidget {
                color: #dbe5f1;
                background: #080e17;
                border: 1px solid #243247;
                border-radius: 12px;
                padding: 7px;
                outline: none;
                font-size: 14px;
            }

            QListWidget::item {
                min-height: 36px;
                border-radius: 8px;
                padding-left: 10px;
                padding-right: 10px;
                margin: 2px;
            }

            QListWidget::item:hover {
                color: #ecfdf5;
                background: #12271d;
            }

            QListWidget::item:selected {
                color: #03210f;
                background: #4ade80;
            }

            /* ================================================
               TEXT INPUTS
               ================================================ */

            QLineEdit {
                min-height: 38px;
                color: #f8fafc;
                background: #080e17;
                border: 1px solid #2b3a50;
                border-radius: 9px;
                padding: 0 11px;
                selection-background-color: #22c55e;
                selection-color: #02160a;
            }

            QLineEdit:hover {
                border: 1px solid #475569;
            }

            QLineEdit:focus {
                background: #0c1522;
                border: 1px solid #4ade80;
            }

            QLineEdit:read-only {
                color: #94a3b8;
                background: #0a1019;
            }

            QTextEdit {
                color: #dbe5f1;
                background: #080e17;
                border: 1px solid #2b3a50;
                border-radius: 10px;
                padding: 8px;
                selection-background-color: #22c55e;
                selection-color: #02160a;
            }

            QTextEdit:focus {
                border: 1px solid #4ade80;
            }

            /* ================================================
               COMBO BOXES
               ================================================ */

            QComboBox {
                min-height: 38px;
                color: #f8fafc;
                background: #080e17;
                border: 1px solid #2b3a50;
                border-radius: 9px;
                padding: 0 11px;
            }

            QComboBox:hover {
                border: 1px solid #475569;
            }

            QComboBox:focus {
                border: 1px solid #4ade80;
            }

            QComboBox::drop-down {
                width: 30px;
                border: none;
            }

            QComboBox QAbstractItemView {
                color: #f8fafc;
                background: #111827;
                border: 1px solid #334155;
                selection-background-color: #22c55e;
                selection-color: #02160a;
                outline: none;
            }

            /* ================================================
               SLIDER
               ================================================ */

            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }

            QSlider::sub-page:horizontal {
                background: #22c55e;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background: #4ade80;
                border: 1px solid #86efac;
                border-radius: 8px;
            }

            /* ================================================
               SCROLLBARS
               ================================================ */

            QScrollBar:vertical {
                width: 10px;
                background: #080e17;
                border: none;
                margin: 0;
            }

            QScrollBar::handle:vertical {
                min-height: 30px;
                background: #334155;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical:hover {
                background: #4ade80;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }

            QScrollBar:horizontal {
                height: 10px;
                background: #080e17;
                border: none;
                margin: 0;
            }

            QScrollBar::handle:horizontal {
                min-width: 30px;
                background: #334155;
                border-radius: 5px;
            }

            QScrollBar::handle:horizontal:hover {
                background: #4ade80;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
            }

            QToolTip {
                color: #f8fafc;
                background: #111827;
                border: 1px solid #4ade80;
                padding: 5px;
            }
            """
        )

        # =====================================================
        # HEADER
        # =====================================================

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(1)

        title = QLabel("CROWBOT")
        title.setObjectName("appTitle")

        subtitle = QLabel("IMVU MUSIC BOT")
        subtitle.setObjectName("appSubtitle")

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch(1)

        self.connection_status = QLabel("●  OFFLINE")
        self.connection_status.setObjectName("connectionStatus")
        self.connection_status.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        header_layout.addWidget(self.connection_status)

        main_layout.addLayout(header_layout)

        # =====================================================
        # PRIMARY CONNECTION CONTROL
        # =====================================================

        self.connect_button = QPushButton("CONNECT BOT")
        self.connect_button.setObjectName("connectButton")
        self.connect_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        main_layout.addWidget(self.connect_button)

        # =====================================================
        # RESPONSIVE DASHBOARD ROW
        #
        # Both cards receive stretch space when the window grows.
        # =====================================================

        dashboard_layout = QHBoxLayout()
        dashboard_layout.setSpacing(16)

        # -----------------------------------------------------
        # NOW PLAYING CARD
        # -----------------------------------------------------

        now_playing_group = QGroupBox("NOW PLAYING")

        now_playing_layout = QVBoxLayout()
        now_playing_layout.setContentsMargins(12, 14, 12, 12)
        now_playing_layout.setSpacing(8)

        self.now_playing_label = QLabel(
            "Nothing is playing."
        )
        self.now_playing_label.setObjectName("nowPlaying")
        self.now_playing_label.setWordWrap(True)

        self.music_status = QLabel("Ready.")
        self.music_status.setObjectName("secondaryText")
        self.music_status.setWordWrap(True)

        now_playing_layout.addWidget(
            self.now_playing_label
        )

        now_playing_layout.addWidget(
            self.music_status
        )

        now_playing_layout.addStretch(1)

        now_playing_group.setLayout(
            now_playing_layout
        )

        # -----------------------------------------------------
        # STATUS CARD
        # -----------------------------------------------------

        status_group = QGroupBox("STATUS")

        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(12, 14, 12, 12)
        status_layout.setSpacing(9)

        self.client_status = QLabel(
            "●  Browser   Offline"
        )

        self.radio_status = QLabel(
            "●  Radio     Offline"
        )

        self.server_status = QLabel(
            "●  Station   Offline"
        )

        self.public_status = QLabel(
            "●  Cloudflare   Offline"
        )

        for status_widget in (
            self.client_status,
            self.radio_status,
            self.server_status,
            self.public_status,
        ):
            status_widget.setObjectName("secondaryText")
            status_widget.setWordWrap(True)
            status_layout.addWidget(status_widget)

        status_layout.addStretch(1)

        status_group.setLayout(status_layout)

        dashboard_layout.addWidget(
            now_playing_group,
            3
        )

        dashboard_layout.addWidget(
            status_group,
            2
        )

        main_layout.addLayout(dashboard_layout)

        # =====================================================
        # QUEUE
        # =====================================================

        queue_group = QGroupBox("QUEUE")

        queue_layout = QVBoxLayout()
        queue_layout.setContentsMargins(12, 14, 12, 12)

        self.queue_list = QListWidget()
        self.queue_list.setMinimumHeight(180)

        queue_layout.addWidget(
            self.queue_list
        )

        queue_group.setLayout(
            queue_layout
        )

        # Queue receives remaining vertical space.
        main_layout.addWidget(
            queue_group,
            1
        )

        # =====================================================
        # FOOTER
        # =====================================================

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        self.settings_button = QPushButton(
            "Settings"
        )
        self.settings_button.setObjectName(
            "secondaryButton"
        )

        self.logs_button = QPushButton(
            "Logs"
        )
        self.logs_button.setObjectName(
            "secondaryButton"
        )

        bottom_layout.addWidget(
            self.settings_button
        )

        bottom_layout.addWidget(
            self.logs_button
        )

        bottom_layout.addStretch(1)

        version_label = QLabel("CrowBot v1.2")
        version_label.setObjectName("secondaryText")

        bottom_layout.addWidget(version_label)

        main_layout.addLayout(bottom_layout)

        # =====================================================
        # HIDDEN COMPATIBILITY WIDGETS
        #
        # These controls are intentionally NOT part of the
        # production dashboard. They remain alive because older
        # runtime methods and connect_signals() may reference
        # them.
        #
        # Once regression testing proves they are dead, they can
        # be physically removed in the cleanup pass.
        # =====================================================

        self._legacy_ui = QWidget(central)
        self._legacy_ui.hide()

        # IMVU configuration compatibility.
        self.username_input = QLineEdit(
            self._legacy_ui
        )
        self.username_input.setPlaceholderText(
            "IMVU username"
        )

        self.room_input = QLineEdit(
            self._legacy_ui
        )
        self.room_input.setPlaceholderText(
            "IMVU Room ID"
        )

        # Old secondary disconnect/status control.
        self.disconnect_button = QPushButton(
            "Clear Status",
            self._legacy_ui
        )

        # Manual radio controls.
        self.radio_url_input = QLineEdit(
            self._legacy_ui
        )
        self.radio_url_input.setPlaceholderText(
            "Direct MP3 / continuous radio stream URL"
        )

        self.start_radio_button = QPushButton(
            "Start Radio",
            self._legacy_ui
        )

        self.stop_radio_button = QPushButton(
            "Stop Radio",
            self._legacy_ui
        )

        self.local_stream_input = QLineEdit(
            "http://127.0.0.1:8765/stream.mp3",
            self._legacy_ui
        )
        self.local_stream_input.setReadOnly(True)

        self.copy_local_button = QPushButton(
            "Copy",
            self._legacy_ui
        )

        self.public_stream_input = QLineEdit(
            self._legacy_ui
        )
        self.public_stream_input.setReadOnly(True)
        self.public_stream_input.setPlaceholderText(
            "Generated automatically when radio starts"
        )

        self.copy_public_button = QPushButton(
            "Copy IMVU URL",
            self._legacy_ui
        )

        # Legacy manual music controls.
        self.play_button = QPushButton(
            "Play",
            self._legacy_ui
        )

        self.pause_button = QPushButton(
            "Pause",
            self._legacy_ui
        )

        self.resume_button = QPushButton(
            "Resume",
            self._legacy_ui
        )

        self.skip_button = QPushButton(
            "Skip",
            self._legacy_ui
        )

        self.stop_button = QPushButton(
            "Stop",
            self._legacy_ui
        )

        self.clear_button = QPushButton(
            "Clear Queue",
            self._legacy_ui
        )

        self.volume_slider = QSlider(
            Qt.Orientation.Horizontal,
            self._legacy_ui
        )
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)

        # Development simulated-chat controls.
        self.simulated_chat_output = QTextEdit(
            self._legacy_ui
        )
        self.simulated_chat_output.setReadOnly(True)

        self.simulated_username_input = QLineEdit(
            self._legacy_ui
        )

        self.simulated_message_input = QLineEdit(
            self._legacy_ui
        )

        self.simulated_send_button = QPushButton(
            "Send Simulated Chat",
            self._legacy_ui
        )

        # Development command console.
        self.command_output = QTextEdit(
            self._legacy_ui
        )
        self.command_output.setReadOnly(True)

        self.command_input = QLineEdit(
            self._legacy_ui
        )

        self.send_command_button = QPushButton(
            "Send Command",
            self._legacy_ui
        )

        # Old user-management button.
        self.users_button = QPushButton(
            "Users",
            self._legacy_ui
        )
    def connect_signals(self):















        # -----------------------------------------------------







        # IMVU







        # -----------------------------------------------------















        self.connect_button.clicked.connect(







            self.toggle_crowbot_connection







        )















        self.disconnect_button.clicked.connect(







            self.disconnect_imvu







        )















        self.imvu_manager.status_changed.connect(







            self.update_imvu_status







        )















        self.imvu_manager.connection_error.connect(







            self.handle_imvu_error







        )















        self.imvu_manager.chat_received.connect(







            self.handle_imvu_chat







        )















        self.imvu_manager.bot_response.connect(







            self.handle_bot_response







        )

        # Background music completion responses
        self.command_handler.async_response.connect(
            self.handle_async_command_response
        )















        # -----------------------------------------------------







        # RADIO







        # -----------------------------------------------------















        self.start_radio_button.clicked.connect(







            self.start_radio







        )















        self.stop_radio_button.clicked.connect(







            self.stop_radio







        )















        self.copy_local_button.clicked.connect(







            self.copy_local_stream_url







        )















        self.copy_public_button.clicked.connect(







            self.copy_public_stream_url







        )















        self.radio_manager.status_changed.connect(







            self.update_radio_status







        )















        self.radio_manager.stream_error.connect(







            self.handle_radio_error







        )















        # -----------------------------------------------------







        # CLOUDFLARE







        # -----------------------------------------------------















        self.cloudflare_tunnel.tunnel_started.connect(







            self.cloudflare_started







        )















        self.cloudflare_tunnel.tunnel_stopped.connect(







            self.cloudflare_stopped







        )















        self.cloudflare_tunnel.tunnel_error.connect(







            self.cloudflare_error







        )















        self.cloudflare_tunnel.status_changed.connect(







            self.cloudflare_status_changed







        )















        # -----------------------------------------------------







        # MUSIC CONTROLS







        # -----------------------------------------------------















        self.play_button.clicked.connect(







            self.music_controller.play







        )















        self.pause_button.clicked.connect(







            self.music_controller.pause







        )















        self.resume_button.clicked.connect(







            self.music_controller.resume







        )















        self.skip_button.clicked.connect(







            self.music_controller.skip







        )















        self.stop_button.clicked.connect(







            self.music_controller.stop







        )















        self.clear_button.clicked.connect(







            self.music_controller.clear_queue







        )















        self.volume_slider.valueChanged.connect(







            self.change_volume







        )















        # -----------------------------------------------------







        # COMMAND CONSOLE







        # -----------------------------------------------------















        self.send_command_button.clicked.connect(







            self.execute_command







        )















        self.command_input.returnPressed.connect(







            self.execute_command







        )















        # -----------------------------------------------------







        # SIMULATED CHAT







        # -----------------------------------------------------















        self.simulated_send_button.clicked.connect(







            self.send_simulated_chat







        )















        self.simulated_message_input.returnPressed.connect(







            self.send_simulated_chat







        )















        # -----------------------------------------------------







        # MUSIC CONTROLLER SIGNALS







        # -----------------------------------------------------















        self.music_controller.now_playing_changed.connect(







            self.update_now_playing







        )















        self.music_controller.queue_changed.connect(







            self.update_queue







        )















        self.music_controller.status_changed.connect(







            self.update_music_status







        )















        self.music_controller.error_occurred.connect(







            self.handle_music_error







        )















        # -----------------------------------------------------







        # WINDOWS







        # -----------------------------------------------------















        self.settings_button.clicked.connect(







            self.open_settings







        )















        self.users_button.clicked.connect(







            self.open_users







        )















        self.logs_button.clicked.connect(







            self.open_logs







        )















    # =========================================================







    # SETTINGS







    # =========================================================















    def load_settings_into_ui(self):















        self.username_input.setText(







            self.settings.get(







                "username",







                ""







            )







        )















        self.room_input.setText(







            self.settings.get(







                "room_id",







                ""







            )







        )







        self.refresh_imvu_client_status()















    def check_first_run_setup(self):
        """
        Open Settings automatically when the application
        has not yet been configured for an IMVU bot/room.

        Existing configured installations are unaffected.
        """

        username = str(
            self.settings.get(
                "username",
                ""
            )
            or ""
        ).strip()

        room_id = str(
            self.settings.get(
                "room_id",
                ""
            )
            or ""
        ).strip()

        if username and room_id:
            return

        self.log(
            "First-run setup required."
        )

        self.open_settings()


    def open_settings(self):















        dialog = SettingsWindow(







            self







        )















        if dialog.exec():















            self.settings = load_settings()















            prefix = self.settings.get(







                "prefix",







                "!"







            )















            self.command_handler.set_prefix(







                prefix







            )















            if self.imvu_manager.command_handler:















                self.imvu_manager.command_handler.set_prefix(







                    prefix







                )















            self.load_settings_into_ui()















            self.log(







                "Settings updated."







            )















    # =========================================================







    # IMVU







    # =========================================================















    def _dedicated_chrome_profile_dir(self):
        from config.runtime_paths import get_chrome_profile_dir

        profile_dir = get_chrome_profile_dir()

        profile_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        return profile_dir
    def _find_chrome_executable(self):
        candidates = [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path.home() / "AppData" / "Local" / "Google" / "Chrome"
            / "Application" / "chrome.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _cdp_port_open(self, host="127.0.0.1", port=9222):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            return False

    def _ensure_dedicated_bot_chrome(self, timeout_seconds=15):
        if self._cdp_port_open():
            self.log("IMVU: Dedicated bot Chrome is already running on port 9222.")
            return True

        chrome_path = self._find_chrome_executable()
        if not chrome_path:
            raise RuntimeError(
                "Google Chrome was not found in the standard Windows locations."
            )

        profile_dir = self._dedicated_chrome_profile_dir()
        command = [
            str(chrome_path),
            "--remote-debugging-port=9222",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ]

        self.log("IMVU: Starting dedicated bot Chrome...")
        self.log(f"IMVU: Bot Chrome profile: {profile_dir}")

        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._cdp_port_open():
                self.log("IMVU: Dedicated bot Chrome CDP is ready on port 9222.")
                return True
            time.sleep(0.25)

        raise RuntimeError(
            "Dedicated bot Chrome started, but port 9222 did not become ready."
        )

    def _open_room_in_dedicated_chrome(self, room_url):
        controller = IMVUWebController()
        try:
            controller.connect()
            room_fragment = room_url.rstrip("/").split("/")[-1].lower()

            for page in controller.context.pages:
                try:
                    if room_fragment in (page.url or "").lower():
                        controller.page = page
                        page.bring_to_front()
                        self.log(
                            "IMVU: Dedicated Chrome already has the configured room open."
                        )
                        return page.url
                except Exception:
                    continue

            target_page = None
            for page in controller.context.pages:
                try:
                    if (page.url or "").lower() in (
                        "",
                        "about:blank",
                        "chrome://newtab/",
                        "chrome://new-tab-page/",
                    ):
                        target_page = page
                        break
                except Exception:
                    continue

            if target_page is None:
                target_page = controller.context.new_page()

            target_page.goto(
                room_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            target_page.bring_to_front()
            self.log(f"IMVU: Opened room in dedicated bot Chrome: {room_url}")
            return target_page.url
        finally:
            controller.disconnect()

    def toggle_crowbot_connection(self):
        """
        Main CrowBot connection button.

        Offline:
            CONNECT BOT -> complete startup sequence

        Online:
            DISCONNECT BOT -> stop listener, radio,
            Cloudflare and IMVU manager connection
        """

        if getattr(self, "_crowbot_connecting", False):
            self.log(
                "CROWBOT: Connection sequence is already running."
            )
            return

        button_text = ""

        try:
            button_text = (
                self.connect_button.text().strip().upper()
            )
        except Exception:
            pass

        if button_text == "DISCONNECT BOT":
            self.disconnect_crowbot()
            return

        self.connect_imvu()


    def disconnect_crowbot(self):
        """
        Shut down CrowBot runtime services cleanly while
        leaving the dedicated Chrome profile available.
        """

        self.log(
            "CROWBOT: Disconnecting..."
        )

        self._crowbot_connecting = False

        try:
            self.connect_button.setEnabled(False)
            self.connect_button.setText(
                "DISCONNECTING..."
            )
        except Exception:
            pass

        self.connection_status.setText(
            "Disconnecting..."
        )

        # -------------------------------------------------
        # CHAT LISTENER
        # -------------------------------------------------

        try:
            self.stop_imvu_chat_listener()
            self.log(
                "CROWBOT: Command listener stopped."
            )
        except Exception as error:
            self.log(
                f"CROWBOT: Listener stop warning: {error}"
            )

        # -------------------------------------------------
        # RADIO + CLOUDFLARE + LOCAL STATION
        # -------------------------------------------------

        try:
            self.stop_radio()
        except Exception as error:
            self.log(
                f"CROWBOT: Radio shutdown warning: {error}"
            )

        # -------------------------------------------------
        # IMVU MANAGER
        # -------------------------------------------------

        try:
            self.disconnect_imvu()
        except Exception as error:
            self.log(
                f"CROWBOT: IMVU disconnect warning: {error}"
            )

        # -------------------------------------------------
        # FINAL UI STATE
        # -------------------------------------------------

        self.connection_status.setText(
            "OFFLINE"
        )

        try:
            self.connect_button.setEnabled(True)
            self.connect_button.setText(
                "CONNECT BOT"
            )
        except Exception:
            pass

        self.log(
            "CROWBOT: OFFLINE."
        )

    def connect_imvu(self):
        """
        Start the complete CrowBot startup sequence.

        Chrome
        -> Room
        -> Join
        -> Radio
        -> Cloudflare
        -> IMVU Radio
        -> Chat listener
        -> READY
        """

        if getattr(self, "_crowbot_connecting", False):
            self.log(
                "CROWBOT: Connection sequence is already running."
            )
            return

        self._crowbot_connecting = True

        try:
            self.connect_button.setEnabled(False)
            self.connect_button.setText("CONNECTING...")
        except Exception:
            pass

        self.connection_status.setText(
            "Connecting CrowBot..."
        )

        self.log(
            "CROWBOT: Starting one-button connection sequence..."
        )

        username = self.username_input.text().strip()
        room_id = self.room_input.text().strip()

        if not room_id:
            QMessageBox.warning(
                self,
                "Missing Room ID",
                "Enter an IMVU Room ID, for example 379262025-7.",
            )
            self._crowbot_connecting = False

            try:
                self.connect_button.setEnabled(True)
                self.connect_button.setText("CONNECT BOT")
            except Exception:
                pass

            return

        raw_room = room_id.strip()

        if "/room-" in raw_room:
            room_id = raw_room.split("/room-", 1)[1]
            room_id = room_id.split("/", 1)[0]
            room_id = room_id.split("?", 1)[0]
            room_id = room_id.split("#", 1)[0]
        else:
            room_id = raw_room.strip("/")
            if room_id.startswith("room-"):
                room_id = room_id[5:]

        room_id = room_id.strip()

        if not room_id:
            QMessageBox.warning(
                self,
                "Invalid Room ID",
                "Enter a valid IMVU Room ID, for example 379262025-7.",
            )
            self._crowbot_connecting = False

            try:
                self.connect_button.setEnabled(True)
                self.connect_button.setText("CONNECT BOT")
            except Exception:
                pass

            return

        room_url = f"https://www.imvu.com/next/chat/room-{room_id}/"
        self.room_input.setText(room_id)

        try:
            self.stop_imvu_chat_listener()

            self.connection_status.setText("Opening Bot Chrome...")
            self.client_status.setText("Client: Dedicated Chrome (CDP)")

            self._ensure_dedicated_bot_chrome()
            opened_url = self._open_room_in_dedicated_chrome(room_url)

            self.connection_status.setText("IMVU Opened")
            self.client_status.setText("Client: Dedicated Chrome (CDP)")

            self.log(
                "Opened IMVU using dedicated bot Chrome. "
                f"Bot username setting: {username or 'Not set'}. "
                f"Room ID: {room_id}."
            )
            self.log(f"Opened IMVU room: {opened_url or room_url}")

            self.start_imvu_auto_join()

        except Exception as error:
            self._crowbot_connecting = False

            try:
                self.connect_button.setEnabled(True)
                self.connect_button.setText("CONNECT BOT")
            except Exception:
                pass

            self.connection_status.setText("Error")
            self.client_status.setText("Client: Dedicated Chrome (CDP)")
            self.log(f"IMVU CLIENT ERROR: {error}")
            QMessageBox.warning(
                self,
                "IMVU Client Error",
                str(error),
            )


    def start_imvu_auto_join(self):



        self.connection_status.setText("Joining Room...")



        self.log("IMVU: Starting automatic room join...")







        worker = IMVUJoinWorker(self)







        worker.succeeded.connect(



            self.imvu_auto_join_succeeded



        )



        worker.failed.connect(



            self.imvu_auto_join_failed



        )



        worker.finished.connect(



            lambda w=worker: self.cleanup_imvu_join_worker(w)



        )







        self.imvu_join_workers.append(worker)



        worker.start()











    def cleanup_imvu_join_worker(self, worker):



        if worker in self.imvu_join_workers:



            self.imvu_join_workers.remove(worker)







        worker.deleteLater()











    def imvu_auto_join_succeeded(self, room_url, clicked):



        self.connection_status.setText("Joined Room")







        if clicked:



            self.log(



                f"IMVU: Automatically joined room: {room_url}"



            )



        else:



            self.log(



                f"IMVU: Room already joined: {room_url}"



            )



        # The bot has joined the room.
        # Build the persistent radio path before accepting commands.
        self.connection_status.setText("Starting Radio...")

        self.log(
            "CROWBOT: Room joined. Starting persistent station and Cloudflare..."
        )

        try:
            self.start_crowbot_station()

        except Exception as error:
            self._crowbot_connecting = False

            try:
                self.connect_button.setEnabled(True)
                self.connect_button.setText("CONNECT BOT")
            except Exception:
                pass

            self.connection_status.setText(
                "Radio Start Failed"
            )

            self.log(
                f"CROWBOT STARTUP ERROR: {error}"
            )





    def imvu_auto_join_failed(self, message):



        self._crowbot_connecting = False

        try:
            self.connect_button.setEnabled(True)
            self.connect_button.setText("CONNECT BOT")
        except Exception:
            pass

        self.connection_status.setText("Join Failed")



        self.log(



            f"IMVU AUTO-JOIN ERROR: {message}"



        )







        QMessageBox.warning(



            self,



            "IMVU Auto-Join",



            "The IMVU room was opened, but automatic JOIN failed.\n\n"



            f"{message}"



        )











    def _schedule_collectible(self):
        """Random 3–7 minute delay; only when a listener is running."""
        import random
        worker = self.imvu_chat_worker
        if worker is not None and worker.isRunning():
            self.collectible_timer.start(random.randint(180000, 420000))

    def _spawn_collectible(self):
        worker = self.imvu_chat_worker
        if worker is None or not worker.isRunning():
            return
        drops = self.command_handler.collectibles
        drops.expired()
        announcement = drops.spawn()
        if announcement:
            self.send_bot_response_to_imvu(announcement)
        self._schedule_collectible()

    def start_secondary_room_monitors(self):
        """Test multiple room tabs without merging independent music queues."""
        controller = IMVUWebController()
        try:
            controller.connect()
            rooms = controller.list_imvu_rooms()
        except Exception as error:
            self.log(f"MULTI-ROOM: Tab discovery failed: {error}")
            return
        finally:
            controller.disconnect()

        # The existing primary worker uses the first room tab.
        for room in rooms[1:]:
            url = room["url"]
            if url in self._secondary_room_url_set:
                continue
            worker = SecondaryRoomWorker(url, self)
            self._secondary_room_url_set.add(url)
            self.secondary_room_workers.append(worker)
            worker.ready.connect(lambda u: self.log(f"MULTI-ROOM: Monitoring {u}"))
            worker.failed.connect(
                lambda u, error: self.log(f"MULTI-ROOM ERROR [{u}]: {error}")
            )
            worker.message_received.connect(self.receive_secondary_room_chat)
            worker.finished.connect(
                lambda w=worker, u=url: self.cleanup_secondary_room_worker(w, u)
            )
            worker.start()

    def cleanup_secondary_room_worker(self, worker, url):
        if worker in self.secondary_room_workers:
            self.secondary_room_workers.remove(worker)
        self._secondary_room_url_set.discard(url)
        worker.deleteLater()

    def receive_secondary_room_chat(self, room_url, username, message):
        if not username or not message:
            return
        self.log(f"MULTI-ROOM [{room_url}] {username}: {message}")
        # Test the routing without putting commands into the primary
        # handler: its music, games, and collectibles are not room-scoped.
        if message.casefold() == "!ping":
            response = f"🏓 CrowBot pong in this room, {username}!"
            self._send_secondary_room_response(room_url, response)

    def _send_secondary_room_response(self, room_url, response):
        worker = IMVUChatSendWorker(response, self, room_url=room_url)
        self.imvu_chat_send_workers.append(worker)
        worker.failed.connect(self.imvu_chat_send_failed)
        worker.finished.connect(
            lambda w=worker: self._cleanup_secondary_sender(w)
        )
        worker.start()

    def _cleanup_secondary_sender(self, worker):
        if worker in self.imvu_chat_send_workers:
            self.imvu_chat_send_workers.remove(worker)
        worker.deleteLater()

    def start_imvu_chat_listener(self):

        if self.imvu_chat_worker is not None and self.imvu_chat_worker.isRunning():

            self.log("IMVU CHAT: Listener is already running.")

            return



        self.log("IMVU CHAT: Starting live room listener...")

        worker = IMVUChatWorker(self)

        self.imvu_chat_worker = worker

        worker.message_received.connect(self.receive_live_imvu_chat)

        worker.started_listening.connect(self.imvu_chat_listener_started)

        worker.failed.connect(self.imvu_chat_listener_failed)

        worker.finished.connect(self.imvu_chat_listener_finished)

        worker.start()
        self._schedule_collectible()
        self.start_secondary_room_monitors()


    def stop_imvu_chat_listener(self, wait_ms=3000):

        for secondary in list(self.secondary_room_workers):
            secondary.stop()
            secondary.wait(wait_ms)
        self.collectible_timer.stop()
        worker = self.imvu_chat_worker

        if worker is None:

            return

        if worker.isRunning():

            worker.stop()

            worker.wait(wait_ms)

        if not worker.isRunning():

            worker.deleteLater()

            self.imvu_chat_worker = None



    def imvu_chat_listener_started(self, existing_count):

        self.log(

            "IMVU CHAT: Live listener active. "

            f"Ignoring {existing_count} existing chat entries."

        )



    def imvu_chat_listener_failed(self, message):

        self.log(f"IMVU CHAT LISTENER ERROR: {message}")



    def imvu_chat_listener_finished(self):

        worker = self.imvu_chat_worker

        if worker is not None and not worker.isRunning():

            worker.deleteLater()

            self.imvu_chat_worker = None



    def reconnect_chat_listener(self, username):
        """Restart the live IMVU chat listener without stopping music or radio."""
        if getattr(self, "_chat_reconnect_pending", False):
            return "CrowBot chat is already reconnecting."

        self._chat_reconnect_pending = True
        self.log(f"CROWBOT: Chat reconnect requested by {username}.")
        # Allow the outgoing acknowledgement to be queued before stopping
        # the reader. The sender uses its own controller/session.
        QTimer.singleShot(1200, self._finish_chat_reconnect)
        return "CrowBot is reconnecting its chat listener..."

    def _finish_chat_reconnect(self):
        """Safely resume chat after the old listener thread has exited."""
        try:
            self.stop_imvu_chat_listener(wait_ms=5000)
            worker = self.imvu_chat_worker
            if worker is not None and worker.isRunning():
                self.log("CROWBOT: Reconnect aborted; old listener is still running.")
                return
            self.start_imvu_chat_listener()
            self.log("CROWBOT: Chat listener restart requested.")
        except Exception as error:
            self.log(f"CROWBOT: Reconnect failed: {error}")
        finally:
            self._chat_reconnect_pending = False

    def receive_live_imvu_chat(self, username, message):
        """
        Process a live IMVU chat message.

        Public commands are handled immediately.

        CrowBot also welcomes each newly observed chatter once per
        application session. Welcome messages are triggered by the
        user's first ordinary (non-command) chat message so they never
        race a command response for the IMVU input field.
        """
        username = str(username or "").strip()
        message = str(message or "").strip()

        if not username or not message:
            return

        prefix = str(
            self.settings.get("prefix", "!")
            or "!"
        )

        user_key = username.lower()

        # React to CrowBot/bot mentions without blocking normal commands.
        # Throttle per user and ignore command-prefixed messages.
        mention_reply = self.command_handler.social.mention(
            username, message, prefix
        )
        if mention_reply:
            self.send_bot_response_to_imvu(mention_reply)

        # Handle the reconnect command before public room commands.
        if message.casefold() == f"{prefix}reconnect".casefold():
            response = self.reconnect_chat_listener(username)
            self.send_bot_response_to_imvu(response)
            return

        # Welcome on first ordinary message from this user.
        if (
            user_key not in self._welcomed_users
            and not message.startswith(prefix)
        ):
            self._welcomed_users.add(user_key)

            self.send_bot_response_to_imvu(
                f"Welcome to the room, {username}! "
                f"Type {prefix}help to see CrowBot commands."
            )

        self._processing_live_imvu_chat = True

        try:
            self.imvu_manager.receive_chat(
                username,
                message,
            )
        finally:
            self._processing_live_imvu_chat = False

    def disconnect_imvu(self):



        self.stop_imvu_chat_listener()







        # The official IMVU client/browser owns the login session.



        # We only clear this application's displayed client status.



        self.connection_status.setText("Disconnected")



        self.refresh_imvu_client_status()



        self.log("IMVU application status cleared.")











    def refresh_imvu_client_status(self):







        selected_client = self.settings.get(



            "imvu_client",



            "Auto Detect"



        )







        resolved_client = (



            self.imvu_client_detector.resolve_client(



                selected_client



            )



        )







        if resolved_client:



            self.client_status.setText(



                f"Client: {resolved_client}"



            )



        else:



            self.client_status.setText(



                "Client: Not detected"



            )











    def update_imvu_status(







        self,







        status







    ):















        self.connection_status.setText(







            status







        )















        self.log(







            f"IMVU: {status}"







        )















    def handle_imvu_error(







        self,







        message







    ):















        self.connection_status.setText(







            "Error"







        )















        self.log(







            f"IMVU ERROR: {message}"







        )















    def handle_imvu_chat(







        self,







        username,







        message







    ):















        self.log(







            f"IMVU CHAT: "







            f"{username}: "







            f"{message}"







        )















        self.command_output.append(







            f"[IMVU] {username}: {message}"







        )















    def handle_async_command_response(
        self,
        username,
        response
    ):
        """
        Handle the final response from a background music request.

        This runs after the original live IMVU command has already
        returned, so the completed response is explicitly sent back
        into the IMVU room.
        """

        response = str(
            response or ""
        ).strip()

        if not response:
            return

        self.log(
            f"ASYNC BOT RESPONSE TO "
            f"{username}: "
            f"{response}"
        )

        self.command_output.append(
            f"[BOT -> {username}] "
            f"{response}"
        )

        self.send_bot_response_to_imvu(
            response
        )

    def handle_bot_response(
        self,
        username,
        response
    ):
        self.log(
            f"BOT RESPONSE TO "
            f"{username}: "
            f"{response}"
        )

        self.command_output.append(
            f"[BOT -> {username}] {response}"
        )

        # Send only responses generated by REAL live IMVU messages.
        # Simulated chat and local command-console tests stay local.
        if self._processing_live_imvu_chat:
            self.send_bot_response_to_imvu(response)

    def send_bot_response_to_imvu(self, response):
        message = str(response or "").strip()
        if not message:
            return
        self._outgoing_chat_queue.append(message)
        self._send_next_chat_response()

    def _send_next_chat_response(self):
        # Only one Playwright sender may use the shared IMVU chat input.
        if self._outgoing_chat_active or not self._outgoing_chat_queue:
            return
        message = self._outgoing_chat_queue.pop(0)
        self._outgoing_chat_active = True
        worker = IMVUChatSendWorker(message, self)
        worker.succeeded.connect(self.imvu_chat_send_succeeded)
        worker.failed.connect(self.imvu_chat_send_failed)
        worker.finished.connect(
            lambda w=worker: self.cleanup_imvu_chat_send_worker(w)
        )
        self.imvu_chat_send_workers.append(worker)
        worker.start()

    def cleanup_imvu_chat_send_worker(self, worker):
        if worker in self.imvu_chat_send_workers:
            self.imvu_chat_send_workers.remove(worker)
        worker.deleteLater()
        self._outgoing_chat_active = False
        self._send_next_chat_response()

    def imvu_chat_send_succeeded(self, message):
        self.log(
            f"IMVU CHAT SEND: Sent: {message}"
        )

    def imvu_chat_send_failed(self, message, error):
        self.log(
            f"IMVU CHAT SEND ERROR: {error}"
        )

    # =========================================================
    # SIMULATED CHAT
    # =========================================================

    def send_simulated_chat(self):















        username = (







            self.simulated_username_input







            .text()







            .strip()







        )















        message = (







            self.simulated_message_input







            .text()







            .strip()







        )















        if not username:







            username = "TestUser"















        if not message:







            return















        self.simulated_chat_output.append(







            f"{username}: {message}"







        )















        self.simulated_message_input.clear()















        self.imvu_manager.receive_chat(







            username,







            message







        )















    # =========================================================







    # RADIO







    # =========================================================















    def start_crowbot_station(self):
        """
        Start CrowBot's persistent station without requiring
        a manually entered radio source URL.

        The RadioStreamServer broadcasts a continuous silent
        MP3 bridge while idle. Music commands later replace
        that idle source without changing the public station URL.
        """

        self.log(
            "CROWBOT: Starting persistent local station..."
        )

        try:
            # -------------------------------------------------
            # IDLE SOURCE
            # -------------------------------------------------

            # Empty source is intentional.
            # RadioStreamServer converts this state into the
            # continuous FFmpeg silent MP3 bridge.
            self.radio_server.clear_sources()

            # -------------------------------------------------
            # LOCAL STATION
            # -------------------------------------------------

            if not self.radio_server.is_running():
                self.radio_server.start()

                self.log(
                    "CROWBOT: Local persistent station started."
                )

            else:
                self.log(
                    "CROWBOT: Local persistent station is "
                    "already running."
                )

            local_stream_url = (
                self.radio_server.get_local_stream_url()
            )

            self.server_status.setText(
                "Local Server: Running"
            )

            self.radio_status.setText(
                "Radio: CrowBot station online"
            )

            self.log(
                "CROWBOT: Idle silent MP3 bridge active."
            )

            self.log(
                f"CROWBOT: Local stream: {local_stream_url}"
            )

            # -------------------------------------------------
            # PUBLIC STREAM STATE
            # -------------------------------------------------

            self.public_stream_url = ""

            try:
                self.public_stream_input.clear()
            except Exception:
                pass

            self.public_status.setText(
                "Public Stream: Starting..."
            )

            # -------------------------------------------------
            # CLOUDFLARE
            # -------------------------------------------------

            if not self.cloudflare_tunnel.is_running():

                self.log(
                    "CROWBOT: Starting Cloudflare tunnel..."
                )

                self.cloudflare_tunnel.start()

            else:
                existing_url = (
                    self.cloudflare_tunnel.get_stream_url()
                )

                if existing_url:

                    self.log(
                        "CROWBOT: Cloudflare tunnel already "
                        "running. Reusing public stream."
                    )

                    self.cloudflare_started(
                        existing_url
                    )

                else:
                    self.log(
                        "CROWBOT: Cloudflare process is running; "
                        "waiting for validated public URL..."
                    )

            return True

        except Exception as error:

            self._crowbot_connecting = False

            try:
                self.connect_button.setEnabled(True)
                self.connect_button.setText(
                    "CONNECT BOT"
                )
            except Exception:
                pass

            self.connection_status.setText(
                "Station Start Failed"
            )

            self.log(
                f"CROWBOT STATION ERROR: {error}"
            )

            try:
                self.radio_server.stop()
            except Exception:
                pass

            return False

    def start_radio(self):















        url = (







            self.radio_url_input







            .text()







            .strip()







        )















        if not url:















            QMessageBox.warning(







                self,







                "Missing URL",







                "Enter a radio stream URL."







            )















            return















        try:















            # -------------------------------------------------







            # SOURCE







            # -------------------------------------------------















            self.radio_server.set_source(







                url







            )















            # -------------------------------------------------







            # LOCAL RADIO SERVER







            # -------------------------------------------------















            if not self.radio_server.is_running():















                self.radio_server.start()















                self.log(







                    "Local radio server started."







                )















            self.server_status.setText(







                "Local Server: Running"







            )















            # -------------------------------------------------







            # LOCAL PLAYBACK







            # -------------------------------------------------















            self.radio_manager.start(







                url







            )















            self.radio_status.setText(







                "Radio running."







            )















            self.log(







                f"Radio started: {url}"







            )















            self.log(







                "Local stream available at: "







                "http://127.0.0.1:8765/stream.mp3"







            )















            # -------------------------------------------------







            # CLOUDFLARE







            # -------------------------------------------------















            self.public_stream_input.clear()















            self.public_stream_url = ""















            self.public_status.setText(







                "Public Stream: Starting..."







            )















            if not self.cloudflare_tunnel.is_running():















                started = (







                    self.cloudflare_tunnel.start()







                )















                if not started:















                    if not self.cloudflare_tunnel.is_running():















                        self.public_status.setText(







                            "Public Stream: Error"







                        )















            else:















                existing_url = (







                    self.cloudflare_tunnel







                    .get_stream_url()







                )















                if existing_url:















                    self.cloudflare_started(







                        existing_url







                    )















        except Exception as error:















            self.server_status.setText(







                "Local Server: Error"







            )















            QMessageBox.critical(







                self,







                "Radio Error",







                str(error)







            )















            self.log(







                f"RADIO ERROR: {error}"







            )















    def stop_radio(self):















        # -----------------------------------------------------







        # STOP CLOUDFLARE







        # -----------------------------------------------------















        if self.cloudflare_tunnel.is_running():















            self.cloudflare_tunnel.stop()















        # -----------------------------------------------------







        # STOP LOCAL PLAYBACK







        # -----------------------------------------------------















        self.radio_manager.stop()















        # -----------------------------------------------------







        # STOP LOCAL SERVER







        # -----------------------------------------------------















        if self.radio_server.is_running():















            self.radio_server.stop()















        self.radio_status.setText(







            "Radio stopped."







        )















        self.server_status.setText(







            "Local Server: Stopped"







        )















        self.public_stream_input.clear()















        self.public_stream_url = ""















        self.public_status.setText(







            "Public Stream: Stopped"







        )















        self.log(







            "Radio stopped."







        )















    def update_radio_status(







        self,







        status







    ):















        self.radio_status.setText(







            status







        )















        self.log(







            f"Radio: {status}"







        )















    def handle_radio_error(







        self,







        message







    ):















        self.radio_status.setText(







            "Radio error."







        )















        self.log(







            f"RADIO ERROR: {message}"







        )















    # =========================================================







    # CLOUDFLARE







    # =========================================================















    def cloudflare_started(self, stream_url):
        """
        cloudflare.py emits tunnel_started only after the public HTTPS
        /stream.mp3 endpoint has been DNS-resolved and actual MP3 bytes
        have been received through the tunnel.

        Do not perform a second urllib readiness test here. The old duplicate
        test could fail inside this long-running Python process even after
        cloudflare.py had already validated the same public stream with curl.
        """
        stream_url = str(stream_url or "").strip()

        if not stream_url:
            self.public_status.setText("Public Stream: Error")
            self.log("CLOUDFLARE ERROR: Validated tunnel returned an empty URL.")
            return

        self.public_stream_url = stream_url
        self.public_stream_input.setText(stream_url)
        self.public_status.setText("Public Stream: Ready for IMVU")

        self.log(
            "Cloudflare public MP3 stream validated. "
            f"Updating IMVU immediately: {stream_url}"
        )

        if getattr(self, "_crowbot_connecting", False):
            self.connection_status.setText(
                "Configuring IMVU Radio..."
            )

        self.start_imvu_radio_update(stream_url)


    def start_imvu_radio_update(self, stream_url):







        self.public_status.setText(



            "Public Stream: Updating IMVU..."



        )







        self.log(



            "Updating IMVU Radio Streaming with the new Cloudflare URL..."



        )







        print("IMVU: Starting automatic Radio Streaming update...")







        worker = IMVURadioUpdateWorker(



            stream_url,



            self



        )







        worker.succeeded.connect(



            self.imvu_radio_update_succeeded



        )







        worker.failed.connect(



            self.imvu_radio_update_failed



        )







        worker.finished.connect(



            lambda w=worker: self.cleanup_imvu_radio_worker(w)



        )







        self.imvu_radio_workers.append(worker)



        worker.start()











    def cleanup_imvu_radio_worker(self, worker):







        if worker in self.imvu_radio_workers:



            self.imvu_radio_workers.remove(worker)







        worker.deleteLater()











    def imvu_radio_update_succeeded(



        self,



        stream_url,



        previous_url



    ):







        self.public_status.setText(



            "Public Stream: Loaded in IMVU"



        )







        self.log(



            "IMVU Radio Streaming updated successfully. "



            f"New URL: {stream_url}"



        )







        print("IMVU: Automatic Radio Streaming update succeeded.")

        if getattr(self, "_crowbot_connecting", False):

            self.log(
                "CROWBOT: IMVU radio configured. "
                "Starting command listener..."
            )

            self.start_imvu_chat_listener()

            self._crowbot_connecting = False

            self.connection_status.setText("READY")

            try:
                self.connect_button.setEnabled(True)
                self.connect_button.setText("DISCONNECT BOT")
            except Exception:
                pass

            self.log(
                "CROWBOT: READY - room, radio, Cloudflare "
                "and command listener are active."
            )











    def imvu_radio_update_failed(self, message):







        self.public_status.setText(



            "Public Stream: IMVU Update Failed"



        )







        self.log(



            f"IMVU RADIO UPDATE ERROR: {message}"



        )







        print(f"IMVU RADIO UPDATE ERROR: {message}")

        if getattr(self, "_crowbot_connecting", False):

            self._crowbot_connecting = False

            self.connection_status.setText(
                "Radio Setup Failed"
            )

            try:
                self.connect_button.setEnabled(True)
                self.connect_button.setText("CONNECT BOT")
            except Exception:
                pass

            self.log(
                "CROWBOT: Startup stopped because IMVU "
                "Radio Streaming could not be configured."
            )















    def cloudflare_stopped(self):















        self.public_stream_url = ""















        self.public_stream_input.clear()















        self.public_status.setText(







            "Public Stream: Stopped"







        )















        self.log(







            "Cloudflare tunnel stopped."







        )















    def cloudflare_error(







        self,







        message







    ):















        self.public_stream_url = ""















        self.public_stream_input.clear()















        self.public_status.setText(







            "Public Stream: Error"







        )















        self.log(







            f"CLOUDFLARE ERROR: {message}"







        )















        QMessageBox.warning(







            self,







            "Cloudflare Error",







            message







        )















    def cloudflare_status_changed(







        self,







        status







    ):















        self.log(







            f"Cloudflare: {status}"







        )















        if (







            "Starting" in status







            and not self.public_stream_url







        ):















            self.public_status.setText(







                "Public Stream: Starting..."







            )















    # =========================================================







    # STREAM URL TOOLS







    # =========================================================















    def copy_local_stream_url(self):















        url = (







            self.local_stream_input







            .text()







            .strip()







        )















        QGuiApplication.clipboard().setText(







            url







        )















        self.log(







            f"Copied local stream URL: {url}"







        )















    def copy_public_stream_url(self):















        url = (







            self.public_stream_input







            .text()







            .strip()







        )















        if not url:















            QMessageBox.warning(







                self,







                "Public Stream Not Ready",







                "Wait for the Cloudflare tunnel "







                "to finish starting."







            )















            return















        if not url.startswith(







            "https://"







        ):















            QMessageBox.warning(







                self,







                "Invalid Public Stream",







                "The IMVU stream URL should use HTTPS."







            )















            return















        if not url.endswith(







            "/stream.mp3"







        ):















            QMessageBox.warning(







                self,







                "Invalid Public Stream",







                "The public stream URL must end "







                "with /stream.mp3."







            )















            return















        QGuiApplication.clipboard().setText(







            url







        )















        self.public_stream_url = url















        self.public_status.setText(







            "Public Stream: Ready for IMVU"







        )















        self.log(







            f"Copied IMVU stream URL: {url}"







        )















    # =========================================================







    # COMMAND CONSOLE







    # =========================================================















    def execute_command(self):















        message = (







            self.command_input







            .text()







            .strip()







        )















        if not message:







            return















        self.command_output.append(







            f"> {message}"







        )















        self.command_input.clear()















        response = (







            self.command_handler.handle(







                message,







                "Owner"







            )







        )















        if response is None:















            self.command_output.append(







                "Not a bot command."







            )















            return















        self.command_output.append(







            response







        )















        self.log(







            f"COMMAND: {message}"







        )















        self.log(







            f"RESPONSE: {response}"







        )















    # =========================================================







    # MUSIC







    # =========================================================















    def update_now_playing(







        self,







        song







    ):















        if not song:















            self.now_playing_label.setText(







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















        self.now_playing_label.setText(







            f"Music: {title}"







        )















        self.log(







            f"Now playing: "







            f"{title} "







            f"(requested by {requester})"







        )















    def update_queue(self):















        self.queue_list.clear()















        queue_items = (







            self.music_controller.get_queue()







        )















        for number, song in enumerate(







            queue_items,







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















            self.queue_list.addItem(







                f"{number}. "







                f"{title} "







                f"(requested by "







                f"{requester})"







            )















    def update_music_status(







        self,







        status







    ):















        self.music_status.setText(







            status







        )















        self.log(







            f"Music: {status}"







        )















    def handle_music_error(







        self,







        message







    ):















        self.music_status.setText(







            message







        )















        self.log(







            f"MUSIC ERROR: {message}"







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







    # WINDOWS







    # =========================================================















    def open_users(self):















        dialog = UsersWindow(







            self.user_manager,







            self







        )















        dialog.exec()















    def open_logs(self):















        dialog = LogsWindow(







            self.logs,







            self







        )















        dialog.exec()















    # =========================================================







    # WINDOW CLOSE







    # =========================================================















    def closeEvent(







        self,







        event







    ):















        try:

            self.stop_imvu_chat_listener()

        except Exception:

            pass

        try:
            for worker in list(self.imvu_chat_send_workers):
                if worker.isRunning():
                    worker.wait(5000)
        except Exception:
            pass



        try:















            if self.cloudflare_tunnel.is_running():















                self.cloudflare_tunnel.stop()















        except Exception:







            pass















        try:















            self.radio_manager.stop()















        except Exception:







            pass















        try:















            if self.radio_server.is_running():















                self.radio_server.stop()















        except Exception:







            pass















        event.accept()















    # =========================================================







    # LOGGING







    # =========================================================















    def log(







        self,







        message







    ):















        self.logs.append(







            message







        )















        print(







            message







        )









