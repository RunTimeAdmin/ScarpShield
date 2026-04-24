# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import asyncio
import json
import os
import urllib.request
import urllib.error

from .base import AlertBackend

MAX_DISCORD_LENGTH = 2000


class DiscordAlert(AlertBackend):
    """Send alerts to a Discord channel via webhook."""

    async def send(self, message: str, metadata: dict = None):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sync, message, metadata)

    def _send_sync(self, message: str, metadata: dict = None):
        url = os.environ.get("SCARPSHIELD_DISCORD_WEBHOOK_URL") or \
            self.settings.get("webhook_url", "")
        if not url:
            print("[!] Discord webhook URL not set. Skipping.")
            return

        content = f"```\n{message}\n```"
        if len(content) > MAX_DISCORD_LENGTH:
            content = content[:MAX_DISCORD_LENGTH - 20] + "\n... [truncated]"

        payload = json.dumps({
            "content": content,
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
