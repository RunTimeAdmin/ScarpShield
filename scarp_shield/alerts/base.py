# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

from abc import ABC, abstractmethod
from datetime import datetime, timezone


class AlertBackend(ABC):
    """Base class for all alert backends."""

    def __init__(self, settings: dict):
        self.settings = settings

    @abstractmethod
    async def send(self, message: str, metadata: dict = None):
        """Send an alert message."""
        pass

    def format_alert(
        self, event_type: str, contract: str,
        details: str, chain: str = "ethereum"
    ) -> str:
        """Format a standard alert message."""
        ts = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        return (
            f"--- ScarpShield Alert ---\n"
            f"Time:     {ts}\n"
            f"Chain:    {chain}\n"
            f"Contract: {contract}\n"
            f"Event:    {event_type}\n"
            f"Details:  {details}\n"
            f"-------------------------"
        )
