from pathlib import Path

ROOT = Path(r"D:\IMVU-Music-Bot")

youtube = ROOT / "music" / "youtube_owned.py"
radio = ROOT / "radio_server" / "server.py"


# ============================================================
# YT-DLP
# ============================================================

text = youtube.read_text(encoding="utf-8")

old = '''                process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
'''

new = '''                process = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if hasattr(subprocess, "CREATE_NO_WINDOW")
                        else 0
                    ),
'''

count = text.count(old)

if count != 2:
    raise RuntimeError(
        f"Expected exactly 2 captured yt-dlp subprocess.run calls; found {count}."
    )

text = text.replace(old, new)


old = '''                process = subprocess.run(
                    command,
                    timeout=600,
                )
'''

new = '''                process = subprocess.run(
                    command,
                    timeout=600,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if hasattr(subprocess, "CREATE_NO_WINDOW")
                        else 0
                    ),
                )
'''

if text.count(old) != 1:
    raise RuntimeError(
        "Could not uniquely locate yt-dlp download subprocess.run call."
    )

text = text.replace(old, new)

youtube.write_text(text, encoding="utf-8")

print("[OK] yt-dlp subprocess windows suppressed.")


# ============================================================
# FFMPEG RADIO PROCESS
# ============================================================

text = radio.read_text(encoding="utf-8")

old = '''                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=None,
                    bufsize=0,
                )
'''

new = '''                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=None,
                    bufsize=0,
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if hasattr(subprocess, "CREATE_NO_WINDOW")
                        else 0
                    ),
                )
'''

if text.count(old) != 1:
    raise RuntimeError(
        "Could not uniquely locate radio FFmpeg subprocess.Popen call."
    )

text = text.replace(old, new)

radio.write_text(text, encoding="utf-8")

print("[OK] FFmpeg radio subprocess window suppressed.")
print("[OK] Patch complete.")
