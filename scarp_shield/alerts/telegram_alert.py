# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import json
import urllib.request
import urllib.error

from .base import AlertBackend


class TelegramAlert(AlertBackend):
    """Send alerts via Telegram bot (optional)."""

    async def send(self, message: str, metadata: dict = None):
        token = self.settings.get("bot_token", "")
        chat_id = self.settings.get("chat_id", "")
        if not all([token, chat_id]):
            print("[!] Telegram not configured. Skipping.")
            return

        url = (
            f"https://api.telegram.org/bot{token}"
            f"/sendMessage"
        )
        payload = json.dumps({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            urllib.request.urlopen(req)
        except urllib.error.URLError as e:
            print(f"[!] Telegram alert failed: {e}")
