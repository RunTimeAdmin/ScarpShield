# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import json
import urllib.request
import urllib.error

from .base import AlertBackend


class DiscordAlert(AlertBackend):
    """Send alerts to a Discord channel via webhook."""

    async def send(self, message: str, metadata: dict = None):
        url = self.settings.get("webhook_url", "")
        if not url:
            print("[!] Discord webhook URL not set. Skipping.")
            return

        payload = json.dumps({
            "content": f"```\n{message}\n```",
            "username": "ScarpShield"
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
            print(f"[!] Discord alert failed: {e}")
