"""Background replies from a local Ollama model."""
import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal


class LocalAIReplyWorker(QThread):
    completed = Signal(str, str, str)  # username, reply, fallback

    def __init__(self, username, message, endpoint, model, mode, fallback="", recent=()):
        super().__init__()
        self.username = str(username or "friend")[:48]
        self.message = " ".join(str(message or "").split())[:500]
        self.endpoint = str(endpoint or "http://127.0.0.1:11434").strip().rstrip("/")
        self.model = str(model or "").strip()
        self.mode = mode
        self.fallback = str(fallback or "")
        self.recent = tuple(recent)[-6:]

    def run(self):
        try:
            parsed = urlparse(self.endpoint)
            if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
                "localhost", "127.0.0.1", "::1"
            }:
                raise ValueError("Local AI endpoint must use localhost.")
            model = self.model
            if model.casefold() in {"", "auto", "detect"}:
                tags_request = Request(self.endpoint + "/api/tags", method="GET")
                with urlopen(tags_request, timeout=8) as response:
                    available = json.loads(response.read().decode("utf-8")).get("models", [])
                if not available:
                    raise RuntimeError("Ollama has no models installed yet.")
                newest = max(
                    available, key=lambda item: str(item.get("modified_at", ""))
                )
                model = str(newest.get("name") or newest.get("model") or "").strip()
            if not model:
                raise ValueError("No installed Ollama model could be detected.")
            if self.mode == "mention":
                instruction = (
                    "Reply directly to the member's message. Answer their question when "
                    "there is one; otherwise respond naturally to what they said."
                )
            else:
                instruction = (
                    "Make one brief, relevant room-chat reaction to this message. "
                    "Keep it casual; don't force a question."
                )
            recent = "\n".join(f"- {item}" for item in self.recent) or "(none)"
            prompt = (
                "You are CrowBot, a witty, warm bird-themed DJ and game host in an IMVU "
                "room. You have a playful personality, notice the conversation, and make "
                "short, friendly comments. Keep replies respectful and never bully, "
                "sexualize, or make cruel judgments about members. You only see the text "
                "provided; never claim to see an avatar, image, or room detail. "
                "Use one natural sentence, under 220 characters. Avoid repeating these "
                f"recent lines:\n{recent}\n\n"
                f"{instruction}\nMember: @{self.username}\nMessage: {self.message}\n"
                "CrowBot:"
            )
            body = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.9, "num_predict": 80},
            }).encode("utf-8")
            request = Request(
                self.endpoint + "/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=40) as response:
                data = json.loads(response.read().decode("utf-8"))
            reply = " ".join(str(data.get("response") or "").split()).strip()
            if not reply:
                raise RuntimeError("The local model returned an empty reply.")
            self.completed.emit(self.username, reply[:250], self.fallback)
        except Exception:
            self.completed.emit(self.username, "", self.fallback)
