"""Lop thao tac he thong hostvn (dong bo, goi qua asyncio.to_thread o handler).

Bao subprocess quanh cac lenh he thong + tai su dung _svc (menu/helpers/environment)
va cac controller hostvn (add_domain...) qua run_ctl.
"""
from __future__ import annotations

import os
import re
import secrets
import shlex
import string
import subprocess
import tempfile
import time
from pathlib import Path

import config as C

DOMAIN_RE = re.compile(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_SKIP_DB = {"information_schema", "performance_schema", "mysql", "sys", "phpmyadmin"}


def _env() -> dict[str, str]:
    return {**os.environ, "PATH": C.PATH_ENV, "DEBIAN_FRONTEND": "noninteractive", "TERM": "dumb"}


# Ban ARM64 co lop truu tuong _svc trong menu/helpers/environment (vi khong co systemd).
# Ban x86 chay systemd nen KHONG can lop do; bot tu cap mot _svc toi gian anh xa sang
# systemctl de phan con lai cua code dung chung khong phai biet minh dang o dau.
_SVC_SHIM = r'''
_svc_unit() {
    # mot vai ten khac nhau giua cac ban phan phoi
    case "$1" in
        redis) systemctl list-unit-files redis.service >/dev/null 2>&1 \
                 && echo redis || echo redis-server ;;
        *) echo "$1" ;;
    esac
}
_svc() {
    local action="$1" svc state; svc="$(_svc_unit "$2")"
    case "${action}" in
        is-active)
            # systemctl da IN trang thai roi ke ca khi thoat khac 0 ("inactive",
            # "failed"...). Chi tu dat "inactive" khi no khong in gi (unit khong ton tai),
            # neu khong se in trung hai lan.
            state="$(systemctl is-active "${svc}" 2>/dev/null)"
            [ -n "${state}" ] || state="inactive"
            echo "${state}"
            [ "${state}" = "active" ] || return 3
            ;;
        enable|disable|daemon-reload) systemctl "${action}" "${svc}" >/dev/null 2>&1 ;;
        *) systemctl "${action}" "${svc}" >/dev/null 2>&1 ;;
    esac
}
_svc_active() { [ "$(systemctl is-active "$(_svc_unit "$1")" 2>/dev/null)" = "active" ]; }
'''


def _env_prefix() -> str:
    """Nap _svc: dung lop cua HostVN neu co, khong thi dung shim systemctl."""
    if Path(C.ENVIRONMENT).exists():
        return f"source {C.ENVIRONMENT} 2>/dev/null; "
    return _SVC_SHIM + "\n"


def sh(script: str, timeout: int = 40, source_env: bool = False, merge: bool = False) -> str:
    """Chay 'bash -c script'. source_env: nap lop dieu khien service (_svc)."""
    prefix = _env_prefix() if source_env else ""
    try:
        p = subprocess.run(
            ["bash", "-c", prefix + script],
            capture_output=True, text=True, timeout=timeout, env=_env(),
        )
        out = p.stdout + (p.stderr if merge else "")
        return out.strip()
    except subprocess.TimeoutExpired:
        return "⏱️ Quá thời gian thực thi."
    except Exception as e:  # noqa: BLE001
        return f"Lỗi: {e}"


def genpw(n: int = 16) -> str:
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(n))


# --------------------------------------------------------------------------- #
# Dich vu (_svc)
# --------------------------------------------------------------------------- #
def svc(action: str, service: str, timeout: int = 40) -> str:
    return sh(f"_svc {shlex.quote(action)} {shlex.quote(service)}", timeout, source_env=True, merge=True)


def svc_status(service: str) -> str:
    return sh(f"_svc is-active {shlex.quote(service)}", 15, source_env=True) or "unknown"


def icon(service: str) -> str:
    return C.E["on"] if svc_status(service) == "active" else C.E["off"]


def services_status(names: list[str]) -> dict[str, str]:
    """Trang thai nhieu dich vu trong 1 lan goi bash (nhanh hon goi tung cai)."""
    script = "; ".join(f'printf "%s:%s\\n" {shlex.quote(n)} "$(_svc is-active {shlex.quote(n)} 2>/dev/null)"'
                       for n in names)
    out = sh(script, 25, source_env=True)
    result: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            result[k.strip()] = v.strip()
    return result


def php_version() -> str:
    out = sh("ls /etc/php 2>/dev/null", 10)
    vers = sorted((x for x in out.split() if x[:1].isdigit()),
                  key=lambda s: [int(p) for p in s.split(".") if p.isdigit()] or [0])
    return vers[-1] if vers else "8.4"


# --------------------------------------------------------------------------- #
# Domain / Database
# --------------------------------------------------------------------------- #
def list_domains() -> list[str]:
    out = sh(f"ls {C.VHOST_DIR} 2>/dev/null", 10)
    doms = [f[:-5] for f in out.split() if f.endswith(".conf")]
    return sorted(d for d in doms if d not in ("default", "web_apps"))


def docroot(domain: str) -> str:
    conf = Path(C.VHOST_DIR) / f"{domain}.conf"
    if not conf.exists():
        return ""
    m = re.search(r"root\s+([^;]+);", conf.read_text(errors="replace"))
    return m.group(1).strip() if m else ""


def http_code(domain: str) -> str:
    return sh(f"curl -sS -H 'Host: {shlex.quote(domain)}' -o /dev/null -w '%{{http_code}}' "
              f"--max-time 6 http://127.0.0.1/", 10) or "?"


def mysql_e(query: str, timeout: int = 15, numeric: bool = True) -> str:
    """Query don gian (khong chua dau nháy kép/backtick) qua mysql -e (chi stdout)."""
    flag = "-N " if numeric else ""
    return sh(f'mysql {flag}--socket={C.MYSQL_SOCK} -e "{query}"', timeout)


