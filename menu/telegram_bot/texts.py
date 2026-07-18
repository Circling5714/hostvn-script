"""Mau tin nhan HTML + escape du lieu nguoi dung."""
from __future__ import annotations

import html

import config as C


def esc(value: object) -> str:
    """Escape moi du lieu nguoi dung/he thong truoc khi nhung vao HTML."""
    return html.escape(str(value))


def greeting(name: str, host: str, mode: str) -> str:
    return (
        f"👋 Xin chào <b>{esc(name)}</b>!\n\n"
        f"{C.E['home']} <b>HOSTVN Control</b> — <code>{esc(host)}</code>\n"
        f"Chọn chức năng từ <b>menu bên dưới</b>.\n\n"
        f"<i>Chế độ: {esc(mode)} · điều khiển server ngay trên Telegram.</i>"
    )


def title(emoji: str, heading: str, hint: str = "") -> str:
    """'<emoji> <b>Tieu de</b>' + dong huong dan (HTML do lap trinh vien cung cap)."""
    msg = f"{emoji} <b>{esc(heading)}</b>"
    if hint:
        msg += f"\n{hint}"
    return msg


def pre(text: str) -> str:
    """Boc trong <pre> (da escape) cho khoi thong tin nhieu dong."""
    return f"<pre>{esc(text)}</pre>"


DENY = f"{C.E['deny']} Bạn không có quyền dùng chức năng này."
NOTIFY_ONLY = f"{C.E['warn']} Bot đang ở chế độ chỉ xem (notify)."
