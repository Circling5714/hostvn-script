"""Khai bao menu bang DU LIEU + ham dung ban phim (hostvn bot).

- MENU CHINH (tang 1): ReplyKeyboardMarkup co dinh, khai bao bang MAIN_MENU (data),
  cap 2 nut/hang, loc theo quyen bang build_keyboard(features).
- SUB-MENU (tang 2): InlineKeyboardMarkup, callback_data = "<mien>|<hanh_dong>|<tham_so>".
- cancel_keyboard(): ban phim rieng chi co "❌ Hủy".
"""
from __future__ import annotations

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import config as C
from permissions import can_see

# --------------------------------------------------------------------------- #
# MENU CHINH - khai bao bang DU LIEU (feature_key, "emoji nhan"), cap 2 nut/hang
# --------------------------------------------------------------------------- #
MAIN_MENU: list[list[tuple[str, str]]] = [
    [(C.F_DOMAIN, f"{C.E['domain']} Domain"),   (C.F_LEMP, f"{C.E['lemp']} LEMP")],
    [(C.F_WP,     f"{C.E['wp']} WordPress"),    (C.F_SSL,  f"{C.E['ssl']} SSL")],
    [(C.F_CACHE,  f"{C.E['cache']} Cache"),     (C.F_BACKUP, f"{C.E['backup']} Backup")],
    [(C.F_FW,     f"{C.E['fw']} Firewall"),     (C.F_SVC,  f"{C.E['svc']} Dịch vụ")],
    [(C.F_SYS,    f"{C.E['sys']} Hệ thống"),    (C.F_VPS,  f"{C.E['vps']} VPS")],
    [(C.F_TOOL,   f"{C.E['tool']} Công cụ"),
     (C.F_PERM,   f"{C.E['perm']} Phân quyền")],
    [(C.F_ACC,    f"{C.E['acc']} Thông tin Acc"),
     (C.F_CRON,   f"{C.E['cron']} Cronjob")],
    [(C.F_UPD,    f"{C.E['upd']} Update HostVN"),
     (C.F_LANG,   f"{C.E['lang']} Change language")],
]


def perm_menu() -> InlineKeyboardMarkup:
    """Mirror menu '6. Phan quyen Chown/Chmod' cua shell."""
    return rows_menu([
        [(f"{C.E['list']} Kiểm tra quyền hiện tại", "a|perm_check")],
        [(f"{C.E['key']} Phân quyền 1 website", "a|perm_one")],
        [(f"{C.E['refresh']} Phân quyền TOÀN BỘ website", "a|perm_all")],
    ])


def lemp_menu() -> InlineKeyboardMarkup:
    """Mirror menu '4. Quan ly LEMP' cua shell: Nginx / PHP / Database / Log."""
    return rows_menu([
        [(f"{C.E['svc']} Nginx", "m|nginx"), (f"{C.E['php']} PHP", "m|php")],
        [(f"{C.E['db']} Database", "m|db"),  (f"{C.E['log']} Log", "m|log")],
    ])


def nginx_menu() -> InlineKeyboardMarkup:
    """Mirror lemp_nginx (4 muc)."""
    return rows_menu([
        [(f"{C.E['refresh']} Restart Nginx", "do|nginx|restart")],
        [(f"{C.E['confirm']} Test cấu hình Nginx", "a|ngx_test")],
        [(f"{C.E['add']} Update Nginx", "a|ngx_update")],
        [("🔨 Rebuild Nginx", "a|ngx_rebuild")],
    ], back="m|lemp")


def log_menu() -> InlineKeyboardMarkup:
    """Mirror lemp_log (5 muc)."""
    return rows_menu([
        [(f"{C.E['svc']} Nginx error log", "lg|nginx")],
        [(f"{C.E['php']} PHP error log", "lg|php")],
        [(f"{C.E['db']} MariaDB error log", "lg|mysql")],
        [(f"{C.E['domain']} Website error log", "lg|site")],
        [(f"{C.E['del']} Xoá toàn bộ error log", "lg|clear")],
    ], back="m|lemp")

LABEL_TO_FEATURE: dict[str, str] = {label: key for row in MAIN_MENU for (key, label) in row}


