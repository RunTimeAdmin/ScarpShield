# ScarpShield

**Official self-hosted monitoring tool for [CounterScarp.io](https://counterscarp.io)**

Lightweight. Private. Runs on your machine.
Get real-time alerts for your smart contracts via Email, Discord, Slack, Telegram, or console.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize config (or copy config.example.json to config.json)
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

All runtime settings are stored in `config.json`. To get started, copy `config.example.json` to `config.json` and edit the values, or use `python main.py init` to generate one automatically.

## Requirements

- Python 3.11+
- `web3`, `typer`

## Roadmap

ScarpShield is under active development. Planned features:

- [ ] **Solana Monitoring** — SPL token transfers, program log subscriptions, and account change detection via Solana RPC
- [ ] **Multi-chain Dashboard** — Unified view across all monitored chains with chain-specific filtering
- [ ] **Persistent Event Storage** — SQLite/PostgreSQL backend for event history beyond in-memory buffer
- [ ] **Custom Event Signatures** — User-defined event ABIs for monitoring non-standard contracts
- [ ] **Webhook Alert Channel** — Generic outbound webhook for custom integrations
- [ ] **Rate Limit Management** — Per-provider RPC quota tracking and automatic failover
- [ ] **Docker Container** — Official Docker image for one-command deployment
- [ ] **CounterScarp.io Integration** — Direct integration with CounterScarp scanning results for pre+post deployment coverage

Have a feature request? [Open an issue](https://github.com/RunTimeAdmin/ScarpShield/issues).

## Security

To report a vulnerability, please see our [Security Policy](SECURITY.md). Do not open public issues for security concerns.

## Support

If ScarpShield helps protect your contracts, consider [sponsoring the project](https://github.com/sponsors/RunTimeAdmin) to support continued development.