def _mysql_file(sql: str, timeout: int = 25) -> str:
    """Chay SQL phuc tap (co backtick) qua file tam de tranh quoting."""
    fd, path = tempfile.mkstemp(suffix=".sql", dir="/tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(sql)
        return sh(f"mysql --socket={C.MYSQL_SOCK} < {path}", timeout, merge=True)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def list_dbs() -> list[str]:
    out = mysql_e("show databases;")
    return [x for x in out.splitlines() if x.strip() and x.strip() not in _SKIP_DB]


def db_exists(name: str) -> bool:
    return mysql_e(f"show databases like '{name}';").strip() == name


def create_db(name: str) -> tuple[bool, str, dict | None]:
    db = re.sub(r"[^a-zA-Z0-9_]", "", name)
    if not db:
        return False, "Tên database không hợp lệ (chỉ chữ/số/gạch dưới).", None
    if db_exists(db):
        return False, f"Database <b>{db}</b> đã tồn tại.", None
    pw = genpw()
    _mysql_file(
        f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        f"CREATE USER IF NOT EXISTS '{db}'@'localhost' IDENTIFIED BY '{pw}';"
        f"GRANT ALL ON `{db}`.* TO '{db}'@'localhost';FLUSH PRIVILEGES;"
    )
    if db_exists(db):
        return True, "", {"db": db, "user": db, "pass": pw, "host": "localhost"}
    return False, "Lỗi tạo database.", None


def delete_db(name: str) -> bool:
    _mysql_file(f"DROP DATABASE IF EXISTS `{name}`;DROP USER IF EXISTS '{name}'@'localhost';FLUSH PRIVILEGES;")
    return not db_exists(name)


# --------------------------------------------------------------------------- #
# Chay controller hostvn voi day du moi truong (nhu menu chinh)
# --------------------------------------------------------------------------- #
def run_ctl(seq: str, controller: str, timeout: int = 180) -> str:
    script = (
        'source /var/hostvn/.hostvn.conf 2>/dev/null;'
        'source /var/hostvn/menu/route/parent 2>/dev/null;'
        'source /var/hostvn/menu/helpers/variable_common 2>/dev/null;'
        'source /var/hostvn/ipaddress 2>/dev/null;'
        'source /var/hostvn/menu/lang/"${lang:-vi}" 2>/dev/null;'
        'for _m in $(compgen -A function 2>/dev/null | grep -E "^menu_"); do eval "${_m}(){ :; }"; done;'
        f'source {shlex.quote(controller)}'
    )
    try:
        p = subprocess.run(["bash", "-c", script], input=seq + "\n",
                           capture_output=True, text=True, timeout=timeout, env=_env())
        return p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return "⏱️ Quá thời gian tạo."


def read_user_conf(domain: str) -> dict[str, str]:
    conf = Path(C.USERS_DIR) / f".{domain}.conf"
    data: dict[str, str] = {}
    if conf.exists():
        for line in conf.read_text(errors="replace").splitlines():
            if "=" in line and not line.startswith("["):
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data


def _domain_user(domain: str) -> str:
    u = read_user_conf(domain).get("username", "")
    if u:
        return u
    out = sh(f"find /home -maxdepth 2 -type d -name {shlex.quote(domain)} 2>/dev/null | head -1", 10)
    parts = out.strip().split("/")
    return parts[2] if len(parts) > 2 else ""


def _php_choice_answer() -> str:
    """Cau tra loi cho buoc chon phien ban PHP cua add_domain — hoac chuoi rong.

    add_domain CHI hoi phien ban PHP khi may cai 2 ban PHP (php2_release=yes).
    Neu cu nhoi san mot dong tra loi ma may khong hoi (hoac nguoc lai), toan bo
    cac cau tra loi sau se lech mot nhip: site tao ra thieu database va thieu
    ma nguon. Vi vay phai do cau hinh THUC TE cua may.
    """
    return "1\n" if conf_val("php2_release") == "yes" else ""


def create_domain(typ: str, domain: str) -> tuple[bool, dict, str]:
    """typ = 'def' (PHP) hoac 'wp' (WordPress). Tra (ok, info_dict, raw_output)."""
    d = domain.strip().lower()
    if d.startswith("www."):
        d = d[4:]
    if (Path(C.VHOST_DIR) / f"{d}.conf").exists():
        return False, {}, "Domain đã tồn tại."
    if typ == "wp":
        wpuser = "hvadmin" + "".join(secrets.choice("0123456789") for _ in range(4))
        wpmail = ""
        fi = Path(C.FILE_INFO)
        if fi.exists():
            m = re.search(r"^admin_email=(.*)$", fi.read_text(errors="replace"), re.M)
            wpmail = m.group(1).strip() if m else ""
        wpmail = wpmail or f"admin@{d}"
        seq = f"{d}\n{_php_choice_answer()}1\ny\ny\ny\n1\nn\n{wpuser}\n{wpmail}\n{d}"
    else:
        seq = f"{d}\n{_php_choice_answer()}20\nn"
    out = run_ctl(seq, "/var/hostvn/menu/controller/domain/add_domain", 200)
    if not (Path(C.VHOST_DIR) / f"{d}.conf").exists():
        tail = "\n".join(out.strip().splitlines()[-4:])
        return False, {}, tail
    uc = read_user_conf(d)
    info = {
        "domain": d,
        "docroot": docroot(d),
        "sftp_user": uc.get("username", ""),
        "sftp_pass": uc.get("user_pass", ""),
        "db_name": uc.get("db_name", ""),
        "db_user": uc.get("db_user", ""),
        "db_pass": uc.get("db_password", ""),
    }
    dr = info["docroot"]
    if dr and (Path(dr) / "wp-admin").is_dir():
        mu = re.search(r"User dang nhap wp-admin\s*:\s*(.+)", out)
        mp = re.search(r"khau dang nhap wp-admin\s*:\s*(.+)", out)
        info["wp_user"] = (mu.group(1).strip() if mu else "")
        info["wp_pass"] = (mp.group(1).strip() if mp else "")

    # vHost ton tai KHONG co nghia la xong. Neu chon WordPress ma thieu database
    # hoac thieu ma nguon thi phai noi ro, dung bao "da tao" cho mot site hong.
    if typ == "wp":
        thieu = []
        if not info["db_name"]:
            thieu.append("database")
        if not (dr and (Path(dr) / "wp-admin").is_dir()):
            thieu.append("mã nguồn WordPress")
        if thieu:
            info["incomplete"] = (
                "Đã tạo vHost, user và thư mục, nhưng THIẾU: " + ", ".join(thieu) + "."
            )
    return True, info, ""


def delete_domain(domain: str) -> bool:
    d = domain.strip().lower()
    if not (Path(C.VHOST_DIR) / f"{d}.conf").exists():
        return False
    info = read_user_conf(d)
    user = _domain_user(d)
    dbn, dbu = info.get("db_name", ""), info.get("db_user", "")
    qd = shlex.quote(d)
    # An toan: chi userdel/rm /home khi user KHONG rong.
    script = (
        f"rm -f /etc/nginx/conf.d/{qd}.conf;"
        f"rm -rf /etc/nginx/php/{qd};"
        f"find /etc/php -name {qd}.conf -delete 2>/dev/null;"
        f"rm -f {shlex.quote(str(Path(C.USERS_DIR) / ('.' + d + '.conf')))};"
    )
    if user:
        qu = shlex.quote(user)
        script += f"userdel -f -r {qu} 2>/dev/null; rm -rf /home/{qu};"
    script += "nginx -t >/dev/null 2>&1 && _svc reload nginx >/dev/null 2>&1"
    sh(script, 60, source_env=True, merge=True)
    if dbn:
        _mysql_file(f"DROP DATABASE IF EXISTS `{dbn}`;DROP USER IF EXISTS '{dbu}'@'localhost';FLUSH PRIVILEGES;")
    # Che do tunnel: phai xoa CNAME nua. Ham nay chay lenh shell thô chu khong goi
    # controller delete_domain, nen khong tu dong huong buoc xoa DNS cua no ->
    # khong lam o day thi ban ghi mo coi van tro vao tunnel.
    if is_tunnel_mode():
        sh(f"bash /var/hostvn/menu/tunnel/cf_tunnel.sh del-dns {qd}", 45, merge=True)
    return not (Path(C.VHOST_DIR) / f"{d}.conf").exists()


# --------------------------------------------------------------------------- #
# Cac khoi thong tin (read-only)
# --------------------------------------------------------------------------- #
def status() -> dict[str, str]:
    pv = php_version()
    keys = {
        "nginx": "nginx", "mariadb": "mariadb", f"php{pv}-fpm": f"php{pv}-fpm",
        "redis": "redis", "memcached": "memcached", "fail2ban": "fail2ban",
        "cloudflared": "cloudflared",
    }
    st = {name: svc_status(svcname) for name, svcname in keys.items()}
    st["disk"] = sh("df -h / | awk 'NR==2{print $3\" / \"$2\" (\"$5\")\"}'", 10)
    st["ram"] = sh("free -h | awk '/Mem:/{print $3\" / \"$2}'", 10)
    st["load"] = sh("cut -d' ' -f1-3 /proc/loadavg", 5)
    st["uptime"] = sh("uptime -p 2>/dev/null | sed 's/up //'", 5)
    st["php_ver"] = pv
    return st


def ssl_expiry() -> str:
    lines = []
    for d in list_domains():
        e = sh(f"echo | timeout 8 openssl s_client -connect {shlex.quote(d)}:443 "
               f"-servername {shlex.quote(d)} 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null "
               f"| cut -d= -f2", 12)
        lines.append(f"{C.E['ssl']} {d}: {e or '?'}")
    return "\n".join(lines) or "(chưa có domain)"


def fail2ban_stats() -> str:
    base = sh("fail2ban-client status 2>/dev/null | tr -d '\t'", 15)
    jails = sh("fail2ban-client status 2>/dev/null | grep 'Jail list' | sed 's/.*://'", 10)
    det = []
    for j in (x.strip() for x in jails.split(",") if x.strip()):
        d = sh(f"fail2ban-client status {shlex.quote(j)} 2>/dev/null | grep -E "
               f"'Currently banned|Total banned' | tr -d '\t'", 10)
        if d:
            det.append(f"[{j}]\n{d}")
    return (base + "\n" + "\n".join(det)).strip() or "(fail2ban chưa chạy)"


def php_info() -> str:
    pv = php_version()
    return sh(f"php{pv} -i 2>/dev/null | grep -iE "
              f"'^memory_limit|^upload_max|^post_max|^max_execution' | head -6", 15) or "(không đọc được)"


def vps_info() -> str:
    return sh("printf 'Host: %s\\nKernel: %s (%s)\\nCPU: %s core\\nUptime: %s\\n' "
              "\"$(hostname)\" \"$(uname -r)\" \"$(uname -m)\" \"$(nproc)\" \"$(uptime -p|sed 's/up //')\"; "
              "df -h / | awk 'NR==2{print \"Disk: \"$3\"/\"$2\" (\"$5\")\"}'; "
              "free -h | awk '/Mem/{print \"RAM: \"$3\"/\"$2}'", 15)


def vps_disk() -> str:
    return sh("du -sh /home/* 2>/dev/null | sort -rh | head -10", 20) or "(trống)"


def largefiles() -> str:
    return sh("find /home -type f -printf '%s %p\\n' 2>/dev/null | sort -rn | head -8 "
              "| awk '{printf \"%.0fMB %s\\n\",$1/1048576,$2}'", 20) or "(trống)"


def admin_links() -> str:
    port = sh(f"grep -m1 '^admin_port=' {C.FILE_INFO} 2>/dev/null | cut -d= -f2", 8)
    ip = sh("hostname -I 2>/dev/null | awk '{print $1}'", 8) or "127.0.0.1"
    return (f"phpMyAdmin: http://{ip}:{port}/phpmyadmin\n"
            f"OPcache   : http://{ip}:{port}/opcache\n"
            f"Nginx st  : http://{ip}:{port}/status")


def clear_fastcgi() -> str:
    sh("rm -rf /var/cache/nginx/* 2>/dev/null; _svc reload nginx 2>/dev/null; echo ok", 20, source_env=True)
    return "Đã xoá FastCGI cache + reload nginx."


def clear_opcache() -> str:
    pv = php_version()
    svc("restart", f"php{pv}-fpm")
    return "Đã clear OPcache (restart php-fpm)."


def restart_stack() -> str:
    pv = php_version()
    for s in ("mariadb", f"php{pv}-fpm", "nginx"):
        svc("restart", s)
    return "Đã restart MariaDB → PHP-FPM → Nginx."


def reboot() -> None:
    subprocess.Popen(["bash", "-c", "sleep 2; reboot"], env=_env())


# --------------------------------------------------------------------------- #
# Quan ly domain nang cao - drive controller hostvn bang canned input.
# _select_domain liet ke tu glob ".*.conf" trong /var/hostvn/users -> domain_index()
# chay DUNG doan glob do de lay so thu tu, khong doan mo.
# --------------------------------------------------------------------------- #
CTL = "/var/hostvn/menu/controller/domain"


def _glob_domains() -> list[str]:
    """Danh sach domain THEO DUNG thu tu glob '.*.conf' ma cac _select_* cua shell dung."""
    out = sh('cd /var/hostvn/users 2>/dev/null && for f in .*.conf; do '
             'd=${f#.}; d=${d%.conf}; [ "$d" != "*" ] && printf "%s\\n" "$d"; done', 15)
    return [x.strip() for x in out.splitlines() if x.strip()]


def domain_index(domain: str) -> int:
    """So thu tu (1-based) cua domain trong menu _select_domain. 0 = khong thay."""
    doms = _glob_domains()
    return doms.index(domain) + 1 if domain in doms else 0


def _need_index(domain: str) -> tuple[int, str]:
    idx = domain_index(domain)
    return idx, ("" if idx else "Không tìm thấy domain trong danh sách hostvn.")


def _has_quic(domain: str) -> bool:
    conf = Path(C.VHOST_DIR) / f"{domain}.conf"
    return "quic" in conf.read_text(errors="replace").lower() if conf.exists() else False


def _ctl_reason(out: str, fallback: str) -> str:
    """Lay dong thong bao co nghia cuoi cung tu output controller."""
    skip = ("Nhap vao lua chon", "1)", "2)", "3)", "Danh sach")
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    for l in reversed(lines):
        if not any(l.startswith(s) for s in skip) and len(l) > 12:
            return l[:220]
    return fallback


def dom_http3(domain: str, enable: bool) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    before = _has_quic(domain)
    if before == enable:
        # KHONG bao thanh cong gia: noi ro la von da o trang thai nay
        return True, (f"HTTP/3 vốn đã <b>{'bật' if enable else 'tắt'}</b> sẵn cho {domain} "
                      f"— không có gì thay đổi.")
    out = run_ctl(f"{1 if enable else 2}\n{idx}", f"{CTL}/http3", 120)
    if _has_quic(domain) == enable:
        svc("reload", "nginx")
        return True, f"Đã {'bật' if enable else 'tắt'} HTTP/3 cho {domain}."
    reason = _ctl_reason(out, "Không đổi được HTTP/3.")
    if "ssl" in reason.lower():
        reason += "\n\n<i>HTTP/3 yêu cầu SSL cấu hình trực tiếp trên nginx. Site chạy qua Cloudflare Tunnel thường không có SSL local nên không bật được.</i>"
    return False, reason


def dom_change_sftp_pass(domain: str, newpass: str = "") -> tuple[bool, str, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err, ""
    pw = newpass or genpw(14)
    if len(pw) < 8:
        return False, "Mật khẩu phải từ 8 ký tự.", ""
    out = run_ctl(f"{idx}\n{pw}", f"{CTL}/change_pass_sftp", 120)
    low = out.lower()
    if "thanh cong" in low or "success" in low:
        return True, f"Đã đổi mật khẩu SFTP cho {domain}.", pw
    return False, (out.strip().splitlines() or ["Không đổi được mật khẩu."])[-1][:200], ""


def dom_rewrite_config(domain: str, source_idx: int) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    out = run_ctl(f"{idx}\n{source_idx}", f"{CTL}/rewrite_config", 180)
    ok = sh("nginx -t 2>&1 | tail -1", 30)
    if "successful" in ok:
        svc("reload", "nginx")
        return True, f"Đã tạo lại vHost cho {domain}. nginx: OK."
    return False, f"nginx test lỗi: {ok[:180]}"


def dom_change_php(domain: str, choice: int) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    out = run_ctl(f"{idx}\n{choice}", f"{CTL}/change_php_version", 180)
    return True, (out.strip().splitlines() or ["Đã gửi yêu cầu đổi phiên bản PHP."])[-1][:200]


def dom_rename(domain: str, new_domain: str) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    nd = new_domain.strip().lower()
    if nd.startswith("www."):
        nd = nd[4:]
    if not DOMAIN_RE.match(nd):
        return False, "Tên miền mới không hợp lệ."
    if (Path(C.VHOST_DIR) / f"{nd}.conf").exists():
        return False, f"Domain {nd} đã tồn tại."
    run_ctl(f"{idx}\n{nd}", f"{CTL}/change_domain", 180)
    if (Path(C.VHOST_DIR) / f"{nd}.conf").exists():
        return True, f"Đã đổi {domain} → {nd}."
    return False, "Đổi tên miền không thành công."


def dom_alias_add(domain: str, alias: str, source_idx: int = 20) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    al = alias.strip().lower()
    if al.startswith("www."):
        al = al[4:]
    if not DOMAIN_RE.match(al):
        return False, "Domain alias không hợp lệ."
    out = run_ctl(f"1\n{idx}\n{al}\n{source_idx}", f"{CTL}/alias_domain", 180)
    conf = Path(C.VHOST_DIR) / f"{domain}.conf"
    txt = conf.read_text(errors="replace") if conf.exists() else ""
    if al in txt or (Path("/etc/nginx/alias") / f"{al}.conf").exists():
        svc("reload", "nginx")
        return True, f"Đã thêm alias {al} → {domain}."
    return False, _ctl_reason(out, "Không thêm được alias.")


def dom_redirect_add(domain: str, target: str) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    rd = target.strip().lower()
    if rd.startswith("www."):
        rd = rd[4:]
    if not DOMAIN_RE.match(rd):
        return False, "Domain redirect không hợp lệ."
    out = run_ctl(f"1\n{idx}\n{rd}", f"{CTL}/redirect_domain", 180)
    if (Path("/etc/nginx/redirect") / f"{rd}.conf").exists():
        svc("reload", "nginx")
        return True, f"Đã thêm redirect {rd} → {domain}."
    return False, _ctl_reason(out, "Không thêm được redirect.")


def dom_protect_dir(domain: str, path: str, user: str, password: str) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    if not user or len(password) < 6:
        return False, "Cần user và mật khẩu tối thiểu 6 ký tự."
    run_ctl(f"{idx}\n1\n{p}\n{user}\n{password}", f"{CTL}/protect_dir", 180)
    ok = sh("nginx -t 2>&1 | tail -1", 30)
    if "successful" in ok:
        svc("reload", "nginx")
        return True, f"Đã bảo vệ thư mục {p} của {domain} (user: {user})."
    return False, f"nginx test lỗi: {ok[:180]}"


# --------------------------------------------------------------------------- #
# Quan ly SSL (mirror menu "2. Quan ly SSL")
# _select_ssl_le_website dung CUNG glob voi _select_domain -> domain_index() dung chung.
# --------------------------------------------------------------------------- #
SSLCTL = "/var/hostvn/menu/controller/ssl"
SSL_DIR = "/etc/nginx/ssl"
CF_API_CONF = "/var/hostvn/.cf_api.conf"


def ssl_has_cert(domain: str) -> bool:
    d = Path(SSL_DIR) / domain
    cert, key = d / "cert.pem", d / "key.pem"
    return cert.exists() and key.exists() and cert.stat().st_size > 0


def is_tunnel_mode() -> bool:
    return "tunnel" in conf_val("network_mode")


def _cert_fields(cmd: str) -> dict:
    out = sh(cmd, 15)
    g = lambda k: (re.search(rf"^{k}=(.*)$", out, re.M).group(1).strip()
                   if re.search(rf"^{k}=(.*)$", out, re.M) else "")
    return {"issuer": g("issuer"), "subject": g("subject"), "expire": g("notAfter")}


def ssl_local_info(domain: str) -> dict:
    """Chung chi THUC SU tren server nay (khong ra Internet).

    kind: letsencrypt = co cert rieng cho domain;
          self-signed = dung cert chung hostvn tu ky luc cai;
          none        = vhost khong khai bao SSL.
    """
    cert = Path(SSL_DIR) / domain / "cert.pem"
    if cert.exists() and cert.stat().st_size > 0:
        info = _cert_fields(f"openssl x509 -noout -issuer -enddate -in {shlex.quote(str(cert))} 2>/dev/null")
        info["kind"] = "letsencrypt"
        return info
    # Doc THANG duong dan tu chi thi ssl_certificate trong vhost (khong doan ten file)
    vhost = Path(C.VHOST_DIR) / f"{domain}.conf"
    if vhost.exists():
        m = re.search(r"^\s*ssl_certificate\s+([^;]+);", vhost.read_text(errors="replace"), re.M)
        if m:
            p = Path(m.group(1).strip())
            if p.exists() and p.stat().st_size > 0:
                info = _cert_fields(
                    f"openssl x509 -noout -issuer -enddate -in {shlex.quote(str(p))} 2>/dev/null")
                iss = info["issuer"].lower()
                info["kind"] = "letsencrypt" if ("let's encrypt" in iss or "r3" in iss
                                                 or "e5" in iss or "e6" in iss) else "self-signed"
                info["path"] = str(p)
                return info
    return {"kind": "none", "issuer": "", "subject": "", "expire": ""}


def ssl_edge_info(domain: str) -> dict:
    """Chung chi NGUOI DUNG THAY khi truy cap domain (co the la cua Cloudflare)."""
    info = _cert_fields(
        f"echo | timeout 10 openssl s_client -connect {shlex.quote(domain)}:443 "
        f"-servername {shlex.quote(domain)} 2>/dev/null | openssl x509 -noout -issuer -subject -enddate 2>/dev/null")
    iss = info["issuer"].lower()
    info["is_cloudflare"] = ("cloudflare" in iss or "google trust" in iss)
    return info


def ssl_list() -> list[dict]:
    """Trang thai chung chi tren SERVER (doc file, khong can mang)."""
    rows = []
    for d in list_domains():
        info = ssl_local_info(d)
        rows.append({"domain": d, "kind": info["kind"], "has_cert": info["kind"] == "letsencrypt",
                     "expire": info["expire"], "issuer": info["issuer"]})
    return rows


def ssl_report() -> str:
    """Bao cao trung thuc: cert TREN SERVER vs cert NGUOI DUNG THAY (bien Cloudflare)."""
    lines = []
    for d in list_domains():
        loc, edge = ssl_local_info(d), ssl_edge_info(d)
        lines.append(f"● {d}")
        kind = {"letsencrypt": "Let's Encrypt (riêng)", "self-signed": "tự ký của hostvn",
                "none": "không có"}[loc["kind"]]
        lines.append(f"   Trên server : {kind}"
                     + (f" · hết hạn {loc['expire']}" if loc["expire"] else ""))
        if edge["expire"]:
            who = "Cloudflare (biên)" if edge.get("is_cloudflare") else "chính server này"
            lines.append(f"   Người dùng thấy: {who} · hết hạn {edge['expire']}")
        else:
            lines.append("   Người dùng thấy: không kết nối được :443")
    return "\n".join(lines) or "(chưa có domain)"


def cf_api_status() -> str:
    p = Path(CF_API_CONF)
    if not p.exists():
        return "Chưa cấu hình CloudFlare DNS API."
    txt = p.read_text(errors="replace")
    email = re.search(r"^CF_Email=(.*)$", txt, re.M)
    tok = re.search(r"^CF_Token=(.*)$", txt, re.M)
    masked = "(có)" if tok and tok.group(1).strip() else "(trống)"
    return f"Đã cấu hình.\nEmail: {email.group(1).strip() if email else '?'}\nToken: {masked}"


def ssl_cf_api_set(token: str, email: str) -> tuple[bool, str]:
    if not token or len(token) < 20:
        return False, "Token không hợp lệ."
    if "@" not in email:
        return False, "Email không hợp lệ."
    out = run_ctl(f"1\n{token}\n{email}", f"{SSLCTL}/cf_api", 90)
    if Path(CF_API_CONF).exists():
        return True, "Đã lưu CloudFlare DNS API."
    return False, _ctl_reason(out, "Không lưu được CF API.")


def ssl_renew_all() -> tuple[bool, str]:
    out = run_ctl("1", f"{SSLCTL}/renew_all_ssl", 600)
    return True, _ctl_reason(out, "Đã chạy gia hạn toàn bộ SSL.")


def ssl_remove(domain: str, source_idx: int = 20) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    out = run_ctl(f"{idx}\n{source_idx}", f"{SSLCTL}/remove_le", 180)
    if not ssl_has_cert(domain):
        svc("reload", "nginx")
        return True, f"Đã gỡ SSL Let's Encrypt của {domain}."
    return False, _ctl_reason(out, "Không gỡ được SSL.")


def ssl_create(domain: str) -> tuple[bool, str]:
    """Dang ky/gia han Let's Encrypt (HTTP-01) cho 1 domain."""
    idx, err = _need_index(domain)
    if err:
        return False, err
    out = run_ctl(f"1\n{idx}\ny\n1", f"{SSLCTL}/create_le_ssl", 400)
    if ssl_has_cert(domain):
        svc("reload", "nginx")
        return True, f"Đã cấp SSL cho {domain}."
    return False, _ctl_reason(out, "Không cấp được SSL.")


def ssl_wildcard(domain: str) -> tuple[bool, str]:
    if not Path(CF_API_CONF).exists():
        return False, "Chưa cấu hình CloudFlare DNS API — vào mục CloudFlare DNS API trước."
    idx, err = _need_index(domain)
    if err:
        return False, err
    out = run_ctl(f"{idx}\n1", f"{SSLCTL}/wildcard", 600)
    if ssl_has_cert(domain):
        svc("reload", "nginx")
        return True, f"Đã cấp wildcard SSL cho *.{domain}."
    return False, _ctl_reason(out, "Không cấp được wildcard SSL.")


# --------------------------------------------------------------------------- #
# Quan ly Cache (mirror menu "3. Quan ly Cache")
# --------------------------------------------------------------------------- #
CACHECTL = "/var/hostvn/menu/controller/cache"


def fastcgi_enabled(domain: str) -> bool:
    """Giong check cua nginx_cache: vhost co include php_cache.conf / php_cache_woo.conf."""
    conf = Path(C.VHOST_DIR) / f"{domain}.conf"
    if not conf.exists():
        return False
    txt = conf.read_text(errors="replace")
    return "php_cache.conf" in txt or "php_cache_woo.conf" in txt


def fastcgi_domains(enabled: bool) -> list[str]:
    """Danh sach domain theo dung thu tu + bo loc ma controller dung."""
    return [d for d in _glob_domains() if fastcgi_enabled(d) == enabled]


def cache_fastcgi_set(domain: str, enable: bool) -> tuple[bool, str]:
    """Bat/Tat Nginx FastCGI cache cho 1 domain (index tinh trong danh sach DA LOC)."""
    lst = fastcgi_domains(not enable)      # bat -> chon trong nhung cai DANG TAT
    if domain not in lst:
        return False, (f"{domain} đã bật FastCGI cache sẵn." if enable
                       else f"{domain} chưa bật FastCGI cache.")
    idx = lst.index(domain) + 1
    out = run_ctl(f"{1 if enable else 2}\n{idx}", f"{CACHECTL}/nginx_cache", 180)
    if fastcgi_enabled(domain) == enable:
        svc("reload", "nginx")
        return True, f"Đã {'bật' if enable else 'tắt'} FastCGI cache cho {domain}."
    return False, _ctl_reason(out, "Không đổi được FastCGI cache.")


def cache_status() -> str:
    pv = php_version()
    st = services_status(["redis", "memcached"])
    opc = sh(f"php{pv} -i 2>/dev/null | grep -iE '^opcache.enable\\b' | head -1", 15)
    ini = sh(f"ls /etc/php/{pv}/fpm/conf.d/ 2>/dev/null | grep -iE 'opcache|redis|memcach' | tr '\\n' ' '", 10)
    on = [d for d in _glob_domains() if fastcgi_enabled(d)]
    off = [d for d in _glob_domains() if not fastcgi_enabled(d)]
    return (f"Redis     : {st.get('redis', '?')}\n"
            f"Memcached : {st.get('memcached', '?')}\n"
            f"OPcache   : {opc or '(không đọc được)'}\n"
            f"PHP ext   : {ini or '(không có)'}\n"
            f"FastCGI bật : {', '.join(on) or '(không có)'}\n"
            f"FastCGI tắt : {', '.join(off) or '(không có)'}")


def cache_clear_all() -> str:
    """Chay controller clear_cache: restart redis/memcached + xoa cache tung website."""
    out = run_ctl("", f"{CACHECTL}/clear_cache", 300)
    return _ctl_reason(out, "Đã xoá cache toàn hệ thống.")


def pkg_service(name: str, install: bool) -> tuple[bool, str]:
    """Cai dat / go bo redis-server hoac memcached (kem extension PHP khi cai redis)."""
    pv = php_version()
    if name == "redis":
        pkgs = f"redis-server php{pv}-redis php{pv}-igbinary"
        probe = "redis-server"
    else:
        pkgs = f"memcached php{pv}-memcached"
        probe = "memcached"
    if install:
        sh(f"DEBIAN_FRONTEND=noninteractive apt-get install -y {pkgs}", 900, merge=True)
        ok = bool(sh(f"command -v {probe}", 10))
        if ok:
            svc("restart", f"php{pv}-fpm")
        return ok, ("Đã cài đặt." if ok else "Cài đặt thất bại.")
    sh(f"DEBIAN_FRONTEND=noninteractive apt-get purge -y {pkgs}", 900, merge=True)
    ok = not sh(f"command -v {probe}", 10)
    return ok, ("Đã gỡ bỏ." if ok else "Gỡ bỏ chưa hoàn tất.")


# --------------------------------------------------------------------------- #
# Firewall (mirror menu "5. Quan ly Firewall")
# fw_backend() do thuc te chu khong gia dinh: may x86 binh thuong co iptables/ufw,
# nhung container LXC/Docker thieu NET_ADMIN thi khong -> khi do fail2ban chi PHAT
# HIEN, phai chan that o Cloudflare WAF.
# --------------------------------------------------------------------------- #
FWCTL = "/var/hostvn/menu/controller/firewall"
CF_WAF_CONF = "/var/hostvn/.cf_waf.conf"


def fw_backend() -> dict:
    """Xac dinh moi truong firewall thuc te."""
    have = {c: bool(sh(f"command -v {c}", 8)) for c in ("iptables", "ufw", "nft")}
    noop = Path("/etc/fail2ban/action.d/hostvn-noop.conf").exists()
    ban = sh("grep -m1 '^banaction' /etc/fail2ban/jail.local 2>/dev/null | cut -d= -f2", 10).strip()
    return {
        "iptables": have["iptables"], "ufw": have["ufw"], "nft": have["nft"],
        "noop": noop, "banaction": ban or "?",
        "cf_waf": Path(CF_WAF_CONF).exists(),
        "tunnel": is_tunnel_mode(),
    }


def f2b_jails() -> list[str]:
    out = sh("fail2ban-client status 2>/dev/null | grep 'Jail list' | sed 's/.*://'", 15)
    return [x.strip() for x in out.split(",") if x.strip()]


def f2b_banned() -> str:
    """Danh sach IP dang bi ban theo tung jail."""
    rows = []
    for j in f2b_jails():
        ips = sh(f"fail2ban-client status {shlex.quote(j)} 2>/dev/null | "
                 f"grep -A1 'Banned IP list' | tail -1 | sed 's/.*://'", 15).strip()
        cnt = sh(f"fail2ban-client status {shlex.quote(j)} 2>/dev/null | "
                 f"grep 'Currently banned' | grep -oE '[0-9]+$'", 10).strip()
        rows.append(f"{j}: {cnt or '0'} IP" + (f"\n   {ips}" if ips else ""))
    return "\n".join(rows) or "(fail2ban chưa chạy)"


def f2b_unban(ip: str) -> tuple[bool, str]:
    if not re.match(r"^[0-9a-fA-F:.]+$", ip or ""):
        return False, "IP không hợp lệ."
    out = sh(f"fail2ban-client unban {shlex.quote(ip)} 2>&1", 30, merge=True)
    return True, (out.strip()[:200] or f"Đã gỡ ban {ip}.")


def f2b_ban(ip: str, jail: str = "sshd") -> tuple[bool, str]:
    if not re.match(r"^[0-9a-fA-F:.]+$", ip or ""):
        return False, "IP không hợp lệ."
    out = sh(f"fail2ban-client set {shlex.quote(jail)} banip {shlex.quote(ip)} 2>&1", 30, merge=True)
    return True, (out.strip()[:200] or f"Đã ban {ip} trong jail {jail}.")


def f2b_extra_jails() -> str:
    out = run_ctl("", f"{FWCTL}/f2b_extra_jails", 180)
    return _ctl_reason(out, "Đã chạy bật thêm jail.")


def cf_waf_status() -> str:
    p = Path(CF_WAF_CONF)
    if not p.exists():
        return "Chưa cấu hình đồng bộ Cloudflare WAF."
    zone = conf_val("CF_WAF_ZONE", CF_WAF_CONF)      # conf_val da bo nhay bao quanh
    tok = conf_val("CF_WAF_TOKEN", CF_WAF_CONF)
    cron = sh("crontab -l 2>/dev/null | grep -c cf_waf", 10).strip()
    return (f"Đã cấu hình.\n"
            f"Zone ID : {(zone[:12] + '…') if zone else '(trống)'}\n"
            f"Token   : {'(có)' if tok else '(trống)'}\n"
            f"Cron đồng bộ: {cron or '0'} mục")


PERMCTL = "/var/hostvn/menu/controller/permission"


def perm_check(domain: str) -> str:
    """Doc quyen/chu so huu hien tai (chi xem, khong doi gi)."""
    uc = read_user_conf(domain)
    user = uc.get("username", "")
    if not user:
        return "Không tìm thấy user của domain."
    home = f"/home/{user}/{domain}"
    out = sh(f"stat -c '%A %U:%G  %n' /home/{shlex.quote(user)} {shlex.quote(home)} "
             f"{shlex.quote(home)}/public_html 2>/dev/null", 20)
    odd_d = sh(f"find {shlex.quote(home)}/public_html -type d ! -perm 755 2>/dev/null | wc -l", 30)
    odd_f = sh(f"find {shlex.quote(home)}/public_html -type f ! -perm 644 2>/dev/null | wc -l", 30)
    wrong = sh(f"find {shlex.quote(home)} ! -user {shlex.quote(user)} 2>/dev/null | wc -l", 30)
    return (f"{out}\n\nThư mục khác 755 : {odd_d}\n"
            f"File khác 644     : {odd_f}\n"
            f"Sai chủ sở hữu    : {wrong}")


def perm_apply_one(domain: str) -> tuple[bool, str]:
    idx, err = _need_index(domain)
    if err:
        return False, err
    out = run_ctl(f"{idx}\ny", f"{PERMCTL}/one", 600)
    return True, _ctl_reason(out, f"Đã phân quyền lại cho {domain}.")


def perm_apply_all() -> tuple[bool, str]:
    out = run_ctl("", f"{PERMCTL}/all", 900)
    return True, _ctl_reason(out, "Đã phân quyền lại toàn bộ website.")


WPCTL = "/var/hostvn/menu/controller/wordpress"


def wp_domains() -> list[str]:
    """Giong _select_wordpress_website: domain co public_html/wp-content, theo thu tu glob."""
    out = []
    for d in _glob_domains():
        u = read_user_conf(d).get("username", "")
        if u and Path(f"/home/{u}/{d}/public_html/wp-content").is_dir():
            out.append(d)
    return out


def wp_index(domain: str) -> int:
    lst = wp_domains()
    return lst.index(domain) + 1 if domain in lst else 0


def wp_info(domain: str) -> str:
    """Thong tin WordPress cua 1 site (doc bang wp-cli)."""
    dr = docroot(domain)
    if not dr or not Path(dr, "wp-includes").is_dir():
        return "Site này không dùng WordPress."
    def wp(cmd, t=40):
        return sh(f"cd {shlex.quote(dr)} && wp {cmd} --allow-root 2>/dev/null", t).strip()
    ver = wp("core version")
    upd = wp("core check-update --field=version --format=csv") or "(đã mới nhất)"
    plug = wp("plugin list --status=active --format=count") or "?"
    pupd = wp("plugin list --update=available --format=count") or "0"
    theme = wp("theme list --status=active --field=name --format=csv")
    return (f"WordPress : {ver}\n"
            f"Bản mới   : {upd}\n"
            f"Theme     : {theme or '?'}\n"
            f"Plugin bật: {plug}  ·  cần update: {pupd}")


def wp_run(ctl: str, seq: str, timeout: int = 300) -> str:
    """Chay 1 controller wordpress voi chuoi tra loi canned."""
    return _ctl_reason(run_ctl(seq, f"{WPCTL}/{ctl}", timeout), "Đã chạy xong.")


def acc_admin_info() -> str:
    port = conf_val("admin_port"); pwd = conf_val("admin_pwd")
    ip = sh("bash -c 'source /var/hostvn/ipaddress; echo $IPADDRESS'", 10)
    return (f"URL  : http://{ip}:{port}\nUser : admin\nPass : {pwd}")


def acc_pma_info() -> str:
    port = conf_val("admin_port"); pwd = conf_val("mysql_pwd")
    ip = sh("bash -c 'source /var/hostvn/ipaddress; echo $IPADDRESS'", 10)
    return (f"URL  : http://{ip}:{port}/phpmyadmin\nUser : admin\nPass : {pwd}")


def acc_ssh_info() -> str:
    p_ = conf_val("ssh_port") or "22"
    listen = sh("ss -ltn 2>/dev/null | awk '{print $4}' | grep -oE '[0-9]+$' | sort -un | tr '\n' ' '", 15)
    ip = sh("bash -c 'source /var/hostvn/ipaddress; echo $IPADDRESS'", 10)
    return f"SSH/SFTP host: {ip}\nSSH/SFTP port: {p_}\n\nCổng đang lắng nghe: {listen}"


def acc_site_info(domain: str) -> str:
    uc = read_user_conf(domain)
    if not uc:
        return "Không có thông tin cho website này."
    ip = sh("bash -c 'source /var/hostvn/ipaddress; echo $IPADDRESS'", 10)
    keys = [("username", "SFTP user"), ("user_pass", "SFTP pass"),
            ("db_name", "DB name"), ("db_user", "DB user"),
            ("db_password", "DB pass"), ("php_version", "PHP"),
            ("public_html", "Docroot")]
    lines = [f"{lbl:<10}: {uc.get(k, '-')}" for k, lbl in keys]
    return f"SFTP host : {ip}\nSFTP port : {conf_val('ssh_port') or '22'}\n" + "\n".join(lines)


def cron_list() -> str:
    out = sh("crontab -l 2>/dev/null", 15)
    files = sh("ls /etc/cron.d 2>/dev/null | tr '\n' ' '", 10)
    return (f"crontab -l:\n{out or '(trống)'}\n\n/etc/cron.d: {files or '(trống)'}")


def cron_delete_all() -> str:
    sh("crontab -r 2>/dev/null; echo done", 20, merge=True)
    return "Đã xoá toàn bộ crontab của root."


def script_versions() -> tuple[str, str]:
    """(ban dang cai, ban tren server phat hanh)."""
    cur = conf_val("script_version") or "?"
    link = sh("grep -m1 '^UPDATE_LINK=' /var/hostvn/menu/helpers/variable_common "
              "| cut -d'\"' -f2", 10)
    new = sh(f"curl -s --max-time 15 {link}/version | grep '^script_version=' | cut -d= -f2", 25)
    return cur, (new.strip() or "?")


def run_update_scripts() -> str:
    out = sh("cd /var/hostvn && curl -so update \"$(grep -m1 '^UPDATE_LINK=' "
             "menu/helpers/variable_common | cut -d'\"' -f2)/update\" && "
             "dos2unix update >/dev/null 2>&1; chmod +x update && bash update; rm -f update",
             900, merge=True)
    tail = "\n".join(out.strip().splitlines()[-5:])
    return tail or "Đã chạy update."


def set_language(code: str) -> tuple[bool, str]:
    if code not in ("vi", "en"):
        return False, "Mã ngôn ngữ không hợp lệ."
    sh(f"sed -i '/^lang=/d' {C.FILE_INFO}; echo 'lang={code}' >> {C.FILE_INFO}", 15)
    return conf_val("lang") == code, f"Đã chuyển ngôn ngữ menu shell sang {code}."


def php_versions() -> list[str]:
    out = sh("ls /etc/php 2>/dev/null", 10)
    return sorted(x for x in out.split() if x[:1].isdigit())


# --------------------------------------------------------------------------- #
# Backup / Restore  (giu DUNG format cua shell hostvn de restore cheo duoc:
#   /home/backup/<YYYY-MM-DD>/<domain>/<domain>.tar.gz  +  <db_name>.sql.gz )
# --------------------------------------------------------------------------- #
BACKUP_ROOT = "/home/backup"


def conf_val(key: str, path: str = C.FILE_INFO) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    m = re.search(rf"^{re.escape(key)}=(.*)$", p.read_text(errors="replace"), re.M)
    return m.group(1).strip().strip("\"'") if m else ""


def backup_site(domain: str, btype: str = "full", remote: str = "") -> tuple[bool, str, str]:
    """btype: full | source | db. remote rong = chi luu tren may.

    Tra (ok, thong_bao, thu_muc_dich).
    """
    uc = read_user_conf(domain)
    user, db = uc.get("username", ""), uc.get("db_name", "")
    if not user:
        return False, "Không tìm thấy user của domain.", ""
    date = time.strftime("%Y-%m-%d")
    dest = f"{BACKUP_ROOT}/{date}/{domain}"
    home = f"/home/{user}/{domain}"
    qd, qdest, qhome = shlex.quote(domain), shlex.quote(dest), shlex.quote(home)
    sh(f"mkdir -p {qdest}", 20)
    done: list[str] = []

    if btype in ("full", "source"):
        # Giong shell: tam copy wp-config vao public_html de nam trong tar, xong xoa ban copy
        script = f"""
cd {qhome} || exit 1
rm -f {qdest}/{qd}.tar.gz
MOVED=""
if [ -f wp-config.php ] && [ ! -f public_html/wp-config.php ]; then
    cp wp-config.php public_html/wp-config.php; MOVED=1
fi
if [ -d public_html/storage ]; then
    tar -cpzf {qdest}/{qd}.tar.gz \
        --exclude "public_html/storage/framework/cache" \
        --exclude "public_html/storage/framework/view" public_html
else
    tar -cpzf {qdest}/{qd}.tar.gz --exclude "public_html/wp-content/cache" public_html
fi
if [ -n "$MOVED" ] && [ -f public_html/wp-config.php ]; then rm -f public_html/wp-config.php; fi
"""
        sh(script, 900, merge=True)
        if Path(f"{dest}/{domain}.tar.gz").exists():
            done.append("mã nguồn")
        else:
            return False, "Nén mã nguồn thất bại.", dest

    if btype in ("full", "db"):
        if not db:
            if btype == "db":
                return False, "Domain này không có database.", dest
        else:
            pw = conf_val("mysql_pwd")
            sh(f"rm -f {qdest}/{shlex.quote(db)}.sql.gz; "
               f"mysqldump -uadmin -p{shlex.quote(pw)} {shlex.quote(db)} | gzip > {qdest}/{shlex.quote(db)}.sql.gz",
               900, merge=True)
            dump = Path(f"{dest}/{db}.sql.gz")
            if dump.exists() and dump.stat().st_size > 20:
                done.append("database")
            else:
                return False, "Dump database thất bại.", dest

    size = sh(f"du -sh {qdest} 2>/dev/null | cut -f1", 20)
    if not remote:
        return True, f"Đã backup {', '.join(done)} ({size}) — lưu trên máy.", dest

    ok, msg = _upload_backup(remote, date, domain, dest)
    if not ok:
        # Giu lai ban tren may de khong mat du lieu khi day len that bai
        return False, f"Đã backup {', '.join(done)} ({size}) nhưng {msg}", dest
    sh(f"rm -rf {qdest}", 60)
    return True, f"Đã backup {', '.join(done)} ({size}) và đẩy lên <b>{remote}</b>.", dest


def _upload_backup(remote: str, date: str, domain: str, dest: str) -> tuple[bool, str]:
    """Day thu muc backup len remote + ghi so muc luc (dung ham cua shell).

    Tai sao goi lai ham shell thay vi viet lai: so muc luc phai GIONG HET ban
    shell ghi, neu khong thi backup tu bot se khong hien khi restore tu shell
    va nguoc lai.
    """
    ip = sh("source /var/hostvn/ipaddress 2>/dev/null; echo $IPADDRESS", 10).strip()
    if not ip:
        ip = sh("hostname -I | awk '{print $1}'", 10).strip()
    qr, qip = shlex.quote(remote), shlex.quote(ip)
    qd, qdest = shlex.quote(domain), shlex.quote(dest)
    qdate = shlex.quote(date)

    # Day TUNG FILE bang copyto thay vi "rclone copy" ca thu muc: co gateway S3
    # khong ho tro liet ke theo prefix nen copy ca thu muc se ra rong.
    #
    # TUYET DOI KHONG xoa file cu roi ghi de. Do tren gateway that: lenh xoa
    # thanh cong nhung lenh ghi ngay sau do bi tu choi ("destination is a file")
    # -> mat luon ban backup cu ma khong co gi thay the. Neu dich da co file thi
    # ghi ca ban backup sang thu muc moi <ngay>_<gio>.
    files = sorted(p.name for p in Path(dest).iterdir() if p.is_file())
    if not files:
        return False, "không có file nào để đẩy lên."

    def _exists(folder: str, f: str) -> bool:
        qfolder = shlex.quote(folder)
        n = sh(f"rclone cat {qr}:{qip}/{qfolder}/{qd}/{shlex.quote(f)} 2>/dev/null "
               f"| head -c 1 | wc -c", 180)
        return n.strip() not in ("", "0")

    def _push(folder: str) -> tuple[int, str]:
        ok_n, err = 0, ""
        qfolder = shlex.quote(folder)
        for f in files:
            qf = shlex.quote(f)
            out = sh(f"rclone copyto {qdest}/{qf} {qr}:{qip}/{qfolder}/{qd}/{qf} "
                     f"--bwlimit 30M 2>&1; echo RC=$?", 1800, merge=True)
            if "RC=0" in out:
                ok_n += 1
            else:
                err = "\n".join(out.strip().splitlines()[-2:])
        return ok_n, err

    fresh = f"{date}_{time.strftime('%H%M%S')}"
    # Dich da co du lieu -> ghi thang sang thu muc moi, khong dung ghi de.
    folder = fresh if any(_exists(date, f) for f in files) else date
    sent, last_err = _push(folder)
    if sent < len(files) and folder == date:
        # Van hong du dich trong: thu mot thu muc moi tinh (duong dan chua
        # tung dung thi gateway luon nhan).
        folder = fresh
        sent, last_err = _push(folder)
    if sent == 0:
        return False, f"đẩy lên {remote} thất bại: {last_err}"
    if sent < len(files):
        return False, f"chỉ đẩy được {sent}/{len(files)} file lên {remote}: {last_err}"
    qdate = shlex.quote(folder)

    # Xac minh bang cach DOC lai mot file theo duong dan chinh xac — khong dung
    # liet ke, vi co gateway S3 khong ho tro liet ke theo prefix.
    probe = files[0]
    n = sh(f"rclone cat {qr}:{qip}/{qdate}/{qd}/{shlex.quote(probe)} 2>/dev/null | head -c 64 | wc -c", 300)
    if n.strip() in ("", "0"):
        return False, f"đã đẩy lên {remote} nhưng đọc lại không thấy dữ liệu"

    sh(f"source /var/hostvn/menu/helpers/function 2>/dev/null; "
       f"backup_index_add {qr} {qdate} {qd} {qdest}", 300, merge=True)
    return True, ""


def backup_dates(domain: str = "") -> list[str]:
    """Danh sach ngay co backup (cho 1 domain neu truyen vao)."""
    root = Path(BACKUP_ROOT)
    if not root.is_dir():
        return []
    out = []
    for d in sorted((p.name for p in root.iterdir() if p.is_dir()), reverse=True):
        if not domain or (root / d / domain).is_dir():
            out.append(d)
    return out


def _index_path(remote: str) -> Path:
    return Path(f"/var/hostvn/.backup_index.{remote}")


def cloud_backups(domain: str = "") -> list[tuple[str, str, str]]:
    """Ban backup nam tren cloud, doc tu so muc luc: [(remote, ngay, domain)].

    Doc SO MUC LUC chu khong liet ke remote: co gateway S3 khong ho tro liet ke
    theo prefix nen "rclone lsf" luon tra ve rong du du lieu van con.
    """
    out: list[tuple[str, str, str]] = []
    for r in rclone_remotes():
        if r.endswith("-s3"):
            continue
        # Lay ban moi nhat tu remote ve roi doc
        sh(f"source /var/hostvn/menu/helpers/function 2>/dev/null; "
           f"backup_index_fetch {shlex.quote(r)}", 120)
        idx = _index_path(r)
        if not idx.exists():
            continue
        for line in idx.read_text(errors="replace").splitlines():
            parts = line.split("|")
            if len(parts) < 3:
                continue
            d, dom = parts[0].strip(), parts[1].strip()
            if d and dom and (not domain or dom == domain):
                out.append((r, d, dom))
    # moi nhat len truoc, bo trung
    return sorted(set(out), key=lambda x: x[1], reverse=True)


def fetch_cloud_backup(remote: str, date: str, domain: str) -> tuple[bool, str]:
    """Tai ban backup tu cloud ve /home/backup/<date>/<domain> de khoi phuc."""
    idx = _index_path(remote)
    files: list[str] = []
    if idx.exists():
        for line in idx.read_text(errors="replace").splitlines():
            parts = line.split("|")
            if len(parts) >= 3 and parts[0].strip() == date and parts[1].strip() == domain:
                files = [f.strip() for f in parts[2].split(",") if f.strip()]
                break
    if not files:
        # Khong co so muc luc: dung ten file theo quy uoc cua script
        db = read_user_conf(domain).get("db_name", "")
        files = [f"{domain}.tar.gz"] + ([f"{db}.sql.gz"] if db else [])

    ip = sh("source /var/hostvn/ipaddress 2>/dev/null; echo $IPADDRESS", 10).strip() \
         or sh("hostname -I | awk '{print $1}'", 10).strip()
    dest = f"{BACKUP_ROOT}/{date}/{domain}"
    sh(f"mkdir -p {shlex.quote(dest)}", 20)

    got = 0
    for f in files:
        # copyto theo DUONG DAN CHINH XAC — khong dua vao liet ke
        rc = sh(f"rclone copyto {shlex.quote(remote)}:{shlex.quote(ip)}/{shlex.quote(date)}/"
                f"{shlex.quote(domain)}/{shlex.quote(f)} {shlex.quote(dest)}/{shlex.quote(f)} "
                f"--bwlimit 30M >/dev/null 2>&1; echo $?", 1800)
        if rc.strip() == "0" and Path(f"{dest}/{f}").exists():
            got += 1
    if got == 0:
        return False, f"Không tải được file nào từ {remote}."
    return True, f"Đã tải {got}/{len(files)} file từ {remote}."


def list_backups() -> list[dict]:
    root = Path(BACKUP_ROOT)
    if not root.is_dir():
        return []
    rows: list[dict] = []
    for date_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True):
        for dom_dir in sorted(p for p in date_dir.iterdir() if p.is_dir()):
            files = [f.name for f in dom_dir.iterdir() if f.is_file()]
            size = sh(f"du -sh {shlex.quote(str(dom_dir))} 2>/dev/null | cut -f1", 15)
            rows.append({"date": date_dir.name, "domain": dom_dir.name,
                         "size": size or "?", "files": files})
    return rows


def delete_backup(domain: str, date: str) -> bool:
    # An toan: bat buoc ca 2 tham so, khong cho ky tu duong dan
    if not domain or not date or "/" in domain or "/" in date or ".." in f"{domain}{date}":
        return False
    target = Path(BACKUP_ROOT) / date / domain
    if not target.is_dir():
        return False
    sh(f"rm -rf {shlex.quote(str(target))}", 60)
    # don thu muc ngay neu rong
    sh(f"rmdir {shlex.quote(str(Path(BACKUP_ROOT) / date))} 2>/dev/null", 10)
    return not target.exists()


def restore_site(domain: str, date: str, rtype: str = "full") -> tuple[bool, str]:
    """rtype: full | source | db. Khoi phuc tu /home/backup/<date>/<domain>."""
    uc = read_user_conf(domain)
    user, db = uc.get("username", ""), uc.get("db_name", "")
    if not user:
        return False, "Không tìm thấy user của domain."
    src = Path(BACKUP_ROOT) / date / domain
    if not src.is_dir():
        return False, "Không có bản backup cho ngày này."
    qsrc, qd = shlex.quote(str(src)), shlex.quote(domain)
    done: list[str] = []

    if rtype in ("full", "source"):
        tarball = src / f"{domain}.tar.gz"
        if not tarball.exists():
            return False, "Bản backup này không có mã nguồn."
        qu, qhome = shlex.quote(user), shlex.quote(f"/home/{user}/{domain}")
        sh(f"""
mkdir -p {qhome}/public_html
rm -rf {qhome}/public_html/*
tar xzf {qsrc}/{qd}.tar.gz -C {qhome}/
chmod 711 /home; chmod 755 /home/{qu}; chmod 711 {qhome}
[ -d {qhome}/logs ] && chmod 711 {qhome}/logs
chmod 755 {qhome}/public_html
find {qhome}/public_html/ -type d -print0 | xargs -0 -r chmod 0755
find {qhome}/public_html/ -type f -print0 | xargs -0 -r chmod 0644
chown root:root /home/{qu}
chown -R {qu}:{qu} {qhome}
[ -d /home/{qu}/tmp ] && chown -R {qu}:{qu} /home/{qu}/tmp
[ -d /home/{qu}/php ] && chown -R {qu}:{qu} /home/{qu}/php
""", 900, merge=True)
        done.append("mã nguồn")

    if rtype in ("full", "db"):
        if not db:
            if rtype == "db":
                return False, "Domain này không có database."
        else:
            gz = src / f"{db}.sql.gz"
            plain = src / f"{db}.sql"
            pw = conf_val("mysql_pwd")
            if gz.exists():
                # zcat: khong lam hong file backup (shell goc gunzip tai cho)
                out = sh(f"zcat {shlex.quote(str(gz))} | mysql -uadmin -p{shlex.quote(pw)} {shlex.quote(db)}",
                         900, merge=True)
            elif plain.exists():
                out = sh(f"mysql -uadmin -p{shlex.quote(pw)} {shlex.quote(db)} < {shlex.quote(str(plain))}",
                         900, merge=True)
            else:
                return False, "Bản backup này không có database."
            if "ERROR" in out.upper():
                return False, f"Lỗi import database: {out.splitlines()[0][:120]}"
            done.append("database")

    return True, f"Đã khôi phục {', '.join(done)} cho {domain}."


def rclone_remotes(include_raw: bool = False) -> list[str]:
    """Ten cac remote. Mac dinh AN remote tho "<ten>-s3".

    Remote tho la phan ky thuat cua ket noi S3 (alias "<ten>" moi la cai tro
    thang vao bucket). Hien no ra chi lam nguoi dung chon nham -> sai duong dan.
    """
    out = sh("rclone listremotes 2>/dev/null", 15)
    names = [x.strip().rstrip(":") for x in out.splitlines() if x.strip()]
    if include_raw:
        return names
    return [n for n in names if not n.endswith("-s3")]


def rclone_remotes_info() -> list[dict]:
    """Remote kem loai va dich den, de hien cho nguoi dung doc duoc."""
    info = []
    for n in rclone_remotes():
        qn = shlex.quote(n)
        typ = sh(f"rclone config show {qn} 2>/dev/null | grep -m1 '^type' | cut -d= -f2", 15).strip()
        tgt = sh(f"rclone config show {qn} 2>/dev/null | grep -m1 '^remote' | cut -d= -f2", 15).strip()
        if typ == "alias" and tgt.split(":")[0].endswith("-s3"):
            info.append({"name": n, "kind": "S3", "detail": f"bucket: {tgt.split(':', 1)[-1]}"})
        else:
            kinds = {"drive": "Google Drive", "onedrive": "OneDrive", "s3": "S3"}
            info.append({"name": n, "kind": kinds.get(typ, typ or "?"), "detail": tgt})
    return info


def rclone_delete_remote(name: str) -> bool:
    """Xoa ket noi: alias + remote tho "<ten>-s3" + so muc luc backup.

    Chi xoa alias thi remote tho o lai mo coi trong rclone.conf — sau nay tao
    lai cung ten se bao "da ton tai".
    """
    if not name or "/" in name:
        return False
    qn = shlex.quote(name)
    sh(f"rclone config delete {qn}", 20, merge=True)
    if f"{name}-s3" in rclone_remotes(include_raw=True):
        sh(f"rclone config delete {shlex.quote(name + '-s3')}", 20, merge=True)
    sh(f"rm -f /var/hostvn/.backup_index.{qn}", 10)
    return name not in rclone_remotes(include_raw=True)


def autobackup_info() -> str:
    cron = sh("crontab -l 2>/dev/null | grep -iE 'backup|hostvn' ", 15)
    files = sh("ls /etc/cron.d 2>/dev/null | tr '\\n' ' '", 10)
    return (f"Cron backup:\n{cron or '(chưa đặt lịch)'}\n\n"
            f"/etc/cron.d: {files or '(trống)'}")
