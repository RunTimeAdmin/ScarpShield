# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import asyncio
import json
import time
from pathlib import Path
from web3 import Web3

from .config import load_config, get_rpc_url
from .alerts.base import format_alert
from .alerts.dispatcher import AlertDispatcher

# Standard ERC-20 event signatures
EVENT_SIGS = {
    "Transfer": Web3.keccak(
        text="Transfer(address,address,uint256)"
    ).hex(),
    "Approval": Web3.keccak(
        text="Approval(address,address,uint256)"
    ).hex(),
    "OwnershipTransferred": Web3.keccak(
        text="OwnershipTransferred(address,address)"
    ).hex(),
}

# Admin / dangerous function signatures to watch
ADMIN_SIGS = {
    "renounceOwnership": "0x715018a6",
    "transferOwnership": "0xf2fde38b",
    "pause": "0x8456cb59",
    "unpause": "0x3f4ba83a",
    "setFeeRecipient": "0xe74b981b",
    "upgradeTo": "0x3659cfe6",
    "upgradeToAndCall": "0x4f1ef286",
}

MAX_BLOCK_RANGE = 100

ERC20_DECIMALS_ABI = [
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [
            {"internalType": "uint8", "name": "", "type": "uint8"}
        ],
        "stateMutability": "view",
        "type": "function",
    }
]

STATE_FILE = Path(".scarpshield_state.json")

_token_decimals = {}


