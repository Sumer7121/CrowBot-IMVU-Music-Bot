from PySide6.QtCore import QObject, Signal

from bot.commands import CommandHandler
from bot.imvu_adapter import IMVUAdapter


class IMVUManager(QObject):

    connection_changed = Signal(bool, str)
    connection_error = Signal(str)

    chat_received = Signal(str, str)
    bot_response = Signal(str, str)

    status_changed = Signal(str)

    def __init__(
        self,
        music_controller=None,
        user_manager=None,
        prefix="!"
    ):

        super().__init__()

        self.username = ""
        self.room = ""

        self.status = "Disconnected"
        self.connected = False

        self.adapter = IMVUAdapter()

        self.command_handler = None

        if music_controller is not None:

            self.command_handler = CommandHandler(
                music_controller,
                user_manager,
                prefix
            )

        # -----------------------------------------------------
        # ADAPTER SIGNALS
        # -----------------------------------------------------

        self.adapter.connected_changed.connect(
            self.on_adapter_connection_changed
        )

        self.adapter.status_changed.connect(
            self.on_adapter_status_changed
        )

        self.adapter.message_received.connect(
            self.on_adapter_message_received
        )

        self.adapter.error_occurred.connect(
            self.on_adapter_error
        )

    # =========================================================
    # CONFIGURATION
    # =========================================================

    def configure(
        self,
        username,
        room
    ):

        self.username = (
            username or ""
        ).strip()

        self.room = (
            room or ""
        ).strip()

        self.adapter.configure(
            self.username,
            self.room
        )

        if self.username and self.room:

            self.set_status(
                "Configured"
            )

        else:

            self.set_status(
                "Disconnected"
            )

    # =========================================================
    # COMMAND HANDLER
    # =========================================================

    def set_command_handler(
        self,
        command_handler
    ):

        self.command_handler = (
            command_handler
        )

    def process_chat_command(
        self,
        username,
        message
    ):

        if not username or not message:

            return None

        if self.command_handler is None:

            self.connection_error.emit(
                "Command handler is not configured."
            )

            return None

        response = (
            self.command_handler.handle(
                message,
                username
            )
        )

        if response is None:

            return None

        self.bot_response.emit(
            username,
            response
        )

        return response

    # =========================================================
    # STATUS
    # =========================================================

    def set_status(
        self,
        status
    ):

        self.status = status

        self.status_changed.emit(
            status
        )

    def get_status(self):

        return self.status

    def is_connected(self):

        return self.connected

    # =========================================================
    # CONNECTION
    # =========================================================

    def connect_bot(self):

        if not self.username:

            self.set_status(
                "Error"
            )

            self.connection_error.emit(
                "IMVU username is required."
            )

            return False

        if not self.room:

            self.set_status(
                "Error"
            )

            self.connection_error.emit(
                "IMVU room is required."
            )

            return False

        self.set_status(
            "Connecting"
        )

        return self.adapter.connect()

    def disconnect(self):

        self.adapter.disconnect()

    # =========================================================
    # SEND MESSAGE
    # =========================================================

    def send_message(
        self,
        message
    ):

        if not self.connected:

            self.connection_error.emit(
                "Cannot send message. "
                "IMVU bot is not connected."
            )

            return False

        if not message:

            return False

        return self.adapter.send_message(
            message
        )

    # =========================================================
    # RECEIVE CHAT
    # =========================================================

    def receive_chat(
        self,
        username,
        message
    ):

        if not username or not message:

            return

        # Notify the rest of the application
        # that chat was received.
        self.chat_received.emit(
            username,
            message
        )

        # Process the message as a bot command.
        self.process_chat_command(
            username,
            message
        )

    # =========================================================
    # ADAPTER EVENTS
    # =========================================================

    def on_adapter_connection_changed(
        self,
        connected
    ):

        self.connected = connected

        if connected:

            self.set_status(
                "Connected"
            )

        else:

            self.set_status(
                "Disconnected"
            )

        self.connection_changed.emit(
            connected,
            self.status
        )

    def on_adapter_status_changed(
        self,
        status
    ):

        self.set_status(
            status
        )

    def on_adapter_message_received(
        self,
        username,
        message
    ):

        self.receive_chat(
            username,
            message
        )

    def on_adapter_error(
        self,
        message
    ):

        self.set_status(
            "Error"
        )

        self.connection_error.emit(
            message
        )