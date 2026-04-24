# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

import asyncio
import json
import queue
import threading
from collections import deque
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, Response

from ..config import (
    DEFAULT_CONFIG,
    add_contract,
    configure_alert,
    get_enabled_alerts,
    get_rpc_url,
    load_config,
    remove_contract,
    save_config,
)
from ..alerts.dispatcher import AlertDispatcher

# ── Global state ─────────────────────────────────

monitor_thread = None
stop_event = threading.Event()
monitor_lock = threading.Lock()

sse_queues = []
event_logs = deque(maxlen=1000)


# ── Alert interception ───────────────────────────

class GUIAlertDispatcher(AlertDispatcher):
    """Dispatcher that also pushes alerts to GUI SSE queues and log buffer."""

    async def dispatch(self, message: str, metadata=None):
        await super().dispatch(message, metadata)
        _push_alert_event(message, metadata)


def _push_alert_event(message: str, metadata=None):
    """Push an alert to all connected SSE clients and the in-memory log."""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "metadata": metadata or {},
    }
    event_logs.append(event)

    dead = []
    for q in sse_queues:
        try:
            q.put_nowait(event)
        except queue.Full:
            dead.append(q)

    for q in dead:
        try:
            sse_queues.remove(q)
        except ValueError:
            pass


# ── Background monitor runner ────────────────────

def run_monitor_background(stop_evt: threading.Event):
    """Stoppable monitor loop that feeds the GUI event stream."""
    config = load_config()
    contracts = config.get("contracts", [])

    if not contracts:
        return

    from web3 import Web3

    from ..monitor import _check_admin_calls, _check_events

    dispatcher = GUIAlertDispatcher(config)
    interval = config.get("poll_interval_seconds", 15)

    # Build / cache Web3 connections per chain
    chains = {}
    last_block = {}

    def _ensure_chain(chain: str):
        if chain in chains:
            return
        rpc = get_rpc_url(config, chain)
        w3 = Web3(Web3.HTTPProvider(rpc))
        if w3.is_connected():
            chains[chain] = w3
            try:
                last_block[chain] = w3.eth.block_number
            except Exception:
                last_block[chain] = 0

    for c in contracts:
        _ensure_chain(c.get("chain", "ethereum"))

    loop = asyncio.new_event_loop()
    try:
        while not stop_evt.is_set():
            # Reload config each iteration so new contracts /
            # chains are picked up
            config = load_config()
            contracts = config.get("contracts", [])
            interval = config.get("poll_interval_seconds", 15)

            for entry in contracts:
                if stop_evt.is_set():
                    break

                addr = entry["address"]
                chain = entry.get("chain", "ethereum")
                label = entry.get("label", addr[:10])
                events = entry.get("events", [])

                _ensure_chain(chain)
                w3 = chains.get(chain)
                if not w3:
                    continue

                try:
                    current = w3.eth.block_number
                    prev = last_block.get(chain, current)

                    if current <= prev:
                        continue

                    _check_events(
                        w3, addr, label, chain,
                        prev, current, events,
                        dispatcher, config, loop
                    )

                    watch_admin = config.get("filters", {}).get(
                        "watch_admin_events", True
                    )
                    if watch_admin:
                        _check_admin_calls(
                            w3, addr, label, chain,
                            prev, current,
                            dispatcher, loop
                        )

                    last_block[chain] = current
                except Exception as e:
                    print(f"[!] Error checking {label} on {chain}: {e}")

            stop_evt.wait(interval)
    except Exception as e:
        print(f"[!] Monitor loop crashed: {e}")
    finally:
        loop.close()


# ── Route registration ───────────────────────────

