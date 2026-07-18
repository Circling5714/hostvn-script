"""Cau hinh bot hostvn (Python) + hang so dung chung.

Doc /var/hostvn/.telegram_bot.conf (dinh dang bash KEY="value"):
    BOT_TOKEN="..."
    ALLOWED_CHAT_IDS="352725269,-1004333782002"
    BOT_MODE="menu"            # notify (chi xem) | menu (dieu khien)
    ADMIN_IDS="352725269"      # (tuy chon) thay tat ca + thao tac nguy hiem; mac dinh = ALLOWED
    USER_FEATURES="123:domain,db;456:svc"   # (tuy chon) phan quyen theo feature cho tung user
"""
from __future__ import annotations

import re
from pathlib import Path

CONF_PATH = "/var/hostvn/.telegram_bot.conf"

# --------------------------------------------------------------------------- #
# Duong dan he thong hostvn
# --------------------------------------------------------------------------- #
BASH_DIR = "/var/hostvn"
FILE_INFO = f"{BASH_DIR}/.hostvn.conf"
USERS_DIR = f"{BASH_DIR}/users"
VHOST_DIR = "/etc/nginx/conf.d"
STATE_DIR = f"{BASH_DIR}/.tgbot_py"
ENVIRONMENT = f"{BASH_DIR}/menu/helpers/environment"
MYSQL_SOCK = "/run/mysqld/mysqld.sock"
PATH_ENV = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# --------------------------------------------------------------------------- #
# Feature keys (khoa quyen theo tung nhom menu hostvn)
# --------------------------------------------------------------------------- #
F_DOMAIN = "domain"
F_DB = "db"
F_WP = "wp"
F_SSL = "ssl"
F_CACHE = "cache"
F_BACKUP = "backup"
F_FW = "fw"
F_PHP = "php"
F_SVC = "svc"
F_SYS = "sys"
F_VPS = "vps"
F_TOOL = "tool"
F_LEMP = "lemp"
F_PERM = "perm"
F_ACC = "acc"     # Xem thong tin tai khoan (menu 11)
F_CRON = "cron"   # Cronjob / Auto Backup (menu 12)
F_UPD = "upd"     # Cap nhat HostVN Scripts (menu 14)
F_LANG = "lang"   # Change language (menu 15)   # Phan quyen Chown/Chmod (menu 6)   # gom Nginx/PHP/Database/Log giong menu 4 cua shell

# Nhom "chi xem" (BOT_MODE=notify van dung duoc).
VIEW_FEATURES = {F_DOMAIN, F_DB, F_WP, F_SSL, F_FW, F_PHP, F_SVC, F_SYS, F_VPS,
                 F_TOOL, F_LEMP, F_PERM, F_ACC, F_CRON, F_UPD, F_LANG}

# --------------------------------------------------------------------------- #
# Quy uoc emoji (moi nhan/tieu de mo dau bang emoji khop nghia)
# --------------------------------------------------------------------------- #
E = {
    "home": "🏠", "menu": "📋",
    "domain": "🌐", "db": "🗄️", "wp": "📝", "ssl": "🔒", "cache": "⚡",
    "backup": "💾", "fw": "🛡️", "php": "🐘", "svc": "🔧", "sys": "🖥️",
    "vps": "⚙️", "tool": "🛠️", "status": "📊", "lemp": "🧱", "log": "📜", "perm": "🔐", "acc": "👤",
    "cron": "⏰", "upd": "🔄", "lang": "🌐", "admin": "🛡️",
    "cancel": "❌", "back": "⬅️", "confirm": "✅", "warn": "⚠️", "deny": "🚫",
    "add": "➕", "del": "🗑️", "info": "ℹ️", "refresh": "🔄", "list": "📋",
    "on": "🟢", "off": "🔴", "start": "▶️", "stop": "⏹", "reboot": "♻️",
    "month": "📅", "seat": "💺", "key": "🔑",
}

LBL_CANCEL = f"{E['cancel']} Hủy"
LBL_MENU = f"{E['menu']} Menu"
LBL_BACK = f"{E['back']} Quay lại"
LBL_HOME = f"{E['home']} Menu chính"

CB_HOME = "nav|home"

# --------------------------------------------------------------------------- #
# Doc file cau hinh dang bash KEY="value"
# --------------------------------------------------------------------------- #
_KV = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$')


def _strip_quotes(v: str) -> str:
    """Bo cap nhay bao quanh (ho tro ca ' lan ") -- conf co the dung mot trong hai."""
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def _read_conf(path: str = CONF_PATH) -> dict[str, str]:
    data: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return data
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _KV.match(line)
        if m:
            data[m.group(1)] = _strip_quotes(m.group(2))
    return data


_conf = _read_conf()

BOT_TOKEN: str = _conf.get("BOT_TOKEN", "")
BOT_MODE: str = _conf.get("BOT_MODE", "menu").strip() or "menu"


def _parse_ids(raw: str) -> set[int]:
    out: set[int] = set()
    for tok in raw.replace(" ", "").split(","):
        if tok.lstrip("-").isdigit():
            out.add(int(tok))
    return out


ALLOWED_CHAT_IDS: set[int] = _parse_ids(_conf.get("ALLOWED_CHAT_IDS", ""))
# Neu khong khai bao ADMIN_IDS -> coi TAT CA chat duoc phep la admin (giu hanh vi cu).
ADMIN_IDS: set[int] = _parse_ids(_conf.get("ADMIN_IDS", "")) or set(ALLOWED_CHAT_IDS)


def _parse_user_features(raw: str) -> dict[int, set[str]]:
    """ "123:domain,db;456:svc,sys" -> {123:{domain,db}, 456:{svc,sys}} """
    out: dict[int, set[str]] = {}
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        uid, feats = chunk.split(":", 1)
        uid = uid.strip()
        if uid.lstrip("-").isdigit():
            out[int(uid)] = {f.strip() for f in feats.split(",") if f.strip()}
    return out


USER_FEATURES: dict[int, set[str]] = _parse_user_features(_conf.get("USER_FEATURES", ""))
