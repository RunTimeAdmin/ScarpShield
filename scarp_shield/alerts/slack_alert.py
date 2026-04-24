# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import asyncio
import json
import os
import urllib.request
import urllib.error

from .base import AlertBackend


class SlackAlert(AlertBackend):
    """Send alerts to a Slack channel via webhook."""

    async def send(self, message: str, metadata: dict = None):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sync, message, metadata)

    def _send_sync(self, message: str, metadata: dict = None):
        url = os.environ.get("SCARPSHIELD_SLACK_WEBHOOK_URL") or \
            self.settings.get("webhook_url", "")
        if not url:
            print("[!] Slack webhook URL not set. Skipping.")
            return

        payload = json.dumps({
            "text": f"```{message}```",
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
            print(f"[!] Slack alert failed: {e}")
