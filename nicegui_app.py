"""NiceGUI entry point for the adaptive Fitness Agent."""

from __future__ import annotations

from pathlib import Path

from nicegui import app, ui

from ui.chat import FitnessAgentPage
from ui.theme import apply_theme
from src.server_settings import server_options


app.add_static_files("/assets", str(Path(__file__).resolve().parent))


@ui.page("/")
def index() -> None:
    apply_theme()
    FitnessAgentPage()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(**server_options())
