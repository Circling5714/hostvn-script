# Dự án Rebuild HOSTVN Script cho Ubuntu hiện đại

> Tài liệu dự án — ghi lại toàn bộ quá trình phân tích, quyết định và thay đổi.
> Ngày thực hiện: **17/07/2026** · Thực hiện: QMV + Claude Code

---

## 1. Tổng quan

| Hạng mục | Thông tin |
|---|---|
| Repo gốc | https://github.com/f97-26082023/hostvn (fork của HOSTVN Script — Sanvv/HOSTVN) |
| Repo mới | https://github.com/Circling5714/hostvn-script |
| Link phân phối (GitHub Pages) | https://circling5714.github.io/hostvn-script |
| Quy mô code | 206 file, ~31.500 dòng Bash |
| Bản gốc hỗ trợ | Ubuntu 18.04 / 20.04, Debian 10 |
| Bản rebuild hỗ trợ | **Ubuntu 22.04 / 24.04 / 26.04 LTS** (26.04 experimental) + **Proxmox LXC** |
| Phiên bản script | 0.2.10 → **1.0.0** |

**Mục tiêu:** rebuild bộ script cài đặt & quản trị LEMP Stack (Nginx – MariaDB – PHP-FPM) để tương thích với các phiên bản Ubuntu LTS mới nhất (2026), sửa các dependency đã chết, và hỗ trợ chạy trong container Proxmox LXC.

## 2. Kiến trúc script (giữ nguyên từ bản gốc)

```
install  ──►  ubuntu  ──►  hostvn  ──►  menu.tar.gz (menu quản trị ~200 file)
(check môi     (cài đặt      (cài LEMP,        │
 trường, OS)   dependencies)  cấu hình)        └─►  update (nâng cấp về sau)
```

- Script tự tải chính nó từ GitHub Pages của repo (mô hình `wget → bash`).
- Menu quản trị nằm trong `menu/`, đóng gói thành `menu.tar.gz`, giải nén vào `/var/hostvn/` khi cài.
- File `version` là "single source of truth" cho phiên bản mọi thành phần.

## 3. Quyết định phạm vi (đã chốt với chủ dự án)

1. **Target OS:** Ubuntu 22.04 + 24.04 + 26.04 (26.04 experimental vì PPA ondrej/php chưa hỗ trợ).
2. **Nginx:** tiếp tục build từ source (giữ đủ module cho tính năng FastCGI cache purge của menu), nâng lên stable 1.30.x, chuyển sang PCRE2 + OpenSSL 3 hệ thống, **bỏ ngx_pagespeed**.
3. **MariaDB mặc định:** 11.8 LTS (hỗ trợ tới 6/2028; 11.8 vẫn giữ symlink lệnh `mysql` mà menu dùng nhiều).
4. **Phân phối:** local-first (cài từ repo clone) + fallback link online, link đặt trong 1 biến có thể override.

## 4. Bối cảnh phiên bản đã xác minh (07/2026)

| Thành phần | Bản gốc | Bản rebuild | Ghi chú |
|---|---|---|---|
| Ubuntu mới nhất | — | 26.04 LTS "Resolute Raccoon" (4/2026) | ondrej/php PPA chưa hỗ trợ |
| Nginx | 1.24.0 | **1.30.4** stable | vá CVE-2026-42533, CVE-2026-60005, CVE-2026-56434 |
| OpenSSL | 1.1.1t build tĩnh (EOL!) | **OpenSSL 3 hệ thống** | 1.1.1 hết hỗ trợ từ 9/2023 |
| PCRE | 8.45 build tĩnh | **PCRE2 hệ thống** | libpcre3 đã bị gỡ khỏi Ubuntu 24.04+ |
| ngx_cache_purge | FRiCKLE 2.3 (chết) | **nginx-modules fork 2.5.6** | có fix cho struct change nginx 1.29.4 |
| headers-more | 0.34 | **0.40** | |
| nginx-module-vts | 0.2.1 | **0.2.5** | |
| ngx_pagespeed | 1.14.33.1-RC1 | **BỎ** | Google bỏ rơi, không có PSOL binary, không compile được GCC mới |
| MariaDB | 10.11 | **11.8 LTS** | |
| PHP mặc định | 8.2 (php2: 7.4) | **8.4** (php2: 8.2) | list: 8.4 / 8.3 / 8.2 / 7.4 (bỏ 5.6) |
| phpMyAdmin | 5.2.1 | **5.2.3** | |
| php-redis (PECL) | 5.3.7 | **6.3.0** | |
| php-memcached (PECL) | 3.2.0 | **3.4.0** | 3.2.0 không build được trên PHP 8.4 |
| igbinary (PECL) | 3.2.14 | **3.2.16** | |
| NodeJS | 12 / 14 | **22 LTS** | NodeSource keyring + repo `nodistro` |

## 5. Các vấn đề phát hiện trong bản gốc

### 5.1. Không tương thích Ubuntu mới
- Chặn cứng OS ở 18.04/20.04 (`LIST_OS_VER_SUPPORT`).
- Gói apt đổi tên/bị gỡ: `python` → `python3`, `libncurses5*` → `libncurses-dev`, `libaio1` → qua `libaio-dev`, `libpcre3*` → `libpcre2-dev`.
- Ubuntu 22.04+ có `needrestart` → apt bật prompt tương tác giữa chừng, **treo cài đặt** nếu không set `DEBIAN_FRONTEND=noninteractive` + `NEEDRESTART_MODE=a`.
- `mariadb_repo_setup` với SHA256 hardcode đã lỗi thời (checksum đổi theo mỗi release).
- `mysql_secure_installation` qua heredoc — thứ tự prompt thay đổi giữa các bản MariaDB → dễ vỡ.
- `listen 443 ssl http2` — syntax deprecated từ nginx 1.25.
- Workflow GitHub Pages dùng `upload-pages-artifact@v1` / `deploy-pages@v1` — **GitHub đã khai tử đầu 2025**, deploy chắc chắn fail.
- Ghi đè `/etc/resolv.conf` xung đột systemd-resolved (code này vốn đã bị comment, đã xoá hẳn).

