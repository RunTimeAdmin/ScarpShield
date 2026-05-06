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
        webhook_url = os.environ.get("SCARPSHIELD_SLACK_WEBHOOK_URL") or \
            self.settings.get("webhook_url", "")
        if not webhook_url:
            print("[!] Slack webhook URL not set. Skipping.")
            return

        # Fallback to plain text when metadata is not available
        if not metadata:
            payload = json.dumps({
                "text": f"```{message}```",
                "username": "ScarpShield"
            }).encode("utf-8")

            req = urllib.request.Request(
                webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                urllib.request.urlopen(req, timeout=10)
            except urllib.error.URLError as e:
                print(f"[!] Slack alert failed: {e}")
            return

        severity = metadata.get("severity", "INFO")
        event_type = metadata.get("event_type", "Alert")
        contract = metadata.get("contract", "Unknown")
        chain = metadata.get("chain", "ethereum")

        # Severity emoji
        emoji_map = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}
        emoji = emoji_map.get(severity, "ℹ️")

        # Block explorer
        explorer_urls = {
            "ethereum": "https://etherscan.io",
            "polygon": "https://polygonscan.com",
            "bsc": "https://bscscan.com",
            "arbitrum": "https://arbiscan.io",
            "base": "https://basescan.org",
        }
        explorer = explorer_urls.get(chain, "https://etherscan.io")

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} ScarpShield — {event_type}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                    {"type": "mrkdwn", "text": f"*Chain:*\n{chain.capitalize()}"},
                    {"type": "mrkdwn", "text": f"*Event:*\n{event_type}"},
                    {"type": "mrkdwn", "text": f"*Contract:*\n`{contract}`"},
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"```{message[:500]}```"}
            },
        ]

        # Add tx hash button if available
        tx_hash = metadata.get("tx_hash", "")
        if tx_hash:
            blocks.append({
                "type": "actions",
                "elements": [{
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View Transaction"},
                    "url": f"{explorer}/tx/{tx_hash}"
                }]
            })

        blocks.append({"type": "divider"})

        payload = json.dumps({
            "blocks": blocks,
            "text": f"ScarpShield Alert: {event_type} on {chain}",  # fallback text
            "username": "ScarpShield"
        }).encode("utf-8")

        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.URLError as e:
            print(f"[!] Slack alert failed: {e}")