def build_keyboard(features: set[str] | None) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    for row in MAIN_MENU:
        visible = [KeyboardButton(label) for key, label in row if can_see(key, features)]
        if visible:
            rows.append(visible)
    if not rows:
        rows = [[KeyboardButton(C.LBL_MENU)]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(C.LBL_CANCEL)]],
                               resize_keyboard=True, one_time_keyboard=True)


# --------------------------------------------------------------------------- #
# Tien ich dung ban phim inline
# --------------------------------------------------------------------------- #
def back_row(target: str = C.CB_HOME) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(C.LBL_BACK, callback_data=target)]


def rows_menu(rows: list[list[tuple[str, str]]], back: str = C.CB_HOME) -> InlineKeyboardMarkup:
    """rows: list cac hang, moi hang list (label, callback_data). Tu them nut Quay lai."""
    kb = [[InlineKeyboardButton(lbl, callback_data=cb) for (lbl, cb) in row] for row in rows]
    kb.append(back_row(back))
    return InlineKeyboardMarkup(kb)


def back_only(target: str = C.CB_HOME) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([back_row(target)])


def confirm_menu(what: str, *params: str, back: str = C.CB_HOME) -> InlineKeyboardMarkup:
    data = "|".join(["yes", what, *[p for p in params if p]])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"{C.E['confirm']} Đồng ý", callback_data=data),
        InlineKeyboardButton(C.LBL_CANCEL, callback_data=back),
    ]])


# --------------------------------------------------------------------------- #
# SUB-MENU tinh (callback "<mien>|<hanh_dong>")
# --------------------------------------------------------------------------- #
def domain_menu() -> InlineKeyboardMarkup:
    """Mirror menu '1. Quan ly ten mien' (13 muc) cua shell hostvn."""
    return rows_menu([
        [(f"{C.E['list']} Danh sách domain", "a|dom_list"),
         (f"{C.E['info']} Thông tin domain", "a|dom_info")],
        [(f"{C.E['add']} Thêm domain", "a|dom_add"),
         (f"{C.E['del']} Xoá domain", "a|dom_del")],
        [("✏️ Đổi tên miền", "a|dom_rename"),
         ("🧬 Clone website", "a|dom_clone")],
        [("🧱 Rewrite vHost", "a|dom_rewrite"),
         (f"{C.E['php']} Đổi phiên bản PHP", "a|dom_php")],
        [("🔗 Alias/Parked", "a|dom_alias"),
         ("↪️ Redirect", "a|dom_redirect")],
        [(f"{C.E['key']} Đổi mật khẩu SFTP", "a|dom_sftp"),
         ("🔐 Bảo vệ thư mục", "a|dom_protect")],
        [("🚀 Bật/Tắt HTTP/3", "a|dom_http3"),
         (f"{C.E['db']} Đổi thông tin DB", "a|dom_dbinfo")],
    ])


def onoff_menu(domain: str, act: str, back: str = "m|domain") -> InlineKeyboardMarkup:
    """Bat/Tat cho 1 domain -> dm|<act>on|<domain> / dm|<act>off|<domain>."""
    return rows_menu([
        [(f"{C.E['on']} Bật", f"dm|{act}on|{domain}"),
         (f"{C.E['off']} Tắt", f"dm|{act}off|{domain}")],
    ], back=back)


def php_choice_menu(domain: str, versions: list[str], back: str = "m|domain") -> InlineKeyboardMarkup:
    """Chon phien ban PHP -> dm|php|<domain>|<lua_chon 1|2>."""
    rows = [[(f"{C.E['php']} PHP {v}", f"dm|php|{domain}|{i + 1}")]
            for i, v in enumerate(versions[:2])]
    return rows_menu(rows, back=back)


def source_menu(domain: str, back: str = "m|domain") -> InlineKeyboardMarkup:
    """Chon loai ma nguon khi rewrite vHost -> dm|rw|<domain>|<source_idx>."""
    common = [("WordPress", 1), ("Laravel", 2), ("Nodejs", 8), ("Khác/Static", 20)]
    rows = [[(f"📦 {name}", f"dm|rw|{domain}|{i}")] for name, i in common]
    return rows_menu(rows, back=back)