### 5.2. Dependency đã chết sẵn trong fork
- **`HOMEPAGE_LINK` không được định nghĩa ở đâu cả** → mọi tính năng tải từ nó đã hỏng từ trước: cài PHP extension redis/memcached/igbinary, update phpMyAdmin, tải redis.conf, Nextcloud auto-install.
- `nginx_new_version` — key không tồn tại trong file `version` → menu "Update Nginx" luôn báo "không có bản mới".
- Menu tự update tải sai file: `curl -sO "${UPDATE_LINK}"` (tải URL gốc thay vì file `update`).

### 5.3. Bug logic
- Điều kiện cài `php-json`: `if != "8.0"` → với PHP 8.2/8.4 apt tìm gói `php8.x-json` không tồn tại → **fail cả lệnh cài PHP**.
- Đổi phiên bản PHP: `apt purge` liệt kê từng gói (gồm `-json`) → gói không có trong archive làm fail cả lệnh purge.

## 6. Thay đổi chi tiết theo file

### `version`
Cập nhật toàn bộ như bảng mục 4. Bỏ các key `openssl_version`, `pcre_version`, `zlib_version` (dùng lib hệ thống). `php_list=php8.4 php8.3 php8.2 php7.4`.

### `install`
- OS check chỉ còn `ubuntu` (bỏ Debian/CentOS), thông báo rõ 22.04/24.04/26.04.
- Export `DEBIAN_FRONTEND=noninteractive`, `NEEDRESTART_MODE=a`; apt upgrade với `--force-confdef/confold`.
- **Local-first**: nếu chạy từ repo clone thì dùng file cạnh nó, không thì tải từ `SCRIPT_LINK` (override qua env `HOSTVN_SCRIPT_LINK`). Truyền `HOSTVN_LOCAL_DIR` xuống các script con.

### `ubuntu`
- `LIST_OS_VER_SUPPORT=('22.04' '24.04' '26.04')`, cảnh báo experimental cho 26.04.
- Sửa package list (mục 5.1); bỏ `apache2-dev`, `libpcre++-dev`, `libgeoip-dev` (chỉ phục vụ pagespeed/modsec); thêm `psmisc`.
- Bỏ `create_source_list` (ghi đè sources.list) và `set_dns_server` (ghi đè resolv.conf).
- `set_timezone` ưu tiên `timedatectl`.
- **Guard container**: bỏ qua tạo swap trong LXC/Docker (swapon bị cấm), hướng dẫn set swap trên host.

### `hostvn` (script cài chính, ~3.700 dòng)
- Hàm `get_version_value()`: đọc file `version` local trước, fallback curl.
- Detect IP qua `api.ipify.org` (fallback cyberpanel.sh).
- `install_nginx`: bỏ toàn bộ pagespeed/PSOL + openssl/pcre/zlib vendored; build với `libpcre2-dev libssl-dev` hệ thống; thêm `--with-http_v3_module` (HTTP/3); cache_purge từ fork nginx-modules; `make -j$(nproc)`.
- `install_mariadb`: keyring `/etc/apt/keyrings/mariadb-keyring.pgp` + deb822 `.sources`; **kiểm tra repo có suite của Ubuntu hiện tại không, nếu chưa → fallback gói distro** (quan trọng cho 26.04 mới phát hành).
- `install_php`: **kiểm tra PPA ondrej có suite không trước khi add** → 26.04 fallback PHP distro; sửa điều kiện `php-json` (chỉ PHP 5.x/7.x).
- `config_my_cnf`: thay `mysql_secure_installation` bằng SQL trực tiếp — root giữ **cả** `unix_socket` **và** password auth (`IDENTIFIED VIA unix_socket OR mysql_native_password`); comment `innodb=ON`; **guard container**: thêm `innodb_use_native_aio = 0` (io_uring bị seccomp chặn trong LXC unprivileged — lỗi MariaDB-không-start phổ biến nhất trên Proxmox).
- `default_vhost`: `listen 443 ssl;` + `http2 on;` (syntax mới).
- `kernel_tweak`: **guard container** — bỏ qua sysctl trong LXC (host quản lý).
- `install_phpmyadmin`, `add_menu`: local-first cho `phpmyadmin.sql` và `menu.tar.gz`.
- Bỏ `mkdir /etc/nginx/pagespeed`.

### `update`
- `script_version=1.0.0`; `UPDATE_LINK` 1 biến override được.
- Khối rebuild nginx: đồng bộ với `install_nginx` mới (PCRE2/OpenSSL3/HTTP3, không pagespeed).
- Sửa `listen 443 ssl http2` và `innodb=ON` trong phần regenerate config.

### `menu/` (gỡ pagespeed + sửa controller)
- **Xoá**: `controller/pagespeed/` (8 file), `route/lemp_ngx_pagespeed`, `template/ngx_pagespeed/` (9 file); gỡ option 5 khỏi `route/lemp`; gỡ 9 hàm wrapper khỏi `route/parent`. (Giữ đoạn dọn dẹp thư mục pagespeed cũ trong `delete_domain`/`clear_cache` — vô hại, giúp dọn cài đặt cũ.)
- `route/lemp_nginx`: viết lại với hàm `_build_nginx()` dùng chung cho Update/Rebuild; option "Update Nginx" giờ so sánh `nginx -v` với `nginx_version` trong file version (sửa key chết `nginx_new_version`).
- `controller/cache/script/install_php_{redis,memcached}.sh`, `controller/php/{change_php1,change_php2,install_php2}`: `MODULE_LINK` → **https://pecl.php.net/get** (PECL chính thức).
- `controller/php/change_php1|2`: purge PHP cũ bằng glob `php${VER}*`.
- `controller/cache/install_redis`: bỏ tải redis.conf từ link chết → dùng config của gói `redis-server` (reinstall `--force-confmiss` nếu thiếu).
- `controller/tools/install_nodejs`: viết lại — NodeSource keyring + repo `nodistro`, Node 22 LTS.
- `controller/tools/install_av`: ImunifyAV mở gate 18.04 → 18.04/20.04/22.04/24.04/26.04 (đã xác minh Imunify hỗ trợ tới 26.04). Lưu ý: ImunifyAV không hỗ trợ chính thức LXC — trong container dùng ClamAV.
- `controller/tools/auto_install_source`: gỡ option Nextcloud (bundle từ server gốc đã chết).
- `controller/admin/update_phpmyadmin`: tải từ files.phpmyadmin.net chính thức.
- `controller/vps/update_scripts`: sửa bug tải sai file update.
- `helpers/variable_common`: `UPDATE_LINK` → link repo mới (nơi duy nhất định nghĩa link cho toàn menu).

