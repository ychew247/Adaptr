"""Modern NiceGUI chat workspace for the adaptive fitness agent."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import json

from nicegui import run, ui

from src.fitness_chat import plan_table_rows, remaining_plan_table_rows
from ui.chat_controller import FitnessChatController
from ui.chat_state import ChatSession, ChatSessionStore


_CHAT_STORAGE_KEY = "adaptr.chat_sessions.v1"


class FitnessAgentPage:
    def __init__(self) -> None:
        self.sessions = ChatSessionStore()
        self.session = ChatSession()
        self.controller = FitnessChatController(self.session)
        self.dark_mode = ui.dark_mode(value=True)
        self._request_token = 0
        self._is_processing = False
        self._thinking_index = 0
        self._thinking_phrases = (
            "Thinking",
            "Reading your plan",
            "Checking readiness",
            "Plotting next steps",
        )
        self._build_shell()
        self._thinking_timer = ui.timer(1.6, self._advance_thinking, active=False)
        ui.timer(0.1, self._initialize_chat, once=True)

    def _build_shell(self) -> None:
        with ui.left_drawer(value=True).props("width=256 show-if-above breakpoint=760").classes("fa-sidebar") as self.left_drawer:
            with ui.column().classes("w-full h-full p-4 gap-2"):
                with ui.row().classes("items-center gap-3 px-2 py-2"):
                    ui.image("/assets/Logo.svg").classes("fa-brand-logo")
                    with ui.column().classes("gap-0"):
                        ui.label("Adaptr").classes("font-semibold text-base")
                        ui.label("Adaptive training").classes("fa-muted text-xs")
                self.new_chat_button = ui.button("New chat", icon="add", on_click=self._new_chat).props("unelevated no-caps").classes(
                    "fa-new-chat w-full justify-start mt-4"
                )
                ui.label("CONVERSATIONS").classes("fa-muted text-xs font-semibold mt-6 px-2")
                with ui.column().classes("w-full gap-1") as self.conversation_list:
                    pass
                ui.space()
                ui.label("WORKSPACE").classes("fa-muted text-xs font-semibold px-2")
                ui.button("Appearance", icon="dark_mode", on_click=self.dark_mode.toggle).props(
                    "flat no-caps align=left"
                ).classes("fa-nav-item w-full justify-start")

        with ui.header().classes("fa-topbar"):
            with ui.row().classes("w-full h-full items-center justify-between px-6"):
                with ui.row().classes("items-center gap-3"):
                    ui.button(icon="menu", on_click=self.left_drawer.toggle).props("flat round dense").tooltip(
                        "Toggle sidebar"
                    )
                    ui.label("Adaptr").classes("fa-topbar-title font-semibold")
                with ui.row().classes("items-center gap-2"):
                    ui.element("div").classes("fa-status-dot")
                    self.status_label = ui.label("Preparing session").classes("fa-muted text-sm")

        with ui.column().classes("fa-main fa-dot-grid w-full"):
            with ui.column().classes("fa-welcome-stage") as self.welcome_stage:
                pass
            with ui.column().classes("fa-message-list") as self.message_list:
                pass

        with ui.element("div").classes("fa-composer-shell") as self.composer_shell:
            with ui.row().classes("fa-composer items-end w-full gap-2"):
                self.composer = ui.textarea(placeholder="Message Adaptr").props("borderless autogrow").classes(
                    "flex-grow"
                )
                self.composer.on("keydown.enter.exact.prevent", self._submit_from_keyboard)
                self.send_button = ui.button(icon="send", on_click=self._composer_action).props("unelevated round").classes("fa-send").tooltip(
                    "Send message"
                )

    async def _initialize_chat(self) -> None:
        if await ui.run_javascript("window.innerWidth <= 760"):
            self.left_drawer.hide()
        if await self._restore_sessions():
            self.status_label.text = self.session.status
            self._render_sidebar_sessions()
            self._render_messages()
            return
        self._create_session()
        await self._run_controller(self.controller.start_new_chat, "Starting your session")

    async def _new_chat(self) -> None:
        if self._is_processing:
            return
        self._create_session()
        await self._run_controller(self.controller.start_new_chat, "Starting a new chat")

    async def _activate_chat(self, session_id: str) -> None:
        if self._is_processing or session_id == self.sessions.active_session_id:
            return
        try:
            self.session = self.sessions.activate(session_id)
        except LookupError:
            return
        self.controller = FitnessChatController(self.session)
        self.status_label.text = self.session.status
        self._render_sidebar_sessions()
        self._render_messages()
        await self._persist_sessions()

    def _open_rename_chat_dialog(self, session_id: str) -> None:
        if self._is_processing:
            return
        try:
            session = next(session for session in self.sessions.sessions if session.session_id == session_id)
        except StopIteration:
            return
        with ui.dialog() as dialog, ui.card().classes("w-80"):
            ui.label("Rename chat").classes("text-lg font-semibold")
            title_input = ui.input(value=session.title, label="Chat name").props("autofocus").classes("w-full")

            async def save_name() -> None:
                try:
                    self.sessions.rename(session_id, title_input.value or "")
                except ValueError:
                    ui.notify("Enter a chat name.", type="warning")
                    return
                dialog.close()
                self._render_sidebar_sessions()
                await self._persist_sessions()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps")
                ui.button("Rename", on_click=save_name).props("unelevated no-caps")
        dialog.open()

    async def _delete_chat(self, session_id: str) -> None:
        if self._is_processing:
            return
        try:
            self.sessions.delete(session_id)
        except LookupError:
            return
        if self.sessions.active_session_id is None:
            self._create_session()
            await self._run_controller(self.controller.start_new_chat, "Starting a new chat")
            return
        self.session = self.sessions.active_session
        self.controller = FitnessChatController(self.session)
        self.status_label.text = self.session.status
        self._render_sidebar_sessions()
        self._render_messages()
        await self._persist_sessions()

    def _create_session(self) -> None:
        self.session = self.sessions.start_new_session("")
        self.controller = FitnessChatController(self.session)
        self._render_sidebar_sessions()

    async def _restore_sessions(self) -> bool:
        try:
            raw_payload = await ui.run_javascript(f"localStorage.getItem({json.dumps(_CHAT_STORAGE_KEY)})")
            if not isinstance(raw_payload, str):
                return False
            self.sessions = ChatSessionStore.from_payload(json.loads(raw_payload))
            if not self.sessions.sessions:
                return False
            self.session = self.sessions.active_session
            self.sessions.refresh_title(self.session)
            self.controller = FitnessChatController(self.session)
            return True
        except (json.JSONDecodeError, LookupError, TypeError, ValueError):
            self.sessions = ChatSessionStore()
            return False

    async def _persist_sessions(self) -> None:
        try:
            payload = json.dumps(self.sessions.to_payload(), separators=(",", ":"))
            await ui.run_javascript(
                f"localStorage.setItem({json.dumps(_CHAT_STORAGE_KEY)}, {json.dumps(payload)})"
            )
        except Exception:
            # Local storage can be disabled or full; live in-memory chats still work.
            return

    async def _composer_action(self) -> None:
        if self._is_processing:
            await self._stop_current_request()
            return
        await self._send()

    async def _send(self) -> None:
        if self._is_processing:
            return
        message = (self.composer.value or "").strip()
        if not message:
            return
        self.composer.value = ""
        queued_message = self.controller.begin_message(message)
        if queued_message is None:
            return
        await self._persist_sessions()
        await self._run_message(queued_message)

    async def _submit_from_keyboard(self, event) -> None:
        if self._is_processing:
            return
        if getattr(event, "args", {}).get("shiftKey"):
            return
        await self._send()

    async def _run_controller(self, action, status: str, *args) -> None:
        self.status_label.text = status
        self._render_messages()
        await run.io_bound(action, *args)
        self.sessions.refresh_title(self.session)
        self.status_label.text = self.session.status
        self._render_sidebar_sessions()
        self._render_messages()
        await self._persist_sessions()

    async def _run_message(self, message: str) -> None:
        self._request_token += 1
        request_token = self._request_token
        self._set_processing(True)
        self.status_label.text = "Working"
        self._render_messages()

        request_session = deepcopy(self.session)
        request_controller = FitnessChatController(request_session)
        await run.io_bound(request_controller.complete_message, message)
        if request_token != self._request_token:
            return

        self.sessions.replace_active(request_session)
        self.session = request_session
        self.controller = request_controller
        self.sessions.refresh_title(self.session)
        self._set_processing(False)
        self.status_label.text = self.session.status
        self._render_sidebar_sessions()
        self._render_messages()
        await self._persist_sessions()

    async def _stop_current_request(self) -> None:
        if not self._is_processing:
            return
        self._request_token += 1
        self.session.status = "Stopped"
        self.session.add_message("assistant", "Stopped", transition=True)
        self._set_processing(False)
        self.status_label.text = "Stopped"
        self._render_sidebar_sessions()
        self._render_messages()
        await self._persist_sessions()

    def _set_processing(self, active: bool) -> None:
        self._is_processing = active
        self._thinking_index = 0
        self._thinking_timer.active = active
        self.send_button.props(f"icon={'stop' if active else 'send'}")
        self.send_button.props(f"aria-label={'Stop generating' if active else 'Send message'}")
        if active:
            self.composer.disable()
            self.new_chat_button.disable()
        else:
            self.composer.enable()
            self.new_chat_button.enable()

    def _advance_thinking(self) -> None:
        if not self._is_processing:
            return
        self._thinking_index = (self._thinking_index + 1) % len(self._thinking_phrases)
        self._render_messages()

    def _render_sidebar_sessions(self) -> None:
        self.conversation_list.clear()
        with self.conversation_list:
            for session in self.sessions.sessions:
                active = session.session_id == self.sessions.active_session_id
                classes = "fa-nav-item w-full justify-start"
                if active:
                    classes += " fa-session-active"
                with ui.element("div").classes("w-full"):
                    ui.button(
                        session.title,
                        icon="chat_bubble_outline",
                        on_click=lambda session_id=session.session_id: self._activate_chat(session_id),
                    ).props("flat no-caps align=left").classes(classes)
                    with ui.context_menu():
                        ui.menu_item(
                            "Rename",
                            on_click=lambda session_id=session.session_id: self._open_rename_chat_dialog(session_id),
                        )
                        ui.menu_item(
                            "Delete",
                            on_click=lambda session_id=session.session_id: self._delete_chat(session_id),
                        ).classes("text-negative")

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
                    elif message.get("transition"):
                        ui.label(message["content"]).classes("fa-processing fa-stopped")
                    else:
                        ui.markdown(message["content"]).classes("fa-agent-message")
                    if message.get("plan"):
                        self._render_plan(
                            message["plan"],
                            message.get("as_of_date"),
                            full_week=message.get("plan_view") == "full_week",
                        )
                    if message.get("print_question"):
                        ui.markdown(message["print_question"]).classes("fa-agent-message font-medium")
                    if message.get("download_url"):
                        ui.link(
                            "Download workout plan (.xlsx)",
                            message["download_url"],
                            new_tab=True,
                        ).classes("mt-2 fa-download-link")
                    elif message.get("download"):
                        ui.button(
                            "Download workout plan (.xlsx)",
                            icon="download",
                            on_click=lambda data=message["download"], name=message["filename"]: ui.download.content(
                                data,
                                name,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ),
                        ).props("outline no-caps").classes("mt-2")
            if self._is_processing:
                ui.label(self._thinking_phrases[self._thinking_index]).classes("fa-processing")

    @staticmethod
    def _render_plan(
        plan: dict, as_of_date: str | None = None, *, full_week: bool = False
    ) -> None:
        rows = plan_table_rows(plan) if full_week else remaining_plan_table_rows(plan, as_of_date or date.today())
        columns = [
            {"name": key, "label": key, "field": key, "align": "left"}
            for key in ("Date", "Day", "Focus", "Exercises", "Sets/Reps", "Adjustment")
        ]
        ui.table(columns=columns, rows=rows, row_key="Day").classes("fa-plan-table mt-2")
