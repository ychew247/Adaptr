"""Modern NiceGUI chat workspace for the adaptive fitness agent."""

from __future__ import annotations

from nicegui import run, ui

from src.fitness_chat import plan_table_rows
from ui.chat_controller import FitnessChatController
from ui.chat_state import ChatSession


class FitnessAgentPage:
    def __init__(self) -> None:
        self.session = ChatSession()
        self.controller = FitnessChatController(self.session)
        self.dark_mode = ui.dark_mode(value=False)
        self._build_shell()
        ui.timer(0.1, self._initialize_chat, once=True)

    def _build_shell(self) -> None:
        with ui.left_drawer(value=True).props("width=256 show-if-above breakpoint=760").classes("fa-sidebar") as self.left_drawer:
            with ui.column().classes("w-full h-full p-4 gap-2"):
                with ui.row().classes("items-center gap-3 px-2 py-2"):
                    ui.label("FA").classes("fa-brand-mark flex items-center justify-center")
                    with ui.column().classes("gap-0"):
                        ui.label("Fitness Agent").classes("font-semibold text-base")
                        ui.label("Adaptive training").classes("fa-muted text-xs")
                ui.button("New chat", icon="add", on_click=self._new_chat).props("unelevated no-caps").classes(
                    "fa-new-chat w-full justify-start mt-4"
                ).style("background: #0f766e !important; color: #ffffff !important")
                ui.label("CONVERSATIONS").classes("fa-muted text-xs font-semibold mt-6 px-2")
                ui.button("Current session", icon="chat_bubble_outline").props("flat no-caps align=left").classes(
                    "fa-nav-item fa-session-active w-full justify-start"
                )
                ui.space()
                ui.label("WORKSPACE").classes("fa-muted text-xs font-semibold px-2")
                ui.button("Appearance", icon="dark_mode", on_click=self.dark_mode.toggle).props(
                    "flat no-caps align=left"
                ).classes("fa-nav-item w-full justify-start")
                ui.button("Inspector", icon="tune", on_click=self._toggle_inspector).props(
                    "flat no-caps align=left"
                ).classes("fa-nav-item w-full justify-start")

        with ui.right_drawer(value=False).props("breakpoint=760").classes("fa-inspector") as self.inspector:
            with ui.column().classes("w-full h-full p-5 gap-5"):
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label("Session inspector").classes("font-semibold")
                    ui.button(icon="close", on_click=self._toggle_inspector).props("flat round dense").tooltip(
                        "Close inspector"
                    )
                ui.label("ACTIVE SERVICES").classes("fa-muted text-xs font-semibold")
                for title, detail in (
                    ("CockroachDB", "Profiles, plans, decisions"),
                    ("Ollama", "Language and plan generation"),
                    ("Validated planner", "Guardrailed training sessions"),
                    ("Excel exporter", "Workout-plan workbook"),
                ):
                    with ui.column().classes("gap-0 py-2 border-b"):
                        ui.label(title).classes("text-sm font-medium")
                        ui.label(detail).classes("fa-muted text-xs")
                ui.space()
                ui.label("Status updates appear here without exposing raw tool logs.").classes(
                    "fa-muted text-xs leading-relaxed"
                )

        with ui.header().classes("fa-topbar"):
            with ui.row().classes("w-full h-full items-center justify-between px-6"):
                with ui.row().classes("items-center gap-3"):
                    ui.button(icon="menu", on_click=self.left_drawer.toggle).props("flat round dense").tooltip(
                        "Toggle sidebar"
                    )
                    ui.label("Fitness Agent").classes("font-semibold")
                with ui.row().classes("items-center gap-2"):
                    ui.element("div").classes("fa-status-dot")
                    self.status_label = ui.label("Preparing session").classes("fa-muted text-sm")
                    ui.button(icon="tune", on_click=self._toggle_inspector).props("flat round dense").tooltip(
                        "Open inspector"
                    )

        with ui.column().classes("fa-main w-full"):
            with ui.column().classes("fa-welcome-stage") as self.welcome_stage:
                pass
            with ui.column().classes("fa-message-list") as self.message_list:
                pass

        with ui.element("div").classes("fa-composer-shell") as self.composer_shell:
            with ui.row().classes("fa-composer items-end w-full gap-2"):
                self.composer = ui.textarea(placeholder="Message Fitness Agent").props("borderless autogrow").classes(
                    "flex-grow"
                )
                self.composer.on("keydown.enter", self._submit_from_keyboard)
                ui.button(icon="send", on_click=self._send).props("unelevated round").classes("fa-send").tooltip(
                    "Send message"
                )

    async def _initialize_chat(self) -> None:
        if await ui.run_javascript("window.innerWidth <= 760"):
            self.left_drawer.hide()
        await self._run_controller(self.controller.start_new_chat, "Starting your session")

    async def _new_chat(self) -> None:
        await self._run_controller(self.controller.start_new_chat, "Starting a new chat")

    async def _send(self) -> None:
        message = (self.composer.value or "").strip()
        if not message:
            return
        self.composer.value = ""
        queued_message = self.controller.begin_message(message)
        if queued_message is None:
            return
        await self._run_controller(self.controller.complete_message, "Working", queued_message)

    async def _submit_from_keyboard(self, event) -> None:
        if getattr(event, "args", {}).get("shiftKey"):
            return
        await self._send()

    async def _run_controller(self, action, status: str, *args) -> None:
        self.status_label.text = status
        self._render_messages()
        await run.io_bound(action, *args)
        self.status_label.text = self.session.status
        self._render_messages()

    def _render_messages(self) -> None:
        is_welcome = self.session.show_welcome_screen
        self.welcome_stage.visible = is_welcome
        self.message_list.visible = not is_welcome
        if is_welcome:
            self.composer_shell.classes(add="fa-welcome-composer")
        else:
            self.composer_shell.classes(remove="fa-welcome-composer")

        self.welcome_stage.clear()
        with self.welcome_stage:
            ui.label(self.session.welcome_headline).classes("fa-welcome-headline")
            if self.session.messages:
                ui.markdown(self.session.messages[0]["content"]).classes("fa-welcome-prompt")

        self.message_list.clear()
        with self.message_list:
            for message in self.session.messages:
                with ui.column().classes("fa-message"):
                    if message["role"] == "user":
                        ui.label(message["content"]).classes("fa-user-message")
                    else:
                        ui.markdown(message["content"]).classes("fa-agent-message")
                    if message.get("plan"):
                        self._render_plan(message["plan"])
                    if message.get("print_question"):
                        ui.markdown(message["print_question"]).classes("fa-agent-message font-medium")
                    if message.get("download"):
                        ui.button(
                            "Download workout plan (.xlsx)",
                            icon="download",
                            on_click=lambda data=message["download"], name=message["filename"]: ui.download.content(
                                data,
                                name,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ),
                        ).props("outline no-caps").classes("mt-2")

    @staticmethod
    def _render_plan(plan: dict) -> None:
        rows = plan_table_rows(plan)
        columns = [
            {"name": key, "label": key, "field": key, "align": "left"}
            for key in ("Date", "Day", "Focus", "Exercises", "Sets/Reps", "Adjustment")
        ]
        ui.table(columns=columns, rows=rows, row_key="Day").classes("fa-plan-table mt-2")

    def _toggle_inspector(self) -> None:
        self.inspector.toggle()
