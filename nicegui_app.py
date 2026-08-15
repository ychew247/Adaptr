"""NiceGUI entry point for the adaptive Fitness Agent."""

from __future__ import annotations

import os
from pathlib import Path

from nicegui import app, ui

from ui.chat import FitnessAgentPage
from ui.theme import apply_theme


app.add_static_files("/assets", str(Path(__file__).resolve().parent))


@ui.page("/")
def index() -> None:
    apply_theme()
    FitnessAgentPage()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="127.0.0.1",
        port=int(os.getenv("NICEGUI_PORT", "8081")),
        title="Adaptr",
        show_welcome_message=False,
        reload=os.getenv("NICEGUI_RELOAD", "").lower() == "true",
    )