### Khác
- `.gitattributes` mới: ép LF cho mọi file text (script CRLF không chạy được trên Linux); `menu.tar.gz` đóng gói lại (204 entries, LF).
- `.github/workflows/static.yml`: nâng lên `checkout@v4`, `configure-pages@v5` (+`enablement: true`), `upload-pages-artifact@v3`, `deploy-pages@v4`; trigger trên `main` + `master`.
- `README.md`: viết lại — changelog, yêu cầu, 2 cách cài, ghi chú LXC.

## 7. Hỗ trợ Proxmox LXC

Script tự phát hiện container qua `systemd-detect-virt --container` và:
1. Bỏ qua tạo swap (swapon bị cấm) → set swap ở Proxmox → Resources.
2. Bỏ qua kernel tweak (sysctl kernel/net do host quản lý).
3. Thêm `innodb_use_native_aio = 0` cho MariaDB (io_uring bị seccomp chặn).

**Yêu cầu container:** template Ubuntu 22.04/24.04, unprivileged OK, **`nesting=1` bắt buộc** (systemd hardening + ufw/fail2ban cần), **≥ 2GB RAM / 2 cores lúc cài** (compile nginx ~5–15 phút), sau cài có thể hạ. Kernel tuning (BBR…) nếu muốn thì set trên host Proxmox. Nên snapshot trước khi cài để rollback được.

## 8. Hạ tầng phân phối

```
┌────────────────────────────────────────────────────────────────┐
│  git push main  ──►  GitHub Actions (static.yml)               │
│                        └──►  GitHub Pages                      │
│                              https://circling5714.github.io/   │
│                              hostvn-script/{install,ubuntu,    │
│                              hostvn,update,version,menu.tar.gz,│
│                              phpmyadmin.sql}                   │
└────────────────────────────────────────────────────────────────┘
```

- Remote `origin` = repo mới; remote `upstream` = repo gốc f97 (để đối chiếu về sau).
- Pages Source = **GitHub Actions** (phải bật tay 1 lần trong Settings → Pages — workflow token không tự tạo Pages site được, lỗi `Resource not accessible by integration`).
- Đã verify sau deploy: cả 7 file phân phối trả HTTP 200, nội dung `version` đúng.

### Cách cài
```sh
# Cách 1: local-first (khuyến nghị)
apt update && apt install git -y
git clone https://github.com/Circling5714/hostvn-script.git && cd hostvn-script && bash install

# Cách 2: online qua Pages
wget https://circling5714.github.io/hostvn-script/install && bash install
```

## 9. Quy trình phát triển (cho lần sửa sau)

1. Sửa code trên branch, **line-ending LF** (đã có `.gitattributes` ép sẵn).
2. Nếu sửa bất kỳ file nào trong `menu/` → **bắt buộc** đóng gói lại: `rm -f menu.tar.gz && tar --format=gnu -czf menu.tar.gz menu`.
3. Nâng phiên bản thành phần → sửa file `version` (menu Update Nginx / update script đọc từ đây).
4. Kiểm tra syntax: `bash -n <file>` cho mọi script đã sửa.
5. Push lên `main` → Pages tự deploy → VPS đã cài dùng menu `hostvn` → mục Update script để nhận bản mới.

## 10. Lịch sử commit chính

| Commit | Nội dung |
|---|---|
| `f2cff52` | (gốc f97) nginx 1.24.0 — điểm xuất phát |
| `7221eab` | **Rebuild for Ubuntu 22.04/24.04/26.04 LTS** — toàn bộ thay đổi mục 6 (41 file, +370/−2205) |
| `3cf51fa` | Trỏ link phân phối về Circling5714/hostvn-script, workflow main + auto-enablement, README |
| `d229198` | Trigger deploy Pages sau khi bật Pages |
| `bdbde52` | docs: PROJECT.md |
| `c9a3ce8` | **fix: version parsing rỗng toàn bộ** — `grep -w "key="` không match khi giá trị bắt đầu bằng chữ/số → đổi sang `grep "^key="`; guard MARIADB_VERSION rỗng; fail-fast install_nginx (tìm ra ở test run 1) |
| `72cee80` | **fix: nginx link fail thiếu brotli** — ngx_brotli master cần `libbrotli-dev` hệ thống; fail-fast sau make (test run 2) |
| `ca42e23` | **fix: image tools sang gói Ubuntu** — optipng (URL fossies chết), jpegoptim (format tag đổi), pngquant (upstream chuyển Rust) (test run 2) |

## 11. Kết quả test thật trên Proxmox LXC (17/07/2026)

Môi trường: Proxmox LXC, 4GB RAM / 2 cores, unprivileged. Lưu ý: template gốc là Ubuntu 24.10 lai sources noble → đã ép đồng bộ toàn bộ userland về **noble 24.04 thật** (pin 1001 + downgrade 239 gói) trước khi test. Test tự động hoá: cài trong tmux + daemon tự trả lời 5 prompt + monitor log từ xa.

- **Run 1**: phát hiện bug version parsing (`c9a3ce8`) — mọi phiên bản rỗng, hỏng dây chuyền.
- **Run 2**: xác nhận fix run 1 (menu PHP hiện đúng 8.4/8.3/8.2/7.4, MariaDB 11.8.8 + PHP 8.4.23 cài OK); phát hiện lỗi brotli (`72cee80`) và 3 lỗi image tools (`ca42e23`).
- **Run 3**: **"Cai dat thanh cong"** — cài sạch từ đầu đến cuối, tự reboot.

Verify sau reboot — tất cả PASS:

