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
        webhook_url = os.environ.get("SCARPSHIELD_DISCORD_WEBHOOK_URL") or \
            self.settings.get("webhook_url", "")
        if not webhook_url:
            print("[!] Discord webhook URL not set. Skipping.")
            return

        # Fallback to plain text when metadata is not available
        if not metadata:
            content = f"```\n{message}\n```"
            if len(content) > MAX_DISCORD_LENGTH:
                content = content[:MAX_DISCORD_LENGTH - 20] + "\n... [truncated]"

            payload = json.dumps({
                "content": content,
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
                print(f"[!] Discord alert failed: {e}")
            return

        # Color by severity
        severity = metadata.get("severity", "INFO")
        color_map = {
            "CRITICAL": 0xFF6B35,  # Orange-red
            "WARNING": 0xFFCC00,   # Gold
            "INFO": 0x00D9FF,      # Cyan
        }
        color = color_map.get(severity, 0x00D9FF)

        # Build embed fields from metadata
        event_type = metadata.get("event_type", "Alert")
        contract = metadata.get("contract", "Unknown")
        chain = metadata.get("chain", "ethereum")

        # Block explorer URL
        explorer_urls = {
            "ethereum": "https://etherscan.io",
            "polygon": "https://polygonscan.com",
            "bsc": "https://bscscan.com",
            "arbitrum": "https://arbiscan.io",
            "base": "https://basescan.org",
        }
        explorer = explorer_urls.get(chain, "https://etherscan.io")

        fields = [
            {"name": "Event", "value": event_type, "inline": True},
            {"name": "Chain", "value": chain.capitalize(), "inline": True},
            {"name": "Severity", "value": severity, "inline": True},
            {"name": "Contract", "value": f"`{contract}`", "inline": False},
        ]

        # Add tx hash link if available
        tx_hash = metadata.get("tx_hash", "")
        if tx_hash:
            fields.append({
                "name": "Transaction",
                "value": f"[View on Explorer]({explorer}/tx/{tx_hash})",
                "inline": False
            })

        description = message[:200] if len(message) > 200 else message
        if len(description) > MAX_DISCORD_LENGTH:
            description = description[:MAX_DISCORD_LENGTH - 20] + "\n... [truncated]"

        embed = {
            "title": f"⚠️ ScarpShield Alert — {event_type}" if severity != "INFO" else f"ScarpShield Alert — {event_type}",
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {"text": "ScarpShield • The Outer Wall of Defense"},
            "timestamp": metadata.get("timestamp", ""),
        }

        payload = json.dumps({
            "embeds": [embed],
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
            print(f"[!] Discord alert failed: {e}")
