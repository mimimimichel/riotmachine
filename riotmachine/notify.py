"""Notifications Telegram (facultatives) et journal des alertes déjà envoyées."""

from __future__ import annotations

import sqlite3

import httpx

from . import db
from .settings import get_settings


def telegram_configured() -> bool:
    s = get_settings()
    return bool(s.telegram_token and s.telegram_chat_id)


def send(text: str) -> bool:
    """Envoie un message Telegram. Sans configuration, écrit dans la console."""
    s = get_settings()
    if not telegram_configured():
        print(f"[notification] {text}")
        return False
    try:
        with httpx.Client(timeout=20) as client:
            r = client.post(
                f"https://api.telegram.org/bot{s.telegram_token}/sendMessage",
                json={
                    "chat_id": s.telegram_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
        return r.status_code < 400
    except httpx.HTTPError as exc:
        print(f"[notification] échec Telegram : {exc}")
        return False


def send_once(conn: sqlite3.Connection, key: str, text: str) -> bool:
    """N'envoie qu'une fois la même alerte (clé unique)."""
    if conn.execute("SELECT 1 FROM notifications WHERE key=?", (key,)).fetchone():
        return False
    conn.execute("INSERT INTO notifications (key, sent_at) VALUES (?,?)", (key, db.now()))
    send(text)
    return True


def regie_link(path: str = "") -> str:
    return f"{get_settings().regie_url}/{path.lstrip('/')}"
