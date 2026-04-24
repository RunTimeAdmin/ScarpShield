# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .base import AlertBackend


class EmailAlert(AlertBackend):
    """Send alerts via SMTP email."""

    async def send(self, message: str, metadata: dict = None):
        host = self.settings.get("smtp_host", "")
        port = self.settings.get("smtp_port", 587)
        user = self.settings.get("smtp_user", "")
        password = self.settings.get("smtp_password", "")
        from_addr = self.settings.get("from_address", user)
        to_addrs = self.settings.get("to_addresses", [])

        if not all([host, user, password, to_addrs]):
            print("[!] Email alert misconfigured. Skipping.")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "ScarpShield Alert"
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
