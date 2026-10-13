import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal


def get_application_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_cloudflared_path():
    app_directory = get_application_directory()

    bundled_path = app_directory / "bin" / "cloudflared.exe"
    if bundled_path.exists():
        return bundled_path

    development_path = app_directory / "cloudflared.exe"
    if development_path.exists():
        return development_path

    return None


class CloudflareTunnel(QObject):
    tunnel_started = Signal(str)
    tunnel_stopped = Signal()
    tunnel_error = Signal(str)
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self.local_url = "http://127.0.0.1:8765"

        self.process = None
        self.reader_thread = None
        self.validation_thread = None

        self.public_url = ""
        self.running = False

        self._lock = threading.Lock()
        self._candidate_url = ""
        self._ready_emitted = False

    # =========================================================
    # STATUS
    # =========================================================

    def is_running(self):
        return (
            self.process is not None
            and self.process.poll() is None
            and self.running
        )

    def get_public_url(self):
        with self._lock:
            return self.public_url

    def get_stream_url(self):
        public_url = self.get_public_url()
        if not public_url:
            return ""
        return public_url.rstrip("/") + "/stream.mp3"

    # =========================================================
    # START
    # =========================================================

    def start(self):
        if self.is_running():
            stream_url = self.get_stream_url()

            if stream_url and self._ready_emitted:
                self.tunnel_started.emit(stream_url)
                return False

            self.status_changed.emit(
                "Cloudflare process is running; waiting for tunnel validation..."
            )
            return False

        cloudflare_path = get_cloudflared_path()

        if not cloudflare_path:
            self.tunnel_error.emit(
                "cloudflared.exe could not be found.\n\n"
                "Expected installed location:\n"
                "bin\\cloudflared.exe"
            )
            return False

        with self._lock:
            self.public_url = ""
            self._candidate_url = ""
            self._ready_emitted = False

        self.status_changed.emit("Starting Cloudflare tunnel...")

        try:
            creation_flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creation_flags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                [
                    str(cloudflare_path),
                    "tunnel",
                    "--url",
                    self.local_url,
                    "--no-autoupdate",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )

            self.running = True

            self.reader_thread = threading.Thread(
                target=self._read_output,
                name="CloudflareOutputReader",
                daemon=True,
            )
            self.reader_thread.start()

            return True

        except Exception as error:
            self.process = None
            self.running = False
            self.tunnel_error.emit(str(error))
            return False

    # =========================================================
    # CLOUDFLARED OUTPUT
    # =========================================================

    def _read_output(self):
        try:
            if not self.process or not self.process.stdout:
                return

            pattern = re.compile(
                r"https://[a-zA-Z0-9-]+\.trycloudflare\.com"
            )

            for line in self.process.stdout:
                if not self.running:
                    break

                clean_line = line.strip()

                if clean_line:
                    print(f"[Cloudflare] {clean_line}")

                match = pattern.search(clean_line)
                if not match:
                    continue

                candidate_url = match.group(0).rstrip("/")

                with self._lock:
                    already_testing = (
                        candidate_url == self._candidate_url
                        and self.validation_thread is not None
                        and self.validation_thread.is_alive()
                    )
                    already_ready = (
                        candidate_url == self.public_url
                        and self._ready_emitted
                    )

                    if not already_testing and not already_ready:
                        self._candidate_url = candidate_url

                if already_testing or already_ready:
                    continue

                self.status_changed.emit(
                    "Cloudflare URL received. Waiting for public availability..."
                )

                self.validation_thread = threading.Thread(
                    target=self._validate_candidate,
                    args=(candidate_url,),
                    name="CloudflareTunnelValidator",
                    daemon=True,
                )
                self.validation_thread.start()

            if (
                self.running
                and self.process
                and self.process.poll() is not None
            ):
                return_code = self.process.returncode
                self.running = False

                with self._lock:
                    self.public_url = ""
                    self._candidate_url = ""
                    self._ready_emitted = False

                if return_code != 0:
                    self.tunnel_error.emit(
                        f"Cloudflare tunnel stopped with exit code {return_code}."
                    )
                else:
                    self.status_changed.emit("Cloudflare tunnel stopped.")
                    self.tunnel_stopped.emit()

        except Exception as error:
            if self.running:
                self.tunnel_error.emit(str(error))

    # =========================================================
    # FRESH WINDOWS DNS CHECK
    # =========================================================

    def _resolve_with_fresh_process(self, hostname):
        """
        Resolve the Quick Tunnel hostname in a fresh Windows process.

        This intentionally avoids relying only on the long-running GUI
        process's resolver state. PowerShell is tried first. nslookup is
        used as a fallback.
        """
        creation_flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creation_flags = subprocess.CREATE_NO_WINDOW

        safe_hostname = hostname.replace("'", "''")

        powershell_command = (
            "$ErrorActionPreference='Stop'; "
            f"$r=Resolve-DnsName -Name '{safe_hostname}' "
            "-Type A -DnsOnly -ErrorAction Stop; "
            "$ips=@($r | Where-Object {$_.IPAddress} | "
            "Select-Object -ExpandProperty IPAddress); "
            "if ($ips.Count -eq 0) { exit 2 }; "
            "$ips -join ','"
        )

        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    powershell_command,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                creationflags=creation_flags,
            )

            output = (result.stdout or "").strip()

            if result.returncode == 0 and output:
                return True, f"PowerShell DNS: {output}"

            ps_error = (result.stderr or "").strip()

        except Exception as error:
            ps_error = str(error)

        try:
            result = subprocess.run(
                ["nslookup.exe", hostname, "1.1.1.1"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                creationflags=creation_flags,
            )

            combined = (
                (result.stdout or "") + "\n" + (result.stderr or "")
            ).strip()

            lowered = combined.lower()

            failed_markers = (
                "non-existent domain",
                "can't find",
                "server failed",
                "timed out",
                "no response from server",
            )

            if (
                result.returncode == 0
                and combined
                and not any(marker in lowered for marker in failed_markers)
            ):
                return True, "nslookup DNS resolved successfully"

            return False, (
                f"PowerShell DNS failed: {ps_error or 'no result'}; "
                f"nslookup failed: {combined or 'no result'}"
            )

        except Exception as error:
            return False, (
                f"PowerShell DNS failed: {ps_error or 'no result'}; "
                f"nslookup error: {error}"
            )

    # =========================================================
    # PUBLIC STREAM CHECK IN FRESH PROCESS
    # =========================================================

    def _probe_stream_with_fresh_process(self, stream_url):
        """
        Validate the public Cloudflare stream with Windows curl.exe.

        curl.exe has already been proven on this machine to:
          - resolve the trycloudflare.com hostname,
          - complete TLS,
          - receive HTTP 200,
          - receive audio/mpeg bytes through the tunnel.

        The stream is continuous, so we intentionally stop after receiving
        a small amount of audio instead of waiting for EOF.
        """
        creation_flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creation_flags = subprocess.CREATE_NO_WINDOW

        try:
            command = [
                "curl.exe",
                "--silent",
                "--show-error",
                "--location",
                "--fail",
                "--max-time",
                "15",
                "--range",
                "0-4095",
                "--output",
                "-",
                stream_url,
            ]

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags,
            )

            received = bytearray()
            deadline = time.time() + 15.0

            while time.time() < deadline:
                if not self.running:
                    try:
                        process.kill()
                    except Exception:
                        pass
                    return False, "Tunnel stopped during curl validation."

                chunk = process.stdout.read(1024) if process.stdout else b""

                if chunk:
                    received.extend(chunk)

                    if len(received) >= 4096:
                        try:
                            process.kill()
                        except Exception:
                            pass

                        try:
                            process.wait(timeout=2)
                        except Exception:
                            pass

                        return True, f"BYTES={len(received)}"

                if process.poll() is not None:
                    break

                time.sleep(0.05)

            if len(received) > 0:
                try:
                    if process.poll() is None:
                        process.kill()
                except Exception:
                    pass

                return True, f"BYTES={len(received)}"

            try:
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass

            stderr_text = ""

            try:
                if process.stderr:
                    stderr_text = process.stderr.read().decode(
                        "utf-8",
                        errors="replace",
                    ).strip()
            except Exception:
                pass

            return False, (
                stderr_text
                or f"curl.exe returned no audio bytes "
                   f"(exit code {process.poll()})."
            )

        except FileNotFoundError:
            return False, (
                "curl.exe was not found. Windows curl.exe is required "
                "for the public stream readiness check."
            )

        except Exception as error:
            return False, f"curl.exe validation error: {error}"

    # =========================================================
    # VALIDATION
    # =========================================================

    def _validate_candidate(self, candidate_url):
        stream_url = candidate_url.rstrip("/") + "/stream.mp3"
        hostname = candidate_url.split("://", 1)[-1].split("/", 1)[0]

        max_attempts = 90
        retry_delay_seconds = 1.0
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            if not self.running:
                return

            with self._lock:
                if candidate_url != self._candidate_url:
                    return

            print(
                f"[Cloudflare] Validation {attempt}/{max_attempts}: "
                f"fresh DNS check for {hostname}"
            )

            dns_ok, dns_message = self._resolve_with_fresh_process(hostname)

            if not dns_ok:
                last_error = dns_message
                print(
                    f"[Cloudflare] Validation not ready: {last_error}"
                )

                if attempt < max_attempts:
                    time.sleep(retry_delay_seconds)

                continue

            print(f"[Cloudflare] {dns_message}")
            print(
                f"[Cloudflare] DNS resolved. Testing public stream: "
                f"{stream_url}"
            )

            stream_ok, stream_message = (
                self._probe_stream_with_fresh_process(stream_url)
            )

            if not stream_ok:
                last_error = stream_message
                print(
                    f"[Cloudflare] Public stream not ready: {last_error}"
                )

                if attempt < max_attempts:
                    time.sleep(retry_delay_seconds)

                continue

            if not self.running:
                return

            with self._lock:
                if candidate_url != self._candidate_url:
                    return

                self.public_url = candidate_url
                self._ready_emitted = True

            print(
                f"[Cloudflare] Public stream returned audio: "
                f"{stream_message}"
            )
            print(
                "[Cloudflare] Quick Tunnel validated successfully: "
                f"{stream_url}"
            )

            self.status_changed.emit("Cloudflare tunnel ready.")
            self.tunnel_started.emit(stream_url)
            return

        if not self.running:
            return

        with self._lock:
            if candidate_url != self._candidate_url:
                return

        message = (
            "Cloudflare Quick Tunnel is still running, but its public "
            "stream did not become reachable within the validation window.\n\n"
            f"URL: {candidate_url}\n"
            f"Last error: {last_error}\n\n"
            "The tunnel was NOT restarted."
        )

        print(f"[Cloudflare] {message}")

        self.status_changed.emit(
            "Cloudflare tunnel is running but public stream validation timed out."
        )
        self.tunnel_error.emit(message)

    # =========================================================
    # STOP
    # =========================================================

    def stop(self):
        self.running = False

        with self._lock:
            self.public_url = ""
            self._candidate_url = ""
            self._ready_emitted = False

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)

            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                    self.process.wait(timeout=2)
                except Exception:
                    pass

            except Exception:
                pass

        self.process = None
        self.reader_thread = None
        self.validation_thread = None

        self.status_changed.emit("Cloudflare tunnel stopped.")

        self.tunnel_stopped.emit()
