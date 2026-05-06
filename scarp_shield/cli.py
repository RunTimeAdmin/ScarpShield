# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import threading
import webbrowser

import typer

from . import __version__
from .config import (
    load_config, save_config,
    add_contract, remove_contract,
    configure_alert, get_enabled_alerts
)

app = typer.Typer(
    name="scarpshield",
    help="ScarpShield - Smart contract monitoring by CounterScarp.io",
    add_completion=False
)


def _banner():
    typer.echo("=" * 50)
    typer.echo(f"  ScarpShield v{__version__}")
    typer.echo("  Powered by CounterScarp.io")
    typer.echo("=" * 50)


# ── Contract management ──────────────────────────


@app.command()
def add(
    address: str = typer.Argument(
        ..., help="Contract address to monitor"
    ),
    label: str = typer.Option(
        "", "--label", "-l", help="Friendly label"
    ),
    chain: str = typer.Option(
        "ethereum", "--chain", "-c",
        help="Chain: ethereum, polygon, bsc, arbitrum, base"
    ),
):
    """Add a contract to the watchlist."""
    config = load_config()
    try:
        config = add_contract(config, address, label, chain)
    except ValueError as e:
        typer.echo(f"[!] {e}")
        raise typer.Exit(1)
    save_config(config)
    name = label or address[:10]
    typer.echo(f"[+] Added {name} on {chain}")


@app.command()
def remove(
    address: str = typer.Argument(
        ..., help="Contract address to remove"
    ),
):
    """Remove a contract from the watchlist."""
    config = load_config()
    config = remove_contract(config, address)
    save_config(config)
    typer.echo(f"[-] Removed {address}")


@app.command(name="list")
def list_contracts():
    """List all monitored contracts."""
    config = load_config()
    contracts = config.get("contracts", [])
    if not contracts:
        typer.echo("No contracts being monitored.")
        typer.echo("Use: scarpshield add <address>")
        return

    _banner()
    for i, c in enumerate(contracts, 1):
        label = c.get("label", "")
        addr = c.get("address", "")
        chain = c.get("chain", "ethereum")
        typer.echo(f"  {i}. [{chain}] {label} - {addr}")
    typer.echo("")


# ── Alert configuration ──────────────────────────


@app.command()
def alerts():
    """Show current alert channel status."""
    config = load_config()
    alerts_cfg = config.get("alerts", {})

    _banner()
    typer.echo("  Alert Channels:")
    for name, channel in alerts_cfg.items():
        status = "ON" if channel.get("enabled") else "OFF"
        typer.echo(f"    {name:12s} [{status}]")
    typer.echo("")


@app.command(name="enable-alert")
def enable_alert(
    channel: str = typer.Argument(
        ...,
        help="Alert channel: console, email, discord, slack, telegram"
    ),
):
    """Enable an alert channel."""
    config = load_config()
    config = configure_alert(config, channel, enabled=True)
    save_config(config)
    typer.echo(f"[+] {channel} alerts enabled")


@app.command(name="disable-alert")
def disable_alert(
    channel: str = typer.Argument(
        ...,
        help="Alert channel to disable"
    ),
):
    """Disable an alert channel."""
    config = load_config()
    config = configure_alert(config, channel, enabled=False)
    save_config(config)
    typer.echo(f"[-] {channel} alerts disabled")


@app.command(name="setup-email")
def setup_email(
    host: str = typer.Option(..., prompt=True),
    port: int = typer.Option(587, prompt=True),
    user: str = typer.Option(..., prompt=True),
    password: str = typer.Option(
        ..., prompt=True, hide_input=True
    ),
    from_addr: str = typer.Option(
        "", "--from", help="From address (defaults to user)"
    ),
    to: str = typer.Option(
        ..., prompt="Recipient email(s), comma-separated"
    ),
):
    """Configure email (SMTP) alerts."""
    config = load_config()
    to_list = [t.strip() for t in to.split(",")]
    config = configure_alert(
        config, "email", enabled=True,
        smtp_host=host, smtp_port=port,
        smtp_user=user, smtp_password=password,
        from_address=from_addr or user,
        to_addresses=to_list
    )
    save_config(config)
    typer.echo(f"[+] Email alerts configured -> {to}")