def register_routes(app: Flask):

    # ── Page routes ──────────────────────────────

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/contracts")
    def contracts_page():
        return render_template("contracts.html")

    @app.route("/alerts")
    def alerts_page():
        return render_template("alerts.html")

    @app.route("/settings")
    def settings_page():
        return render_template("settings.html")

    @app.route("/logs")
    def logs_page():
        return render_template("logs.html")

    # ── Contract API ─────────────────────────────

    @app.route("/api/contracts", methods=["GET"])
    def api_contracts_list():
        config = load_config()
        return jsonify(config.get("contracts", []))

    @app.route("/api/contracts", methods=["POST"])
    def api_contracts_add():
        data = request.get_json(silent=True) or {}
        address = data.get("address")
        if not address:
            return jsonify({"error": "'address' is required"}), 400

        label = data.get("label", "")
        chain = data.get("chain", "ethereum")
        default_events = ["Transfer", "OwnershipTransferred", "Approval"]
        events = data.get("events", default_events)

        config = load_config()
        config = add_contract(config, address, label, chain)

        # Override default events if provided
        for c in config.get("contracts", []):
            if c["address"].lower() == address.lower():
                c["events"] = events
                break

        save_config(config)
        return jsonify({"success": True})

    @app.route("/api/contracts/<address>", methods=["DELETE"])
    def api_contracts_remove(address):
        config = load_config()
        config = remove_contract(config, address)
        save_config(config)
        return jsonify({"success": True})

    # ── Status & Monitor API ─────────────────────

    @app.route("/api/status", methods=["GET"])
    def api_status():
        config = load_config()
        contracts = config.get("contracts", [])
        enabled = get_enabled_alerts(config)

        with monitor_lock:
            running = monitor_thread is not None and monitor_thread.is_alive()

        return jsonify({
            "running": running,
            "contract_count": len(contracts),
            "enabled_alerts": enabled,
            "poll_interval": config.get("poll_interval_seconds", 15),
            "chains": list({c.get("chain", "ethereum") for c in contracts}),
            "event_log_count": len(event_logs),
        })

    @app.route("/api/monitor/start", methods=["POST"])
    def api_monitor_start():
        global monitor_thread, stop_event
        with monitor_lock:
            if monitor_thread is not None and monitor_thread.is_alive():
                return jsonify({"error": "Monitor is already running"}), 409
            stop_event = threading.Event()
            monitor_thread = threading.Thread(
                target=run_monitor_background,
                args=(stop_event,),
                daemon=True,
            )
            monitor_thread.start()
        return jsonify({"success": True, "status": "started"})

    @app.route("/api/monitor/stop", methods=["POST"])
    def api_monitor_stop():
        global monitor_thread, stop_event
        with monitor_lock:
            if monitor_thread is None or not monitor_thread.is_alive():
                return jsonify({"error": "Monitor is not running"}), 409
            stop_event.set()
            monitor_thread.join(timeout=5)
            monitor_thread = None
        return jsonify({"success": True, "status": "stopped"})

    # ── Alert channel API ────────────────────────

    @app.route("/api/alerts", methods=["GET"])
    def api_alerts():
        config = load_config()
        alerts_cfg = config.get("alerts", {})
        result = {}
        for name, channel in alerts_cfg.items():
            result[name] = {
                "enabled": channel.get("enabled", False),
                "settings": channel.get("settings", {}),
            }
        return jsonify(result)

    @app.route("/api/alerts/<channel>/enable", methods=["POST"])
    def api_alert_enable(channel):
        config = load_config()
        config = configure_alert(config, channel, enabled=True)
        save_config(config)
        return jsonify({"success": True, "channel": channel, "enabled": True})

    @app.route("/api/alerts/<channel>/disable", methods=["POST"])
    def api_alert_disable(channel):
        config = load_config()
        config = configure_alert(config, channel, enabled=False)
        save_config(config)
        return jsonify({"success": True, "channel": channel, "enabled": False})

    @app.route("/api/alerts/test", methods=["POST"])
    def api_alerts_test():
        config = load_config()
        dispatcher = AlertDispatcher(config)
        if not dispatcher.backends:
            return jsonify({"error": "No alert backends are enabled"}), 400

        msg = dispatcher.backends[0][1].format_alert(
            event_type="TEST",
            contract="0x000...TEST",
            details="This is a test alert from ScarpShield GUI.",
            chain="test",
        )

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(dispatcher.dispatch(msg))
        finally:
            loop.close()

        return jsonify({"success": True, "message": "Test alert dispatched"})

    # ── Setup API ────────────────────────────────

    @app.route("/api/setup/email", methods=["POST"])
    def api_setup_email():
        data = request.get_json(silent=True) or {}
        config = load_config()
        config = configure_alert(
            config, "email", enabled=True,
            smtp_host=data.get("smtp_host", ""),
            smtp_port=data.get("smtp_port", 587),
            smtp_user=data.get("smtp_user", ""),
            smtp_password=data.get("smtp_password", ""),
            from_address=data.get("from_address", data.get("smtp_user", "")),
            to_addresses=data.get("to_addresses", []),
        )
        save_config(config)
        return jsonify({"success": True})

    @app.route("/api/setup/discord", methods=["POST"])
    def api_setup_discord():
        data = request.get_json(silent=True) or {}
        config = load_config()
        config = configure_alert(
            config, "discord", enabled=True,
            webhook_url=data.get("webhook_url", ""),
        )
        save_config(config)
        return jsonify({"success": True})

    @app.route("/api/setup/slack", methods=["POST"])
    def api_setup_slack():
        data = request.get_json(silent=True) or {}
        config = load_config()
        config = configure_alert(
            config, "slack", enabled=True,
            webhook_url=data.get("webhook_url", ""),
        )
        save_config(config)
        return jsonify({"success": True})

    @app.route("/api/setup/telegram", methods=["POST"])
    def api_setup_telegram():
        data = request.get_json(silent=True) or {}
        config = load_config()
        config = configure_alert(
            config, "telegram", enabled=True,
            bot_token=data.get("bot_token", ""),
            chat_id=data.get("chat_id", ""),
        )
        save_config(config)
        return jsonify({"success": True})

    # ── Config API ───────────────────────────────

    @app.route("/api/config", methods=["GET"])
    def api_config_get():
        import copy
        config = load_config()
        safe_config = copy.deepcopy(config)
        alerts = safe_config.get("alerts", {})
        for channel_name, channel_cfg in alerts.items():
            settings = channel_cfg.get("settings", {})
            for key in ("smtp_password", "webhook_url", "bot_token"):
                if key in settings and isinstance(settings[key], str):
                    if settings[key]:
                        settings[key] = "********"
        return jsonify(safe_config)

    @app.route("/api/config", methods=["POST"])
    def api_config_update():
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid config data"}), 400

        # Full replacement for raw config editor
        if data.get("_full_replace") or "contracts" in data:
            save_config(data)
            return jsonify({"success": True})

        config = load_config()
        if "filters" in data:
            config.setdefault("filters", {}).update(data["filters"])
        if "poll_interval_seconds" in data:
            config["poll_interval_seconds"] = data["poll_interval_seconds"]
        if "rpc_endpoints" in data:
            config["rpc_endpoints"] = data["rpc_endpoints"]
        save_config(config)
        return jsonify({"success": True})

    @app.route("/api/config/init", methods=["POST"])
    def api_config_init():
        save_config(DEFAULT_CONFIG.copy())
        return jsonify(
            {"success": True, "message": "Config reset to defaults"}
        )

    # ── SSE event stream ─────────────────────────

    @app.route("/api/events/stream")
    def api_events_stream():
        def generate():
            q = queue.Queue(maxsize=100)
            sse_queues.append(q)
            try:
                while True:
                    try:
                        event = q.get(timeout=30)
                        yield f"data: {json.dumps(event)}\n\n"
                    except queue.Empty:
                        yield f"data: {json.dumps({'type': 'ping'})}\n\n"
            except GeneratorExit:
                pass
            finally:
                try:
                    sse_queues.remove(q)
                except ValueError:
                    pass

        return Response(generate(), mimetype="text/event-stream")

    # ── Log history API ──────────────────────────

    @app.route("/api/logs", methods=["GET"])
    def api_logs():
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        search = request.args.get("search", "").lower()

        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 1
        if per_page > 200:
            per_page = 200

        logs_list = list(event_logs)

        if search:
            logs_list = [
                log for log in logs_list
                if search in log.get("message", "").lower()
            ]

        total = len(logs_list)
        start = (page - 1) * per_page
        end = start + per_page
        paginated = logs_list[start:end]

        return jsonify({
            "logs": paginated,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        })

    # ── Error handlers ───────────────────────────

    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("dashboard.html")

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({"error": "Internal server error"}), 500