| Hạng mục | Kết quả |
|---|---|
| Services | nginx / mariadb / php8.4-fpm / fail2ban đều `active` |
| nginx | 1.30.4, `nginx -t` OK, đủ module: cache_purge 2.5.6, headers-more 0.40, vts 0.2.5, brotli, **HTTP/3** |
| MariaDB | 11.8.8, login user admin OK |
| PHP | 8.4.23 (PPA ondrej) |
| Web | `http://localhost` → 200; admin port → 401 (auth basic đúng) |
| Container guard | `innodb_use_native_aio = 0` được áp tự động; swap/sysctl bỏ qua đúng |
| Khác | ufw active, php-fpm socket đúng quyền, menu `/usr/bin/hostvn` sẵn sàng, `.hostvn.conf` ghi đúng |

## 12. Trạng thái & việc tiếp theo

- [x] Phân tích + rebuild toàn bộ codebase
- [x] Repo mới + GitHub Pages hoạt động, verify đủ file phân phối
- [x] Hỗ trợ container (Proxmox LXC)
- [x] **Test cài đặt thật trên LXC (24.04): THÀNH CÔNG** — 3 vòng test, tìm và vá 5 bug
- [ ] Test các tính năng menu chính sau cài: thêm domain, SSL Let's Encrypt, cache Redis/Memcached, backup Rclone
- [ ] (Tuỳ chọn) Theo dõi ondrej/php PPA hỗ trợ 26.04 để bỏ nhãn experimental
- [ ] (Khuyến nghị) Tắt SSH password authentication trên server test (đã có key)

## 13. Tính năng bổ sung (feature-add phase, 17/07/2026)

Sau khi bản rebuild cài chạy ổn, bổ sung 5 tính năng — tất cả đã test end-to-end trên LXC (feature 3/4/5 dùng creds thật) và merge vào `main`.

| # | Tính năng | Menu | Chi tiết |
|---|---|---|---|
| 1 | HTTP/3 (QUIC) per-domain | Domain → 13 | Bật/tắt HTTP/3 cho từng website. `reuseport` neo 1 lần ở default_server, mỗi domain thêm `listen 443 quic;` + `Alt-Svc`. Cần SSL trước. Installer mở UDP 443. |
| 2 | Nginx VTS dashboard | Admin Tool → 7 | Dashboard traffic realtime tại `http://IP:ADMIN_PORT/vts_status`, sau auth_basic của admin port. |
| 3 | Wildcard SSL Cloudflare | SSL → 6, 7 | Cấp `*.domain` qua acme.sh dns_cf (nhận CF_Token scoped hoặc Global Key), auto-renew. Menu 7 = kiểm tra hạn mọi cert. Vá bug CF_Key export lồng chuỗi có sẵn. |
| 4 | Backup S3-compatible | Backup → 7 | AWS/Backblaze/MinIO/Wasabi/DigitalOcean/Other. Tạo remote thô `<tên>-s3` + alias `<tên>` trỏ vào bucket → dùng chung luồng backup/restore/auto-backup. |
| 5 | Telegram control bot | Telegram Notify → 5 | 3 chế độ chọn lúc setup: `notify` (chỉ cảnh báo), `menu` (lệnh định sẵn), `shell` (thêm `/sh`). Whitelist `ALLOWED_CHAT_IDS`. Daemon systemd `hostvn-telegram-bot.service`. |

**Kết quả test E2E (LXC 24.04):** HTTP/3 → nginx listen UDP 443 + Alt-Svc; VTS → dashboard HTTP 200; wildcard → cert Let's Encrypt SAN `*.test01.caominh.net`; S3 → ghi/list/xoá vào bucket thật qua alias; Telegram → bot thật xử lý lệnh, whitelist + 3 chế độ đúng.

**Lưu ý bảo mật:** chế độ `shell` của bot cho phép chạy lệnh root qua Telegram — chỉ nên bật khi hiểu rõ rủi ro (token lộ = mất server); production nên dùng `menu`.

**File mới:** `menu/controller/domain/http3`, `menu/controller/admin/vts_status`, `menu/controller/ssl/wildcard`, `menu/controller/ssl/check_expiry`, `menu/controller/backup/connect_s3`, `menu/controller/telegram/control_bot`, `menu/telegram_bot/bot.sh`.

### Tăng cường Fail2ban (đợt 2)

| Tính năng | Menu | Chi tiết |
|---|---|---|
| 3 jail mới | tự bật khi cài + Firewall → 9 | `recidive` (ban dài hạn IP tái phạm), `nginx-limit-req`, `nginx-botsearch` (chống scan/bot). `fail2ban.local` set logtarget ra file để recidive theo dõi được. |
| Thống kê Fail2ban | Firewall → 8 | Bảng từng jail: đang ban / tổng ban / đang fail + danh sách IP bị ban. |
| Đồng bộ Cloudflare WAF | Firewall → 10 | Khi fail2ban ban IP → tạo IP Access Rule chặn trên Cloudflare; unban → gỡ. Setup validate token + resolve zone + kiểm tra quyền bằng rule thử. |

**Cloudflare WAF sync — chi tiết kỹ thuật:**
- Token cần **Zone:Read + Firewall Services:Edit** (ghi rõ trong comment code, màn hình setup, thông báo lỗi, header wrapper). Token DNS của wildcard SSL **không đủ quyền**.
- Wrapper `menu/fail2ban/cf_waf.sh` gọi Cloudflare IP Access Rules API; action.d/cloudflare-hostvn gắn vào jail qua `jail.d/zz-cloudflare.local` (fail2ban đọc `.conf` trước `.local` nên phải đặt ở `.local` đọc sau cùng mới có hiệu lực — điểm này dễ sai).
- Test E2E: fail2ban ban → IP lên Cloudflare (mode=block, notes=fail2ban-hostvn); unban → gỡ khỏi Cloudflare. Đã xác nhận với token thật.

**File mới đợt 2:** `menu/controller/firewall/f2b_stats`, `menu/controller/firewall/f2b_extra_jails`, `menu/controller/firewall/cf_waf`, `menu/fail2ban/cf_waf.sh`.

### Cloudflare Tunnel (chế độ mạng — đợt 3)

Chế độ tuỳ chọn: mọi website phục vụ qua Cloudflare Tunnel, **VPS ẩn IP hoàn toàn** (không mở 80/443). Truy cập: VPS management → 11.

