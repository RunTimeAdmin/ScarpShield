# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import asyncio
import time
from collections import defaultdict

from .console import ConsoleAlert
from .email_alert import EmailAlert
from .discord_alert import DiscordAlert
from .slack_alert import SlackAlert
from .telegram_alert import TelegramAlert

BACKENDS = {
    "console": ConsoleAlert,
    "email": EmailAlert,
    "discord": DiscordAlert,
    "slack": SlackAlert,
    "telegram": TelegramAlert,
}


class AlertDispatcher:
    """Routes alerts to all enabled backends."""

    DEDUP_WINDOW = 60  # seconds

    def __init__(self, config: dict):
        self.backends = []
        alerts_cfg = config.get("alerts", {})
        for name, cls in BACKENDS.items():
            channel = alerts_cfg.get(name, {})
            if channel.get("enabled", False):
                settings = channel.get("settings", {})
                self.backends.append(
                    (name, cls(settings))
                )

        if not self.backends:
            # Always have console as fallback
            self.backends.append(
                ("console", ConsoleAlert({}))
            )

        self._recent_alerts = {}  # key -> (timestamp, count)

    def _dedup_key(self, metadata):
        """Generate a deduplication key from metadata."""
        if not metadata:
            return None
        event_type = metadata.get("event_type", "")
        contract = metadata.get("contract", "")
        chain = metadata.get("chain", "")
        return f"{event_type}:{contract}:{chain}"

    def _should_suppress(self, metadata):
        """Check if this alert should be suppressed (duplicate within window)."""
        key = self._dedup_key(metadata)
        if not key:
            return False

        # Never suppress CRITICAL alerts
        severity = (metadata or {}).get("severity", "")
        if severity == "CRITICAL":
            return False

        now = time.time()
        if key in self._recent_alerts:
            last_time, count = self._recent_alerts[key]
            if now - last_time < self.DEDUP_WINDOW:
                # Still within window — suppress and increment count
                self._recent_alerts[key] = (last_time, count + 1)
                return True

        # New alert or window expired — allow and reset
        self._recent_alerts[key] = (now, 1)
        return False

    def _cleanup_old_entries(self):
        """Remove expired entries from the dedup cache."""
        now = time.time()
        expired = [k for k, (ts, _) in self._recent_alerts.items()
                   if now - ts >= self.DEDUP_WINDOW]
        for k in expired:
            del self._recent_alerts[k]

    async def dispatch(self, message: str, metadata=None):
        """Send alert to all enabled backends."""
        # Periodic cleanup
        self._cleanup_old_entries()

        # Check deduplication
        if self._should_suppress(metadata):
            key = self._dedup_key(metadata)
            _, count = self._recent_alerts.get(key, (0, 0))
            if count == 2:  # Log once when suppression starts
                print(f"[~] Suppressing duplicate alerts for {key} (60s window)")
            return

        tasks = []
        for name, backend in self.backends:
            tasks.append(
                self._safe_send(name, backend, message, metadata)
            )
        await asyncio.gather(*tasks)

    async def _safe_send(
        self, name, backend, message, metadata
    ):
        """Send with error handling per backend."""
        try:
            await backend.send(message, metadata)
        except Exception as e:
            print(f"[!] Alert backend '{name}' error: {e}")

    def list_enabled(self) -> list[str]:
        """Return names of enabled backends."""
        return [name for name, _ in self.backends]
