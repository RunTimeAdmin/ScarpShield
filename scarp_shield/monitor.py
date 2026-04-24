# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import asyncio
import time
from web3 import Web3

from .config import load_config, get_rpc_url
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
    last_block = {}
    for chain, w3 in chains.items():
        try:
            last_block[chain] = w3.eth.block_number
        except Exception:
            last_block[chain] = 0

    print("\nMonitoring started. Press Ctrl+C to stop.\n")

    loop = asyncio.new_event_loop()

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

                try:
                    current = w3.eth.block_number
                    prev = last_block.get(chain, current)

                    if current <= prev:
                        continue

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

                except Exception as e:
                    print(
                        f"[!] Error checking {label} "
                        f"on {chain}: {e}"
                    )

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
    min_val = filters_cfg.get("min_transfer_value_eth", 0.0)

    for event_name in watch_events:
        sig = EVENT_SIGS.get(event_name)
        if not sig:
            continue

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
                w3, event_name, log, min_val
            )
            if details is None:
                continue

            alert_msg = dispatcher.backends[0][1].format_alert(
                event_type=event_name,
                contract=f"{label} ({address})",
                details=details,
                chain=chain
            )
            loop.run_until_complete(
                dispatcher.dispatch(alert_msg)
            )


def _parse_log(w3, event_name, log, min_val):
    """Parse a log entry and return details string."""
    tx_hash = log.get("transactionHash", b"").hex()

    if event_name == "Transfer" and len(log["topics"]) >= 3:
        frm = _topic_to_addr(log["topics"][1])
        to = _topic_to_addr(log["topics"][2])
        raw = int(log["data"].hex(), 16) if log["data"] else 0
        value = raw / 1e18

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
        value = raw / 1e18
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
                        msg = (
                            dispatcher.backends[0][1]
                            .format_alert(
                                event_type=f"ADMIN: {fname}()",
                                contract=f"{label} ({address})",
                                details=(
                                    f"Caller: {tx.get('from')}\n"
                                    f"          Tx: "
                                    f"{tx['hash'].hex()}"
                                ),
                                chain=chain
                            )
                        )
                        loop.run_until_complete(
                            dispatcher.dispatch(msg)
                        )
    except Exception as e:
        print(f"[!] Admin check error on {label}: {e}")


def _topic_to_addr(topic) -> str:
    """Convert a 32-byte log topic to an address."""
    if isinstance(topic, bytes):
        return Web3.to_checksum_address(
            "0x" + topic.hex()[-40:]
        )
    return str(topic)