@app.command(name="setup-discord")
def setup_discord(
    webhook_url: str = typer.Option(
        ..., prompt="Discord webhook URL"
    ),
):
    """Configure Discord webhook alerts."""
    config = load_config()
    config = configure_alert(
        config, "discord", enabled=True,
        webhook_url=webhook_url
    )
    save_config(config)
    typer.echo("[+] Discord alerts configured")


@app.command(name="setup-slack")
def setup_slack(
    webhook_url: str = typer.Option(
        ..., prompt="Slack webhook URL"
    ),
):
    """Configure Slack webhook alerts."""
    config = load_config()
    config = configure_alert(
        config, "slack", enabled=True,
        webhook_url=webhook_url
    )
    save_config(config)
    typer.echo("[+] Slack alerts configured")


@app.command(name="setup-telegram")
def setup_telegram(
    token: str = typer.Option(
        ..., prompt="Bot token"
    ),
    chat_id: str = typer.Option(
        ..., prompt="Chat ID"
    ),
):
    """Configure Telegram bot alerts (optional)."""
    config = load_config()
    config = configure_alert(
        config, "telegram", enabled=True,
        bot_token=token, chat_id=chat_id
    )
    save_config(config)
    typer.echo("[+] Telegram alerts configured")


# ── Monitoring ───────────────────────────────────


@app.command()
def start():
    """Start monitoring all watched contracts."""
    _banner()
    from .monitor import run_monitor
    run_monitor()


@app.command()
def init():
    """Initialize a fresh config.json with defaults."""
    config = load_config()
    save_config(config)
    typer.echo("[+] config.json created with defaults")
    typer.echo("    Edit it or use CLI commands to configure.")


@app.command()
def status():
    """Show current monitoring configuration summary."""
    config = load_config()
    contracts = config.get("contracts", [])
    enabled = get_enabled_alerts(config)

    _banner()
    typer.echo(f"  Contracts:  {len(contracts)}")
    typer.echo(f"  Alerts:     {', '.join(enabled) or 'none'}")
    interval = config.get("poll_interval_seconds", 15)
    typer.echo(f"  Poll rate:  {interval}s")

    chains = set(
        c.get("chain", "ethereum") for c in contracts
    )
    typer.echo(f"  Chains:     {', '.join(chains) or 'none'}")
    typer.echo("")


@app.command(name="test-alerts")
def test_alerts():
    """Send a test alert to all enabled channels."""
    import asyncio
    from .alerts.base import format_alert
    from .alerts.dispatcher import AlertDispatcher

    config = load_config()
    dispatcher = AlertDispatcher(config)
    msg = format_alert(
        event_type="TEST",
        contract="0x000...TEST",
        details="This is a test alert from ScarpShield.",
        chain="test"
    )

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(dispatcher.dispatch(msg))
        typer.echo("[+] Test alert sent to all enabled channels.")
    finally:
        loop.close()


@app.command()
def gui(
    port: int = typer.Option(
        8050, "--port", "-p", help="Port to run the GUI on"
    ),
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h", help="Host to bind the GUI server"
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not open browser automatically"
    ),
    password: str = typer.Option(
        None, "--password", "-P", help="Set dashboard password (enables authentication)"
    ),
):
    """Launch the ScarpShield web dashboard."""
    from .gui import create_app

    if password is None and host == "0.0.0.0":
        typer.echo(
            "WARNING: Dashboard exposed without authentication. Use --password to protect."
        )

    app_flask = create_app(password=password)
    url = f"http://{host}:{port}"

    banner = f"""╔══════════════════════════════════════════╗
║       ScarpShield Web Dashboard          ║
║   THE OUTER WALL OF DEFENSE              ║
╠══════════════════════════════════════════╣
║   Running at: {url:30s}   ║
║   Press Ctrl+C to stop                   ║
╚══════════════════════════════════════════╝"""
    typer.echo(banner)

    if not no_browser:
        threading.Timer(1.5, webbrowser.open, args=[url]).start()

    app_flask.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    app()
