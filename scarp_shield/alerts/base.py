# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

from abc import ABC, abstractmethod
from datetime import datetime, timezone


# Severity levels
SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"
SEVERITY_CRITICAL = "CRITICAL"


def classify_severity(event_type, details=""):
    """Classify alert severity based on event type."""
    critical_events = {"OwnershipTransferred", "upgradeTo", "upgradeToAndCall",
                       "renounceOwnership", "transferOwnership", "AdminCall"}
    warning_events = {"Approval", "LargeTransfer"}

    if event_type in critical_events:
        return SEVERITY_CRITICAL
    elif event_type in warning_events:
        return SEVERITY_WARNING
    else:
        return SEVERITY_INFO


def format_alert(event_type, contract, details, chain="ethereum", severity=None):
    """Format a standard alert message."""
    if severity is None:
        severity = classify_severity(event_type)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"--- ScarpShield Alert [{severity}] ---\n"
        f"Time:     {ts}\n"
        f"Severity: {severity}\n"
        f"Chain:    {chain}\n"
        f"Contract: {contract}\n"
        f"Event:    {event_type}\n"
        f"Details:  {details}\n"
        f"{'=' * 33}"
    )


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
        details: str, chain: str = "ethereum", severity: str = None
    ) -> str:
        """Format a standard alert message."""
        return format_alert(event_type, contract, details, chain, severity)