def db_menu() -> InlineKeyboardMarkup:
    """Mirror lemp_database (7 muc)."""
    return rows_menu([
        [(f"{C.E['list']} Danh sách DB", "a|db_list")],
        [(f"{C.E['add']} Tạo database", "a|db_add"),
         (f"{C.E['del']} Xoá database", "a|db_del")],
        [(f"{C.E['key']} Đổi mật khẩu MySQL user", "a|db_pass")],
        [(f"{C.E['refresh']} Restart MariaDB", "do|mariadb|restart")],
        [("📥 Import database", "a|db_import"),
         ("🌐 Remote MySQL", "a|db_remote")],
    ], back="m|lemp")


def wp_menu() -> InlineKeyboardMarkup:
    """Mirror menu '7. Quan ly WordPress' (10 muc) cua shell."""
    return rows_menu([
        [(f"{C.E['list']} Site WordPress", "a|wp_list"),
         (f"{C.E['info']} Thông tin site", "a|wp_info")],
        [(f"{C.E['add']} Cài WordPress tự động", "a|wp_install")],
        [(f"{C.E['refresh']} Update WordPress Core", "a|wp_core")],
        [("🧩 Plugins manager", "a|wp_plugins")],
        [(f"{C.E['db']} Tối ưu Database", "a|wp_optimize")],
        [(f"{C.E['key']} Đổi mật khẩu wp-admin", "a|wp_pass")],
        [("📦 Move wp-config", "a|wp_moveconf"),
         ("🔐 Bảo vệ wp-admin", "a|wp_htpasswd")],
        [("✏️ Sửa theme/plugin", "a|wp_edit"),
         ("🔒 Lockdown", "a|wp_lockdown")],
        [(f"{C.E['cache']} Xoá cache WP", "a|wp_cache")],
        [("⚙️ Nâng cao", "m|wpadv")],
    ])


def wp_plugins_menu(back: str = "m|wp") -> InlineKeyboardMarkup:
    """Mirror wordpress_plugins_manage (2 muc)."""
    return rows_menu([
        [(f"{C.E['refresh']} Update plugins", "a|wp_plugupd")],
        [(f"{C.E['off']} Huỷ kích hoạt toàn bộ plugins", "a|wp_plugoff")],
    ], back=back)


def wp_adv_menu(back: str = "m|wp") -> InlineKeyboardMarkup:
    """Mirror wordpress_advanced (11 muc)."""
    return rows_menu([
        [("🟠 Yoast SEO config", "a|wpa_yoast"),
         ("🟣 Rank Math config", "a|wpa_rank")],
        [("🖼️ WebP Express", "a|wpa_webp"),
         (f"{C.E['cache']} Nginx + plugin cache", "a|wpa_cacheplug")],
        [("🔑 Thêm cache key", "a|wpa_cachekey")],
        [("🐞 Debug mode", "a|wpa_debug"),
         ("🛠️ Chế độ bảo trì", "a|wpa_maint")],
        [("🚫 Disable XMLRPC", "a|wpa_xmlrpc"),
         ("🙅 Block User API", "a|wpa_userapi")],
        [("⏰ WP-Cron", "a|wpa_cron"),
         ("🗑️ Xoá Post Revisions", "a|wpa_revision")],
    ], back=back)


def wp_onoff_menu(key: str, domain: str, on_lbl: str, off_lbl: str,
                  back: str = "m|wp") -> InlineKeyboardMarkup:
    """Chon 1/2 cho controller toggle -> wp|<key>|<domain>|<1|2>."""
    return rows_menu([
        [(f"{C.E['on']} {on_lbl}", f"wp|{key}|{domain}|2"),
         (f"{C.E['off']} {off_lbl}", f"wp|{key}|{domain}|1")],
    ], back=back)


def ssl_menu() -> InlineKeyboardMarkup:
    """Mirror menu '2. Quan ly SSL' (Let's Encrypt 7 muc + SSL tra phi)."""
    return rows_menu([
        [(f"{C.E['list']} Trạng thái SSL", "a|ssl_list"),
         (f"{C.E['month']} Kiểm tra hạn", "a|ssl_check")],
        [(f"{C.E['add']} Cấp/Gia hạn Let's Encrypt", "a|ssl_create")],
        [("🌟 Wildcard SSL (CF DNS)", "a|ssl_wildcard")],
        [(f"{C.E['refresh']} Gia hạn tất cả", "a|ssl_renew")],
        [("🔗 SSL cho Alias domain", "a|ssl_alias"),
         (f"{C.E['del']} Gỡ Let's Encrypt", "a|ssl_remove")],
        [("☁️ CloudFlare DNS API", "a|ssl_cfapi")],
        [("📜 SSL trả phí (CSR/CRT)", "a|ssl_paid")],
    ])


