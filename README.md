# ScarpShield

**Official self-hosted monitoring tool for [CounterScarp.io](https://counterscarp.io)**

Lightweight. Private. Runs on your machine.
Get real-time alerts for your smart contracts via Email, Discord, Slack, Telegram, or console.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize config
python main.py init

# Add a contract
python main.py add 0xYourContractAddress --chain ethereum --label "My Token"

# Configure alerts (pick one or more)
python main.py setup-email
python main.py setup-discord
python main.py setup-slack
python main.py setup-telegram

# Start monitoring
python main.py start
```

## CLI Commands

| Command | Description |
|---|---|
| `add <address>` | Add a contract (flags: `--chain`, `--label`) |
| `remove <address>` | Remove a contract |
| `list` | Show all monitored contracts |
| `start` | Start the monitoring loop |
| `status` | Show config summary |
| `alerts` | Show alert channel status |
| `enable-alert <channel>` | Enable a channel |
| `disable-alert <channel>` | Disable a channel |
| `setup-email` | Configure SMTP email alerts |
| `setup-discord` | Configure Discord webhook |
| `setup-slack` | Configure Slack webhook |
| `setup-telegram` | Configure Telegram bot |
| `gui` | Launch the web dashboard (flags: `--port`, `--host`, `--no-browser`) |
| `test-alerts` | Send a test alert to all enabled channels |
| `init` | Create default config.json |

## Web Dashboard

ScarpShield now includes a polished web GUI featuring the [CounterScarp.io](https://counterscarp.io) dark cyberpunk theme.

Launch it with:

```bash
python main.py gui
```

Options:
- `--port` — Port to run on (default: `8050`)
- `--host` — Host to bind to (default: `127.0.0.1`)
- `--no-browser` — Skip auto-opening the browser

By default, the dashboard runs at **http://127.0.0.1:8050**.

**Features:**
- **Dashboard** — Real-time monitoring overview with live event feed (SSE), alert channel status, and contract summary
- **Contracts** — Add, remove, and manage monitored contracts with chain and label editing
- **Alerts** — Enable/disable channels and configure Email, Discord, Slack, and Telegram settings inline
- **Settings** — Edit global config (RPC endpoints, API keys, polling interval) with validation
- **Logs** — Browse the event history with filtering, and export logs to JSON

## Alert Channels

- **Console** — always on, prints to terminal
- **Email** — SMTP (Gmail, Outlook, custom)
- **Discord** — webhook integration
- **Slack** — webhook integration
- **Telegram** — bot API (optional)

## Supported Chains

Ethereum, Polygon, BSC, Arbitrum, Base (add custom RPCs in config.json)

## What It Monitors

- ERC-20 Transfer events
- Approval events
- OwnershipTransferred events
- Admin function calls (pause, transferOwnership, upgradeTo, etc.)

## Config

All settings stored in `config.json`. Edit directly or use CLI commands.

## Requirements

- Python 3.11+
- `web3`, `typer`
