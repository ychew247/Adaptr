"""Runtime settings for the NiceGUI web server."""

from __future__ import annotations

from collections.abc import Mapping
import os


def server_options(environment: Mapping[str, str] | None = None) -> dict[str, object]:
    """Build NiceGUI options, retaining localhost as the safe development default."""
    values = os.environ if environment is None else environment
    return {
        "host": values.get("NICEGUI_HOST", "127.0.0.1"),
        "port": int(values.get("NICEGUI_PORT", "8081")),
        "title": "Adaptr",
        "show_welcome_message": False,
        "reload": values.get("NICEGUI_RELOAD", "").lower() == "true",
    }