def cache_menu() -> InlineKeyboardMarkup:
    """Mirror menu '3. Quan ly Cache' cua shell."""
    return rows_menu([
        [(f"{C.E['list']} Trạng thái cache", "a|cache_status")],
        [(f"{C.E['cache']} Xoá toàn bộ cache", "a|cache_clear_all")],
        [(f"{C.E['db']} Memcached", "a|cache_mc"),
         ("🔴 Redis", "a|cache_redis")],
        [(f"{C.E['php']} PHP OPcache", "a|cache_opcache")],
        [("🚀 Nginx FastCGI cache", "a|cache_fastcgi")],
    ])


def svc_pkg_menu(name: str, running: bool, installed: bool,
                 back: str = "m|cache") -> InlineKeyboardMarkup:
    """Quan ly 1 dich vu cache: bat/tat + cai/go. cb: cc|<act>|<name>."""
    rows = []
    if installed:
        rows.append([(f"{C.E['stop']} Tắt", f"cc|off|{name}") if running
                     else (f"{C.E['start']} Bật", f"cc|on|{name}"),
                     (f"{C.E['refresh']} Restart", f"cc|restart|{name}")])
        rows.append([(f"{C.E['del']} Gỡ bỏ", f"cc|uninstall|{name}")])
    else:
        rows.append([(f"{C.E['add']} Cài đặt", f"cc|install|{name}")])
    return rows_menu(rows, back=back)


def opcache_menu(back: str = "m|cache") -> InlineKeyboardMarkup:
    return rows_menu([
        [(f"{C.E['on']} Bật OPcache", "cc|opon|-"),
         (f"{C.E['off']} Tắt OPcache", "cc|opoff|-")],
        [(f"{C.E['cache']} Xoá OPcache", "a|opcache_clear")],
        [("🚫 Blacklist website", "a|opcache_bl")],
    ], back=back)


def fastcgi_menu(on: list[str], off: list[str], back: str = "m|cache") -> InlineKeyboardMarkup:
    """Bat cho domain dang tat, tat cho domain dang bat."""
    rows = [[(f"{C.E['on']} Bật cho {d}", f"cc|fcon|{d}")] for d in off[:10]]
    rows += [[(f"{C.E['off']} Tắt cho {d}", f"cc|fcoff|{d}")] for d in on[:10]]
    if not rows:
        rows = [[("(chưa có domain)", "noop")]]
    return rows_menu(rows, back=back)


def backup_menu() -> InlineKeyboardMarkup:
    """Mirror menu 'Sao luu/Khoi phuc du lieu' cua shell hostvn."""
    return rows_menu([
        [(f"{C.E['backup']} Backup website", "a|bk_run")],
        [(f"♻️ Khôi phục (Restore)", "a|bk_restore")],
        [(f"{C.E['list']} Danh sách bản backup", "a|bk_list")],
        [(f"{C.E['del']} Xoá bản backup", "a|bk_del")],
        [("⏰ Auto backup (cron)", "a|bk_auto")],
        [("☁️ Remote đã kết nối", "a|bk_remotes")],
        [("🔗 Kết nối GDrive / OneDrive / S3", "a|bk_connect")],
    ])


def backup_type_menu(domain: str, back: str = "m|backup") -> InlineKeyboardMarkup:
    """Chon loai backup -> bk|run|<type>|<domain>."""
    return rows_menu([
        [(f"{C.E['confirm']} Full (mã nguồn + DB)", f"bk|run|full|{domain}")],
        [("📁 Chỉ mã nguồn", f"bk|run|source|{domain}")],
        [(f"{C.E['db']} Chỉ database", f"bk|run|db|{domain}")],
    ], back=back)


def restore_type_menu(domain: str, date: str, back: str = "m|backup") -> InlineKeyboardMarkup:
    """Chon loai khoi phuc -> bk|rst|<type>|<domain>|<date>."""
    return rows_menu([
        [(f"{C.E['confirm']} Full (mã nguồn + DB)", f"bk|rst|full|{domain}|{date}")],
        [("📁 Chỉ mã nguồn", f"bk|rst|source|{domain}|{date}")],
        [(f"{C.E['db']} Chỉ database", f"bk|rst|db|{domain}|{date}")],
    ], back=back)


