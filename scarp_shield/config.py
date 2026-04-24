# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import json
from pathlib import Path
from dataclasses import dataclass, field

from web3 import Web3

# Resolve config relative to project root (where main.py lives)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"
ENV_FILE = PROJECT_ROOT / ".env"


@dataclass
class AlertChannelConfig:
    """Configuration for a single alert channel."""
    enabled: bool = False
    settings: dict = field(default_factory=dict)


@dataclass
class ContractEntry:
    """A monitored contract."""
    address: str
    label: str = ""
    chain: str = "ethereum"
    events: list = field(default_factory=lambda: ["Transfer", "OwnershipTransferred"])


DEFAULT_CONFIG = {
    "project": "CounterScarp.io",
    "tool": "ScarpShield",
    "version": "0.1.0",
    "contracts": [],
    "rpc_endpoints": {
        "ethereum": "https://eth.llamarpc.com",
        "polygon": "https://polygon-rpc.com",
        "bsc": "https://bsc-dataseed.binance.org",
        "arbitrum": "https://arb1.arbitrum.io/rpc",
        "base": "https://mainnet.base.org",
    },
    "poll_interval_seconds": 15,
    "alerts": {
        "console": {
            "enabled": True,
            "settings": {}
        },
        "email": {
            "enabled": False,
            "settings": {
                "smtp_host": "",
                "smtp_port": 587,
                "smtp_user": "",
                "smtp_password": "",
                "from_address": "",
                "to_addresses": []
            }
        },
        "discord": {
            "enabled": False,
            "settings": {
                "webhook_url": ""
            }
        },
        "slack": {
            "enabled": False,
            "settings": {
                "webhook_url": ""
            }
        },
        "telegram": {
            "enabled": False,
            "settings": {
                "bot_token": "",
                "chat_id": ""
            }
        }
    },
    "filters": {
        "min_transfer_value": 0.0,
        "watch_admin_events": True,
        "watch_large_transfers": True,
        "watch_approvals": True
    }
}


def load_config() -> dict:
    """Load config from config.json, creating default if missing."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("[!] config.json is malformed. Loading defaults.")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save config to config.json."""
    CONFIG_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_enabled_alerts(config: dict) -> list[str]:
    """Return list of enabled alert channel names."""
    alerts = config.get("alerts", {})
    return [name for name, channel in alerts.items() if channel.get("enabled")]


def get_rpc_url(config: dict, chain: str) -> str:
    """Get RPC endpoint for a given chain."""
    endpoints = config.get("rpc_endpoints", {})
    return endpoints.get(chain, endpoints.get("ethereum", "https://eth.llamarpc.com"))


def add_contract(config: dict, address: str, label: str = "", chain: str = "ethereum") -> dict:
    """Add a contract to the watchlist."""
    # Validate and checksum the address
    try:
        address = Web3.to_checksum_address(address)
    except (ValueError, Exception):
        raise ValueError(f"Invalid Ethereum address: {address}")

    entry = {
        "address": address,
        "label": label or address[:10],
        "chain": chain,
        "events": ["Transfer", "OwnershipTransferred", "Approval"]
    }
    # Avoid duplicates
    existing = [c["address"].lower() for c in config.get("contracts", [])]
    if address.lower() not in existing:
        config.setdefault("contracts", []).append(entry)
    return config


def remove_contract(config: dict, address: str) -> dict:
    """Remove a contract from the watchlist."""
    config["contracts"] = [
        c for c in config.get("contracts", [])
        if c["address"].lower() != address.lower()
    ]
    return config


def configure_alert(config: dict, channel: str, enabled: bool, **settings) -> dict:
    """Enable/disable and configure an alert channel."""
    if channel not in config.get("alerts", {}):
        config.setdefault("alerts", {})[channel] = {"enabled": False, "settings": {}}
    config["alerts"][channel]["enabled"] = enabled
    if settings:
        config["alerts"][channel]["settings"].update(settings)
    return config
