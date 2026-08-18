"""Shared visual tokens for the NiceGUI fitness-agent interface."""

from __future__ import annotations

from nicegui import ui


def apply_theme() -> None:
    ui.colors(primary="#a3e635", secondary="#9895b9", accent="#a3e635")
    ui.add_head_html(
        """
        <style>
        :root {
          --fa-bg: #0d0d14;
          --fa-surface: #16161f;
          --fa-surface-hover: #20202c;
          --fa-border: #2a2a3d;
          --fa-text: #f2f0f8;
          --fa-text-muted: #9895b9;
          --fa-accent: #a3e635;
          --fa-accent-soft: #2b2a43;
          --fa-success: #a3e635;
          --fa-warning: #f4c95d;
          --fa-shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
        }
        body:not(.body--dark) {
          --fa-bg: #f7f6fb;
          --fa-surface: #ffffff;
          --fa-surface-hover: #efedf6;
          --fa-border: #d9d6e7;
          --fa-text: #15141d;
          --fa-text-muted: #6f6a8e;
          --fa-accent-soft: #e7f6c8;
          --fa-shadow: 0 18px 45px rgba(34, 30, 53, 0.12);
        }
        *, *::before, *::after { box-sizing: border-box; }
        body { background: var(--fa-bg); color: var(--fa-text); overflow-x: hidden; }
        .q-page-container { padding-top: 0 !important; }
        .fa-sidebar { width: 256px !important; background: var(--fa-surface); border-right: 1px solid var(--fa-border); }
        .fa-sidebar .q-drawer__content { background: var(--fa-surface); }
        .fa-topbar { left: var(--q-layout-left, 0px) !important; right: var(--q-layout-right, 0px) !important; height: 58px; background: rgba(13, 13, 20, 0.95); border-bottom: 1px solid var(--fa-border); box-shadow: none; backdrop-filter: blur(12px); color: var(--fa-text) !important; }
        .fa-topbar .q-btn, .fa-topbar .q-icon { color: var(--fa-text) !important; }
        .fa-topbar-title { color: #f2f0f8 !important; }
        .fa-main { width: 100%; margin-left: 0; padding: 88px max(5vw, 32px) 132px; max-width: none; min-height: 100vh; }
        .fa-dot-grid { background-color: var(--fa-bg); background-image: radial-gradient(circle, rgba(152, 149, 185, 0.18) 1px, transparent 1.2px); background-size: 26px 26px; }
        .fa-brand-logo { width: 50px; height: 50px; border: 1px solid var(--fa-border); border-radius: 11px; overflow: hidden; }
        .fa-nav-item { border-radius: 7px; color: var(--fa-text-muted); min-height: 38px; }
        .fa-nav-item:hover { background: var(--fa-surface-hover); color: var(--fa-accent); }
        .fa-session-active { background: var(--fa-accent-soft); color: var(--fa-accent); }
        .fa-new-chat { background: var(--fa-accent) !important; color: #101015 !important; border-radius: 8px; min-height: 48px; font-weight: 700; }
        .fa-message-list { width: 100%; max-width: 900px; margin: 0 auto; gap: 18px; }
        .fa-welcome-stage { width: min(900px, 100%); min-height: calc(100vh - 260px); margin: 0 auto; align-items: center; justify-content: center; text-align: center; gap: 18px; padding-bottom: 130px; }
        .fa-welcome-headline { max-width: 760px; color: var(--fa-text); font-size: clamp(2.7rem, 5vw, 4rem); line-height: 1.02; font-weight: 800; letter-spacing: -0.04em; }
        .fa-welcome-prompt { max-width: 620px; color: var(--fa-text-muted); font-size: 1.08rem; line-height: 1.6; }
        .fa-message { width: 100%; align-items: flex-start; }
        .fa-user-message { margin-left: auto; max-width: min(76%, 660px); background: var(--fa-accent); color: #101015; border-radius: 12px; padding: 11px 14px; line-height: 1.5; white-space: pre-wrap; }
        .fa-agent-message { align-self: flex-start; width: 100%; max-width: 900px; color: var(--fa-text); line-height: 1.6; }
        .fa-agent-message .nicegui-markdown { color: var(--fa-text); }
        .fa-processing { color: var(--fa-text-muted); font-size: 0.8rem; line-height: 1.4; opacity: 0.72; padding-left: 2px; animation: fa-processing-pulse 1.6s ease-in-out infinite; }
        .fa-stopped { animation: none; opacity: 0.62; }
        @keyframes fa-processing-pulse { 0%, 100% { opacity: 0.46; } 50% { opacity: 0.8; } }
        .fa-plan-table { width: 100%; border: 1px solid var(--fa-border); border-radius: 10px; overflow: hidden; background: var(--fa-surface); }
        .fa-plan-table th { color: var(--fa-text-muted); font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0; }
        .fa-plan-table td { white-space: pre-line; vertical-align: top; color: var(--fa-text); }
        .fa-composer-shell { position: fixed; left: 0; right: 0; bottom: 0; box-sizing: border-box; padding: 16px max(5vw, 32px) 22px; background: transparent; transition: left 0.2s ease; z-index: 1000; }
        .fa-welcome-composer { top: 50%; bottom: auto; transform: translateY(90px); }
        body:has(.q-drawer--left[style*="translateX(0px)"]) .fa-composer-shell { left: 256px; }
        .fa-composer { max-width: 825px; margin: 0 auto; padding: 9px 10px 9px 18px; background: var(--fa-surface); border: 1px solid var(--fa-border); border-radius: 17px; box-shadow: var(--fa-shadow); }
        .fa-composer:focus-within { border-color: var(--fa-accent); }
        .fa-composer textarea { color: var(--fa-text) !important; }
        .fa-send { width: 46px; height: 46px; border-radius: 12px; background: #302f47 !important; color: #aaa7c7 !important; }
        .fa-composer:focus-within .fa-send { background: var(--fa-accent) !important; color: #101015 !important; }
        .fa-status-dot { width: 7px; height: 7px; border-radius: 99px; background: var(--fa-success); }
        .fa-muted { color: var(--fa-text-muted); }
        @media (max-width: 760px) {
          .fa-sidebar { width: 256px !important; }
          .fa-topbar { left: 0 !important; }
          .fa-main { margin-left: 0; padding: 78px 16px 128px; }
          .fa-welcome-stage { min-height: calc(100vh - 220px); padding-bottom: 120px; }
          .fa-welcome-headline { font-size: 2.25rem; }
          .fa-composer-shell { left: 0; padding: 14px 16px 18px; }
          .fa-welcome-composer { top: 54%; }
          body:has(.q-drawer--left[style*="translateX(0px)"]) .fa-composer-shell { left: 0; }
          .fa-user-message { max-width: 88%; }
        }
        </style>
        """,
        shared=True,
    )
