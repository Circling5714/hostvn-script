"""Handler + dinh tuyen trung tam (hostvn bot).

- /start, /menu, /cancel
- on_menu_text: nut menu chinh (ReplyKeyboard gui text) + nhap lieu cho conversation
- on_callback: tach callback_data bang split("|") -> dinh tuyen theo <mien>
- Cac tac vu he thong chay qua asyncio.to_thread (khong chan event loop)
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import config as C
import hostvn
import menus
import progress
import texts
from permissions import (can_write, get_user_features, has_feature,
                         is_actor_allowed, is_allowed)

HTML = ParseMode.HTML
E = C.E
title = texts.title
pre = texts.pre

WRITE_ACTIONS = {"dom_add", "db_add", "cache_clear", "opcache_clear", "php_restart",
                 "bk_run", "bk_restore", "bk_del",
                 "dom_rename", "dom_rewrite", "dom_php", "dom_alias", "dom_redirect",
                 "dom_sftp", "dom_protect", "dom_http3", "dom_clone", "dom_dbinfo",
                 "ssl_create", "ssl_wildcard", "ssl_remove", "ssl_alias",
                 "ssl_renew", "ssl_cfapi",
                 "cache_clear_all", "cache_mc", "cache_redis",
                 "cache_opcache", "cache_fastcgi",
                 "fw_ban", "fw_unban", "fw_jails",
                 "perm_one", "perm_all",
                 "wp_core", "wp_plugins", "wp_plugupd", "wp_plugoff", "wp_optimize",
                 "wp_moveconf", "wp_htpasswd", "wp_edit", "wp_lockdown",
                 "wpa_yoast", "wpa_rank", "wpa_webp", "wpa_cacheplug",
                 "wpa_cachekey", "wpa_debug", "wpa_maint", "wpa_xmlrpc",
                 "wpa_userapi", "wpa_cron", "wpa_revision",
                 "cron_del", "cron_local", "cron_gg", "cron_od", "cron_custom",
                 "adm_pass", "adm_port", "adm_pma", "adm_opc", "adm_redis",
                 "adm_mc", "tool_nodejs", "tool_img", "tool_unzip",
                 "tool_deploy", "tool_av", "tool_ggdl", "acc_sftp"}


# --------------------------------------------------------------------------- #
# Tien ich gui / sua tin
# --------------------------------------------------------------------------- #
async def _show(update: Update, text: str, kb, edit: bool) -> None:
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, parse_mode=HTML, reply_markup=kb)


def _features(chat_id: int):
    return get_user_features(chat_id)


async def _make_editor(update: Update, edit_existing: bool):
    """Tra ve async editor(text, kb=None) nham vao tin can cap nhat.

    - callback: sua chinh tin nhan vua bam (edit_existing=True).
    - text tap: gui 1 tin '⏳' roi sua dan (edit_existing=False).
    Dung cho ca khung animate (goi editor(text)) lan ket qua (editor(text, kb)).
    """
    if edit_existing and update.callback_query:
        q = update.callback_query

        async def _edit_cb(text, kb=None):
            try:
                await q.edit_message_text(text, parse_mode=HTML, reply_markup=kb)
            except Exception:  # noqa: BLE001
                pass
        return _edit_cb

    msg = await update.effective_message.reply_text(
        f"⏳ <b>Đang tải…</b>\n<code>{progress.bar(3)}</code>", parse_mode=HTML)

    async def _edit_msg(text, kb=None):
        try:
            await msg.edit_text(text, parse_mode=HTML, reply_markup=kb)
        except Exception:  # noqa: BLE001
            pass
    return _edit_msg


async def _progress_op(update, edit_existing, loading_title, work, render, est=5.0, stages=None):
    """Hien thanh tien trinh khi chay 'work' (awaitable) roi hien ket qua.

    render(result) -> (text, keyboard).
    """
    editor = await _make_editor(update, edit_existing)
    result = await progress.run(editor, loading_title, work, est=est, stages=stages)
    text, kb = render(result)
    await editor(text, kb)
    return result


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Kiem quyen: LUON dua tren NGUOI bam, khong phai khung chat
#
# Trong nhom, moi thanh vien deu bam duoc nut cua tin nhan bot gui. Neu chi
# kiem chat id thi ai o trong nhom cung dieu khien duoc may chu bang quyen
# root. Vi vay: chat phai nam trong ALLOWED_CHAT_IDS *va* nguoi bam cung phai
# duoc phep; moi kiem tra phia sau (can_write/has_feature) dung id NGUOI bam.
# --------------------------------------------------------------------------- #
def _actor(update: Update) -> int | None:
    u = getattr(update, "effective_user", None)
    return u.id if u else None


def _gate(update: Update) -> int | None:
    """Tra id nguoi bam neu duoc phep, None neu tu choi."""
    ch = getattr(update, "effective_chat", None)
    if ch is None or not is_allowed(ch.id):
        return None
    actor = _actor(update)
    return actor if is_actor_allowed(actor) else None


# --------------------------------------------------------------------------- #
# Lenh
# --------------------------------------------------------------------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _gate(update)
    if chat is None:
        return await update.message.reply_text("🚫 Bạn không có quyền dùng bot này.")
    user = update.effective_user
    host = await asyncio.to_thread(hostvn.sh, "hostname", 5)
    await update.message.reply_text(
        texts.greeting(user.first_name or "bạn", host, C.BOT_MODE),
        parse_mode=HTML,
        reply_markup=menus.build_keyboard(_features(_actor(update))),
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, note: str = "") -> None:
    if _gate(update) is None:
        return
    hint = note or "Chọn chức năng từ <b>menu bên dưới</b>."
    await update.effective_message.reply_text(
        title(E["home"], "Menu chính", hint),
        parse_mode=HTML,
        reply_markup=menus.build_keyboard(_features(_actor(update))),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("flow", None)
    await update.effective_message.reply_text(
        title(E["cancel"], "Đã huỷ", "Chọn lại từ <b>menu bên dưới</b>."),
        parse_mode=HTML,
        reply_markup=menus.build_keyboard(_features(_actor(update))),
    )


# --------------------------------------------------------------------------- #
# Nut menu chinh + nhap lieu conversation
# --------------------------------------------------------------------------- #
async def on_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = _gate(update)
    if chat is None:
        return
    text = (update.message.text or "").strip()

    if text == C.LBL_CANCEL:
        return await cancel(update, context)
    if text == C.LBL_MENU:
        return await show_menu(update, context)

    feature = menus.LABEL_TO_FEATURE.get(text)
    flow = context.user_data.get("flow")
    if flow and feature is None:
        return await handle_flow(update, context, flow, text)
    if feature is None:
        return await show_menu(update, context, "Vui lòng chọn từ <b>menu bên dưới</b>.")

    context.user_data.pop("flow", None)  # dieu huong sang nhom khac -> huy flow
    if not has_feature(chat, feature):
        return await update.message.reply_text(texts.DENY, parse_mode=HTML)
    await open_group(update, context, feature, edit=False)


# --------------------------------------------------------------------------- #
# Man hinh nhom (sync builder -> chay trong thread)
# --------------------------------------------------------------------------- #
def _screen_domain():
    return title(E["domain"], "Quản lý Domain", ""), menus.domain_menu()


def _screen_db():
    return title(E["db"], "Quản lý Database", ""), menus.db_menu()


def _screen_wp():
    return title(E["wp"], "WordPress", "Chọn thao tác:"), menus.wp_menu()


def _screen_ssl():
    return title(E["ssl"], "Quản lý SSL", ""), menus.ssl_menu()


def _screen_cache():
    return (title(E["cache"], "Cache",
                  f"Redis {hostvn.icon('redis')} · Memcached {hostvn.icon('memcached')}"),
            menus.cache_menu())


def _screen_backup():
    return title(E["backup"], "Backup", ""), menus.backup_menu()


def _screen_fw():
    return (title(E["fw"], "Firewall / Fail2ban", f"Fail2ban {hostvn.icon('fail2ban')}"),
            menus.fw_menu())


def _screen_php():
    return title(E["php"], f"PHP {hostvn.php_version()}", ""), menus.php_menu()


def _screen_wpadv():
    return title(E["wp"], "WordPress nâng cao", "Chọn thao tác:"), menus.wp_adv_menu()


def _screen_wpplug():
    return title("🧩", "Plugins manager", "Chọn thao tác:"), menus.wp_plugins_menu()


def _screen_acc():
    return title(E["acc"], "Thông tin tài khoản", "Chọn mục cần xem:"), menus.acc_menu()


def _screen_cron():
    return title(E["cron"], "Cronjob / Auto Backup", "Chọn thao tác:"), menus.cron_menu()


def _screen_admin():
    port = hostvn.conf_val("admin_port")
    return (title(E["admin"], "Admin Tool", f"Cổng quản trị: <b>{port}</b>"),
            menus.admin_menu())


def _screen_upd():
    cur, new = hostvn.script_versions()
    has_new = bool(new and new != "?" and new != cur)
    body = f"Đang cài  : {cur}\nPhát hành : {new}"
    hint = ("\n\n⚠️ Cập nhật sẽ thay toàn bộ thư mục <code>menu/</code> (gồm cả file bot). "
            "Bot sẽ được khởi động lại sau khi xong." if has_new else "")
    return (title(E["upd"], "Cập nhật HostVN Scripts", pre(body) + hint),
            menus.upd_menu(has_new, new))


def _screen_lang():
    cur = hostvn.conf_val("lang") or "vi"
    return (title(E["lang"], "Change language",
                  f"Ngôn ngữ menu <b>shell</b> hiện tại: <b>{cur}</b>\n"
                  f"<i>Chỉ đổi menu khi gõ lệnh <code>hostvn</code> qua SSH; "
                  f"menu bot luôn tiếng Việt.</i>"),
            menus.lang_menu(cur))


def _screen_perm():
    return (title(E["perm"], "Phân quyền Chown/Chmod",
                  "Đặt lại quyền chuẩn: thư mục 755, file 644, chủ sở hữu là user của website."),
            menus.perm_menu())


def _screen_lemp():
    pv = hostvn.php_version()
    st = hostvn.services_status(["nginx", "mariadb", f"php{pv}-fpm"])
    ic = lambda n: E["on"] if st.get(n) == "active" else E["off"]
    body = (f"Nginx {ic('nginx')}  ·  MariaDB {ic('mariadb')}  ·  "
            f"PHP {pv} {ic(f'php{pv}-fpm')}")
    return (title(E["lemp"], "Quản lý LEMP", body + "\nChọn thành phần:"),
            menus.lemp_menu())


def _screen_nginx():
    v = hostvn.sh("nginx -v 2>&1 | head -1", 10)
    ok = hostvn.sh("nginx -t 2>&1 | tail -1", 20)
    return (title(E["svc"], "Nginx", pre(f"{v}\n{ok}")), menus.nginx_menu())


def _screen_log():
    def sz(p):
        s = hostvn.sh(f"du -h {p} 2>/dev/null | cut -f1", 10)
        return s or "—"
    body = (f"nginx : {sz('/var/log/nginx/error.log')}\n"
            f"php   : {sz('/var/log/php-fpm/error.log')}\n"
            f"mysql : {sz('/var/log/mysql/mysqld.log')}")
    return title(E["log"], "Error Log", pre(body)), menus.log_menu()


def _screen_svc():
    pv = hostvn.php_version()
    names = ["nginx", "mariadb", f"php{pv}-fpm", "redis", "memcached",
             "fail2ban", "cloudflared", "cron"]
    stat = hostvn.services_status(names)
    items = [((E["on"] if stat.get(n) == "active" else E["off"]) + f" {n}", n) for n in names]
    return title(E["svc"], "Dịch vụ", "Bấm để điều khiển:"), menus.services_menu(items)


def _screen_sys():
    st = hostvn.status()
    pv = st["php_ver"]
    body = (
        f"Nginx      : {st['nginx']}\n"
        f"MariaDB    : {st['mariadb']}\n"
        f"PHP-FPM    : {st['php' + pv + '-fpm']}\n"
        f"Redis      : {st['redis']}\n"
        f"Memcached  : {st['memcached']}\n"
        f"Fail2ban   : {st['fail2ban']}\n"
        f"Cloudflared: {st['cloudflared']}\n"
        f"Disk : {st['disk']}\n"
        f"RAM  : {st['ram']}\n"
        f"Load : {st['load']}\n"
        f"Uptime: {st['uptime']}"
    )
    return title(E["sys"], "Trạng thái hệ thống", pre(body)), menus.sys_menu()


def _screen_vps():
    return title(E["vps"], "Quản lý VPS", ""), menus.vps_menu()


def _screen_tool():
    return title(E["tool"], "Công cụ", ""), menus.tool_menu()


GROUP_SCREENS = {
    C.F_DOMAIN: _screen_domain, C.F_DB: _screen_db, C.F_WP: _screen_wp,
    C.F_SSL: _screen_ssl, C.F_CACHE: _screen_cache, C.F_BACKUP: _screen_backup,
    C.F_FW: _screen_fw, C.F_PHP: _screen_php, C.F_SVC: _screen_svc,
    C.F_SYS: _screen_sys, C.F_VPS: _screen_vps, C.F_TOOL: _screen_tool,
    C.F_LEMP: _screen_lemp, C.F_PERM: _screen_perm,
    C.F_ACC: _screen_acc, C.F_CRON: _screen_cron,
    C.F_UPD: _screen_upd, C.F_LANG: _screen_lang,
    # man phu (mo qua "m|nginx" / "m|log", khong nam o menu chinh)
    "nginx": _screen_nginx, "log": _screen_log,
    "wpadv": _screen_wpadv, "wpplug": _screen_wpplug,
    "admin": _screen_admin,
}


# Nhan hien thi cua tung nhom (dung cho tieu de thanh tien trinh)
FEATURE_LABEL = {k: lbl for row in menus.MAIN_MENU for k, lbl in row}


async def open_group(update: Update, context: ContextTypes.DEFAULT_TYPE, feature: str, edit: bool) -> None:
    builder = GROUP_SCREENS.get(feature)
    if builder is None:
        return await show_menu(update, context)
    label = FEATURE_LABEL.get(feature, "")
    await _progress_op(
        update, edit,
        f"⏳ <b>Đang tải</b> {texts.esc(label)}…",
        asyncio.to_thread(builder),
        lambda r: r,          # builder da tra (text, keyboard)
        est=4.0,
    )


# --------------------------------------------------------------------------- #
# Router callback trung tam
# --------------------------------------------------------------------------- #
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat = _gate(update)
    if chat is None:
        return

    parts = (query.data or "").split("|")
    domain = parts[0] if parts else ""
    action = parts[1] if len(parts) > 1 else ""
    params = parts[2:]

    route = CALLBACK_ROUTES.get(domain)
    if route is None:
        return await query.edit_message_text("⚠️ Lựa chọn không hợp lệ.", parse_mode=HTML)
    await route(update, context, action, params)


async def cb_nav(update, context, action, params):
    if action == "home":
        await update.callback_query.edit_message_text(
            title(E["home"], "Menu chính", "Dùng <b>menu bên dưới</b> để chọn chức năng."),
            parse_mode=HTML,
        )


_SUB_FEATURE = {"nginx": C.F_LEMP, "log": C.F_LEMP,
                "wpadv": C.F_WP, "wpplug": C.F_WP, "admin": C.F_TOOL}


async def cb_open(update, context, feature, params):
    if not has_feature(_actor(update), _SUB_FEATURE.get(feature, feature)):
        return await update.callback_query.edit_message_text(texts.DENY, parse_mode=HTML)
    await open_group(update, context, feature, edit=True)


# ---- Dich vu ---------------------------------------------------------------- #
async def cb_svc(update, context, service, params):
    chat = _actor(update)
    if not has_feature(chat, C.F_SVC):
        return await update.callback_query.edit_message_text(texts.DENY, parse_mode=HTML)

    def render(state):
        ic = E["on"] if state == "active" else E["off"]
        return (title(E["svc"], service, f"Trạng thái: <b>{texts.esc(state)}</b> {ic}"),
                menus.service_one_menu(service, can_write(chat)))

    await _progress_op(update, True, f"⏳ <b>Đang kiểm tra</b> {texts.esc(service)}…",
                       asyncio.to_thread(hostvn.svc_status, service), render, est=3.0)


def _svc_act_then_status(act: str, service: str) -> str:
    hostvn.svc(act, service)
    return hostvn.svc_status(service)


async def cb_do(update, context, service, params):
    q = update.callback_query
    act = params[0] if params else ""
    if not can_write(_actor(update)):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|svc"))

    def render(state):
        ic = E["on"] if state == "active" else E["off"]
        return (title(E["confirm"], f"{act} {service}",
                      f"Trạng thái: <b>{texts.esc(state)}</b> {ic}"),
                menus.service_one_menu(service, True))

    await _progress_op(
        update, True,
        f"{E['refresh']} <b>Đang {texts.esc(act)}</b> {texts.esc(service)}…",
        asyncio.to_thread(_svc_act_then_status, act, service),
        render, est=5.0,
        stages=[(45, f"{E['refresh']} <b>Đang khởi động lại</b> {texts.esc(service)}…"),
                (80, f"{E['refresh']} <b>Đang kiểm tra trạng thái</b>…")],
    )


# ---- Hanh dong "a|..." ------------------------------------------------------ #
async def cb_action(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)

    if action in WRITE_ACTIONS and not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only())

    # ----- Cac hanh dong mo flow / picker -----
    if action == "dom_add":
        return await start_flow(update, context, "dom_add", "m|domain",
                                E["domain"], "Thêm domain",
                                "Nhập <b>tên miền</b> (vd: shop.com):")
    if action == "db_add":
        return await start_flow(update, context, "db_add", "m|db",
                                E["db"], "Tạo database",
                                "Nhập <b>tên database</b> (chỉ chữ/số/gạch dưới):")
    if action in ("fw_ban", "fw_unban"):
        ban = action == "fw_ban"
        return await start_flow(
            update, context, "fw_ban" if ban else "fw_unban", "m|fw",
            "⛔" if ban else "🔓", "Ban IP" if ban else "Unban IP",
            f"Nhập <b>địa chỉ IP</b> muốn {'chặn' if ban else 'gỡ chặn'} (vd: 1.2.3.4):")
    if action == "perm_all":
        return await q.edit_message_text(
            title(E["warn"], "Phân quyền TOÀN BỘ website",
                  "Đặt lại quyền cho <b>tất cả</b> website (thư mục 755, file 644, chown về "
                  "user của từng site). Với nhiều site có thể mất vài phút. Tiếp tục?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("permall", back="m|perm"))
    if action == "fw_jails":
        return await q.edit_message_text(
            title(E["warn"], "Bật thêm jail",
                  "Bật các jail bổ sung (recidive / nginx-botsearch / nginx-limit-req) "
                  "và restart Fail2ban. Tiếp tục?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("f2bjails", back="m|fw"))

    if action == "wp_plugins":
        return await open_group(update, context, "wpplug", edit=True)
    if action == "wp_install":
        return (await q.edit_message_text(
            title(E["wp"], "Cài WordPress tự động",
                  "Trên bot, cách nhanh nhất là tạo site mới đã kèm WordPress:\n"
                  "🌐 <b>Domain</b> → <b>Thêm domain</b> → chọn <b>📝 WordPress</b>.\n\n"
                  "Cài WordPress vào site PHP <i>đã có sẵn</i> cần nhập tên site, user và "
                  "email quản trị — chạy qua SSH: <code>hostvn</code> → "
                  "<b>7. Quan ly WordPress</b> → <b>1</b>."),
            parse_mode=HTML, reply_markup=menus.back_only("m|wp")))
    if action in WP_OPS or action in ("wp_info", "wp_pass"):
        pick = {"wp_info": "wpinfo2", "wp_pass": "wppass"}.get(action, f"wpop_{action}")
        lbl = WP_LABEL.get(action, {"wp_info": "Thông tin site",
                                    "wp_pass": "Đổi mật khẩu wp-admin"}.get(action, action))
        return await _progress_op(
            update, True, "⏳ <b>Đang tìm site WordPress…</b>",
            asyncio.to_thread(hostvn.wp_domains),
            lambda ds: (title(E["wp"], lbl,
                              "Chọn website:" if ds else "Chưa có website nào dùng WordPress."),
                        menus.picker_menu(pick, ds, E["wp"], "m|wp")),
            est=4.0)

    # ----- Cache: cac buoc rieng -----
    if action in ("cache_mc", "cache_redis"):
        name = "memcached" if action == "cache_mc" else "redis"
        def _mk(_n=name):
            installed = bool(hostvn.sh(
                f"command -v {'redis-server' if _n == 'redis' else 'memcached'}", 10))
            running = hostvn.svc_status(_n) == "active"
            ic = E["on"] if running else E["off"]
            body = (f"Cài đặt : {'có' if installed else 'chưa'}\n"
                    f"Trạng thái: {hostvn.svc_status(_n)}")
            return (title(E["cache"], _n.capitalize(), f"{ic}\n" + pre(body)),
                    menus.svc_pkg_menu(_n, running, installed))
        return await _progress_op(update, True, f"⏳ <b>Đang kiểm tra {name}…</b>",
                                  asyncio.to_thread(_mk), lambda r: r, est=4.0)
    if action == "cache_opcache":
        return await q.edit_message_text(
            title(E["php"], "PHP OPcache", "Chọn thao tác:"),
            parse_mode=HTML, reply_markup=menus.opcache_menu())
    if action == "cache_fastcgi":
        def _fc():
            on, off = hostvn.fastcgi_domains(True), hostvn.fastcgi_domains(False)
            body = (f"Đang bật: {', '.join(on) or '(không có)'}\n"
                    f"Đang tắt: {', '.join(off) or '(không có)'}")
            return (title("🚀", "Nginx FastCGI cache", pre(body)),
                    menus.fastcgi_menu(on, off))
        return await _progress_op(update, True, "⏳ <b>Đang đọc cấu hình vHost…</b>",
                                  asyncio.to_thread(_fc), lambda r: r, est=4.0)
    if action == "cache_clear_all":
        return await q.edit_message_text(
            title(E["warn"], "Xoá toàn bộ cache",
                  "Sẽ restart Redis/Memcached và xoá cache của tất cả website. Tiếp tục?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("clrall", back="m|cache"))

    if action == "acc_site":
        return await _progress_op(
            update, True, "⏳ <b>Đang tải danh sách website…</b>",
            asyncio.to_thread(hostvn.list_domains),
            lambda ds: (title(E["acc"], "Thông tin theo Website", "Chọn website:"),
                        menus.picker_menu("accsite", ds, E["domain"], "m|acc")),
            est=4.0)
    if action == "cron_del":
        return await q.edit_message_text(
            title(E["warn"], "Xoá cronjob",
                  "Xoá <b>toàn bộ</b> crontab của root, gồm cả lịch auto-backup và "
                  "lịch gia hạn SSL (acme.sh). Tiếp tục?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("cronclr", back="m|cron"))
    if action in ("adm_pma", "adm_opc", "adm_redis", "adm_mc"):
        ctl = {"adm_pma": "update_phpmyadmin", "adm_opc": "opcache_panel",
               "adm_redis": "redis_panel", "adm_mc": "php_memcached_admin"}[action]
        lbl = {"adm_pma": "phpMyAdmin", "adm_opc": "Opcache Panel",
               "adm_redis": "Redis Admin", "adm_mc": "Memcached Admin"}[action]
        return await q.edit_message_text(
            title(E["warn"], f"Update {lbl}",
                  f"Tải lại {lbl} từ nguồn chính thức và cài đè. Tiếp tục?"),
            parse_mode=HTML,
            reply_markup=menus.confirm_menu(f"admupd_{ctl}", lbl, back="m|admin"))
    if action == "tool_nodejs":
        return await q.edit_message_text(
            title("🟩", "Cài NodeJS", "Cài Node.js + npm từ NodeSource. Tiếp tục?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("nodejs", back="m|tool"))
    # ----- SSL: cac buoc rieng -----
    if action == "ssl_cfapi":
        return await _progress_op(
            update, True, "⏳ <b>Đang đọc cấu hình CF API…</b>",
            asyncio.to_thread(hostvn.cf_api_status),
            lambda st: (title("☁️", "CloudFlare DNS API", pre(st) +
                              "\n\nDùng cho <b>Wildcard SSL</b> (xác thực DNS-01)."),
                        menus.rows_menu([[("☁️ Nhập/Cập nhật token", "ssl|cfset")]], back="m|ssl")),
            est=3.0)
    if action == "ssl_renew":
        return await q.edit_message_text(
            title(E["warn"], "Gia hạn tất cả SSL",
                  "Chạy gia hạn cho <b>toàn bộ</b> chứng chỉ? Có thể mất vài phút."),
            parse_mode=HTML, reply_markup=menus.confirm_menu("sslrenew", back="m|ssl"))

    # ----- Backup: cac buoc rieng -----
    if action == "bk_del":
        return await _progress_op(
            update, True, "⏳ <b>Đang quét bản backup…</b>",
            asyncio.to_thread(hostvn.list_backups),
            lambda rows: (
                title(E["del"], "Xoá bản backup",
                      "Chọn bản muốn xoá:" if rows else "Chưa có bản backup nào."),
                menus.backup_entry_menu(
                    [(r["domain"], r["date"], f"{E['del']} {r['domain']} · {r['date']} ({r['size']})")
                     for r in rows], "del")),
            est=4.0)
    if action == "bk_remotes":
        return await _progress_op(
            update, True, "⏳ <b>Đang đọc cấu hình rclone…</b>",
            asyncio.to_thread(hostvn.rclone_remotes),
            lambda rs: (title("☁️", "Remote đã kết nối",
                              (pre("\n".join(rs)) + "\nBấm để <b>xoá</b> kết nối.") if rs
                              else "Chưa kết nối remote nào."),
                        menus.remotes_menu(rs)),
            est=3.0)

    # ----- Cac picker (tai danh sach) -----
    PICKERS = {
        "dom_info": (hostvn.list_domains, "dominfo", E["domain"], "m|domain",
                     (E["domain"], "Chọn domain", "Xem thông tin:")),
        "dom_del":  (hostvn.list_domains, "domdel", E["domain"], "m|domain",
                     (E["del"], "Xoá domain", "Chọn domain để XOÁ:")),
        "db_del":   (hostvn.list_dbs, "dbdel", E["db"], "m|db",
                     (E["del"], "Xoá database", "Chọn DB để XOÁ:")),
        "wp_cache": (hostvn.list_domains, "wpcache", E["wp"], "m|wp",
                     (E["wp"], "Xoá cache WP", "Chọn site:")),
        "bk_run":   (hostvn.list_domains, "bkdom", E["backup"], "m|backup",
                     (E["backup"], "Backup website", "Chọn website cần backup:")),
        "bk_restore": (hostvn.list_domains, "rsdom", E["domain"], "m|backup",
                       ("♻️", "Khôi phục dữ liệu", "Chọn website cần khôi phục:")),
        # --- Quan ly domain nang cao ---
        "dom_rename":   (hostvn.list_domains, "dmrename", E["domain"], "m|domain",
                         ("✏️", "Đổi tên miền", "Chọn domain cần đổi:")),
        "dom_rewrite":  (hostvn.list_domains, "dmrw", E["domain"], "m|domain",
                         ("🧱", "Rewrite vHost", "Chọn domain cần tạo lại vHost:")),
        "dom_php":      (hostvn.list_domains, "dmphp", E["domain"], "m|domain",
                         (E["php"], "Đổi phiên bản PHP", "Chọn domain:")),
        "dom_alias":    (hostvn.list_domains, "dmalias", E["domain"], "m|domain",
                         ("🔗", "Alias/Parked domain", "Chọn domain chính:")),
        "dom_redirect": (hostvn.list_domains, "dmredir", E["domain"], "m|domain",
                         ("↪️", "Redirect domain", "Chọn domain đích:")),
        "dom_sftp":     (hostvn.list_domains, "dmsftp", E["domain"], "m|domain",
                         (E["key"], "Đổi mật khẩu SFTP", "Chọn domain:")),
        "dom_protect":  (hostvn.list_domains, "dmprot", E["domain"], "m|domain",
                         ("🔐", "Bảo vệ thư mục", "Chọn domain:")),
        "dom_http3":    (hostvn.list_domains, "dmhttp3", E["domain"], "m|domain",
                         ("🚀", "HTTP/3 (QUIC)", "Chọn domain:")),
        # --- SSL ---
        "ssl_create":   (hostvn.list_domains, "sslnew", E["ssl"], "m|ssl",
                         (E["ssl"], "Cấp/Gia hạn Let's Encrypt", "Chọn domain:")),
        "ssl_wildcard": (hostvn.list_domains, "sslwild", E["ssl"], "m|ssl",
                         ("🌟", "Wildcard SSL", "Chọn domain gốc:")),
        "ssl_remove":   (hostvn.list_domains, "ssldel", E["ssl"], "m|ssl",
                         (E["del"], "Gỡ Let's Encrypt", "Chọn domain:")),
        "perm_check":   (hostvn.list_domains, "permchk", E["perm"], "m|perm",
                         (E["perm"], "Kiểm tra quyền", "Chọn website:")),
        "perm_one":     (hostvn.list_domains, "permone", E["perm"], "m|perm",
                         (E["key"], "Phân quyền 1 website", "Chọn website:")),
        "ssl_alias":    (hostvn.list_domains, "sslalias", E["ssl"], "m|ssl",
                         ("🔗", "SSL cho Alias domain", "Chọn domain chính:")),
    }
    if action in PICKERS:
        loader, pick_act, emo, back, (t_emo, t_head, t_hint) = PICKERS[action]
        return await _progress_op(
            update, True, "⏳ <b>Đang tải danh sách…</b>",
            asyncio.to_thread(loader),
            lambda items: (title(t_emo, t_head, t_hint),
                           menus.picker_menu(pick_act, items, emo, back)),
            est=3.0,
        )

    # ----- Cac hanh dong tra ket qua -----
    await _progress_op(
        update, True, "⏳ <b>Đang xử lý…</b>",
        asyncio.to_thread(_run_action, action, chat),
        lambda r: (r[0], menus.back_only(r[1])),
        est=6.0,
        stages=[(60, "⚙️ <b>Đang thu thập dữ liệu…</b>")],
    )


def _run_action(action: str, chat: int):
    """Sync: thuc hien 1 hanh dong read/write -> (text, back_target)."""
    if action == "dom_list":
        ds = hostvn.list_domains()
        body = "\n".join(f"{E['domain']} {d} — {hostvn.http_code(d)}" for d in ds) or "(chưa có)"
        return title(E["domain"], "Domain", pre(body)), "m|domain"
    if action == "db_list":
        body = "\n".join(f"{E['db']} {d}" for d in hostvn.list_dbs()) or "(chưa có)"
        return title(E["db"], "Database", pre(body)), "m|db"
    if action == "wp_list":
        lines = []
        for d in hostvn.list_domains():
            dr = hostvn.docroot(d)
            tag = "WP" if dr and (Path(dr) / "wp-admin").is_dir() else "—"
            lines.append(f"{E['wp']} {d} [{tag}]")
        return title(E["wp"], "Site WordPress", pre("\n".join(lines) or "(chưa có)")), "m|wp"
    if action == "ssl_check":
        note = ""
        if hostvn.is_tunnel_mode():
            note = ("\n<i>Lưu ý: qua Cloudflare Tunnel, chứng chỉ người dùng thấy là của "
                    "Cloudflare — không phản ánh chứng chỉ trên server.</i>")
        return (title(E["month"], "Đối chiếu chứng chỉ",
                      pre(hostvn.ssl_report()) + note), "m|ssl")
    if action == "f2b_stats":
        return title(E["fw"], "Fail2ban", pre(hostvn.fail2ban_stats())), "m|fw"
    if action == "php_info":
        return title(E["php"], f"PHP {hostvn.php_version()}", pre(hostvn.php_info())), "m|php"
    if action == "vps_info":
        return title(E["vps"], "Thông tin VPS", pre(hostvn.vps_info())), "m|vps"
    if action == "vps_disk":
        return title(E["vps"], "Dung lượng /home", pre(hostvn.vps_disk())), "m|vps"
    if action == "links":
        return title(E["tool"], "Link Admin", pre(hostvn.admin_links())), "m|tool"
    if action == "largefiles":
        return title(E["tool"], "File lớn /home", pre(hostvn.largefiles())), "m|tool"
    if action == "bk_list":
        rows = hostvn.list_backups()
        if not rows:
            body = "(chưa có bản backup nào)"
        else:
            body = "\n".join(f"{r['date']}  {r['domain']}  {r['size']}\n   " +
                             ", ".join(r["files"]) for r in rows[:15])
        return (title(E["backup"], "Danh sách bản backup",
                      pre(body) + f"\nThư mục: <code>{hostvn.BACKUP_ROOT}</code>"), "m|backup")
    if action == "bk_auto":
        return (title("⏰", "Auto backup", pre(hostvn.autobackup_info()) +
                      "\n<i>Đặt lịch chi tiết ở menu Cronjob trong shell.</i>"), "m|backup")
    if action == "acc_admin":
        return title(E["admin"], "Thông tin Admin Tool",
                     pre(hostvn.acc_admin_info()) + "\n⚠️ <b>Bảo mật — xoá tin sau khi xem.</b>"), "m|acc"
    if action == "acc_pma":
        return title(E["db"], "Thông tin phpMyAdmin",
                     pre(hostvn.acc_pma_info()) + "\n⚠️ <b>Bảo mật — xoá tin sau khi xem.</b>"), "m|acc"
    if action == "acc_ssh":
        return title("🔌", "SSH / SFTP", pre(hostvn.acc_ssh_info())), "m|acc"
    if action == "cron_list":
        return title(E["cron"], "Danh sách cronjob", pre(hostvn.cron_list())), "m|cron"
    if action == "tool_size":
        out = hostvn.sh("du -sh /home/*/*/public_html 2>/dev/null | sort -rh | head -12", 60)
        return title("📐", "Dung lượng website", pre(out or "(trống)")), "m|tool"
    if action == "adm_vts":
        port = hostvn.conf_val("admin_port")
        ip = hostvn.sh("bash -c 'source /var/hostvn/ipaddress; echo $IPADDRESS'", 10)
        code = hostvn.sh(f"curl -s -o /dev/null -w '%{{http_code}}' -u admin:"
                         f"{hostvn.conf_val('admin_pwd')} --max-time 8 "
                         f"http://127.0.0.1:{port}/vts_status", 15)
        return (title("📊", "Nginx Status (VTS)",
                      pre(f"URL : http://{ip}:{port}/vts_status\nHTTP: {code}") +
                      "\n<i>Mở bằng trình duyệt, đăng nhập admin.</i>"), "m|tool")
    if action == "fw_status":
        b = hostvn.fw_backend()
        yn = lambda v: "có" if v else "KHÔNG"
        body = (f"iptables : {yn(b['iptables'])}\n"
                f"ufw      : {yn(b['ufw'])}\n"
                f"nftables : {yn(b['nft'])}\n"
                f"fail2ban banaction: {b['banaction']}\n"
                f"Cloudflare WAF    : {'đã cấu hình' if b['cf_waf'] else 'chưa'}\n"
                f"Cloudflare Tunnel : {'bật' if b['tunnel'] else 'tắt'}")
        note = ""
        if not b["iptables"] and not b["ufw"]:
            note = ("\n\n⚠️ <b>Máy này không có iptables/ufw</b> (thường gặp ở container "
                    "LXC/Docker không được cấp quyền NET_ADMIN). Fail2ban chỉ "
                    "<b>phát hiện</b> chứ không chặn được ở tầng máy.")
            if b["tunnel"]:
                note += ("\n\nLưu lượng vào qua <b>Cloudflare Tunnel</b>, nên việc chặn thật "
                         "phải làm ở <b>Cloudflare WAF</b> — dùng mục ☁️ bên dưới.")
        return title(E["fw"], "Trạng thái firewall", pre(body) + note), "m|fw"
    if action == "fw_banned":
        return title("🚫", "IP đang bị ban", pre(hostvn.f2b_banned())), "m|fw"
    if action == "fw_cfwaf":
        b = hostvn.fw_backend()
        extra = ("\n<i>Đây là lớp chặn <b>thật</b> duy nhất trên máy này, vì không có "
                 "iptables/ufw.</i>" if not b["iptables"] and not b["ufw"] else "")
        return (title("☁️", "Cloudflare WAF", pre(hostvn.cf_waf_status()) + extra +
                      "\n\nBật/tắt đồng bộ hoặc đổi token: <code>hostvn</code> → "
                      "<b>5. Quan ly Firewall</b> → <b>10</b>."), "m|fw")
    if action == "fw_port":
        b = hostvn.fw_backend()
        if not b["iptables"] and not b["ufw"]:
            return (title("🔌", "Mở port / Bật-Tắt firewall",
                          "Máy này <b>không có iptables/ufw</b> nên các thao tác mở port, "
                          "bật/tắt firewall <b>không áp dụng được</b>.\n\n"
                          "Hãy mở/đóng cổng ở lớp bên ngoài:\n"
                          "• <b>Cloudflare</b> nếu lưu lượng vào qua Tunnel\n"
                          "• <b>Firewall của nhà cung cấp / máy chủ vật lý</b>\n\n"
                          "Xem cổng đang lắng nghe ở 🖥️ Hệ thống."), "m|fw")
        return (title("🔌", "Mở port / Bật-Tắt firewall",
                      "Chạy qua SSH: <code>hostvn</code> → <b>5. Quan ly Firewall</b> "
                      "→ mục 1, 5, 6, 7."), "m|fw")
    _SSH_ONLY = {
        "tool_img":    ("🖼️", "Nén ảnh", "13. Cong cu", "1",
                        "Cần chọn website và mức nén, xử lý hàng loạt ảnh."),
        "tool_unzip":  ("📦", "Giải nén file", "13. Cong cu", "3",
                        "Cần nhập đường dẫn file đã có sẵn trên máy chủ."),
        "tool_deploy": ("🚀", "Deploy website", "13. Cong cu", "2",
                        "Cần nhập nguồn mã và nhiều tuỳ chọn."),
        "tool_av":     ("🦠", "Cài Anti Virus", "13. Cong cu", "6",
                        "Cài ImunifyAV, quá trình cài kéo dài và cần xác nhận."),
        "tool_ggdl":   ("☁️", "Tải file Google Drive", "13. Cong cu", "9",
                        "Cần nhập link/ID file và thư mục đích."),
        "adm_pass":    (E["key"], "Đổi mật khẩu Admin Tool", "9. Admin Tool", "5",
                        "Cần nhập mật khẩu mới."),
        "adm_port":    ("🔌", "Đổi port Admin Tool", "9. Admin Tool", "6",
                        "Đổi port sẽ ảnh hưởng link truy cập đang dùng."),
        "acc_sftp":    (E["key"], "Đổi mật khẩu SFTP", "11. Xem thong tin tai khoan", "5",
                        "Đã có sẵn ở 🌐 Domain → Đổi mật khẩu SFTP (chạy được trên bot)."),
        "cron_local":  (E["backup"], "Auto backup tại VPS", "12. Cronjob/Auto Backup", "2",
                        "Cần chọn website, giờ chạy và số bản giữ lại."),
        "cron_gg":     ("☁️", "Auto backup Google Drive", "12. Cronjob/Auto Backup", "3",
                        "Cần chọn remote, website và lịch chạy."),
        "cron_od":     ("☁️", "Auto backup OneDrive", "12. Cronjob/Auto Backup", "4",
                        "Cần chọn remote, website và lịch chạy."),
        "cron_custom": ("✏️", "Cronjob tuỳ chỉnh", "12. Cronjob/Auto Backup", "5",
                        "Cần nhập biểu thức cron và lệnh — dễ sai nếu gõ qua chat."),
    }
    if action in _SSH_ONLY:
        emo, lbl, menu, num, why = _SSH_ONLY[action]
        back = ("m|acc" if action.startswith("acc_") else
                "m|cron" if action.startswith("cron_") else "m|tool")
        return (title(emo, lbl, f"{why}\n\nChạy qua SSH: <code>hostvn</code> → "
                      f"<b>{menu}</b> → <b>{num}</b>."), back)
    if action == "ngx_test":
        return title(E["svc"], "Test cấu hình Nginx",
                     pre(hostvn.sh("nginx -t 2>&1", 30))), "m|nginx"
    if action in ("ngx_update", "ngx_rebuild"):
        what = "Update" if action == "ngx_update" else "Rebuild"
        return (title(E["warn"], f"{what} Nginx",
                      "Thao tác này <b>biên dịch Nginx từ mã nguồn</b> (kèm các module). "
                      "Trên điện thoại ARM việc này mất ~20 phút, ngốn RAM/CPU và "
                      "từng là nguyên nhân gây <b>reboot máy</b>.\n\n"
                      "Chỉ nên chạy trực tiếp qua SSH để theo dõi được tiến trình:\n"
                      "<code>hostvn</code> → <b>4. Quan ly LEMP</b> → <b>1. Nginx</b>."), "m|nginx")
    if action == "php_params":
        pv = hostvn.php_version()
        cur = hostvn.sh(f"php{pv} -i 2>/dev/null | grep -iE "
                        f"'^memory_limit|^upload_max|^post_max|^max_execution|^max_input' | head -6", 15)
        return (title(E["php"], "Cấu hình tham số PHP", pre(cur) +
                      "\n<i>Sửa giá trị cần chọn nhiều tham số một lúc — chạy qua SSH: "
                      "<code>hostvn</code> → 4 → 2 → 2.</i>"), "m|php")
    if action in ("php_default", "php_second", "php_ioncube"):
        lbl = {"php_default": "Đổi phiên bản PHP mặc định",
               "php_second": "Cài/đổi PHP thứ hai",
               "php_ioncube": "Cài ionCube Loader"}[action]
        return (title(E["php"], lbl,
                      "Thao tác này cài/đổi gói PHP toàn hệ thống (apt + rebuild pool), "
                      "ảnh hưởng mọi website nên <b>chưa đưa lên bot</b>.\n\n"
                      "Chạy qua SSH: <code>hostvn</code> → <b>4. Quan ly LEMP</b> → "
                      "<b>2. PHP</b>."), "m|php")
    if action == "db_pass":
        return (title(E["key"], "Đổi mật khẩu MySQL user",
                      "Đổi mật khẩu DB sẽ làm site lỗi nếu file cấu hình (wp-config.php…) "
                      "không sửa khớp.\n\nChạy qua SSH: <code>hostvn</code> → "
                      "<b>4. Quan ly LEMP</b> → <b>3. Database</b> → <b>3</b>."), "m|db")
    if action == "db_import":
        return (title("📥", "Import database",
                      "Import cần file .sql/.sql.gz nằm sẵn trên máy chủ — không gửi qua chat "
                      "được.\n\nTải file lên (SFTP) rồi chạy: <code>hostvn</code> → "
                      "<b>4. Quan ly LEMP</b> → <b>3. Database</b> → <b>6</b>."), "m|db")
    if action == "db_remote":
        bind = hostvn.sh("grep -rhE '^bind-address' /etc/mysql/ 2>/dev/null | head -2", 15)
        port = hostvn.sh("ss -ltn 2>/dev/null | grep -c ':3306'", 10)
        return (title("🌐", "Remote MySQL", pre(f"{bind or '(không thấy bind-address)'}\n"
                      f"cổng 3306 đang lắng nghe: {port}") +
                      "\n<i>Bật/tắt truy cập từ xa cần khai báo IP nguồn — chạy qua SSH: "
                      "<code>hostvn</code> → 4 → 3 → 7.</i>"), "m|db")
    if action == "cache_status":
        return title(E["cache"], "Trạng thái cache", pre(hostvn.cache_status())), "m|cache"
    if action == "opcache_bl":
        return (title("🚫", "OPcache blacklist",
                      "Thêm/xoá website khỏi blacklist OPcache cần chọn website và "
                      "sửa file cấu hình PHP.\n\nChạy qua SSH: <code>hostvn</code> → "
                      "<b>3. Quan ly Cache</b> → <b>3. PHP Opcache</b>."), "m|cache")
    if action == "ssl_list":
        rows = hostvn.ssl_list()
        icon = {"letsencrypt": "🔒", "self-signed": "🟡", "none": "🔓"}
        label = {"letsencrypt": "Let's Encrypt", "self-signed": "tự ký (hostvn)", "none": "không có"}
        body = "\n".join(
            f"{icon[r['kind']]} {r['domain']} — {label[r['kind']]}"
            + (f"\n   hết hạn: {r['expire']}" if r["expire"] else "")
            for r in rows) or "(chưa có domain)"
        note = ""
        if hostvn.is_tunnel_mode():
            note = ("\n\n<i>Đang chạy Cloudflare Tunnel: TLS được Cloudflare xử lý ở biên, "
                    "đoạn cloudflared→Cloudflare đã mã hoá sẵn. Chứng chỉ tự ký ở đây là bình "
                    "thường và <b>không cần</b> cấp Let's Encrypt.</i>")
        return title(E["ssl"], "Chứng chỉ trên server", pre(body) + note), "m|ssl"
    if action == "ssl_paid":
        return (title("📜", "SSL trả phí",
                      "Quy trình này cần tạo CSR (nhập quốc gia, tỉnh, tổ chức…) rồi "
                      "<b>dán nội dung file CRT/CA/Private Key</b> nhiều dòng — không phù hợp "
                      "để nhập qua chat.\n\nChạy qua SSH: <code>hostvn</code> → "
                      "<b>2. Quan ly SSL</b> → <b>2. SSL tra phi</b>."), "m|ssl")
    if action == "dom_clone":
        return (title("🧬", "Clone website",
                      "Clone gồm nhiều bước hỏi ghi đè dữ liệu nguồn/đích nên "
                      "<b>chưa đưa lên bot</b> để tránh mất dữ liệu.\n\n"
                      "Chạy qua SSH: <code>hostvn</code> → <b>1. Quan ly ten mien</b> → "
                      "<b>9. Clone website</b>."), "m|domain")
    if action == "dom_dbinfo":
        return (title(E["db"], "Đổi thông tin Database",
                      "Đổi tên DB/user/mật khẩu sẽ làm site lỗi nếu file cấu hình "
                      "(wp-config.php…) không được sửa khớp, nên <b>chưa đưa lên bot</b>.\n\n"
                      "Chạy qua SSH: <code>hostvn</code> → <b>1. Quan ly ten mien</b> → "
                      "<b>10. Doi thong tin Database</b>."), "m|domain")
    if action == "bk_connect":
        return (title("🔗", "Kết nối kho lưu trữ",
                      "Google Drive và OneDrive cần đăng nhập OAuth qua trình duyệt, "
                      "còn S3 cần nhập access key/secret — <b>không an toàn khi gõ qua chat</b>.\n\n"
                      "Vui lòng chạy qua SSH:\n<code>hostvn</code> → <b>8. Sao luu/Khoi phuc</b> → "
                      "mục 4 (GDrive) / 6 (OneDrive) / 7 (S3).\n\n"
                      "Sau khi kết nối xong, remote sẽ hiện ở <b>☁️ Remote đã kết nối</b>."), "m|backup")
    # write:
    if action == "cache_clear":
        return title(E["cache"], "Xoá cache", hostvn.clear_fastcgi()), "m|cache"
    if action == "opcache_clear":
        return title(E["cache"], "OPcache", hostvn.clear_opcache()), "m|cache"
    if action == "php_restart":
        pv = hostvn.php_version()
        hostvn.svc("restart", f"php{pv}-fpm")
        return title(E["php"], "PHP-FPM", f"Đã restart php{pv}-fpm."), "m|php"
    return title(E["warn"], "Chưa hỗ trợ", ""), C.CB_HOME


# ---- Picker (chon domain/db) ------------------------------------------------ #
async def cb_pick(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)
    target = params[0] if params else ""

    if action == "dominfo":
        return await _progress_op(
            update, True, f"⏳ <b>Đang đọc</b> {texts.esc(target)}…",
            asyncio.to_thread(_domain_info, target),
            lambda t: (t, menus.back_only("m|domain")), est=5.0)
    if action == "wpcache":
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|wp"))
        return await _progress_op(
            update, True, f"{E['cache']} <b>Đang xoá cache</b> {texts.esc(target)}…",
            asyncio.to_thread(_wp_cache_flush, target),
            lambda _: (title(E["wp"], target, "Đã xoá cache WordPress (nếu có)."),
                       menus.back_only("m|wp")), est=6.0)
    # ----- SSL: sau khi chon domain -> xac nhan roi chay -----
    if action in ("sslnew", "sslwild", "ssldel", "sslalias"):
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|ssl"))
        what = {"sslnew": ("Cấp/Gia hạn Let's Encrypt cho", "sslnew"),
                "sslwild": ("Cấp Wildcard SSL cho *.", "sslwild"),
                "ssldel": ("GỠ chứng chỉ Let's Encrypt của", "ssldel"),
                "sslalias": ("Cấp SSL cho Alias domain của", "sslalias")}[action]
        extra = ""
        if action in ("sslnew", "sslalias") and await asyncio.to_thread(hostvn.is_tunnel_mode):
            extra = ("\n\n⚠️ Đang chạy <b>Cloudflare Tunnel</b>: TLS đã do Cloudflare xử lý nên "
                     "chứng chỉ này thường <b>không cần</b>, và xác thực HTTP-01 có thể thất bại "
                     "vì port 80 không mở trực tiếp ra Internet.\n"
                     "Muốn có chứng chỉ thật trên server thì dùng <b>Wildcard SSL (CF DNS)</b>.")
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận", f"{what[0]}<b>{texts.esc(target)}</b>?" + extra),
            parse_mode=HTML,
            reply_markup=menus.confirm_menu(what[1], target, back="m|ssl"))

    # ----- Quan ly domain nang cao: sau khi chon domain -----
    if action in ("dmrename", "dmrw", "dmphp", "dmalias", "dmredir",
                  "dmsftp", "dmprot", "dmhttp3"):
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|domain"))
        context.user_data["dom"] = target
        if action == "dmhttp3":
            return await q.edit_message_text(
                title("🚀", f"HTTP/3 — {target}", "Bật hay tắt HTTP/3 (QUIC)?"),
                parse_mode=HTML, reply_markup=menus.onoff_menu(target, "h3"))
        if action == "dmrw":
            return await q.edit_message_text(
                title("🧱", f"Rewrite vHost — {target}",
                      "Chọn loại mã nguồn để tạo lại file cấu hình:"),
                parse_mode=HTML, reply_markup=menus.source_menu(target))
        if action == "dmphp":
            vers = await asyncio.to_thread(hostvn.php_versions)
            if len(vers) < 2:
                return await q.edit_message_text(
                    title(E["php"], "Đổi phiên bản PHP",
                          f"Máy chỉ cài <b>một</b> phiên bản PHP ({', '.join(vers) or '?'}).\n"
                          "Cài thêm PHP thứ hai qua SSH rồi mới đổi được."),
                    parse_mode=HTML, reply_markup=menus.back_only("m|domain"))
            return await q.edit_message_text(
                title(E["php"], f"Đổi PHP — {target}", "Chọn phiên bản:"),
                parse_mode=HTML, reply_markup=menus.php_choice_menu(target, vers))
        if action == "dmsftp":
            return await q.edit_message_text(
                title(E["key"], "Đổi mật khẩu SFTP",
                      f"Tạo mật khẩu SFTP mới ngẫu nhiên cho <b>{texts.esc(target)}</b>?"),
                parse_mode=HTML,
                reply_markup=menus.confirm_menu("sftp", target, back="m|domain"))
        # Cac thao tac can nhap lieu
        prompts = {
            "dmrename": ("✏️", "Đổi tên miền", "Nhập <b>tên miền mới</b> (vd: moi.com):"),
            "dmalias":  ("🔗", "Alias/Parked", "Nhập <b>domain alias</b> (vd: alias.com):"),
            "dmredir":  ("↪️", "Redirect", f"Nhập <b>domain nguồn</b> sẽ chuyển hướng về {texts.esc(target)}:"),
            "dmprot":   ("🔐", "Bảo vệ thư mục",
                         "Nhập <b>đường_dẫn user mật_khẩu</b> cách nhau bởi dấu cách.\n"
                         "Ví dụ: <code>/upload admin MatKhau123</code>"),
        }
        emo, head, prompt = prompts[action]
        flow = {"dmrename": "dom_rename", "dmalias": "dom_alias",
                "dmredir": "dom_redirect", "dmprot": "dom_protect"}[action]
        return await start_flow(update, context, flow, "m|domain", emo,
                                f"{head} — {target}", prompt)

    if action == "wpinfo2":
        return await _progress_op(
            update, True, f"{E['wp']} <b>Đang đọc thông tin</b> {texts.esc(target)}…",
            asyncio.to_thread(hostvn.wp_info, target),
            lambda t: (title(E["wp"], target, pre(t)), menus.back_only("m|wp")), est=20.0)
    if action == "wppass":
        return await q.edit_message_text(
            title(E["key"], "Đổi mật khẩu wp-admin",
                  f"Đổi mật khẩu quản trị của <b>{texts.esc(target)}</b> cần nhập user và mật "
                  f"khẩu mới — chạy qua SSH: <code>hostvn</code> → "
                  f"<b>7. Quan ly WordPress</b> → <b>5</b>."),
            parse_mode=HTML, reply_markup=menus.back_only("m|wp"))
    if action.startswith("wpop_"):
        key = action[5:]
        if key not in WP_OPS:
            return
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|wp"))
        _ctl, kind, on_lbl, off_lbl = WP_OPS[key]
        lbl = WP_LABEL.get(key, key)
        if kind == "toggle":
            return await q.edit_message_text(
                title(E["wp"], f"{lbl} — {target}", "Chọn thao tác:"),
                parse_mode=HTML,
                reply_markup=menus.wp_onoff_menu(key, target, on_lbl, off_lbl))
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận", f"{lbl} cho <b>{texts.esc(target)}</b>?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu(f"wp_{key}", target, back="m|wp"))

    if action == "accsite":
        return await _progress_op(
            update, True, f"{E['acc']} <b>Đang đọc</b> {texts.esc(target)}…",
            asyncio.to_thread(hostvn.acc_site_info, target),
            lambda t: (title(E["acc"], target, pre(t) +
                             "\n⚠️ <b>Bảo mật — xoá tin sau khi xem.</b>"),
                       menus.back_only("m|acc")), est=8.0)
    if action == "permchk":
        return await _progress_op(
            update, True, f"{E['perm']} <b>Đang kiểm tra quyền</b> {texts.esc(target)}…",
            asyncio.to_thread(hostvn.perm_check, target),
            lambda t: (title(E["perm"], f"Quyền: {target}", pre(t)),
                       menus.back_only("m|perm")), est=15.0)
    if action == "permone":
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|perm"))
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận phân quyền",
                  f"Đặt lại quyền cho <b>{texts.esc(target)}</b>?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("permone", target, back="m|perm"))
    if action == "bkdom":     # chon website -> chon loai backup
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|backup"))
        return await q.edit_message_text(
            title(E["backup"], f"Backup {target}", "Chọn nội dung cần backup:"),
            parse_mode=HTML, reply_markup=menus.backup_type_menu(target))
    if action == "rsdom":     # chon website -> chon ngay backup
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|backup"))
        return await _progress_op(
            update, True, f"⏳ <b>Đang tìm bản backup của</b> {texts.esc(target)}…",
            asyncio.to_thread(hostvn.backup_dates, target),
            lambda dates: (title("♻️", f"Khôi phục {target}",
                                 "Chọn ngày backup:" if dates
                                 else "Website này chưa có bản backup nào."),
                           menus.backup_date_menu(target, dates)),
            est=3.0)
    if action == "domdel":
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|domain"))
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận xoá domain",
                  f"Xoá <b>{texts.esc(target)}</b> và toàn bộ dữ liệu?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("domdel", target))
    if action == "dbdel":
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|db"))
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận xoá database", f"Xoá <b>{texts.esc(target)}</b>?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("dbdel", target))


def _domain_info(d: str) -> str:
    dr = hostvn.docroot(d)
    code = hostvn.http_code(d)
    size = hostvn.sh(f"du -sh {Path(dr).parent} 2>/dev/null | cut -f1", 15) if dr else "?"
    wp = "có" if dr and (Path(dr) / "wp-admin").is_dir() else "không"
    body = f"HTTP: {code}\nWordPress: {wp}\nDung lượng: {size}\nDocroot: {dr}"
    return title(E["domain"], d, pre(body))


def _wp_cache_flush(d: str) -> None:
    dr = hostvn.docroot(d)
    if dr:
        hostvn.sh(f"cd {dr} && wp cache flush --allow-root 2>/dev/null", 30)


# ---- Tao domain (nd|def|<d> / nd|wp|<d>) ------------------------------------ #
async def cb_nd(update, context, typ, params):
    q = update.callback_query
    chat = _actor(update)
    domain = params[0] if params else ""
    if not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|domain"))
    is_wp = typ == "wp"
    kind = "WordPress" if is_wp else "website PHP"
    base = f"{E['domain']} <b>Đang tạo {kind}</b> {texts.esc(domain)}…"
    if is_wp:
        est = 40.0
        stages = [
            (12, f"{E['domain']} <b>Tạo user &amp; thư mục</b> {texts.esc(domain)}…"),
            (32, f"{E['db']} <b>Tạo database &amp; user MySQL</b>…"),
            (52, f"{E['wp']} <b>Đang tải mã nguồn WordPress</b>…"),
            (76, f"{E['wp']} <b>Đang cài đặt WordPress</b>…"),
            (90, f"{E['refresh']} <b>Tạo vHost &amp; reload nginx</b>…"),
        ]
    else:
        est = 14.0
        stages = [
            (25, f"{E['domain']} <b>Tạo user &amp; thư mục</b>…"),
            (55, f"{E['php']} <b>Cấu hình PHP-FPM pool</b>…"),
            (82, f"{E['refresh']} <b>Tạo vHost &amp; reload nginx</b>…"),
        ]

    def render(res):
        ok, info, err = res
        if not ok:
            return (title(E["warn"], f"Chưa tạo được {domain}", pre(err)),
                    menus.back_only("m|domain"))
        lines = [f"Docroot   : {info['docroot']}",
                 f"SFTP user : {info['sftp_user']}",
                 f"SFTP pass : {info['sftp_pass']}"]
        if info.get("db_name"):
            lines += [f"DB name   : {info['db_name']}",
                      f"DB user   : {info['db_user']}",
                      f"DB pass   : {info['db_pass']}"]
        if info.get("wp_user"):
            lines += [f"WP admin  : {info['wp_user']}",
                      f"WP pass   : {info['wp_pass']}",
                      f"WP login  : http://{domain}/wp-admin"]
        if info.get("incomplete"):
            return (title(E["warn"], f"Tạo {domain} chưa trọn vẹn",
                          pre("\n".join(lines)) +
                          f"\n⚠️ {texts.esc(info['incomplete'])}\n\n"
                          "Xoá site này rồi tạo lại, hoặc hoàn tất qua SSH: "
                          "<code>hostvn</code> → <b>1. Quan ly ten mien</b>."),
                    menus.back_only("m|domain"))
        return (title(E["confirm"], f"Đã tạo {domain}",
                      f"<code>{progress.bar(100)}</code>\n" + pre("\n".join(lines)) +
                      "\n⚠️ <b>Lưu lại thông tin này!</b>"),
                menus.back_only("m|domain"))

    await _progress_op(update, True, base,
                       asyncio.to_thread(hostvn.create_domain, typ, domain),
                       render, est=est, stages=stages)



# --------------------------------------------------------------------------- #
# Bang thao tac WordPress (mirror menu 7 + submenu Advanced)
#   controller : file trong menu/controller/wordpress
#   kind       : "toggle" (chon 1=tat / 2=bat roi chon site)  |  "run" (chon site roi chay)
#   on/off     : nhan hien thi cho 2 lua chon cua toggle
# Thu tu prompt cua shell: chon THAO TAC truoc, chon WEBSITE sau -> seq "<n>\n<idx>"
# --------------------------------------------------------------------------- #
WP_OPS = {
    "wpa_yoast":     ("yoast_seo", "toggle", "Bật Yoast config", "Tắt Yoast config"),
    "wpa_rank":      ("rank_math_seo", "toggle", "Bật Rank Math config", "Tắt Rank Math config"),
    "wpa_webp":      ("webp_express", "toggle", "Bật WebP Express", "Tắt WebP Express"),
    "wpa_cacheplug": ("cache_plugins", "toggle", "Bật cache plugin config", "Tắt cache plugin config"),
    "wpa_debug":     ("debug_mode", "toggle", "Bật Debug mode", "Tắt Debug mode"),
    "wpa_maint":     ("maintenance_mode", "toggle", "Bật bảo trì", "Tắt bảo trì"),
    "wpa_xmlrpc":    ("disable_xmlrpc", "toggle", "Chặn XMLRPC", "Bỏ chặn XMLRPC"),
    "wpa_userapi":   ("disable_user_api", "toggle", "Chặn User API", "Bỏ chặn User API"),
    "wpa_cron":      ("cron_job", "toggle", "Tối ưu WP-Cron", "Huỷ tối ưu WP-Cron"),
    "wp_edit":       ("disable_edit_theme_plugins", "toggle",
                      "Cho phép sửa theme/plugin", "Không cho phép sửa"),
    "wp_lockdown":   ("wordpress_lockdown", "toggle", "Bật Lockdown", "Tắt Lockdown"),
    "wp_htpasswd":   ("htpasswd_wp_admin", "toggle", "Bật bảo vệ wp-admin", "Tắt bảo vệ"),
    "wp_core":       ("update_wordpress", "run", "", ""),
    "wp_plugupd":    ("update_plugins", "run", "", ""),
    "wp_plugoff":    ("deactivate_all_plugins", "run", "", ""),
    "wp_optimize":   ("optimize_database", "run", "", ""),
    "wpa_revision":  ("post_revision", "run", "", ""),
    "wpa_cachekey":  ("cache_key", "run", "", ""),
    "wp_moveconf":   ("move_wp_config", "run", "", ""),
}
WP_LABEL = {
    "wpa_yoast": "Yoast SEO config", "wpa_rank": "Rank Math config",
    "wpa_webp": "WebP Express", "wpa_cacheplug": "Nginx + plugin cache",
    "wpa_debug": "Debug mode", "wpa_maint": "Chế độ bảo trì",
    "wpa_xmlrpc": "XMLRPC", "wpa_userapi": "User API", "wpa_cron": "WP-Cron",
    "wp_edit": "Sửa theme/plugin", "wp_lockdown": "WordPress Lockdown",
    "wp_htpasswd": "Bảo vệ wp-admin", "wp_core": "Update WordPress Core",
    "wp_plugupd": "Update plugins", "wp_plugoff": "Huỷ kích hoạt plugins",
    "wp_optimize": "Tối ưu Database", "wpa_revision": "Xoá Post Revisions",
    "wpa_cachekey": "Thêm cache key", "wp_moveconf": "Move wp-config",
}

# ---- Update scripts (mien "up") / Language (mien "lg2") --------------------- #
async def cb_up(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_UPD) or not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|upd"))
    if action != "run":
        return
    await _progress_op(
        update, True, f"{E['upd']} <b>Đang cập nhật HostVN Scripts</b>…",
        asyncio.to_thread(hostvn.run_update_scripts),
        lambda out: (title(E["confirm"], "Cập nhật xong",
                           pre(out) + "\n<i>Đang khởi động lại bot…</i>"),
                     menus.back_only(C.CB_HOME)),
        est=180.0,
        stages=[(40, "📦 <b>Đang tải gói menu mới</b>…"),
                (75, "🔧 <b>Đang áp dụng thay đổi</b>…")])
    # menu/ vua bi thay (gom ca file bot) -> khoi dong lai de nap ban moi
    await asyncio.to_thread(hostvn.svc, "restart", "hostvn-telegram-bot")


async def cb_lg2(update, context, code, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_LANG) or not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|lang"))
    ok, msg = await asyncio.to_thread(hostvn.set_language, code)
    text, kb = await asyncio.to_thread(_screen_lang)
    await q.edit_message_text(
        title(E["confirm"] if ok else E["warn"], "Change language", texts.esc(msg)) +
        "\n\n" + text, parse_mode=HTML, reply_markup=kb)


# ---- WordPress (mien "wp") -------------------------------------------------- #
async def cb_wp(update, context, key, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_WP):
        return await q.edit_message_text(texts.DENY, parse_mode=HTML)
    if not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|wp"))
    if key not in WP_OPS or len(params) < 2:
        return
    domain, choice = params[0], params[1]
    ctl = WP_OPS[key][0]
    lbl = WP_LABEL.get(key, key)
    idx = await asyncio.to_thread(hostvn.wp_index, domain)
    if not idx:
        return await q.edit_message_text(
            title(E["warn"], lbl, "Không tìm thấy site WordPress này."),
            parse_mode=HTML, reply_markup=menus.back_only("m|wp"))
    # shell hoi THAO TAC truoc roi moi chon WEBSITE
    seq = f"{choice}\n{idx}"
    return await _progress_op(
        update, True, f"{E['wp']} <b>{texts.esc(lbl)}</b> — {texts.esc(domain)}…",
        asyncio.to_thread(hostvn.wp_run, ctl, seq, 300),
        lambda msg: (title(E["confirm"], lbl, pre(msg)), menus.back_only("m|wp")),
        est=30.0, stages=[(60, f"{E['refresh']} <b>Đang áp dụng cấu hình</b>…")])


# ---- PHP toggles (mien "pp") ------------------------------------------------ #
# Cac controller nay chi hoi y/n roi ghi vao 00-hostvn-custom.ini + restart php-fpm.
_PHP_TOGGLES = {
    "basedir":  ("open_basedir", "Open Basedir", "open_basedir"),
    "urlfopen": ("allow_url_fopen", "allow_url_fopen", "allow_url_fopen"),
    "procopen": ("proc_close", "proc_open / proc_close", "disable_functions"),
}


def _php_ini_state(needle: str) -> str:
    pv = hostvn.php_version()
    ini = f"/etc/php/{pv}/fpm/conf.d/00-hostvn-custom.ini"
    cur = hostvn.sh(f"grep -iE '{needle}' {ini} 2>/dev/null | head -3", 10)
    return cur or "(chưa cấu hình trong 00-hostvn-custom.ini)"


async def cb_pp(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_PHP) and not has_feature(chat, C.F_LEMP):
        return await q.edit_message_text(texts.DENY, parse_mode=HTML)
    if action not in _PHP_TOGGLES:
        return
    ctl, label, needle = _PHP_TOGGLES[action]

    if params and params[0] in ("y", "n"):        # pp|<key>|y|n -> thuc thi
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|php"))
        ans = params[0]
        return await _progress_op(
            update, True,
            f"{E['php']} <b>Đang {'bật' if ans == 'y' else 'tắt'} {texts.esc(label)}</b>…",
            asyncio.to_thread(hostvn.run_ctl, ans,
                              f"/var/hostvn/menu/controller/php/{ctl}", 180),
            lambda _out: (title(E["confirm"], label,
                                pre(_php_ini_state(needle))), menus.back_only("m|php")),
            est=25.0)

    # Man hinh trang thai + 2 nut bat/tat
    return await _progress_op(
        update, True, f"⏳ <b>Đang đọc cấu hình {texts.esc(label)}…</b>",
        asyncio.to_thread(_php_ini_state, needle),
        lambda cur: (title(E["php"], label, pre(cur) + "\nChọn thao tác:"),
                     menus.rows_menu([[(f"{E['on']} Bật", f"pp|{action}|y"),
                                       (f"{E['off']} Tắt", f"pp|{action}|n")]], back="m|php")),
        est=4.0)


# ---- Log (mien "lg") -------------------------------------------------------- #
_LOG_FILES = {
    "nginx": ("/var/log/nginx/error.log", "Nginx error log"),
    "php":   ("/var/log/php-fpm/error.log", "PHP error log"),
    "mysql": ("/var/log/mysql/mysqld.log", "MariaDB error log"),
}


def _tail_log(path: str) -> str:
    if not Path(path).exists():
        return "(không có file log)"
    return hostvn.sh(f"tail -n 20 {path}", 20) or "(log trống)"


def _site_logs() -> str:
    out = []
    for d in hostvn.list_domains():
        dr = hostvn.docroot(d)
        if not dr:
            continue
        logf = str(Path(dr).parent / "logs" / "error.log")
        if Path(logf).exists():
            body = hostvn.sh(f"tail -n 8 {logf}", 15) or "(trống)"
            out.append(f"● {d}\n{body}")
    return "\n\n".join(out) or "(không website nào có error log)"


def _clear_logs() -> str:
    hostvn.sh("rm -f /var/log/nginx/*.log /var/log/php-fpm/*.log /var/log/mysql/*.log "
              "/home/*/*/logs/*.log 2>/dev/null; echo done", 60, merge=True)
    for s_ in ("nginx", "mariadb"):
        hostvn.svc("reload", s_)
    return "Đã xoá error log của Nginx, PHP, MariaDB và các website."


async def cb_lg(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_LEMP):
        return await q.edit_message_text(texts.DENY, parse_mode=HTML)

    if action in _LOG_FILES:
        path, label = _LOG_FILES[action]
        return await _progress_op(
            update, True, f"{E['log']} <b>Đang đọc {texts.esc(label)}</b>…",
            asyncio.to_thread(_tail_log, path),
            lambda t: (title(E["log"], label, pre(t[-3000:])), menus.back_only("m|log")),
            est=5.0)
    if action == "site":
        return await _progress_op(
            update, True, f"{E['log']} <b>Đang đọc log website</b>…",
            asyncio.to_thread(_site_logs),
            lambda t: (title(E["log"], "Website error log", pre(t[-3000:])),
                       menus.back_only("m|log")), est=8.0)
    if action == "clear":
        if not can_write(chat):
            return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                             reply_markup=menus.back_only("m|log"))
        return await q.edit_message_text(
            title(E["warn"], "Xoá error log",
                  "Xoá toàn bộ error log của Nginx, PHP, MariaDB và các website?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("logclr", back="m|log"))


# ---- Cache (mien "cc") ------------------------------------------------------ #
async def cb_cc(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_CACHE):
        return await q.edit_message_text(texts.DENY, parse_mode=HTML)
    if not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|cache"))
    arg = params[0] if params else ""

    if action in ("on", "off", "restart"):        # bat/tat/restart redis|memcached
        act = {"on": "start", "off": "stop", "restart": "restart"}[action]
        return await _progress_op(
            update, True, f"{E['refresh']} <b>Đang {act} {texts.esc(arg)}</b>…",
            asyncio.to_thread(_svc_act_then_status, act, arg),
            lambda st: (title(E["confirm"], arg, f"Trạng thái: <b>{texts.esc(st)}</b>"),
                        menus.back_only("m|cache")),
            est=8.0)

    if action in ("install", "uninstall"):        # apt: nang, hoi xac nhan truoc
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận",
                  f"{'Cài đặt' if action == 'install' else 'Gỡ bỏ'} <b>{texts.esc(arg)}</b>"
                  f"{' (kèm extension PHP)' if action == 'install' else ''}? "
                  f"Thao tác apt có thể mất vài phút."),
            parse_mode=HTML,
            reply_markup=menus.confirm_menu(f"pkg{action}", arg, back="m|cache"))

    if action in ("opon", "opoff"):               # bat/tat OPcache
        on = action == "opon"
        return await _progress_op(
            update, True, f"{E['php']} <b>Đang {'bật' if on else 'tắt'} OPcache</b>…",
            asyncio.to_thread(hostvn.run_ctl, "1" if on else "2",
                              "/var/hostvn/menu/controller/cache/opcache/enable_disable", 120),
            lambda out: (title(E["php"], "OPcache",
                               pre(hostvn._ctl_reason(out, "Đã gửi yêu cầu."))),
                         menus.back_only("m|cache")),
            est=15.0)

    if action in ("fcon", "fcoff"):               # bat/tat FastCGI cache cho 1 domain
        on = action == "fcon"
        return await _progress_op(
            update, True,
            f"🚀 <b>Đang {'bật' if on else 'tắt'} FastCGI cache</b> — {texts.esc(arg)}…",
            asyncio.to_thread(hostvn.cache_fastcgi_set, arg, on),
            lambda r: ((title(E["confirm"], "FastCGI cache", texts.esc(r[1])) if r[0]
                        else title(E["warn"], "Không đổi được", texts.esc(r[1]))),
                       menus.back_only("m|cache")),
            est=20.0)


# ---- SSL (mien "ssl") ------------------------------------------------------- #
async def cb_ssl(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_SSL):
        return await q.edit_message_text(texts.DENY, parse_mode=HTML)
    if not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|ssl"))
    if action == "cfset":
        return await start_flow(
            update, context, "ssl_cfapi", "m|ssl", "☁️", "CloudFlare DNS API",
            "Gửi <b>token</b> và <b>email</b> cách nhau bởi dấu cách.\n"
            "Ví dụ: <code>cfut_xxxxx you@mail.com</code>\n\n"
            "⚠️ <b>Hãy xoá tin nhắn đó sau khi gửi</b> — token nằm trong lịch sử chat.")


# ---- Quan ly domain nang cao (mien "dm") ------------------------------------ #
async def cb_dm(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_DOMAIN):
        return await q.edit_message_text(texts.DENY, parse_mode=HTML)
    if not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|domain"))
    domain = params[0] if params else ""

    if action in ("h3on", "h3off"):
        on = action == "h3on"
        return await _progress_op(
            update, True,
            f"🚀 <b>Đang {'bật' if on else 'tắt'} HTTP/3</b> cho {texts.esc(domain)}…",
            asyncio.to_thread(hostvn.dom_http3, domain, on),
            lambda r: ((title(E["confirm"], "HTTP/3", texts.esc(r[1])) if r[0]
                        else title(E["warn"], "Không đổi được HTTP/3", texts.esc(r[1]))),
                       menus.back_only("m|domain")),
            est=20.0)

    if action == "rw":       # dm|rw|<domain>|<source_idx>
        src = int(params[1]) if len(params) > 1 and params[1].isdigit() else 20
        return await _progress_op(
            update, True, f"🧱 <b>Đang tạo lại vHost</b> cho {texts.esc(domain)}…",
            asyncio.to_thread(hostvn.dom_rewrite_config, domain, src),
            lambda r: ((title(E["confirm"], "Rewrite vHost", texts.esc(r[1])) if r[0]
                        else title(E["warn"], "Rewrite thất bại", texts.esc(r[1]))),
                       menus.back_only("m|domain")),
            est=25.0)

    if action == "php":      # dm|php|<domain>|<1|2>
        choice = int(params[1]) if len(params) > 1 and params[1].isdigit() else 1
        return await _progress_op(
            update, True, f"{E['php']} <b>Đang đổi phiên bản PHP</b> cho {texts.esc(domain)}…",
            asyncio.to_thread(hostvn.dom_change_php, domain, choice),
            lambda r: (title(E["confirm"] if r[0] else E["warn"], "Đổi phiên bản PHP",
                             texts.esc(r[1])), menus.back_only("m|domain")),
            est=30.0)


# ---- Backup / Restore (mien "bk") ------------------------------------------ #
async def cb_bk(update, context, action, params):
    q = update.callback_query
    chat = _actor(update)
    if not has_feature(chat, C.F_BACKUP):
        return await q.edit_message_text(texts.DENY, parse_mode=HTML)
    if not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|backup"))

    # bk|run|<type>|<domain>  -> chay backup ngay
    if action == "run":
        btype = params[0] if params else "full"
        domain = params[1] if len(params) > 1 else ""
        names = {"full": "full (mã nguồn + DB)", "source": "mã nguồn", "db": "database"}
        return await _progress_op(
            update, True,
            f"{E['backup']} <b>Đang backup</b> {texts.esc(domain)} — {names.get(btype, btype)}…",
            asyncio.to_thread(hostvn.backup_site, domain, btype),
            lambda r: ((title(E["confirm"], f"Backup {domain}",
                              f"<code>{progress.bar(100)}</code>\n{r[1]}\n"
                              f"Thư mục: <code>{texts.esc(r[2])}</code>") if r[0]
                        else title(E["warn"], f"Backup {domain} thất bại", texts.esc(r[1]))),
                       menus.back_only("m|backup")),
            est=45.0,
            stages=[(30, f"📁 <b>Đang nén mã nguồn</b> {texts.esc(domain)}…"),
                    (70, f"{E['db']} <b>Đang dump database</b>…"),
                    (90, "🔄 <b>Đang hoàn tất</b>…")])

    # bk|rsd|<domain>|<date> -> chon loai khoi phuc
    if action == "rsd":
        domain = params[0] if params else ""
        date = params[1] if len(params) > 1 else ""
        return await q.edit_message_text(
            title("♻️", f"Khôi phục {domain}", f"Bản ngày <b>{texts.esc(date)}</b>. Chọn nội dung:"),
            parse_mode=HTML, reply_markup=menus.restore_type_menu(domain, date))

    # bk|rst|<type>|<domain>|<date> -> XAC NHAN (ghi de du lieu hien tai)
    if action == "rst":
        rtype = params[0] if params else "full"
        domain = params[1] if len(params) > 1 else ""
        date = params[2] if len(params) > 2 else ""
        what = {"full": "mã nguồn + database", "source": "mã nguồn", "db": "database"}.get(rtype, rtype)
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận khôi phục",
                  f"Khôi phục <b>{what}</b> cho <b>{texts.esc(domain)}</b> "
                  f"từ bản <b>{texts.esc(date)}</b>?\n\n"
                  f"⚠️ Dữ liệu hiện tại sẽ bị <b>GHI ĐÈ</b>."),
            parse_mode=HTML,
            reply_markup=menus.confirm_menu("rst", rtype, domain, date, back="m|backup"))

    # bk|del|<domain>|<date> -> XAC NHAN xoa ban backup
    if action == "del":
        domain = params[0] if params else ""
        date = params[1] if len(params) > 1 else ""
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận xoá backup",
                  f"Xoá bản backup <b>{texts.esc(domain)}</b> ngày <b>{texts.esc(date)}</b>?"),
            parse_mode=HTML,
            reply_markup=menus.confirm_menu("bkdel", domain, date, back="m|backup"))

    # bk|rmdel|<remote> -> XAC NHAN xoa ket noi rclone
    if action == "rmdel":
        remote = params[0] if params else ""
        return await q.edit_message_text(
            title(E["warn"], "Xác nhận xoá kết nối",
                  f"Xoá remote <b>{texts.esc(remote)}</b> khỏi rclone?\n"
                  f"<i>Chỉ xoá cấu hình kết nối, không xoá dữ liệu trên cloud.</i>"),
            parse_mode=HTML,
            reply_markup=menus.confirm_menu("rmdel", remote, back="m|backup"))


# ---- Xac nhan thao tac nguy hiem (cf / yes) --------------------------------- #
async def cb_cf(update, context, action, params):
    q = update.callback_query
    if not can_write(_actor(update)):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only("m|vps"))
    if action == "restartall":
        await q.edit_message_text(
            title(E["warn"], "Xác nhận", "Restart tất cả dịch vụ (MariaDB/PHP/Nginx)?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("restartall"))
    elif action == "reboot":
        await q.edit_message_text(
            title(E["warn"], "Xác nhận", "Reboot server?"),
            parse_mode=HTML, reply_markup=menus.confirm_menu("reboot"))


async def cb_yes(update, context, what, params):
    q = update.callback_query
    chat = _actor(update)
    if not can_write(chat):
        return await q.edit_message_text(texts.NOTIFY_ONLY, parse_mode=HTML,
                                         reply_markup=menus.back_only())
    param = params[0] if params else ""

    if what == "restartall":
        return await _progress_op(
            update, True, f"{E['refresh']} <b>Đang restart toàn bộ dịch vụ</b>…",
            asyncio.to_thread(hostvn.restart_stack),
            lambda msg: (title(E["confirm"], "Hoàn tất",
                               f"<code>{progress.bar(100)}</code>\n{msg}"),
                         menus.back_only("m|vps")),
            est=12.0,
            stages=[(30, f"{E['db']} <b>Đang restart MariaDB</b>…"),
                    (60, f"{E['php']} <b>Đang restart PHP-FPM</b>…"),
                    (85, f"{E['svc']} <b>Đang restart Nginx</b>…")],
        )
    if what == "reboot":
        await q.edit_message_text(
            title(E["reboot"], "Server đang reboot…",
                  f"<code>{progress.bar(100)}</code>\nBot sẽ tự chạy lại sau khi khởi động."),
            parse_mode=HTML)
        await asyncio.to_thread(hostvn.reboot)
        return
    if what == "domdel":
        return await _progress_op(
            update, True, f"{E['del']} <b>Đang xoá domain</b> {texts.esc(param)}…",
            asyncio.to_thread(hostvn.delete_domain, param),
            lambda ok: ((title(E["confirm"], "Đã xoá domain",
                               f"<code>{progress.bar(100)}</code>\n{texts.esc(param)}") if ok
                         else title(E["warn"], "Không xoá được", texts.esc(param))),
                        menus.back_only("m|domain")),
            est=10.0,
            stages=[(40, f"{E['del']} <b>Xoá vHost &amp; PHP pool</b>…"),
                    (70, f"{E['del']} <b>Xoá user, thư mục &amp; database</b>…")],
        )
    if what.startswith("wp_") and what[3:] in WP_OPS:
        key = what[3:]
        ctl = WP_OPS[key][0]
        lbl = WP_LABEL.get(key, key)
        idx = await asyncio.to_thread(hostvn.wp_index, param)
        if not idx:
            return await q.edit_message_text(
                title(E["warn"], lbl, "Không tìm thấy site WordPress này."),
                parse_mode=HTML, reply_markup=menus.back_only("m|wp"))
        return await _progress_op(
            update, True, f"{E['wp']} <b>{texts.esc(lbl)}</b> — {texts.esc(param)}…",
            asyncio.to_thread(hostvn.wp_run, ctl, str(idx), 600),
            lambda msg: (title(E["confirm"], lbl, pre(msg)), menus.back_only("m|wp")),
            est=60.0, stages=[(50, f"{E['refresh']} <b>Đang xử lý</b>…")])
    if what == "permone":
        return await _progress_op(
            update, True, f"{E['perm']} <b>Đang phân quyền</b> {texts.esc(param)}…",
            asyncio.to_thread(hostvn.perm_apply_one, param),
            lambda r: (title(E["confirm"], "Phân quyền", texts.esc(r[1])),
                       menus.back_only("m|perm")), est=45.0,
            stages=[(50, "🔧 <b>Đang chmod thư mục &amp; file</b>…"),
                    (80, "👤 <b>Đang chown về user website</b>…")])
    if what == "permall":
        return await _progress_op(
            update, True, f"{E['perm']} <b>Đang phân quyền toàn bộ website</b>…",
            asyncio.to_thread(hostvn.perm_apply_all),
            lambda r: (title(E["confirm"], "Phân quyền toàn bộ",
                             f"<code>{progress.bar(100)}</code>\n{texts.esc(r[1])}"),
                       menus.back_only("m|perm")), est=120.0,
            stages=[(40, "🔧 <b>Đang xử lý từng website</b>…"),
                    (80, "👤 <b>Đang chown</b>…")])
    if what == "f2bjails":
        return await _progress_op(
            update, True, f"{E['fw']} <b>Đang bật thêm jail</b>…",
            asyncio.to_thread(hostvn.f2b_extra_jails),
            lambda msg: (title(E["confirm"], "Fail2ban jail", texts.esc(msg)),
                         menus.back_only("m|fw")), est=25.0)
    if what == "cronclr":
        return await _progress_op(
            update, True, f"{E['cron']} <b>Đang xoá cronjob</b>…",
            asyncio.to_thread(hostvn.cron_delete_all),
            lambda msg: (title(E["confirm"], "Cronjob", texts.esc(msg) +
                               "\n⚠️ Lịch auto-backup và gia hạn SSL cũng bị xoá — "
                               "cân nhắc tạo lại."),
                         menus.back_only("m|cron")), est=8.0)
    if what.startswith("admupd_"):
        ctl = what[7:]
        return await _progress_op(
            update, True, f"{E['refresh']} <b>Đang cập nhật</b> {texts.esc(param)}…",
            asyncio.to_thread(hostvn.run_ctl, "",
                              f"/var/hostvn/menu/controller/admin/{ctl}", 600),
            lambda out: (title(E["confirm"], param,
                               pre(hostvn._ctl_reason(out, "Đã cập nhật."))),
                         menus.back_only("m|admin")), est=90.0)
    if what == "nodejs":
        return await _progress_op(
            update, True, "🟩 <b>Đang cài NodeJS</b>…",
            asyncio.to_thread(hostvn.run_ctl, "",
                              "/var/hostvn/menu/controller/tools/install_nodejs", 900),
            lambda out: (title(E["confirm"], "NodeJS",
                               pre(hostvn.sh("node -v 2>/dev/null; npm -v 2>/dev/null", 15)
                                   or hostvn._ctl_reason(out, "Đã chạy."))),
                         menus.back_only("m|tool")), est=180.0)
    if what == "logclr":
        return await _progress_op(
            update, True, f"{E['log']} <b>Đang xoá error log</b>…",
            asyncio.to_thread(_clear_logs),
            lambda msg: (title(E["confirm"], "Xoá log", texts.esc(msg)),
                         menus.back_only("m|log")), est=10.0)
    if what == "clrall":
        return await _progress_op(
            update, True, f"{E['cache']} <b>Đang xoá toàn bộ cache</b>…",
            asyncio.to_thread(hostvn.cache_clear_all),
            lambda msg: (title(E["confirm"], "Xoá cache",
                               f"<code>{progress.bar(100)}</code>\n{texts.esc(msg)}"),
                         menus.back_only("m|cache")), est=30.0)
    if what in ("pkginstall", "pkguninstall"):
        inst = what == "pkginstall"
        return await _progress_op(
            update, True,
            f"{E['cache']} <b>Đang {'cài đặt' if inst else 'gỡ bỏ'}</b> {texts.esc(param)}…",
            asyncio.to_thread(hostvn.pkg_service, param, inst),
            lambda r: (title(E["confirm"] if r[0] else E["warn"], param, texts.esc(r[1])),
                       menus.back_only("m|cache")), est=120.0,
            stages=[(40, "📦 <b>Đang tải gói từ apt</b>…"), (75, "🔧 <b>Đang cấu hình</b>…")])

    # ----- SSL -----
    _SSL_OPS = {
        "sslnew":   (hostvn.ssl_create,   "Cấp SSL", 90.0),
        "sslwild":  (hostvn.ssl_wildcard, "Wildcard SSL", 180.0),
        "ssldel":   (hostvn.ssl_remove,   "Gỡ SSL", 30.0),
    }
    if what in _SSL_OPS:
        fn, label, est = _SSL_OPS[what]
        return await _progress_op(
            update, True, f"{E['ssl']} <b>{label}</b> — {texts.esc(param)}…",
            asyncio.to_thread(fn, param),
            lambda r: ((title(E["confirm"], label,
                              f"<code>{progress.bar(100)}</code>\n{texts.esc(r[1])}") if r[0]
                        else title(E["warn"], f"{label} thất bại", texts.esc(r[1]))),
                       menus.back_only("m|ssl")),
            est=est,
            stages=[(40, f"{E['ssl']} <b>Đang xác thực với Let's Encrypt</b>…"),
                    (75, "🔄 <b>Đang cài chứng chỉ &amp; reload nginx</b>…")])
    if what == "sslalias":
        return await _progress_op(
            update, True, f"{E['ssl']} <b>SSL Alias</b> — {texts.esc(param)}…",
            asyncio.to_thread(hostvn.run_ctl, f"{hostvn.domain_index(param)}\n1",
                              f"{hostvn.SSLCTL}/le_alias_domain", 300),
            lambda out: (title(E["info"], "SSL Alias domain",
                               pre(hostvn._ctl_reason(out, "Đã chạy xong."))),
                         menus.back_only("m|ssl")),
            est=90.0)
    if what == "sslrenew":
        return await _progress_op(
            update, True, f"{E['refresh']} <b>Đang gia hạn toàn bộ SSL</b>…",
            asyncio.to_thread(hostvn.ssl_renew_all),
            lambda r: (title(E["confirm"], "Gia hạn SSL",
                             f"<code>{progress.bar(100)}</code>\n{texts.esc(r[1])}"),
                       menus.back_only("m|ssl")),
            est=180.0,
            stages=[(50, f"{E['ssl']} <b>Đang liên hệ Let's Encrypt</b>…")])

    if what == "sftp":      # yes|sftp|<domain> -> doi mat khau SFTP ngau nhien
        return await _progress_op(
            update, True, f"{E['key']} <b>Đang đổi mật khẩu SFTP</b> {texts.esc(param)}…",
            asyncio.to_thread(hostvn.dom_change_sftp_pass, param, ""),
            lambda r: ((title(E["confirm"], "Đã đổi mật khẩu SFTP",
                              pre(f"Domain : {param}\nUser   : xem menu Thông tin domain\n"
                                  f"Pass   : {r[2]}") + "\n⚠️ <b>Lưu lại!</b>") if r[0]
                        else title(E["warn"], "Không đổi được", texts.esc(r[1]))),
                       menus.back_only("m|domain")),
            est=20.0)
    if what == "rst":       # yes|rst|<type>|<domain>|<date>
        rtype = params[0] if params else "full"
        domain = params[1] if len(params) > 1 else ""
        date = params[2] if len(params) > 2 else ""
        return await _progress_op(
            update, True, f"♻️ <b>Đang khôi phục</b> {texts.esc(domain)} ({texts.esc(date)})…",
            asyncio.to_thread(hostvn.restore_site, domain, date, rtype),
            lambda r: ((title(E["confirm"], "Khôi phục xong",
                              f"<code>{progress.bar(100)}</code>\n{texts.esc(r[1])}") if r[0]
                        else title(E["warn"], "Khôi phục thất bại", texts.esc(r[1]))),
                       menus.back_only("m|backup")),
            est=45.0,
            stages=[(35, "📁 <b>Đang giải nén mã nguồn</b>…"),
                    (70, f"{E['db']} <b>Đang import database</b>…"),
                    (90, "🔄 <b>Đang phân quyền lại</b>…")])
    if what == "bkdel":     # yes|bkdel|<domain>|<date>
        domain = params[0] if params else ""
        date = params[1] if len(params) > 1 else ""
        return await _progress_op(
            update, True, f"{E['del']} <b>Đang xoá backup</b> {texts.esc(domain)} {texts.esc(date)}…",
            asyncio.to_thread(hostvn.delete_backup, domain, date),
            lambda ok: ((title(E["confirm"], "Đã xoá bản backup",
                               f"{texts.esc(domain)} · {texts.esc(date)}") if ok
                         else title(E["warn"], "Không xoá được", "Kiểm tra lại bản backup.")),
                        menus.back_only("m|backup")),
            est=6.0)
    if what == "rmdel":     # yes|rmdel|<remote>
        return await _progress_op(
            update, True, f"{E['del']} <b>Đang xoá remote</b> {texts.esc(param)}…",
            asyncio.to_thread(hostvn.rclone_delete_remote, param),
            lambda ok: ((title(E["confirm"], "Đã xoá kết nối", texts.esc(param)) if ok
                         else title(E["warn"], "Không xoá được", texts.esc(param))),
                        menus.back_only("m|backup")),
            est=4.0)
    if what == "dbdel":
        return await _progress_op(
            update, True, f"{E['del']} <b>Đang xoá database</b> {texts.esc(param)}…",
            asyncio.to_thread(hostvn.delete_db, param),
            lambda ok: ((title(E["confirm"], "Đã xoá database",
                               f"<code>{progress.bar(100)}</code>\n{texts.esc(param)}") if ok
                         else title(E["warn"], "Không xoá được", texts.esc(param))),
                        menus.back_only("m|db")),
            est=5.0,
        )


# --------------------------------------------------------------------------- #
# Conversation flow (nhap lieu)
# --------------------------------------------------------------------------- #
async def start_flow(update, context, flow, back, emoji, heading, prompt):
    context.user_data["flow"] = flow
    q = update.callback_query
    await q.edit_message_text(
        title(emoji, heading, f"✍️ {prompt}\nNhập vào ô chat bên dưới, hoặc bấm ❌ Hủy."),
        parse_mode=HTML, reply_markup=menus.back_only(back))
    await context.bot.send_message(update.effective_chat.id, f"{emoji} {prompt}",
                                   parse_mode=HTML, reply_markup=menus.cancel_keyboard())


async def handle_flow(update, context, flow, text):
    chat = _actor(update)

    if flow == "db_add":
        editor = await _make_editor(update, False)
        ok, err, info = await progress.run(
            editor, f"{E['db']} <b>Đang tạo database</b> {texts.esc(text)}…",
            asyncio.to_thread(hostvn.create_db, text), est=6.0,
            stages=[(50, f"{E['db']} <b>Tạo user &amp; cấp quyền</b>…")])
        if info:
            body = (f"DB   : {info['db']}\nUser : {info['user']}\n"
                    f"Pass : {info['pass']}\nHost : {info['host']}")
            await editor(title(E["confirm"], "Đã tạo database",
                               f"<code>{progress.bar(100)}</code>\n" + pre(body) +
                               "\n⚠️ <b>Lưu lại!</b>"))
            context.user_data.pop("flow", None)
            await update.message.reply_text(
                title(E["home"], "Menu chính", "Chọn chức năng từ <b>menu bên dưới</b>."),
                parse_mode=HTML, reply_markup=menus.build_keyboard(_features(chat)))
        else:
            await editor(f"{E['warn']} {err} Nhập lại hoặc bấm ❌ Hủy.")
        return

    if flow in ("fw_ban", "fw_unban"):
        ban = flow == "fw_ban"
        editor = await _make_editor(update, False)
        ok, msg = await progress.run(
            editor, f"{'⛔' if ban else '🔓'} <b>Đang xử lý {texts.esc(text)}</b>…",
            asyncio.to_thread(hostvn.f2b_ban if ban else hostvn.f2b_unban, text.strip()),
            est=10.0)
        extra = ""
        if ban:
            b = await asyncio.to_thread(hostvn.fw_backend)
            if not b["iptables"] and not b["ufw"]:
                extra = ("\n\n⚠️ Fail2ban ở máy này dùng action <code>hostvn-noop</code> nên "
                         "lệnh ban <b>chỉ ghi nhận</b>, không chặn thật. Muốn chặn thật hãy "
                         "chặn IP ở <b>Cloudflare WAF</b>.")
        await editor(title(E["confirm"] if ok else E["warn"],
                           "Ban IP" if ban else "Unban IP", texts.esc(msg) + extra))
        context.user_data.pop("flow", None)
        await update.message.reply_text(
            title(E["home"], "Menu chính", "Chọn chức năng từ <b>menu bên dưới</b>."),
            parse_mode=HTML, reply_markup=menus.build_keyboard(_features(chat)))
        return

    if flow == "ssl_cfapi":
        bits = text.split()
        if len(bits) < 2:
            return await update.message.reply_text(
                f"{E['warn']} Cần đủ <b>token</b> và <b>email</b>. Nhập lại:", parse_mode=HTML)
        editor = await _make_editor(update, False)
        ok, msg = await progress.run(
            editor, "☁️ <b>Đang lưu CloudFlare DNS API</b>…",
            asyncio.to_thread(hostvn.ssl_cf_api_set, bits[0], bits[1]), est=10.0)
        await editor(title(E["confirm"] if ok else E["warn"],
                           "CloudFlare DNS API", texts.esc(msg) +
                           ("\n\n⚠️ <b>Nhớ xoá tin nhắn chứa token</b> ở trên." if ok else "")))
        context.user_data.pop("flow", None)
        await update.message.reply_text(
            title(E["home"], "Menu chính", "Chọn chức năng từ <b>menu bên dưới</b>."),
            parse_mode=HTML, reply_markup=menus.build_keyboard(_features(chat)))
        return

    # ----- Cac flow quan ly domain nang cao -----
    if flow in ("dom_rename", "dom_alias", "dom_redirect", "dom_protect"):
        dom = context.user_data.get("dom", "")
        if not dom:
            context.user_data.pop("flow", None)
            return await update.message.reply_text(f"{E['warn']} Mất ngữ cảnh domain, chọn lại.",
                                                   parse_mode=HTML)
        editor = await _make_editor(update, False)

        if flow == "dom_protect":
            bits = text.split()
            if len(bits) < 3:
                return await update.message.reply_text(
                    f"{E['warn']} Cần đủ 3 phần: <code>/đường_dẫn user mật_khẩu</code>. Nhập lại:",
                    parse_mode=HTML)
            path, usr, pwd = bits[0], bits[1], " ".join(bits[2:])
            work = asyncio.to_thread(hostvn.dom_protect_dir, dom, path, usr, pwd)
            titlemsg = f"🔐 <b>Đang bảo vệ thư mục</b> {texts.esc(path)}…"
        elif flow == "dom_rename":
            work = asyncio.to_thread(hostvn.dom_rename, dom, text)
            titlemsg = f"✏️ <b>Đang đổi tên miền</b> {texts.esc(dom)}…"
        elif flow == "dom_alias":
            work = asyncio.to_thread(hostvn.dom_alias_add, dom, text)
            titlemsg = f"🔗 <b>Đang thêm alias</b> {texts.esc(text)}…"
        else:
            work = asyncio.to_thread(hostvn.dom_redirect_add, dom, text)
            titlemsg = f"↪️ <b>Đang thêm redirect</b> {texts.esc(text)}…"

        ok, msg = await progress.run(editor, titlemsg, work, est=25.0,
                                     stages=[(60, "🔄 <b>Đang cập nhật cấu hình nginx</b>…")])
        await editor(title(E["confirm"] if ok else E["warn"],
                           "Hoàn tất" if ok else "Không thành công",
                           f"<code>{progress.bar(100)}</code>\n{texts.esc(msg)}" if ok
                           else texts.esc(msg)))
        context.user_data.pop("flow", None)
        context.user_data.pop("dom", None)
        await update.message.reply_text(
            title(E["home"], "Menu chính", "Chọn chức năng từ <b>menu bên dưới</b>."),
            parse_mode=HTML, reply_markup=menus.build_keyboard(_features(chat)))
        return

    if flow == "dom_add":
        d = text.strip().lower()
        if d.startswith("www."):
            d = d[4:]
        if not hostvn.DOMAIN_RE.match(d):
            return await update.message.reply_text(
                f"{E['warn']} Tên miền không hợp lệ, nhập lại (vd: shop.com):", parse_mode=HTML)
        if (Path(C.VHOST_DIR) / f"{d}.conf").exists():
            context.user_data.pop("flow", None)
            return await update.message.reply_text(
                f"{E['warn']} Domain <b>{texts.esc(d)}</b> đã tồn tại.",
                parse_mode=HTML, reply_markup=menus.build_keyboard(_features(chat)))
        context.user_data.pop("flow", None)
        await update.message.reply_text(
            title(E["domain"], d, "Chọn loại website:"),
            parse_mode=HTML, reply_markup=menus.new_domain_type_menu(d))
        # tra lai ban phim chinh
        await update.message.reply_text("👇", reply_markup=menus.build_keyboard(_features(chat)))
        return

    context.user_data.pop("flow", None)


CALLBACK_ROUTES = {
    "nav": cb_nav, "m": cb_open, "a": cb_action, "svc": cb_svc, "do": cb_do,
    "pick": cb_pick, "nd": cb_nd, "cf": cb_cf, "yes": cb_yes, "bk": cb_bk,
    "dm": cb_dm, "ssl": cb_ssl, "cc": cb_cc, "lg": cb_lg, "pp": cb_pp, "wp": cb_wp, "up": cb_up, "lg2": cb_lg2,
}