def backup_date_menu(domain: str, dates: list[str], back: str = "m|backup") -> InlineKeyboardMarkup:
    """Chon ngay backup de khoi phuc: bk|rsd|<domain>|<date>."""
    rows = [[(f"📅 {d}", f"bk|rsd|{domain}|{d}")] for d in dates[:20]]
    return rows_menu(rows, back=back)


def backup_entry_menu(rows_data: list[tuple[str, str, str]], action: str,
                      back: str = "m|backup") -> InlineKeyboardMarkup:
    """rows_data: list (domain, date, nhan). callback bk|<action>|<domain>|<date>."""
    rows = [[(label, f"bk|{action}|{dom}|{dt}")] for dom, dt, label in rows_data[:20]]
    return rows_menu(rows, back=back)


def remotes_menu(remotes: list[str], back: str = "m|backup") -> InlineKeyboardMarkup:
    rows = [[(f"☁️ {r}", f"bk|rmdel|{r}")] for r in remotes[:15]]
    return rows_menu(rows, back=back)


def fw_menu() -> InlineKeyboardMarkup:
    """Mirror menu '5. Quan ly Firewall' (10 muc) cua shell."""
    return rows_menu([
        [(f"{C.E['list']} Trạng thái firewall", "a|fw_status")],
        [(f"{C.E['status']} Thống kê Fail2ban", "a|f2b_stats"),
         ("🚫 IP đang bị ban", "a|fw_banned")],
        [("⛔ Ban IP", "a|fw_ban"), ("🔓 Unban IP", "a|fw_unban")],
        [("🧱 Bật thêm jail", "a|fw_jails")],
        [(f"{C.E['refresh']} Restart Fail2ban", "do|fail2ban|restart")],
        [("☁️ Cloudflare WAF", "a|fw_cfwaf")],
        [("🔌 Mở port / Bật-Tắt firewall", "a|fw_port")],
    ])


def php_menu() -> InlineKeyboardMarkup:
    """Mirror lemp_php (10 muc)."""
    return rows_menu([
        [(f"{C.E['info']} php.ini settings", "a|php_info")],
        [(f"{C.E['refresh']} Restart PHP-FPM", "a|php_restart")],
        [("⚙️ Cấu hình tham số PHP", "a|php_params")],
        [("🔀 Đổi PHP mặc định", "a|php_default"),
         ("2️⃣ PHP thứ hai", "a|php_second")],
        [("🧩 Cài ionCube", "a|php_ioncube")],
        [("🔒 Open Basedir", "pp|basedir"),
         ("🌐 allow_url_fopen", "pp|urlfopen")],
        [("⚡ proc_open/proc_close", "pp|procopen"),
         ("🎛️ PHP Process Manager", "a|php_pm")],
    ], back="m|lemp")


def sys_menu() -> InlineKeyboardMarkup:
    return rows_menu([[(f"{C.E['refresh']} Làm mới", "m|sys")]])


def vps_menu() -> InlineKeyboardMarkup:
    return rows_menu([
        [(f"{C.E['info']} Thông tin VPS", "a|vps_info")],
        [(f"{C.E['sys']} Dung lượng thư mục", "a|vps_disk")],
        [(f"{C.E['refresh']} Restart tất cả dịch vụ", "cf|restartall")],
        [(f"{C.E['reboot']} Reboot server", "cf|reboot")],
    ])


def tool_menu() -> InlineKeyboardMarkup:
    """Mirror menu '13. Cong cu' (9 muc) + loi vao '9. Admin Tool'."""
    return rows_menu([
        [("🔗 Link Admin", "a|links"),
         (f"{C.E['sys']} File/thư mục lớn", "a|largefiles")],
        [("📐 Dung lượng website", "a|tool_size"),
         ("🖼️ Nén ảnh", "a|tool_img")],
        [("📦 Giải nén file", "a|tool_unzip"),
         ("🚀 Deploy website", "a|tool_deploy")],
        [("🟩 Cài NodeJS", "a|tool_nodejs"),
         ("🦠 Cài Anti Virus", "a|tool_av")],
        [("☁️ Tải file Google Drive", "a|tool_ggdl")],
        [(f"{C.E['admin']} Admin Tool", "m|admin")],
    ])