- **Kiến trúc:** ingress catch-all → `http://localhost:80` (set 1 lần), nginx tự route theo Host header. Thêm web = chỉ tạo 1 CNAME proxied trỏ vào tunnel (helper `menu/tunnel/cf_tunnel.sh`).
- **Setup** (`menu/controller/tunnel/setup`): cài cloudflared → tạo remotely-managed tunnel qua API (`config_src=cloudflare`) → ingress → `cloudflared service install <token>` → real_ip + firewall → lưu `network_mode=tunnel`, đồng bộ site hiện có.
- **Real IP / fail2ban (điểm chí tử):** tunnel mode làm traffic đến từ `127.0.0.1`. Cấu hình `real_ip_header CF-Connecting-IP` + `real_ip_recursive on` + trust `127.0.0.1` → nginx log **IP thật** → fail2ban ban đúng attacker. Ép `ignoreip 127.0.0.1/8 ::1`. Vì iptables ban vô hiệu (traffic từ localhost), setup cảnh báo bật WAF sync (Firewall → 10) để ban tại edge.
- **add/delete domain:** tự tạo/xoá CNAME khi `network_mode=tunnel`. Installer lưu `network_mode=direct` mặc định + hướng dẫn bật Tunnel ngay sau cài.
- **Token cần:** Account `Cloudflare Tunnel:Edit` + `Cloudflare One Connectors:Edit`, Zone `DNS:Edit` (ghi rõ trong code + UI).
- **Test E2E (token thật):** `curl https://tuntest.caominh.net` qua Cloudflare edge → tunnel → nginx trả 200 với `real_ip = IP thật của client` (không phải 127.0.0.1). cloudflared status healthy. Disable trả về direct chuẩn.

**File mới đợt 3:** `menu/controller/tunnel/setup`, `menu/tunnel/cf_tunnel.sh`.

## 14. Rủi ro đã biết / lưu ý

- **Ubuntu 26.04**: chưa có PPA ondrej → chỉ có PHP mặc định của distro; MariaDB repo có thể chưa có suite `resolute` → script tự fallback gói distro.
- **PHP 5.6** đã bỏ khỏi danh sách; code xử lý 5.6 trong menu vẫn còn (vô hại) phòng người dùng cũ.
- `wp package install` (wp-cli-rename-db-prefix…) có thể kêu ca trên PHP 8.4 — không chặn cài đặt.
- `optipng 0.7.7` / `jpegoptim 1.5.2` giữ nguyên phiên bản (URL còn sống, build được GCC mới) — có thể nâng sau.
- ngx_cache_purge nhánh 3.x (async purge) đã ra — hiện dùng 2.5.6 cho ổn định, cân nhắc nâng sau khi 3.x trưởng thành.

## 15. Bot Telegram giao diện menu + các fix back-port từ nhánh ARM64 (18/07/2026)

Nhánh ARM64 (`hostvn-script-arm64`, chạy trên Android/Linux Deploy) được phát triển song song
và trong quá trình đó phát sinh nhiều thứ **không phụ thuộc kiến trúc**. Đợt này back-port
những thứ đó về bản x86, đồng thời **giữ nguyên** phần chỉ đúng với ARM64.

### 15.1. Bot Telegram được viết lại bằng Python

Bản cũ (`menu/telegram_bot/bot.sh`) chỉ có vài lệnh gõ tay. Bản mới mirror **toàn bộ 15 nhóm
menu của shell `hostvn`** thành nút bấm — dùng được mà không cần SSH.

| Thành phần | Vai trò |
|---|---|
| `bot.py` | Điểm vào, `run_polling(drop_pending_updates=True)`, đăng ký `MenuButtonCommands` |
| `config.py` | Đọc `.telegram_bot.conf`, khai báo `F_*` (feature key) và bảng emoji `E` |
| `permissions.py` | `is_allowed` / `is_admin` / `can_write` / feature-gating theo từng chat |
| `menus.py` | `MAIN_MENU` khai báo bằng dữ liệu (16 nút) + các builder submenu inline |
| `handlers.py` | Router `on_callback`, `callback_data` dạng `<miền>\|<hành_động>\|<tham_số>` |
| `hostvn.py` | Tầng nghiệp vụ: bọc subprocess quanh controller shell có sẵn |
| `progress.py` | Thanh tiến trình động (tiệm cận 96%, chốt 100% khi xong) |
| `texts.py` | Escape HTML, định dạng tiêu đề/khối `<pre>` |

- **Menu chính** là `ReplyKeyboardMarkup` nên nút nằm cố định ở đáy khung chat; submenu là inline.
- **Feature-gating:** admin (`features=None`) thấy đủ 16 nút, chat bị giới hạn chỉ thấy phần được cấp.
- Các thao tác cần nhập nhiều bước (nén ảnh, deploy, đổi port admin…) cố tình **để lại cho SSH**,
  bot hiển thị đúng đường dẫn menu thay vì làm nửa vời — bảng `_SSH_ONLY` trong `handlers.py`.

**Khác biệt x86 ↔ ARM64 — lớp dịch vụ.** Bản ARM64 không có systemd nên có lớp trừu tượng `_svc`
trong `menu/helpers/environment`. Bản x86 chạy systemd nên `hostvn.py` tự cấp một **shim `_svc`
tối giản ánh xạ sang `systemctl`** (`_SVC_SHIM` / `_env_prefix()`), nhờ đó phần còn lại của code
dùng chung được cho cả hai. Shim cũng xử lý việc unit đổi tên giữa các bản phân phối
(`redis` ↔ `redis-server`).

**Cài đặt:** `hostvn` → **Telegram Notify** → **5**. `control_bot` tự dựng venv riêng
(`_ensure_python_bot`: `python3 -m venv`, nếu thiếu ensurepip thì `apt install python3-venv`
rồi thử lại) và tạo unit `hostvn-telegram-bot.service` trỏ thẳng vào `venv/bin/python bot.py`.
`bot.sh` chỉ còn là đường lui khi venv chưa sẵn sàng.

> `menu/telegram_bot/venv/` **không** commit vào repo — dựng tại chỗ lúc setup.

### 15.2. Các fix back-port kèm theo

