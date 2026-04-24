# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import asyncio
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .base import AlertBackend


class EmailAlert(AlertBackend):
    """Send alerts via SMTP email."""

    async def send(self, message: str, metadata: dict = None):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_sync, message, metadata)

    def _send_sync(self, message: str, metadata: dict = None):
        host = self.settings.get("smtp_host", "")
        port = self.settings.get("smtp_port", 587)
        user = os.environ.get("SCARPSHIELD_SMTP_USER") or \
            self.settings.get("smtp_user", "")
        password = os.environ.get("SCARPSHIELD_SMTP_PASSWORD") or \
            self.settings.get("smtp_password", "")
        from_addr = self.settings.get("from_address", user)
        to_addrs = self.settings.get("to_addresses", [])

        if not all([host, user, password, to_addrs]):
            print("[!] Email alert misconfigured. Skipping.")
            return

        event_type = (metadata or {}).get("event_type", "Alert")
        contract = (metadata or {}).get("contract", "")
        chain = (metadata or {}).get("chain", "")

        if contract and chain:
            subject = (
                f"ScarpShield — {event_type} on "
                f"{contract[:10]}... [{chain}]"
            )
        elif event_type:
            subject = f"ScarpShield — {event_type}"
        else:
            subject = "ScarpShield Alert"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)

        # Plain text body
        msg.attach(MIMEText(message, "plain"))

        try:
            with smtplib.SMTP(host, port) as server:
                server.starttls()
                server.login(user, password)
                server.sendmail(
                    from_addr, to_addrs, msg.as_string()
                )
        except Exception as e:
            print(f"[!] Email send failed: {e}")
