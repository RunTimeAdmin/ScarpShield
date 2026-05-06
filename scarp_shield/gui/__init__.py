# ScarpShield - Official monitoring tool for CounterScarp.io
# https://counterscarp.io

from pathlib import Path
from flask import Flask


def create_app(password: str = None) -> Flask:
    """Flask application factory for ScarpShield GUI."""
    gui_dir = Path(__file__).resolve().parent
    template_dir = gui_dir / "templates"
    static_dir = gui_dir / "static"

    app = Flask(
        __name__,
        template_folder=str(template_dir),
        static_folder=str(static_dir),
    )

    from .app import register_routes, setup_auth

    register_routes(app)

    if password is not None:
        setup_auth(app, password)

    return app
