from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_desktop_chat_layout_uses_the_space_remaining_after_the_sidebar():
    theme = (PROJECT_ROOT / "ui" / "theme.py").read_text(encoding="utf-8")
    chat = (PROJECT_ROOT / "ui" / "chat.py").read_text(encoding="utf-8")

    assert ".fa-main { width: 100%; margin-left: 0;" in theme
    assert ".fa-message-list { width: 100%; max-width: 900px; margin: 0 auto;" in theme
    assert 'body:has(.q-drawer--left[style*="translateX(0px)"]) .fa-composer-shell { left: 256px; }' in theme
    assert ".fa-composer-shell { position: fixed; left: 0; right: 0; bottom: 0; box-sizing: border-box; padding: 16px max(5vw, 32px) 22px; background: transparent;" in theme
    assert 'ui.left_drawer(value=True).props("width=256 show-if-above breakpoint=760")' in chat
    assert 'with ui.column().classes("fa-main w-full"):' in chat


def test_welcome_screen_has_a_centered_headline_and_composer_before_chat_begins():
    theme = (PROJECT_ROOT / "ui" / "theme.py").read_text(encoding="utf-8")
    chat = (PROJECT_ROOT / "ui" / "chat.py").read_text(encoding="utf-8")

    assert ".fa-welcome-stage {" in theme
    assert ".fa-welcome-headline {" in theme
    assert ".fa-welcome-composer { top: 50%; bottom: auto;" in theme
    assert "self.welcome_stage.visible = is_welcome" in chat
    assert "self.composer_shell.classes(add=\"fa-welcome-composer\")" in chat
