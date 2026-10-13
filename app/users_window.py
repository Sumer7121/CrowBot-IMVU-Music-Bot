from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class UsersWindow(QDialog):

    users_changed = Signal()

    def __init__(
        self,
        user_manager,
        parent=None
    ):

        super().__init__(parent)

        self.user_manager = user_manager

        self.setWindowTitle(
            "IMVU Music Bot - Users"
        )

        self.setMinimumSize(
            550,
            500
        )

        layout = QVBoxLayout(self)

        # =========================================
        # TITLE
        # =========================================

        title = QLabel(
            "User Management"
        )

        title.setStyleSheet(
            """
            font-size: 24px;
            font-weight: bold;
            """
        )

        layout.addWidget(
            title
        )

        # =========================================
        # USER FORM
        # =========================================

        form = QFormLayout()

        self.username_input = QLineEdit()

        self.username_input.setPlaceholderText(
            "Enter IMVU username"
        )

        self.role_combo = QComboBox()

        self.role_combo.addItems(
            [
                "User",
                "DJ",
                "Moderator",
                "Owner",
            ]
        )

        form.addRow(
            "Username:",
            self.username_input
        )

        form.addRow(
            "Role:",
            self.role_combo
        )

        layout.addLayout(
            form
        )

        # =========================================
        # ADD / UPDATE
        # =========================================

        add_button = QPushButton(
            "Add / Update User"
        )

        add_button.clicked.connect(
            self.add_user
        )

        layout.addWidget(
            add_button
        )

        # =========================================
        # USER LIST
        # =========================================

        list_label = QLabel(
            "Configured Users"
        )

        list_label.setStyleSheet(
            """
            font-weight: bold;
            """
        )

        layout.addWidget(
            list_label
        )

        self.user_list = QListWidget()

        layout.addWidget(
            self.user_list
        )

        # =========================================
        # BUTTONS
        # =========================================

        buttons = QHBoxLayout()

        edit_button = QPushButton(
            "Edit Selected"
        )

        remove_button = QPushButton(
            "Remove Selected"
        )

        close_button = QPushButton(
            "Close"
        )

        edit_button.clicked.connect(
            self.edit_selected
        )

        remove_button.clicked.connect(
            self.remove_selected
        )

        close_button.clicked.connect(
            self.accept
        )

        buttons.addWidget(
            edit_button
        )

        buttons.addWidget(
            remove_button
        )

        buttons.addStretch()

        buttons.addWidget(
            close_button
        )

        layout.addLayout(
            buttons
        )

        # =========================================
        # INITIAL LOAD
        # =========================================

        self.refresh_users()

    # =============================================
    # ADD / UPDATE USER
    # =============================================

    def add_user(self):

        username = (
            self.username_input
            .text()
            .strip()
        )

        role = (
            self.role_combo
            .currentText()
        )

        if not username:

            QMessageBox.warning(
                self,
                "Missing Username",
                "Please enter a username."
            )

            return

        success = (
            self.user_manager.add_user(
                username,
                role
            )
        )

        if not success:

            QMessageBox.warning(
                self,
                "Error",
                "The user could not be added."
            )

            return

        self.username_input.clear()

        self.refresh_users()

        self.users_changed.emit()

    # =============================================
    # REFRESH USERS
    # =============================================

    def refresh_users(self):

        self.user_list.clear()

        users = (
            self.user_manager.get_users()
        )

        for user in users:

            username = user["username"]
            role = user["role"]

            self.user_list.addItem(
                f"{username} — {role}"
            )

    # =============================================
    # EDIT USER
    # =============================================

    def edit_selected(self):

        item = (
            self.user_list
            .currentItem()
        )

        if item is None:

            QMessageBox.information(
                self,
                "Select User",
                "Please select a user first."
            )

            return

        text = item.text()

        username = text.split(
            " — "
        )[0]

        user = (
            self.user_manager
            .get_user(username)
        )

        if user is None:
            return

        self.username_input.setText(
            user["username"]
        )

        index = (
            self.role_combo.findText(
                user["role"]
            )
        )

        if index >= 0:

            self.role_combo.setCurrentIndex(
                index
            )

    # =============================================
    # REMOVE USER
    # =============================================

    def remove_selected(self):

        item = (
            self.user_list
            .currentItem()
        )

        if item is None:

            QMessageBox.information(
                self,
                "Select User",
                "Please select a user first."
            )

            return

        text = item.text()

        username = text.split(
            " — "
        )[0]

        confirm = QMessageBox.question(
            self,
            "Remove User",
            f"Remove user '{username}'?"
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        success = (
            self.user_manager.remove_user(
                username
            )
        )

        if success:

            self.refresh_users()

            self.users_changed.emit()