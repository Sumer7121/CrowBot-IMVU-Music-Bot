from PySide6.QtCore import QObject, Signal


class IMVUAdapter(QObject):

    connected_changed = Signal(bool)
    status_changed = Signal(str)
    message_received = Signal(str, str)
    message_sent = Signal(str)
    error_occurred = Signal(str)

    def __init__(self):

        super().__init__()

        self.username = ""
        self.room = ""

        self.connected = False

        self.transport = None

        self.transport_name = (
            "Not configured"
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

        if self.username and self.room:

            self.status_changed.emit(
                "IMVU account and room configured."
            )

        else:

            self.status_changed.emit(
                "IMVU account or room not configured."
            )

    # =========================================================
    # TRANSPORT
    # =========================================================

    def set_transport(
        self,
        transport,
        name="External IMVU Transport"
    ):

        self.transport = transport

        self.transport_name = (
            name or
            "External IMVU Transport"
        )

        self.status_changed.emit(
            f"IMVU transport configured: "
            f"{self.transport_name}"
        )

    def clear_transport(self):

        if self.connected:

            self.disconnect()

        self.transport = None

        self.transport_name = (
            "Not configured"
        )

        self.status_changed.emit(
            "IMVU transport removed."
        )

    # =========================================================
    # CONNECT
    # =========================================================

    def connect(self):

        if not self.username:

            self.status_changed.emit(
                "Username is required."
            )

            self.error_occurred.emit(
                "IMVU username is required."
            )

            return False

        if not self.room:

            self.status_changed.emit(
                "Room is required."
            )

            self.error_occurred.emit(
                "IMVU room is required."
            )

            return False

        if self.transport is None:

            self.status_changed.emit(
                "IMVU transport is not configured."
            )

            self.error_occurred.emit(
                "No supported IMVU transport "
                "is configured."
            )

            return False

        try:

            result = self.transport.connect(
                self.username,
                self.room
            )

        except Exception as error:

            self.connected = False

            self.connected_changed.emit(
                False
            )

            self.status_changed.emit(
                "IMVU connection failed."
            )

            self.error_occurred.emit(
                f"IMVU connection error: {error}"
            )

            return False

        if result:

            self.connected = True

            self.connected_changed.emit(
                True
            )

            self.status_changed.emit(
                "Connected to IMVU."
            )

            return True

        self.connected = False

        self.connected_changed.emit(
            False
        )

        self.status_changed.emit(
            "IMVU connection failed."
        )

        self.error_occurred.emit(
            "The IMVU transport could not connect."
        )

        return False

    # =========================================================
    # DISCONNECT
    # =========================================================

    def disconnect(self):

        if self.transport is not None:

            try:

                self.transport.disconnect()

            except Exception as error:

                self.error_occurred.emit(
                    f"IMVU disconnect error: {error}"
                )

        self.connected = False

        self.connected_changed.emit(
            False
        )

        self.status_changed.emit(
            "Disconnected from IMVU."
        )

    # =========================================================
    # SEND MESSAGE
    # =========================================================

    def send_message(
        self,
        message
    ):

        message = (
            message or ""
        ).strip()

        if not message:

            return False

        if not self.connected:

            self.error_occurred.emit(
                "Cannot send IMVU message. "
                "The bot is not connected."
            )

            return False

        if self.transport is None:

            self.error_occurred.emit(
                "Cannot send IMVU message. "
                "No transport is configured."
            )

            return False

        try:

            result = self.transport.send_message(
                message
            )

        except Exception as error:

            self.error_occurred.emit(
                f"IMVU message error: {error}"
            )

            return False

        if result:

            self.message_sent.emit(
                message
            )

            return True

        self.error_occurred.emit(
            "The IMVU transport could not "
            "send the message."
        )

        return False

    # =========================================================
    # RECEIVE MESSAGE
    # =========================================================

    def receive_message(
        self,
        username,
        message
    ):

        username = (
            username or ""
        ).strip()

        message = (
            message or ""
        ).strip()

        if not username or not message:

            return

        self.message_received.emit(
            username,
            message
        )

    # =========================================================
    # TRANSPORT STATUS
    # =========================================================

    def transport_status(
        self,
        status
    ):

        if not status:

            return

        self.status_changed.emit(
            str(status)
        )

    # =========================================================
    # TRANSPORT ERROR
    # =========================================================

    def transport_error(
        self,
        message
    ):

        if not message:

            return

        self.error_occurred.emit(
            str(message)
        )

    # =========================================================
    # CONNECTION STATUS
    # =========================================================

    def set_connected(
        self,
        connected
    ):

        connected = bool(
            connected
        )

        self.connected = connected

        self.connected_changed.emit(
            connected
        )

        if connected:

            self.status_changed.emit(
                "Connected to IMVU."
            )

        else:

            self.status_changed.emit(
                "Disconnected from IMVU."
            )

    # =========================================================
    # GETTERS
    # =========================================================

    def is_connected(self):

        return self.connected

    def get_username(self):

        return self.username

    def get_room(self):

        return self.room

    def get_transport_name(self):

        return self.transport_name