def run_monitor():
    """Main monitoring loop."""
    config = load_config()
    contracts = config.get("contracts", [])

    if not contracts:
        print("[!] No contracts to monitor.")
        print("    Use: scarpshield add <address>")
        return

    dispatcher = AlertDispatcher(config)
    enabled = dispatcher.list_enabled()
    interval = config.get("poll_interval_seconds", 15)

    print("=" * 50)
    print("  ScarpShield v0.1 - CounterScarp.io")
    print("=" * 50)
    print(f"  Monitoring {len(contracts)} contract(s)")
    print(f"  Alert channels: {', '.join(enabled)}")
    print(f"  Poll interval:  {interval}s")
    print("=" * 50)

    # Build Web3 connections per chain
    chains = {}
    for c in contracts:
        chain = c.get("chain", "ethereum")
        if chain not in chains:
            rpc = get_rpc_url(config, chain)
            w3 = Web3(Web3.HTTPProvider(rpc))
            if w3.is_connected():
                print(f"  [{chain}] Connected")
                chains[chain] = w3
            else:
                print(f"  [!] {chain}: Cannot connect")

    # Track last-seen block per chain
    state = load_state()
    last_block = state.get("last_block", {})
    for chain, w3 in chains.items():
        try:
            if chain not in last_block:
                last_block[chain] = w3.eth.block_number
        except Exception:
            last_block[chain] = 0

    failures = {}
    last_failure_time = {}

    print("\nMonitoring started. Press Ctrl+C to stop.\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        while True:
            for entry in contracts:
                addr = entry["address"]
                chain = entry.get("chain", "ethereum")
                label = entry.get("label", addr[:10])
                events = entry.get("events", [])

                w3 = chains.get(chain)
                if not w3:
                    continue

                # Check backoff for this chain
                if failures.get(chain, 0) > 0:
                    backoff = min(interval * (2 ** failures[chain]), 300)
                    if time.time() - last_failure_time.get(chain, 0) < backoff:
                        continue

                try:
                    current = w3.eth.block_number
                    prev = last_block.get(chain, current)

                    if current <= prev:
                        continue

                    # Backfill cap
                    if current - prev > MAX_BLOCK_RANGE:
                        skipped = current - prev - MAX_BLOCK_RANGE
                        print(
                            f"[!] {chain}: Skipping {skipped} "
                            f"blocks (backfill cap)"
                        )
                        prev = current - MAX_BLOCK_RANGE
                        last_block[chain] = prev

                    # Check event logs
                    _check_events(
                        w3, addr, label, chain,
                        prev, current, events,
                        dispatcher, config, loop
                    )

                    # Check pending txns for admin calls
                    if config.get("filters", {}).get(
                        "watch_admin_events", True
                    ):
                        _check_admin_calls(
                            w3, addr, label, chain,
                            prev, current,
                            dispatcher, loop
                        )

                    last_block[chain] = current
                    failures[chain] = 0

                except Exception as e:
                    print(
                        f"[!] Error checking {label} "
                        f"on {chain}: {e}"
                    )
                    failures[chain] = min(failures.get(chain, 0) + 1, 5)
                    last_failure_time[chain] = time.time()

            save_state({"last_block": last_block})
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nScarpShield stopped.")
    finally:
        loop.close()


def _check_events(
    w3, address, label, chain,
    from_block, to_block, watch_events,
    dispatcher, config, loop
):
    """Check for watched events on a contract."""
    filters_cfg = config.get("filters", {})
    min_val = filters_cfg.get(
        "min_transfer_value",
        filters_cfg.get("min_transfer_value_eth", 0.0)
    )

    for event_name in watch_events:
        sig = EVENT_SIGS.get(event_name)
        if not sig:
            continue

        decimals = get_token_decimals(w3, address)

        try:
            logs = w3.eth.get_logs({
                "fromBlock": from_block + 1,
                "toBlock": to_block,
                "address": Web3.to_checksum_address(address),
                "topics": [sig]
            })
        except Exception:
            continue

        for log in logs:
            details = _parse_log(
                w3, event_name, log, min_val, decimals
            )
            if details is None:
                continue

            alert_msg = format_alert(
                event_type=event_name,
                contract=f"{label} ({address})",
                details=details,
                chain=chain
            )
            loop.run_until_complete(
                dispatcher.dispatch(alert_msg)
            )


def _parse_log(w3, event_name, log, min_val, decimals=18):
    """Parse a log entry and return details string."""
    tx_hash = log.get("transactionHash", b"").hex()

    if event_name == "Transfer" and len(log["topics"]) >= 3:
        frm = _topic_to_addr(log["topics"][1])
        to = _topic_to_addr(log["topics"][2])
        raw = int(log["data"].hex(), 16) if log["data"] else 0
        value = raw / (10 ** decimals)

        if min_val > 0 and value < min_val:
            return None

        return (
            f"From: {frm}\n"
            f"          To:   {to}\n"
            f"          Value: {value:.4f}\n"
            f"          Tx:   {tx_hash}"
        )

    if event_name == "Approval" and len(log["topics"]) >= 3:
        owner = _topic_to_addr(log["topics"][1])
        spender = _topic_to_addr(log["topics"][2])
        raw = int(log["data"].hex(), 16) if log["data"] else 0
        value = raw / (10 ** decimals)
        return (
            f"Owner:   {owner}\n"
            f"          Spender: {spender}\n"
            f"          Value:   {value:.4f}\n"
            f"          Tx:      {tx_hash}"
        )

    if event_name == "OwnershipTransferred":
        if len(log["topics"]) >= 3:
            old = _topic_to_addr(log["topics"][1])
            new = _topic_to_addr(log["topics"][2])
            return (
                f"CRITICAL: Ownership changed!\n"
                f"          Old: {old}\n"
                f"          New: {new}\n"
                f"          Tx:  {tx_hash}"
            )

    return f"Tx: {tx_hash}"


def _check_admin_calls(
    w3, address, label, chain,
    from_block, to_block,
    dispatcher, loop
):
    """Check blocks for admin function calls."""
    addr_lower = address.lower()
    try:
        for block_num in range(from_block + 1, to_block + 1):
            block = w3.eth.get_block(
                block_num, full_transactions=True
            )
            for tx in block.get("transactions", []):
                to = (tx.get("to") or "").lower()
                if to != addr_lower:
                    continue
                inp = tx.get("input", "0x")
                sel = inp[:10] if len(inp) >= 10 else ""
                for fname, fsig in ADMIN_SIGS.items():
                    if sel == fsig:
                        msg = format_alert(
                            event_type=f"ADMIN: {fname}()",
                            contract=f"{label} ({address})",
                            details=(
                                f"Caller: {tx.get('from')}\n"
                                f"          Tx: "
                                f"{tx['hash'].hex()}"
                            ),
                            chain=chain
                        )
                        loop.run_until_complete(
                            dispatcher.dispatch(msg)
                        )
    except Exception as e:
        print(f"[!] Admin check error on {label}: {e}")


def get_token_decimals(w3, address):
    """Fetch ERC20 decimals with caching."""
    addr = Web3.to_checksum_address(address)
    if addr in _token_decimals:
        return _token_decimals[addr]
    try:
        contract = w3.eth.contract(
            address=addr, abi=ERC20_DECIMALS_ABI
        )
        decimals = contract.functions.decimals().call()
    except Exception:
        decimals = 18
    _token_decimals[addr] = decimals
    return decimals


def load_state():
    """Load last_block state from disk."""
    if STATE_FILE.exists():
        try:
            return json.loads(
                STATE_FILE.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(state):
    """Save last_block state to disk."""
    try:
        STATE_FILE.write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def _topic_to_addr(topic) -> str:
    """Convert a 32-byte log topic to an address."""
    if isinstance(topic, bytes):
        return Web3.to_checksum_address(
            "0x" + topic.hex()[-40:]
        )
    return str(topic)