| # | Fix | File |
|---|---|---|
| 1 | Chế độ Tunnel: đổi tên miền / thêm-xoá alias / redirect nay **đồng bộ luôn bản ghi DNS**. Trước đây chỉ `add`/`delete domain` mới tạo CNAME, nên đổi tên miền xong site chết vì hostname mới không có DNS. Đổi tên: thêm CNAME mới **trước** rồi mới xoá cũ để không có khoảng trống. | `controller/domain/{change_domain,alias_domain,redirect_domain}` |
| 2 | Bộ ngôn ngữ EN: bổ sung key thiếu `lang_permission_manager` (thiếu key này menu 6 hiện trống) + sửa 20 chỗ dịch sai/khác nghĩa so với bản VI. Hai file nay cùng số key. | `menu/lang/en`, `menu/lang/vi` |
| 3 | PHP redis/igbinary: thử `apt` (PPA ondrej có sẵn gói đúng phiên bản) **trước**, biên dịch PECL chỉ còn là đường lui → cài nhanh hơn nhiều và hết lỗi build. | `controller/cache/script/install_php_redis.sh` |
| 4 | `menu.tar.gz` do **GitHub Actions sinh lúc build Pages**, không commit nữa. Trước đây phải đóng gói tay; quên một lần là người dùng bấm Update nhận bản menu cũ. Kèm fallback trong `add_menu()`: cài từ repo clone mà không có tarball thì tự đóng gói từ `menu/`. | `.github/workflows/static.yml`, `hostvn` |

### 15.3. Cố ý KHÔNG back-port

Những thứ này chỉ đúng trong môi trường Android/chroot, mang sang x86 sẽ có hại:

- Lớp `_svc` thay systemd, autostart qua `/etc/rc.local`, memcached qua unix socket.
- `hostvn-noop` cho fail2ban (Android không có iptables) — x86 dùng `iptables-multiport` bình thường.
- Allowlist RFC1918, `IPADDRESS` sinh động (giải quyết việc IP LAN của điện thoại hay đổi).
- Tinh chỉnh eatmydata / `nobarrier` / `vm.dirty_*` / MariaDB trên tmpfs / giới hạn OOM.
- Thương hiệu và số hiệu phiên bản riêng của nhánh ARM64 (`HostVN Scripts ARM64`, 1.1.1).

### 15.4. Kết quả test thật trên máy x86 (Ubuntu 24.04.4, Proxmox LXC, chế độ tunnel)

| Hạng mục | Kết quả |
|---|---|
| Tầng nghiệp vụ `hostvn.py` (21 phép thử) | **21/21** — trạng thái dịch vụ, liệt kê domain/DB/WP, firewall, SSL, tài khoản, phân quyền |
| Render 23 màn hình nhóm + menu chính | **26/26** — độ dài ≤ 4096, thẻ HTML hợp lệ, `callback_data` ≤ 64 byte, feature-gating lọc đúng 2/16 nút |
| Dựng venv qua `_ensure_python_bot` | Đạt — chạy đúng nhánh fallback `apt install python3-venv`, cài `python-telegram-bot 21.11.1` |
| Hook DNS tunnel (`add-dns` → `del-dns`) | Đạt — tạo/xoá CNAME thật qua Cloudflare API, kiểm chứng bằng truy vấn ngược, đã dọn bản ghi test |
| Cú pháp toàn bộ file shell đã sửa | `bash -n` sạch; `py_compile` sạch |

**Lỗi test này bắt được:** shim `_svc is-active` in trạng thái **hai lần** (`inactive\ninactive`)
với unit không active — vì `systemctl is-active` đã in ra rồi mà nhánh `||` còn in thêm. Lỗi lộ
thẳng ra màn hình 🔧 Dịch vụ và 🖥️ Hệ thống. Đã sửa: bắt output vào biến, chỉ tự đặt `inactive`
khi `systemctl` không in gì (unit không tồn tại).

**Chưa test:** phiên Telegram thật đầu-cuối (bấm nút trên điện thoại) — cần bot token hợp lệ.
Toàn bộ tầng dưới đã kiểm bằng test ở trên; phần vận chuyển Telegram dùng chung mã với nhánh
ARM64 và đã chạy thực tế ở đó.

## 16. Rà soát bảo mật, backup lên cloud và các lỗi tìm ra khi dùng thật (19/07/2026)

Đợt này chủ yếu là **sửa lỗi phát hiện khi vận hành thật**, không phải thêm
tính năng. Nhiều lỗi chỉ lộ ra khi chạy trên máy có cấu hình khác máy phát
triển, hoặc khi gặp một máy chủ S3 không chuẩn.

### 16.1. Rà soát bảo mật

**Nặng — bot phân quyền theo phòng chat, không theo người bấm.** Mọi kiểm tra
(`is_allowed` / `can_write` / `has_feature`) đều dùng `effective_chat.id`;
`effective_user.id` chưa từng được dùng để xét quyền. Trong nhóm thì mọi thành
viên đều bấm được nút của tin nhắn bot gửi, nên **ai ở trong nhóm cũng điều
khiển được máy chủ với quyền root** — kể cả người được thêm vào sau. Chính
docstring của config lại gợi ý đưa ID nhóm vào `ALLOWED_CHAT_IDS`.

Đã dựng kịch bản chứng minh: người lạ trong nhóm được `can_write = True`. Nay
thêm `is_actor_allowed()` và `_gate()` — chat phải được phép **và** người bấm
cũng phải được phép; mọi kiểm tra phía sau dùng id người bấm.

> Ai đang dùng bot trong nhóm phải thêm **ID người dùng** của mình vào
> `ALLOWED_CHAT_IDS` (hoặc `ADMIN_IDS`) mới dùng tiếp được — cố ý chặn trước.

Ba lỗi khác kèm theo:

| Lỗi | Hậu quả |
|---|---|
| ionCube tải qua HTTP trần | Gói chứa `.so` nạp vào mọi tiến trình PHP → chèn được gói giữa đường là chạy mã tuỳ ý. `downloads3` không hỗ trợ TLS, `downloads.ioncube.com` thì có |
| ClamAV tải bộ chữ ký qua HTTP trần (2 file) | Chèn giữa đường thì ép được antivirus bỏ qua mã độc |
| Bot token bị ghi vào log | httpx log nguyên URL mọi request ở mức INFO, mà URL Telegram có chứa token. Đã hạ xuống WARNING, kèm chặn thông báo `InvalidToken` của PTB (nó in nguyên token vào traceback) |

