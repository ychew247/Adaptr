"""Shared visual tokens for the NiceGUI fitness-agent interface."""

from __future__ import annotations

from nicegui import ui


def apply_theme() -> None:
    ui.add_head_html(
        """
        <style>
        :root {
          --fa-bg: #f7f8f8;
          --fa-surface: #ffffff;
          --fa-surface-hover: #eef3f2;
          --fa-border: #dde5e2;
          --fa-text: #18211f;
          --fa-text-muted: #68736f;
          --fa-accent: #0f766e;
          --fa-accent-soft: #dff3ee;
          --fa-success: #258158;
          --fa-warning: #a66c00;
          --fa-shadow: 0 10px 28px rgba(31, 47, 42, 0.08);
        }
        body.body--dark {
          --fa-bg: #151a19;
          --fa-surface: #1d2421;
          --fa-surface-hover: #26302c;
          --fa-border: #34403b;
          --fa-text: #edf4f0;
          --fa-text-muted: #a7b4ae;
          --fa-accent: #4dc6ad;
          --fa-accent-soft: #173d35;
          --fa-success: #65c68d;
          --fa-warning: #e3ad4a;
          --fa-shadow: 0 12px 28px rgba(0, 0, 0, 0.24);
        }
        *, *::before, *::after { box-sizing: border-box; }
        body { background: var(--fa-bg); color: var(--fa-text); overflow-x: hidden; }
        .q-page-container { padding-top: 0 !important; }
        .fa-sidebar { width: 256px !important; background: var(--fa-surface); border-right: 1px solid var(--fa-border); }
        .fa-sidebar .q-drawer__content { background: var(--fa-surface); }
        .fa-topbar { left: var(--q-layout-left, 0px) !important; right: var(--q-layout-right, 0px) !important; height: 64px; background: color-mix(in srgb, var(--fa-bg) 92%, transparent); border-bottom: 1px solid var(--fa-border); box-shadow: none; backdrop-filter: blur(12px); color: var(--fa-text) !important; }
        .fa-topbar .q-btn, .fa-topbar .q-icon { color: var(--fa-text) !important; }
        .fa-main { width: 100%; margin-left: 0; padding: 96px max(5vw, 32px) 132px; max-width: none; min-height: 100vh; }
        .fa-brand-mark { width: 34px; height: 34px; border-radius: 9px; background: var(--fa-accent); color: white; font-weight: 800; }
        .fa-nav-item { border-radius: 7px; color: var(--fa-text-muted); min-height: 38px; }
        .fa-nav-item:hover { background: var(--fa-surface-hover); color: var(--fa-text); }
        .fa-session-active { background: var(--fa-accent-soft); color: var(--fa-text); }
        .fa-new-chat { background: var(--fa-accent) !important; color: #ffffff !important; border-radius: 7px; min-height: 40px; }
        .fa-message-list { width: 100%; max-width: 900px; margin: 0 auto; gap: 18px; }
        .fa-welcome-stage { width: min(900px, 100%); min-height: calc(100vh - 260px); margin: 0 auto; align-items: center; justify-content: center; text-align: center; gap: 18px; padding-bottom: 130px; }
        .fa-welcome-headline { max-width: 760px; color: var(--fa-text); font-size: 3rem; line-height: 1.08; font-weight: 750; letter-spacing: 0; }
        .fa-welcome-prompt { max-width: 620px; color: var(--fa-text-muted); font-size: 1.08rem; line-height: 1.6; }
        .fa-message { width: 100%; align-items: flex-start; }
        .fa-user-message { margin-left: auto; max-width: min(76%, 660px); background: var(--fa-accent); color: white; border-radius: 12px; padding: 11px 14px; line-height: 1.5; white-space: pre-wrap; }
        .fa-agent-message { align-self: flex-start; width: 100%; max-width: 900px; color: var(--fa-text); line-height: 1.6; }
        .fa-agent-message .nicegui-markdown { color: var(--fa-text); }
        .fa-plan-table { width: 100%; border: 1px solid var(--fa-border); border-radius: 8px; overflow: hidden; background: var(--fa-surface); }
        .fa-plan-table th { color: var(--fa-text-muted); font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0; }
        .fa-plan-table td { white-space: pre-line; vertical-align: top; color: var(--fa-text); }
        .fa-composer-shell { position: fixed; left: 0; right: 0; bottom: 0; box-sizing: border-box; padding: 16px max(5vw, 32px) 22px; background: transparent; transition: left 0.2s ease; z-index: 1000; }
        .fa-welcome-composer { top: 50%; bottom: auto; transform: translateY(90px); }
        body:has(.q-drawer--left[style*="translateX(0px)"]) .fa-composer-shell { left: 256px; }
        .fa-composer { max-width: 900px; margin: 0 auto; padding: 7px 8px 7px 15px; background: var(--fa-surface); border: 1px solid var(--fa-border); border-radius: 12px; box-shadow: var(--fa-shadow); }
        .fa-composer:focus-within { border-color: var(--fa-accent); }
        .fa-composer textarea { color: var(--fa-text) !important; }
        .fa-send { width: 40px; height: 40px; border-radius: 8px; background: var(--fa-accent) !important; color: white !important; }
        .fa-status-dot { width: 7px; height: 7px; border-radius: 99px; background: var(--fa-success); }
        .fa-inspector { width: 320px !important; background: var(--fa-surface); border-left: 1px solid var(--fa-border); }
        .fa-inspector .q-drawer__content { background: var(--fa-surface); }
        .fa-muted { color: var(--fa-text-muted); }
        @media (max-width: 760px) {
          .fa-sidebar { width: 256px !important; }
          .fa-topbar { left: 0 !important; }
          .fa-main { margin-left: 0; padding: 86px 16px 128px; }
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
