"""Diem khoi chay HOSTVN Telegram bot (python-telegram-bot v20+, async).

Doc token/quyen tu /var/hostvn/.telegram_bot.conf (thiet lap qua menu control_bot).
Chay:  python bot.py    (systemd unit hostvn-telegram-bot goi qua venv/bin/python)
"""
from __future__ import annotations

import asyncio
import logging
import os
import urllib.error
import urllib.request

from telegram import MenuButtonCommands, Update
from telegram.error import InvalidToken
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config as C
import handlers as H
import hostvn
import menus
from permissions import get_user_features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
# httpx log nguyen URL moi request, ma URL cua Telegram co CHUA BOT TOKEN
# -> token bi ghi vao journald/log file. Chi giu lai muc canh bao tro len.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("hostvn-bot")


async def _broadcast(app: Application, text: str, kb=None) -> None:
    for cid in C.ALLOWED_CHAT_IDS:
        try:
            await app.bot.send_message(cid, text, parse_mode="HTML", reply_markup=kb)
        except Exception as e:  # noqa: BLE001
            log.warning("broadcast %s: %s", cid, e)


async def _monitor(app: Application) -> None:
    """Canh bao khi dich vu chinh chet hoac o dia day (5 phut/lan)."""
    down: set[str] = set()
    disk_warned = False
    while True:
        try:
            pv = await asyncio.to_thread(hostvn.php_version)
            names = ["nginx", "mariadb", f"php{pv}-fpm"]
            stat = await asyncio.to_thread(hostvn.services_status, names)
            for n in names:
                if stat.get(n) != "active":
                    if n not in down:
                        await _broadcast(app, f"⚠️ Dịch vụ <b>{n}</b> KHÔNG chạy.")
                        down.add(n)
                else:
                    down.discard(n)
            raw = await asyncio.to_thread(hostvn.sh, "df / | awk 'NR==2{print $5}' | tr -d '%'", 10)
            usage = int(raw) if raw.isdigit() else 0
            if usage >= 90 and not disk_warned:
                await _broadcast(app, f"⚠️ Ổ đĩa đã dùng {usage}%.")
                disk_warned = True
            elif usage < 90:
                disk_warned = False
        except Exception as e:  # noqa: BLE001
            log.warning("monitor: %s", e)
        await asyncio.sleep(300)


async def post_init(app: Application) -> None:
    try:
        await app.bot.set_my_commands([
            ("menu", "Mở menu HOSTVN"),
            ("start", "Bắt đầu"),
            ("cancel", "Huỷ"),
        ])
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception as e:  # noqa: BLE001
        log.warning("set menu button: %s", e)

    for cid in C.ALLOWED_CHAT_IDS:
        try:
            kb = menus.build_keyboard(get_user_features(cid))
            await app.bot.send_message(
                cid,
                f"🤖 <b>HOSTVN Bot</b> sẵn sàng (chế độ: {C.BOT_MODE}).\n"
                f"Bấm <b>menu bên dưới</b> hoặc gõ /menu.",
                parse_mode="HTML", reply_markup=kb,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("boot notify %s: %s", cid, e)

    # PTB canh bao task tao o post_init khong duoc tu dong await luc tat (app chua
    # start). Vong lap _monitor van chay dung; canh bao chi lien quan luc shutdown.
    # Builder cua PTB 21.x KHONG co hook post_start de chuyen sang, va JobQueue can
    # extra 'python-telegram-bot[job-queue]' — nen giu nguyen cach nay.
    app.create_task(_monitor(app))


async def on_error(update: object, context) -> None:
    log.exception("handler error: %s", getattr(context, "error", None))


BAD_TOKEN_MSG = ("BOT_TOKEN bi Telegram tu choi. Kiem tra lai token trong "
                 "/var/hostvn/.telegram_bot.conf (hostvn -> Telegram Notify -> 5).")


def _token_rejected() -> bool:
    """Token co bi tu choi khong (401)?

    Kiem TRUOC khi dung Application: khi token sai, PTB nem InvalidToken voi
    thong bao CO NHUNG NGUYEN BOT TOKEN, va traceback do bi in ra stderr ->
    token roi vao journald/log file. Chan tu day thi PTB khong co co hoi do.

    Chi coi 401 la loi chi tu. Moi truong hop khac (mat mang, DNS hong...)
    deu bo qua de bot van khoi dong va tu thu lai nhu truoc.
    """
    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{C.BOT_TOKEN}/getMe", timeout=15
        ):
            return False
    except urllib.error.HTTPError as e:
        return e.code == 401
    except Exception:  # noqa: BLE001
        return False


def main() -> None:
    if not C.BOT_TOKEN:
        raise SystemExit("Thiếu BOT_TOKEN trong /var/hostvn/.telegram_bot.conf")
    if _token_rejected():
        raise SystemExit(BAD_TOKEN_MSG)
    os.makedirs(C.STATE_DIR, exist_ok=True)

    app = Application.builder().token(C.BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", H.start))
    app.add_handler(CommandHandler("menu", H.show_menu))
    app.add_handler(CommandHandler("cancel", H.cancel))
    app.add_handler(CallbackQueryHandler(H.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, H.on_menu_text))
    app.add_error_handler(on_error)

    log.info("HOSTVN bot dang chay (long polling)...")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except InvalidToken:
        # Luoi thu hai: token bi thu hoi GIUA CHUNG khi bot dang chay.
        raise SystemExit(BAD_TOKEN_MSG) from None


if __name__ == "__main__":
    main()
