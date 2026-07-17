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

Môi trường: Proxmox LXC 10.0.0.10, 4GB RAM / 2 cores, unprivileged. Lưu ý: template gốc là Ubuntu 24.10 lai sources noble → đã ép đồng bộ toàn bộ userland về **noble 24.04 thật** (pin 1001 + downgrade 239 gói) trước khi test. Test tự động hoá: cài trong tmux + daemon tự trả lời 5 prompt + monitor log từ xa.

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