def admin_menu() -> InlineKeyboardMarkup:
    """Mirror menu '9. Admin Tool' (7 muc)."""
    return rows_menu([
        [("📊 Nginx Status (VTS)", "a|adm_vts")],
        [(f"{C.E['key']} Đổi mật khẩu Admin Tool", "a|adm_pass"),
         ("🔌 Đổi port Admin Tool", "a|adm_port")],
        [(f"{C.E['refresh']} Update phpMyAdmin", "a|adm_pma")],
        [(f"{C.E['refresh']} Update Opcache Panel", "a|adm_opc"),
         (f"{C.E['refresh']} Update Redis Admin", "a|adm_redis")],
        [(f"{C.E['refresh']} Update Memcached Admin", "a|adm_mc")],
    ], back="m|tool")


def acc_menu() -> InlineKeyboardMarkup:
    """Mirror menu '11. Xem thong tin tai khoan' (5 muc)."""
    return rows_menu([
        [("🛡️ Thông tin Admin Tool", "a|acc_admin")],
        [(f"{C.E['db']} Thông tin phpMyAdmin", "a|acc_pma")],
        [("🔌 SSH / SFTP Port", "a|acc_ssh")],
        [(f"{C.E['domain']} Thông tin theo Website", "a|acc_site")],
        [(f"{C.E['key']} Đổi mật khẩu SFTP website", "a|acc_sftp")],
    ])


def cron_menu() -> InlineKeyboardMarkup:
    """Mirror menu '12. Cronjob/Auto Backup' (6 muc)."""
    return rows_menu([
        [(f"{C.E['list']} Danh sách cronjob", "a|cron_list")],
        [(f"{C.E['backup']} Auto backup tại VPS", "a|cron_local")],
        [("☁️ Auto backup Google Drive", "a|cron_gg"),
         ("☁️ Auto backup OneDrive", "a|cron_od")],
        [("✏️ Cronjob tuỳ chỉnh", "a|cron_custom")],
        [(f"{C.E['del']} Xoá cronjob", "a|cron_del")],
    ])


def upd_menu(has_new: bool, new: str = "") -> InlineKeyboardMarkup:
    rows = [[(f"{C.E['refresh']} Cập nhật lên {new}", "up|run")]] if has_new else []
    return rows_menu(rows or [[(f"{C.E['confirm']} Đang là bản mới nhất", "noop")]])


def lang_menu(cur: str) -> InlineKeyboardMarkup:
    mark = lambda c: " ✅" if cur == c else ""
    return rows_menu([
        [(f"🇻🇳 Tiếng Việt{mark('vi')}", "lg2|vi"),
         (f"🇬🇧 English{mark('en')}", "lg2|en")],
    ])


# --------------------------------------------------------------------------- #
# SUB-MENU dong (nhan du lieu tu handler)
# --------------------------------------------------------------------------- #
def services_menu(items: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """items: list (label, service). Moi service 1 nut svc|<service>."""
    rows = [[(lbl, f"svc|{svc}")] for lbl, svc in items]
    return rows_menu(rows)


def service_one_menu(service: str, can_write: bool) -> InlineKeyboardMarkup:
    if can_write:
        rows = [
            [(f"{C.E['refresh']} Restart", f"do|{service}|restart"),
             (f"{C.E['start']} Start", f"do|{service}|start")],
            [(f"{C.E['stop']} Stop", f"do|{service}|stop"),
             (f"{C.E['info']} Làm mới", f"svc|{service}")],
        ]
    else:
        rows = [[(f"{C.E['info']} Làm mới", f"svc|{service}")]]
    return rows_menu(rows, back="m|svc")


def picker_menu(action: str, items: list[str], emoji: str, back: str = C.CB_HOME) -> InlineKeyboardMarkup:
    """Danh sach chon (domain/db...). callback pick|<action>|<item>."""
    rows = [[(f"{emoji} {it}", f"pick|{action}|{it}")] for it in items[:25]]
    return rows_menu(rows, back=back)


def new_domain_type_menu(domain: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{C.E['php']} Website PHP", callback_data=f"nd|def|{domain}"),
         InlineKeyboardButton(f"{C.E['wp']} WordPress", callback_data=f"nd|wp|{domain}")],
        [InlineKeyboardButton(C.LBL_CANCEL, callback_data="m|domain")],
    ])
