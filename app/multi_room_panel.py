"""Visible multi-room dashboard for CrowBot's existing PySide6 main window.

The widget is presentation-only. Radio controllers and Playwright workers stay
owned by MainWindow; Qt signals request actions from the main application.
"""
from collections import defaultdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QHeaderView,
)


class MultiRoomPanel(QWidget):
    add_requested = Signal(str)
    refresh_requested = Signal()
    remove_requested = Signal(str)
    reload_requested = Signal(str)
    skip_requested = Signal(str)
    stop_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshots = {}
        self._logs = defaultdict(list)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        group = QGroupBox("ROOM MANAGER · INDEPENDENT RADIOS")
        group_layout = QVBoxLayout(group)
        form = QHBoxLayout()
        self.room_id_input = QLineEdit()
        self.room_id_input.setPlaceholderText("Additional room ID (e.g. 391169385-9) or full IMVU URL")
        self.join_button = QPushButton("ADD / JOIN ROOM")
        self.refresh_button = QPushButton("REFRESH ROOMS")
        self.remove_button = QPushButton("REMOVE SELECTED")
        self.reload_button = QPushButton("RELOAD RADIO")
        self.skip_button = QPushButton("SKIP SONG")
        self.stop_button = QPushButton("STOP MUSIC")
        form.addWidget(self.room_id_input, 3)
        form.addWidget(self.join_button)
        form.addWidget(self.refresh_button)
        form.addWidget(self.remove_button)
        group_layout.addLayout(form)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("SELECTED ROOM CONTROLS:"))
        controls.addWidget(self.reload_button)
        controls.addWidget(self.skip_button)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)
        group_layout.addLayout(controls)

        self.room_table = QTableWidget(0, 5)
        self.room_table.setHorizontalHeaderLabels(
            ["ROOM ID", "TYPE", "STATUS", "RADIO PORT", "NOW PLAYING"]
        )
        self.room_table.verticalHeader().setVisible(False)
        self.room_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.room_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.room_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.room_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.room_table.setMinimumHeight(135)
        group_layout.addWidget(self.room_table)

        stream_row = QHBoxLayout()
        stream_row.addWidget(QLabel("SELECTED RADIO URL"))
        self.stream_url_input = QLineEdit()
        self.stream_url_input.setReadOnly(True)
        self.stream_url_input.setPlaceholderText("Waiting for selected room's Cloudflare stream")
        self.copy_stream_button = QPushButton("COPY URL")
        stream_row.addWidget(self.stream_url_input, 1)
        stream_row.addWidget(self.copy_stream_button)
        group_layout.addLayout(stream_row)

        details = QSplitter(Qt.Orientation.Horizontal)
        queue_side = QWidget()
        queue_layout = QVBoxLayout(queue_side)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_label = QLabel("Select a room to inspect its music and queue.")
        self.detail_label.setWordWrap(True)
        self.queue_list = QListWidget()
        queue_layout.addWidget(self.detail_label)
        queue_layout.addWidget(self.queue_list)
        details.addWidget(queue_side)

        log_side = QWidget()
        log_layout = QVBoxLayout(log_side)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel("ROOM LOGS (select a room to filter)"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        details.addWidget(log_side)
        details.setSizes([460, 530])
        group_layout.addWidget(details)
        layout.addWidget(group)

        self.join_button.clicked.connect(
            lambda: self.add_requested.emit(self.room_id_input.text().strip())
        )
        self.room_id_input.returnPressed.connect(
            lambda: self.add_requested.emit(self.room_id_input.text().strip())
        )
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.copy_stream_button.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(self.stream_url_input.text())
            if self.stream_url_input.text() else None
        )
        self.remove_button.clicked.connect(self._request_removal)
        self.reload_button.clicked.connect(
            lambda: self.reload_requested.emit(self.selected_room())
        )
        self.skip_button.clicked.connect(
            lambda: self.skip_requested.emit(self.selected_room())
        )
        self.stop_button.clicked.connect(
            lambda: self.stop_requested.emit(self.selected_room())
        )
        self.room_table.itemSelectionChanged.connect(self._display_selection)

    def selected_room(self):
        row = self.room_table.currentRow()
        if row < 0:
            return ""
        item = self.room_table.item(row, 0)
        return item.text() if item else ""

    def _request_removal(self):
        room_id = self.selected_room()
        if room_id:
            self.remove_requested.emit(room_id)

    def set_rooms(self, snapshots):
        """Render room state without resetting a user's selected room."""
        selected = self.selected_room()
        rooms = {str(record["room_id"]): record for record in snapshots}
        if rooms == self._snapshots:
            return
        self._snapshots = rooms
        self.room_table.blockSignals(True)
        self.room_table.setRowCount(len(rooms))
        for row, (room_id, record) in enumerate(rooms.items()):
            for col, value in enumerate((
                room_id,
                record.get("type", "Secondary"),
                record.get("status", "Starting"),
                str(record.get("port", "—")),
                record.get("playing", "—"),
            )):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, room_id)
                self.room_table.setItem(row, col, item)
        ids = list(rooms)
        if ids:
            target = selected if selected in rooms else ids[0]
            self.room_table.selectRow(ids.index(target))
        self.room_table.blockSignals(False)
        self._display_selection()

    def add_log(self, room_id, message):
        key = str(room_id or "ALL")
        entries = self._logs[key]
        entries.append(str(message))
        if len(entries) > 350:
            del entries[:-350]
        if self.selected_room() == key:
            self.log_view.append(str(message))

    def _display_selection(self):
        room_id = self.selected_room()
        record = self._snapshots.get(room_id, {})
        self.remove_button.setEnabled(bool(room_id and record.get("type") != "Primary"))
        for button in (self.reload_button, self.skip_button, self.stop_button):
            button.setEnabled(bool(room_id))
        if not room_id:
            self.detail_label.setText("Select a room to inspect its music and queue.")
            self.queue_list.clear()
            self.log_view.clear()
            self.stream_url_input.clear()
            return
        self.stream_url_input.setText(record.get("stream_url", ""))
        playing = record.get("playing", "Nothing playing")
        status = record.get("status", "Offline")
        source = record.get("source", "Idle")
        clients = record.get("clients", "—")
        self.detail_label.setText(
            f"ROOM {room_id} · {status} · Now: {playing} · Source: {source} · "
            f"Listeners: {clients}"
        )
        self.queue_list.clear()
        for index, song in enumerate(record.get("queue", []), start=1):
            self.queue_list.addItem(
                f"{index}. {song.get('title', 'Unknown')} "
                f"— {song.get('requested_by', 'Unknown')}"
            )
        self.log_view.setPlainText("\n".join(self._logs.get(room_id, [])))
