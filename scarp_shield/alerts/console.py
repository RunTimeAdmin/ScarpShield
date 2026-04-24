# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

from .base import AlertBackend


class ConsoleAlert(AlertBackend):
    """Print alerts to stdout. Always enabled."""

    async def send(self, message: str, metadata: dict = None):
        print(f"\n{message}\n")
