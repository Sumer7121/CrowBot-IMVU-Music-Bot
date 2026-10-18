"""Non-invasive test for simultaneous IMVU room listeners.

Usage:
    python tools/two_room_probe.py --list
    python tools/two_room_probe.py --rooms
    python tools/two_room_probe.py --rooms --reply-ping

Run in the existing bot Chrome (CDP 9222). This doesn't change the main
CrowBot application, store credentials, or start any music streams.
"""
import argparse
import queue
import threading
import time

# Support direct execution: python tools/two_room_probe.py --list
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bot.imvu_web_controller import IMVUWebController


def watch_room(room_url, output, stop, reply_ping=False):
    controller = IMVUWebController()
    try:
        controller.connect()
        if controller.find_imvu_room(room_url) is None:
            raise RuntimeError("Requested room tab is no longer open")
        controller.ensure_joined(timeout_ms=30000)
        controller.prime_chat_listener()
        output.put((room_url, "READY", ""))
        while not stop.is_set():
            messages = controller.wait_for_new_chat_messages(timeout_ms=450)
            for message in messages:
                user = message.get("username", "?")
                body = (message.get("message") or "").strip()
                output.put((room_url, user, body))
                if reply_ping and body.casefold() == "!ping":
                    # Send only into this exact room, from its own worker.
                    controller.send_chat_message(f"🏓 CrowBot pong in this room, {user}!")
    except Exception as error:
        output.put((room_url, "ERROR", str(error)))
    finally:
        controller.disconnect()


def main():
    parser = argparse.ArgumentParser(description="IMVU two-room isolation probe")
    parser.add_argument("--list", action="store_true", help="List room tabs without listening")
    parser.add_argument("--rooms", action="store_true", help="Listen in exactly two room tabs")
    parser.add_argument("--reply-ping", action="store_true", help="Reply to !ping in the matching room")
    args = parser.parse_args()
    if not (args.list or args.rooms):
        parser.error("Choose --list or --rooms")

    controller = IMVUWebController()
    try:
        controller.connect()
        rooms = controller.list_imvu_rooms()
    finally:
        controller.disconnect()
    if args.list:
        for i, room in enumerate(rooms, 1):
            print(f"{i}. {room['title']} | {room['url']}")
        print(f"Total room tabs: {len(rooms)}")
        return
    if len(rooms) != 2:
        parser.error(f"Open exactly two IMVU room tabs (found {len(rooms)}).")
    if rooms[0]["url"].rstrip("/") == rooms[1]["url"].rstrip("/"):
        parser.error("Open two DIFFERENT room URLs.")

    output = queue.Queue()
    stop = threading.Event()
    threads = [
        threading.Thread(target=watch_room, args=(room["url"], output, stop, args.reply_ping), daemon=True)
        for room in rooms
    ]
    for worker in threads:
        worker.start()
    print("Monitoring both rooms. Use !ping in each room. Ctrl+C to stop.")
    print("Responses only enabled with --reply-ping. No music queues are changed.")
    try:
        while True:
            try:
                url, who, message = output.get(timeout=0.5)
                print(f"[{url}] {who}: {message}", flush=True)
            except queue.Empty:
                if not any(thread.is_alive() for thread in threads):
                    break
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        stop.set()
        for worker in threads:
            worker.join(timeout=3)


if __name__ == "__main__":
    main()