**Đã kiểm và loại trừ** (không phải lỗ hổng, không sửa): quyền file bí mật
(600 root, thử đọc bằng user website → bị chặn); mật khẩu MySQL trên dòng lệnh
(client MariaDB tự che argv, `ps` chỉ hiện `-px xxxxxxxxxx`); tấn công symlink
`/tmp` (kernel chặn nhờ `fs.protected_symlinks=1`); tiêm lệnh qua tên miền
(`DOMAIN_RE` chỉ cho `[a-zA-Z0-9.-]`); tiêm SQL khi tạo database (đã lọc ký
tự); không có `eval`, không có `curl|bash`, không có bí mật trong git.

### 16.2. Thương hiệu và phiên bản

`HOSTVN.VN` thành `HostVN` / `HostVN Scripts`, phiên bản `1.0.0` thành
`1.1.1`, lời chào SSH mô tả script và trỏ Document về repo này.

Số phiên bản phải đổi ở **cả ba nguồn**: `hostvn` (installer), `version`
(Pages), `update` (script cập nhật). Sót một chỗ là máy cập nhật xong vẫn hiện
số cũ và bị báo "có bản mới" mãi.

Kèm hai fix cho chính cơ chế ghi lời chào: `ssh_login_notify()` chống trùng
bằng cách tìm chuỗi `${AUTHOR}` trong `.bashrc` — đổi thương hiệu là chốt này
gãy, chạy lại installer sẽ cộng thêm lời chào thứ hai; và `update` không hề
đụng `.bashrc` nên máy đã cài giữ lời chào cũ vĩnh viễn.

### 16.3. CI phát hành: build Pages luôn thất bại

Bước kiểm tra gói dùng `tar tzf ... | grep -q`. `grep -q` thoát ngay khi thấy
dòng khớp, `tar` bị đứt ống (SIGPIPE), và `set -o pipefail` coi cả pipeline là
thất bại — nên báo "thiếu file" **dù file có thật**, làm hỏng mọi lần deploy.

Với gói nhỏ thì output lọt hết vào bộ đệm ống 64KB nên lỗi không xuất hiện —
đó là lý do nó lọt qua lúc viết. Tái hiện được với danh sách 263KB.

Hậu quả: GitHub Pages phục vụ bản cũ, người dùng bấm Update nhận `menu.tar.gz`
từ trước khi có bot. Nay liệt kê ra file rồi mới kiểm tra.

Kèm phát hiện: repo ARM64 để Pages ở `build_type: legacy` (xuất bản thẳng
nhánh, bỏ qua artifact workflow) nên `menu.tar.gz` trả 404 — update hỏng hoàn
toàn. Đã chuyển sang `workflow`.

### 16.4. Cập nhật script làm chết bot

`add_menu()` chạy `rm -rf menu` để thay thư mục menu, mà **venv của bot nằm ở
`menu/telegram_bot/venv`** và không thuộc gói `menu.tar.gz`. Mỗi lần bấm "Cập
nhật HostVN Scripts" là venv bị xoá sạch, unit systemd trỏ vào
`venv/bin/python` không còn nên bot chết hẳn.

Kèm theo: kể cả khi venv còn thì bot vẫn chạy **mã nguồn cũ** sau khi cập
nhật, vì Python nạp module một lần lúc khởi chạy chứ không đọc lại file trên
đĩa. Nay giữ venv qua lần cập nhật rồi khởi động lại service.

### 16.5. Lệnh `hostvn-bot`

```
hostvn-bot {restart|start|stop|status|log [số_dòng]}
```

Sau khi cập nhật mã nguồn bot **bắt buộc** phải restart (lý do ở 16.4). Trước
đây muốn làm phải lần vào `hostvn` → Telegram Notify → chọn trong menu. Lệnh
này kiểm cú pháp trước khi restart để tránh tắt bot cũ rồi bot mới không lên
được. Đăng ký trong `add_menu()` nên cài mới/cập nhật là có sẵn.

### 16.6. Backup lên cloud từ bot + sổ mục lục

**Bot chỉ backup được xuống máy.** `backup_site()` nén xong rồi để nguyên ở
`/home/backup`, không hề gọi `rclone`; menu cũng nhảy thẳng từ "chọn loại
backup" sang chạy luôn. Nay có bước chọn nơi lưu (Local / từng remote), và
khôi phục cũng đọc được bản trên cloud — bắt buộc phải làm cùng lúc, vì backup
lên cloud sẽ xoá bản local.

**Sổ mục lục backup.** Gateway S3 của người dùng (telecloud, lưu qua Telegram,
dùng `gofakes3`) **không hỗ trợ tham số `prefix` của `ListObjectsV2`**:

```
liệt kê gốc bucket           -> 19 mục      OK
liệt kê AUDIO/ CINEMA/ ...   -> 0 mục       (thư mục có thật, đầy dữ liệu)
đọc theo đường dẫn chính xác -> OK, nội dung đúng
```

Mà restore của hostvn dựng menu bằng `rclone lsf`, nên báo "không có backup"
trong khi dữ liệu vẫn nằm nguyên. Cách giải: mỗi lần backup ghi lại **đã lưu
gì ở đâu** vào sổ mục lục, đặt cả ở máy (`/var/hostvn/.backup_index.<remote>`)
lẫn trên remote. Restore đọc sổ thay vì liệt kê, rồi tải từng file theo đường
dẫn chính xác.

Hai chi tiết chỉ đo mới biết: sổ **không đặt được** ở `<IP>/backup_index.txt`
(ghi vào đường dẫn nhiều cấp bị "destination is a file"), phải đặt ở gốc
remote; và gateway chỉ cho **ghi một lần** vào một đường dẫn, xoá trước rồi
ghi lại thì được.

Restore có ba mức: liệt kê được thì như cũ; không liệt kê được nhưng có sổ thì
dựng menu từ sổ; không có sổ thì nhập ngày thủ công, tên file suy theo quy ước
(`<domain>.tar.gz`, `<db_name>.sql.gz`).

### 16.7. Chọn "Cloud" khi backup không nhận kết nối S3

