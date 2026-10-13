import os
import shutil
import subprocess
from pathlib import Path


class IMVUClientDetector:
    """
    Detects and launches supported IMVU client environments.

    Supported modes:
        Auto Detect
        IMVU Web (Chrome)
        IMVU Desktop
        IMVU Classic

    This class does NOT:
        - store IMVU passwords
        - read browser cookies
        - extract IMVU session tokens
        - modify IMVU client files
    """

    AUTO_DETECT = "Auto Detect"
    WEB_CHROME = "IMVU Web (Chrome)"
    DESKTOP = "IMVU Desktop"
    CLASSIC = "IMVU Classic"

    def __init__(self):

        self.chrome_path = None
        self.desktop_path = None
        self.classic_path = None

        self.refresh()

    # =========================================================
    # REFRESH DETECTION
    # =========================================================

    def refresh(self):

        self.chrome_path = (
            self._find_chrome()
        )

        self.desktop_path = (
            self._find_imvu_desktop()
        )

        self.classic_path = (
            self._find_imvu_classic()
        )

    # =========================================================
    # CHROME
    # =========================================================

    def _find_chrome(self):

        possible_paths = [
            Path(
                r"C:\Program Files\Google\Chrome"
                r"\Application\chrome.exe"
            ),

            Path(
                r"C:\Program Files (x86)\Google\Chrome"
                r"\Application\chrome.exe"
            ),
        ]

        local_app_data = os.environ.get(
            "LOCALAPPDATA"
        )

        if local_app_data:

            possible_paths.append(
                Path(local_app_data)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe"
            )

        for path in possible_paths:

            if path.exists():
                return path

        command_path = shutil.which(
            "chrome.exe"
        )

        if command_path:
            return Path(command_path)

        return None

    # =========================================================
    # IMVU DESKTOP
    # =========================================================

    def _find_imvu_desktop(self):

        possible_paths = []

        local_app_data = os.environ.get(
            "LOCALAPPDATA"
        )

        program_files = os.environ.get(
            "PROGRAMFILES"
        )

        program_files_x86 = os.environ.get(
            "PROGRAMFILES(X86)"
        )

        if local_app_data:

            possible_paths.extend(
                [
                    Path(local_app_data)
                    / "IMVU"
                    / "IMVU Desktop"
                    / "IMVU.exe",

                    Path(local_app_data)
                    / "Programs"
                    / "IMVU"
                    / "IMVU.exe",
                ]
            )

        if program_files:

            possible_paths.extend(
                [
                    Path(program_files)
                    / "IMVU"
                    / "IMVU.exe",

                    Path(program_files)
                    / "IMVU Desktop"
                    / "IMVU.exe",
                ]
            )

        if program_files_x86:

            possible_paths.extend(
                [
                    Path(program_files_x86)
                    / "IMVU"
                    / "IMVU.exe",

                    Path(program_files_x86)
                    / "IMVU Desktop"
                    / "IMVU.exe",
                ]
            )

        for path in possible_paths:

            if path.exists():
                return path

        return None

    # =========================================================
    # IMVU CLASSIC
    # =========================================================

    def _find_imvu_classic(self):

        possible_paths = []

        app_data = os.environ.get(
            "APPDATA"
        )

        local_app_data = os.environ.get(
            "LOCALAPPDATA"
        )

        program_files = os.environ.get(
            "PROGRAMFILES"
        )

        program_files_x86 = os.environ.get(
            "PROGRAMFILES(X86)"
        )

        if app_data:

            possible_paths.extend(
                [
                    Path(app_data)
                    / "IMVUClient"
                    / "IMVUClient.exe",
                ]
            )

        if local_app_data:

            possible_paths.extend(
                [
                    Path(local_app_data)
                    / "IMVU"
                    / "IMVUClient.exe",

                    Path(local_app_data)
                    / "IMVUClient"
                    / "IMVUClient.exe",
                ]
            )

        if program_files:

            possible_paths.append(
                Path(program_files)
                / "IMVU"
                / "IMVUClient.exe"
            )

        if program_files_x86:

            possible_paths.append(
                Path(program_files_x86)
                / "IMVU"
                / "IMVUClient.exe"
            )

        for path in possible_paths:

            if path.exists():
                return path

        return None

    # =========================================================
    # PROCESS DETECTION
    # =========================================================

    def _get_running_processes(self):

        try:

            result = subprocess.run(
                [
                    "tasklist",
                    "/FO",
                    "CSV",
                    "/NH",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if hasattr(
                        subprocess,
                        "CREATE_NO_WINDOW"
                    )
                    else 0
                ),
            )

            return (
                result.stdout.lower()
            )

        except Exception:

            return ""

    def is_chrome_running(self):

        processes = (
            self._get_running_processes()
        )

        return (
            '"chrome.exe"' in processes
        )

    def is_desktop_running(self):

        processes = (
            self._get_running_processes()
        )

        possible_names = [
            '"imvu.exe"',
            '"imvudesktop.exe"',
        ]

        return any(
            name in processes
            for name in possible_names
        )

    def is_classic_running(self):

        processes = (
            self._get_running_processes()
        )

        possible_names = [
            '"imvuclient.exe"',
        ]

        return any(
            name in processes
            for name in possible_names
        )

    # =========================================================
    # CLIENT STATUS
    # =========================================================

    def get_status(self):

        self.refresh()

        return {
            self.WEB_CHROME: {
                "installed": (
                    self.chrome_path
                    is not None
                ),
                "running": (
                    self.is_chrome_running()
                ),
                "path": (
                    str(self.chrome_path)
                    if self.chrome_path
                    else ""
                ),
            },

            self.DESKTOP: {
                "installed": (
                    self.desktop_path
                    is not None
                ),
                "running": (
                    self.is_desktop_running()
                ),
                "path": (
                    str(self.desktop_path)
                    if self.desktop_path
                    else ""
                ),
            },

            self.CLASSIC: {
                "installed": (
                    self.classic_path
                    is not None
                ),
                "running": (
                    self.is_classic_running()
                ),
                "path": (
                    str(self.classic_path)
                    if self.classic_path
                    else ""
                ),
            },
        }

    # =========================================================
    # AUTO DETECT
    # =========================================================

    def auto_detect(self):

        self.refresh()

        # Prefer a currently running client.

        if self.is_desktop_running():
            return self.DESKTOP

        if self.is_classic_running():
            return self.CLASSIC

        if self.is_chrome_running():
            return self.WEB_CHROME

        # Otherwise prefer installed clients.

        if self.desktop_path:
            return self.DESKTOP

        if self.classic_path:
            return self.CLASSIC

        if self.chrome_path:
            return self.WEB_CHROME

        return None

    # =========================================================
    # RESOLVE CLIENT
    # =========================================================

    def resolve_client(
        self,
        selected_client
    ):

        if (
            selected_client
            == self.AUTO_DETECT
        ):
            return self.auto_detect()

        return selected_client

    # =========================================================
    # LAUNCH CLIENT
    # =========================================================

    def launch(
        self,
        selected_client,
        url=None
    ):

        self.refresh()

        client = self.resolve_client(
            selected_client
        )

        if not client:

            return {
                "success": False,
                "client": None,
                "message": (
                    "No supported IMVU client "
                    "environment was detected."
                ),
            }

        # -----------------------------------------------------
        # IMVU WEB / CHROME
        # -----------------------------------------------------

        if client == self.WEB_CHROME:

            if not self.chrome_path:

                return {
                    "success": False,
                    "client": client,
                    "message": (
                        "Google Chrome could "
                        "not be found."
                    ),
                }

            command = [
                str(self.chrome_path)
            ]

            if url:
                command.append(url)

            try:

                subprocess.Popen(
                    command
                )

                return {
                    "success": True,
                    "client": client,
                    "message": (
                        "Google Chrome launched."
                    ),
                }

            except Exception as error:

                return {
                    "success": False,
                    "client": client,
                    "message": str(error),
                }

        # -----------------------------------------------------
        # IMVU DESKTOP
        # -----------------------------------------------------

        if client == self.DESKTOP:

            if not self.desktop_path:

                return {
                    "success": False,
                    "client": client,
                    "message": (
                        "IMVU Desktop could "
                        "not be found."
                    ),
                }

            try:

                subprocess.Popen(
                    [
                        str(
                            self.desktop_path
                        )
                    ]
                )

                return {
                    "success": True,
                    "client": client,
                    "message": (
                        "IMVU Desktop launched."
                    ),
                }

            except Exception as error:

                return {
                    "success": False,
                    "client": client,
                    "message": str(error),
                }

        # -----------------------------------------------------
        # IMVU CLASSIC
        # -----------------------------------------------------

        if client == self.CLASSIC:

            if not self.classic_path:

                return {
                    "success": False,
                    "client": client,
                    "message": (
                        "IMVU Classic could "
                        "not be found."
                    ),
                }

            try:

                subprocess.Popen(
                    [
                        str(
                            self.classic_path
                        )
                    ]
                )

                return {
                    "success": True,
                    "client": client,
                    "message": (
                        "IMVU Classic launched."
                    ),
                }

            except Exception as error:

                return {
                    "success": False,
                    "client": client,
                    "message": str(error),
                }

        return {
            "success": False,
            "client": client,
            "message": (
                "Unsupported IMVU client."
            ),
        }