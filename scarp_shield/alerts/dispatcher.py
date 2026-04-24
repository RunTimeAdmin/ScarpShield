# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import asyncio

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

    async def dispatch(self, message: str, metadata=None):
        """Send alert to all enabled backends."""
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