Một dòng gác cổng dò chữ `"drive"` trong `rclone.conf` để quyết định "đã có
kết nối cloud chưa". Cấu hình S3 gồm `[<tên>-s3] type = s3` và
`[<tên>] type = alias` — **không có chữ "drive" nào**, nên script kết luận
chưa có kết nối, quay ra hỏi tạo Google Drive và không bao giờ chạy tới bước
chọn remote. Máy chỉ dùng S3 thì vĩnh viễn không backup lên cloud được.

Đây là lỗi có sẵn trong code gốc, bị che khuất vì trước đây ai cũng dùng
Google Drive.

### 16.8. Xem và xoá kết nối cloud

- Shell không có chỗ nào xem danh sách kết nối, thêm mục **9. Xem cac ket noi
  cloud** (tên · loại · bucket).
- Mục xoá ghi nhãn "Delete connect Google Drive" nhưng dùng chung cho mọi
  loại, đã đổi nhãn.
- **Xoá kết nối S3 chỉ xoá alias `<tên>`, để lại remote thô `<tên>-s3` mồ côi**
  trong `rclone.conf` — lần sau tạo lại cùng tên sẽ báo "đã tồn tại". Đã gặp
  đúng tình trạng này trên máy test. Nay xoá cả hai phần kèm sổ mục lục, ở cả
  shell lẫn bot.
- Bot: danh sách hiện loại và đích, **ẩn remote thô** (chọn nhầm nó là sai
  đường dẫn vì thiếu tên bucket).

### 16.9. Đẩy backup lên gateway S3 không chuẩn

Ba vòng chẩn đoán sai trước khi ra nguyên nhân thật. Ghi lại để không lặp:

| Giả thuyết | Kết luận |
|---|---|
| "Gateway đồng bộ chậm nên chưa thấy file" | **Sai** — đo mốc 0/1/5 phút: đọc được ngay, đủ byte |
| "Một thư mục chỉ chứa được một file" | **Sai** — DB gateway có thư mục chứa 2–3 file bình thường |
| Nguyên nhân thật | `rclone copy` cả thư mục thì OK; `copyto` từng file thì file thứ hai bị từ chối |

Tức là chính việc đổi từ `rclone copy` sang `copyto` từng file gây ra lỗi mất
file thứ hai. Bản gốc dùng `rclone copy` và chạy đúng.

Nguy hiểm hơn: một phiên bản trung gian dùng **xoá trước rồi ghi** — trên
gateway này lệnh xoá **thành công** còn lệnh ghi vẫn hỏng, nên mất luôn bản
backup cũ. Đã kiểm: chưa mất dữ liệu thật nào (đường dẫn đó chưa từng có
backup), nhưng rủi ro là thật.

Cách làm hiện tại:

- `rclone copy` cả thư mục như bản gốc
- Đường dẫn đích **luôn mới**: `<ngày>` đã có dữ liệu thì dùng `<ngày>_<giờ>`,
  giữ nguyên bản cũ — không bao giờ xoá trước khi ghi
- **Không tin mã thoát của rclone** (gateway hay báo lỗi ở bước kiểm tra đích
  dù dữ liệu vẫn vào) nên xác minh bằng `rclone lsjson` trên đường dẫn chính xác
- Thư mục backup rỗng thì báo thất bại. Thiếu chốt này thì hàm xác minh chạy
  trên tập rỗng sẽ báo thành công rồi bên gọi xoá bản trên máy, mất trắng

### 16.10. Hai lỗi giao diện bot chỉ lộ khi dùng thật

**Nút cũ trong lịch sử chat.** Khi thêm bước chọn nơi lưu, nhánh cũ `bk|run`
được giữ "cho tương thích". Nút nằm trong tin nhắn cũ vẫn mang `callback_data`
cũ nên bấm vào là chạy thẳng backup xuống máy, bỏ qua bước chọn đích. Nhìn từ
phía người dùng thì đúng là "bot chạy bản cũ", mà thực ra là nút cũ. Nay quy
`run` về `dst` ngay đầu `cb_bk`.

> Bỏ hẳn một `callback_data` cũ thì nút cũ báo "Lựa chọn không hợp lệ" — rõ
> ràng. Giữ lại mà xử lý theo đường cũ thì **lặng lẽ chạy sai**, khó thấy hơn.

**Nhánh xử lý đặt nhầm hàm.** Nút gửi `bk|rscl|<i>`, router đưa prefix `bk`
tới `cb_bk`, nhưng nhánh `rscl` lại nằm trong `cb_pick`. `cb_bk` không khớp
nhánh nào nên trả về `None` — bot **im lặng tuyệt đối**, không crash, không
log. Đây là kiểu lỗi khó thấy nhất trong bộ router này.

Đã viết bộ kiểm tra tự động đối chiếu **mọi** `callback_data` bot sinh ra (177
nút) với hàm mà router chỉ đến. Nó tìm thêm một nút chết nữa: `a|php_pm`
(PHP Process Manager) chưa từng có handler nào, đã đưa vào bảng `_SSH_ONLY`.

### 16.11. Script test không được chạm vào cấu hình thật

Script test render màn hình ghi token giả thẳng vào
`/var/hostvn/.telegram_bot.conf` để `config.py` import được. Chạy lại nó trên
máy đang chạy thật đã **đè mất token**, bot crash-loop 18 lần.

Nay `config.py` đọc đường dẫn từ biến môi trường `HOSTVN_TGBOT_CONF` (mặc
định vẫn là file cũ), nên test dùng file riêng ở `/tmp`.

### 16.12. Ghi chú vận hành

- **Sau khi sửa mã nguồn bot phải `hostvn-bot restart`** — Python nạp module
  một lần lúc khởi chạy. Lỗi này đã vấp nhiều lần trong đợt.
- **Sửa repo không có nghĩa là máy đã cập nhật.** Push và deploy là hai việc
  độc lập; đã vấp ba lần trong đợt (quên deploy nhóm file shell, quên restart,
  quên deploy sang ARM64).
- Gateway telecloud dùng `gofakes3` — không hỗ trợ liệt kê theo prefix, không
  cho ghi đè, phản hồi lỗi cả khi ghi thành công. Mọi thao tác với nó phải
  **xác minh bằng đọc lại**, không tin mã thoát.
