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







            if not controller.radio_controls_visible():



                raise RuntimeError(



                    "IMVU Radio Streaming controls are not visible. "



                    "Open Media and switch Radio Streaming ON."



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

                    timeout_ms=750,

                    poll_interval_ms=250,

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





class IMVUChatSendWorker(QThread):
    """Send one generated bot response into the active IMVU Web room."""

    succeeded = Signal(str)
    failed = Signal(str, str)

    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.message = str(message or "").strip()

    def run(self):
        controller = IMVUWebController()

        try:
            if not self.message:
                raise ValueError("Cannot send an empty IMVU chat message.")

            print("IMVU CHAT SEND: Connecting to Chrome on port 9222...")
            controller.connect()

            page = controller.find_imvu_room()
            if not page:
                raise RuntimeError(
                    "No IMVU room tab was found in the dedicated bot Chrome session."
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
        self._processing_live_imvu_chat = False

        # =====================================================







        # UI







        # =====================================================















        self.setup_ui()







        self.connect_signals()







        self.load_settings_into_ui()















        self.log("Application started.")















    # =========================================================







    # UI SETUP







    # =========================================================















    def setup_ui(self):















        central = QWidget()







        self.setCentralWidget(central)















        main_layout = QVBoxLayout(central)















        # =====================================================







        # HEADER







        # =====================================================















        header_layout = QHBoxLayout()















        title = QLabel("IMVU Music Bot")















        title.setStyleSheet(







            """







            font-size: 28px;







            font-weight: bold;







            """







        )















        header_layout.addWidget(title)







        header_layout.addStretch()















        header_layout.addWidget(







            QLabel("IMVU Status:")







        )















        self.connection_status = QLabel(







            "Disconnected"







        )















        self.connection_status.setStyleSheet(







            """







            font-weight: bold;







            """







        )















        header_layout.addWidget(







            self.connection_status







        )















        main_layout.addLayout(







            header_layout







        )















        # =====================================================







        # IMVU CONNECTION







        # =====================================================















        imvu_group = QGroupBox(







            "IMVU Connection"







        )















        imvu_layout = QHBoxLayout()















        self.username_input = QLineEdit()















        self.username_input.setPlaceholderText(







            "IMVU username"







        )















        self.room_input = QLineEdit()















        self.room_input.setPlaceholderText(







            "IMVU Room ID"







        )















        self.connect_button = QPushButton(







            "Open IMVU Room"







        )















        self.disconnect_button = QPushButton(







            "Clear Status"







        )















        imvu_layout.addWidget(







            QLabel("Bot Username:")







        )















        imvu_layout.addWidget(







            self.username_input







        )















        imvu_layout.addWidget(







            QLabel("Room ID:")







        )















        imvu_layout.addWidget(







            self.room_input







        )















        imvu_layout.addWidget(







            self.connect_button







        )















        imvu_layout.addWidget(







            self.disconnect_button







        )















        self.client_status = QLabel("Client: Detecting...")







        imvu_layout.addWidget(







            self.client_status







        )















        imvu_group.setLayout(







            imvu_layout







        )















        main_layout.addWidget(







            imvu_group







        )















        # =====================================================







        # RADIO STREAM







        # =====================================================















        radio_group = QGroupBox(







            "IMVU Radio Streaming"







        )















        radio_layout = QVBoxLayout()















        # -----------------------------------------------------







        # SOURCE STREAM







        # -----------------------------------------------------















        source_layout = QHBoxLayout()















        self.radio_url_input = QLineEdit()















        self.radio_url_input.setPlaceholderText(







            "Direct MP3 / continuous radio stream URL"







        )















        self.start_radio_button = QPushButton(







            "Start Radio"







        )















        self.stop_radio_button = QPushButton(







            "Stop Radio"







        )















        source_layout.addWidget(







            QLabel("Source URL:")







        )















        source_layout.addWidget(







            self.radio_url_input







        )















        source_layout.addWidget(







            self.start_radio_button







        )















        source_layout.addWidget(







            self.stop_radio_button







        )















        radio_layout.addLayout(







            source_layout







        )















        # -----------------------------------------------------







        # LOCAL STREAM







        # -----------------------------------------------------















        local_layout = QHBoxLayout()















        self.local_stream_input = QLineEdit(







            "http://127.0.0.1:8765/stream.mp3"







        )















        self.local_stream_input.setReadOnly(







            True







        )















        self.copy_local_button = QPushButton(







            "Copy"







        )















        local_layout.addWidget(







            QLabel("Local Stream:")







        )















        local_layout.addWidget(







            self.local_stream_input







        )















        local_layout.addWidget(







            self.copy_local_button







        )















        radio_layout.addLayout(







            local_layout







        )















        # -----------------------------------------------------







        # PUBLIC IMVU STREAM







        # -----------------------------------------------------















        public_layout = QHBoxLayout()















        self.public_stream_input = QLineEdit()















        self.public_stream_input.setReadOnly(







            True







        )















        self.public_stream_input.setPlaceholderText(







            "Generated automatically when radio starts"







        )















        self.copy_public_button = QPushButton(







            "Copy IMVU URL"







        )















        public_layout.addWidget(







            QLabel("IMVU Stream:")







        )















        public_layout.addWidget(







            self.public_stream_input







        )















        public_layout.addWidget(







            self.copy_public_button







        )















        radio_layout.addLayout(







            public_layout







        )















        # -----------------------------------------------------







        # STATUS







        # -----------------------------------------------------















        status_layout = QHBoxLayout()















        self.radio_status = QLabel(







            "Radio stopped."







        )















        self.server_status = QLabel(







            "Local Server: Stopped"







        )















        self.public_status = QLabel(







            "Public Stream: Stopped"







        )















        status_layout.addWidget(







            self.radio_status







        )















        status_layout.addStretch()















        status_layout.addWidget(







            self.server_status







        )















        status_layout.addWidget(







            self.public_status







        )















        radio_layout.addLayout(







            status_layout







        )















        radio_group.setLayout(







            radio_layout







        )















        main_layout.addWidget(







            radio_group







        )















        # =====================================================







        # NOW PLAYING







        # =====================================================















        now_playing_group = QGroupBox(







            "Now Playing"







        )















        now_playing_layout = QVBoxLayout()















        self.now_playing_label = QLabel(







            "Nothing is playing."







        )















        self.now_playing_label.setStyleSheet(







            """







            font-size: 20px;







            font-weight: bold;







            """







        )















        now_playing_layout.addWidget(







            self.now_playing_label







        )















        self.music_status = QLabel(







            "Ready."







        )















        now_playing_layout.addWidget(







            self.music_status







        )















        now_playing_group.setLayout(







            now_playing_layout







        )















        main_layout.addWidget(







            now_playing_group







        )















        # =====================================================







        # MUSIC CONTROLS







        # =====================================================















        controls_layout = QHBoxLayout()















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















        self.clear_button = QPushButton(







            "Clear Queue"







        )















        controls_layout.addWidget(







            self.play_button







        )















        controls_layout.addWidget(







            self.pause_button







        )















        controls_layout.addWidget(







            self.resume_button







        )















        controls_layout.addWidget(







            self.skip_button







        )















        controls_layout.addWidget(







            self.stop_button







        )















        controls_layout.addWidget(







            self.clear_button







        )















        main_layout.addLayout(







            controls_layout







        )















        # =====================================================







        # VOLUME







        # =====================================================















        volume_layout = QHBoxLayout()















        volume_layout.addWidget(







            QLabel("Volume:")







        )















        self.volume_slider = QSlider(







            Qt.Orientation.Horizontal







        )















        self.volume_slider.setRange(







            0,







            100







        )















        self.volume_slider.setValue(







            80







        )















        volume_layout.addWidget(







            self.volume_slider







        )















        main_layout.addLayout(







            volume_layout







        )















        # =====================================================







        # MUSIC QUEUE







        # =====================================================















        queue_group = QGroupBox(







            "Music Queue"







        )















        queue_layout = QVBoxLayout()















        self.queue_list = QListWidget()















        queue_layout.addWidget(







            self.queue_list







        )















        queue_group.setLayout(







            queue_layout







        )















        main_layout.addWidget(







            queue_group







        )















        # =====================================================







        # SIMULATED IMVU CHAT







        # =====================================================















        chat_group = QGroupBox(







            "Simulated IMVU Chat - Development Test"







        )















        chat_layout = QVBoxLayout()















        self.simulated_chat_output = QTextEdit()















        self.simulated_chat_output.setReadOnly(







            True







        )















        self.simulated_username_input = QLineEdit()















        self.simulated_username_input.setPlaceholderText(







            "Test IMVU username"







        )















        self.simulated_message_input = QLineEdit()















        self.simulated_message_input.setPlaceholderText(







            "Example: !help"







        )















        self.simulated_send_button = QPushButton(







            "Send Simulated Chat"







        )















        simulated_input_layout = QHBoxLayout()















        simulated_input_layout.addWidget(







            self.simulated_username_input







        )















        simulated_input_layout.addWidget(







            self.simulated_message_input







        )















        simulated_input_layout.addWidget(







            self.simulated_send_button







        )















        chat_layout.addWidget(







            self.simulated_chat_output







        )















        chat_layout.addLayout(







            simulated_input_layout







        )















        chat_group.setLayout(







            chat_layout







        )















        main_layout.addWidget(







            chat_group







        )















        # =====================================================







        # COMMAND CONSOLE







        # =====================================================















        command_group = QGroupBox(







            "Command Console"







        )















        command_layout = QVBoxLayout()















        self.command_output = QTextEdit()















        self.command_output.setReadOnly(







            True







        )















        self.command_input = QLineEdit()















        self.command_input.setPlaceholderText(







            "Enter command, example: !help"







        )















        self.send_command_button = QPushButton(







            "Send Command"







        )















        command_input_layout = QHBoxLayout()















        command_input_layout.addWidget(







            self.command_input







        )















        command_input_layout.addWidget(







            self.send_command_button







        )















        command_layout.addWidget(







            self.command_output







        )















        command_layout.addLayout(







            command_input_layout







        )















        command_group.setLayout(







            command_layout







        )















        main_layout.addWidget(







            command_group







        )















        # =====================================================







        # BOTTOM BUTTONS







        # =====================================================















        bottom_layout = QHBoxLayout()















        self.settings_button = QPushButton(







            "Settings"







        )















        self.users_button = QPushButton(







            "Users"







        )















        self.logs_button = QPushButton(







            "Logs"







        )















        bottom_layout.addWidget(







            self.settings_button







        )















        bottom_layout.addWidget(







            self.users_button







        )















        bottom_layout.addWidget(







            self.logs_button







        )















        bottom_layout.addStretch()















        main_layout.addLayout(







            bottom_layout







        )















    # =========================================================







    # SIGNAL CONNECTIONS







    # =========================================================















    def connect_signals(self):















        # -----------------------------------------------------







        # IMVU







        # -----------------------------------------------------















        self.connect_button.clicked.connect(







            self.connect_imvu







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

    def connect_imvu(self):
        username = self.username_input.text().strip()
        room_id = self.room_input.text().strip()

        if not room_id:
            QMessageBox.warning(
                self,
                "Missing Room ID",
                "Enter an IMVU Room ID, for example 379262025-7.",
            )
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



        self.start_imvu_chat_listener()





    def imvu_auto_join_failed(self, message):



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



    def stop_imvu_chat_listener(self, wait_ms=3000):

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



    def receive_live_imvu_chat(self, username, message):
        """
        Process a live IMVU chat message.

        The shared IMVU command handler controls the MusicController,
        queue, and RadioStreamServer.

        The public Cloudflare stream is a persistent station URL.
        Song changes happen internally and must NOT restart the radio
        transport or reload the IMVU Radio Streaming URL.
        """
        self._processing_live_imvu_chat = True

        try:
            self.imvu_manager.receive_chat(username, message)
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

        worker = IMVUChatSendWorker(message, self)

        worker.succeeded.connect(
            self.imvu_chat_send_succeeded
        )
        worker.failed.connect(
            self.imvu_chat_send_failed
        )
        worker.finished.connect(
            lambda w=worker: self.cleanup_imvu_chat_send_worker(w)
        )

        self.imvu_chat_send_workers.append(worker)

        self.log(
            f"IMVU CHAT SEND: Queued bot response: {message}"
        )

        worker.start()

    def cleanup_imvu_chat_send_worker(self, worker):
        if worker in self.imvu_chat_send_workers:
            self.imvu_chat_send_workers.remove(worker)

        worker.deleteLater()

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











    def imvu_radio_update_failed(self, message):







        self.public_status.setText(



            "Public Stream: IMVU Update Failed"



        )







        self.log(



            f"IMVU RADIO UPDATE ERROR: {message}"



        )







        print(f"IMVU RADIO UPDATE ERROR: {message}")















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


