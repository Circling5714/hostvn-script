<p align="center"><strong>Auto Install & Optimize LEMP Stack on Ubuntu (22.04, 24.04, 26.04)</strong></p>
<p align="center"><strong>##############################################</strong></p>

This is a shell script used to install LEMP Stack (Nginx - MariaDB - PHP-FPM) on Ubuntu 22.04 / 24.04 / 26.04 LTS.

> Đây là bản **rebuild** từ HOSTVN Script gốc (vốn chỉ hỗ trợ Ubuntu 18.04/20.04), được cập nhật để tương thích với các phiên bản Ubuntu LTS mới nhất.

<b>Please do not copy or distribute this for commercial purposes, donations. Thank you.</b>

## 1. Script Details:

### 1.1. Installation

- Nginx **1.30.x** (stable) build từ source với **PCRE2 + OpenSSL 3 của hệ thống**, hỗ trợ **HTTP/2 + HTTP/3**, kèm module: ngx_cache_purge (fork nginx-modules), headers-more, brotli, vts.
- MariaDB **11.8 LTS** (repo chính thức, tự fallback về gói distro nếu repo chưa hỗ trợ bản Ubuntu mới).
- PHP đa phiên bản qua PPA ondrej/php: **8.4, 8.3, 8.2, 7.4** (chọn được 2 bản chạy song song).
- phpMyAdmin **5.2.x**.
- Configure Nginx FastCGI cache, Brotli Compress.
- Install PHPMemcachedAdmin, phpRedisAdmin, Opcache Dashboard.
- Install memcached, redis cache (not enabled by default) — PHP extension build từ **PECL chính thức**.
- Install Fail2ban, Let's Encrypt SSL (acme.sh), CloudFlare DNS API.
- Install WP-CLI, Composer, supervisor, Rclone, ClamAV, ImunifyAV.
- DO NOT COLLECT ANY INFORMATION ON YOUR VPS.

### 1.2. Thay đổi so với bản gốc (rebuild 2026)

- ✅ Hỗ trợ Ubuntu **22.04 / 24.04 / 26.04** (bỏ 18.04/20.04, Debian).
- ✅ Nginx 1.24 → **1.30.4**; bỏ OpenSSL 1.1.1t (EOL) và PCRE 8.45 tĩnh → dùng **OpenSSL 3 + PCRE2** của hệ thống, thêm **HTTP/3**.
- ✅ MariaDB 10.11 → **11.8 LTS**; bỏ SHA256 hardcode của `mariadb_repo_setup` → dùng keyring + deb822 sources chính thức.
- ✅ PHP mặc định 8.2 → **8.4**; sửa điều kiện gói `php-json` (PHP 8+ đã tích hợp sẵn).
- ✅ Kiểm tra PPA ondrej/php có hỗ trợ suite trước khi thêm (Ubuntu 26.04 fallback về PHP distro).
- ✅ Thay `mysql_secure_installation` heredoc bằng SQL trực tiếp (root giữ cả unix_socket + password auth).
- ✅ Set `DEBIAN_FRONTEND=noninteractive` + `NEEDRESTART_MODE=a` (tránh treo prompt needrestart trên 22.04+).
- ✅ Sửa tên gói apt cho Ubuntu mới: `python3`, `libncurses-dev`, `libaio-dev`, `libpcre2-dev`…
- ✅ PHP extension (redis/memcached/igbinary) tải từ **PECL chính thức** thay vì server hostvn đã chết.
- ✅ NodeJS 12/14 → **NodeJS 22 LTS** (NodeSource keyring + repo nodistro).
- ✅ ImunifyAV mở khoá cho 20.04/22.04/24.04/26.04 (trước chỉ 18.04).
- ✅ Cài đặt **local-first**: ưu tiên file trong repo đã clone, fallback tải online (link chỉnh trong 1 biến).
- ✅ Sửa bug menu update tải sai file; nginx `listen 443 ssl` + `http2 on;` theo syntax mới.
- ❌ **Bỏ ngx_pagespeed** — Google đã ngừng phát triển, không có binary PSOL và không compile được trên toolchain mới.
- ❌ Bỏ Nextcloud auto-install (phụ thuộc bundle từ server gốc đã ngừng hoạt động).

### 1.3. Bot Telegram điều khiển bằng menu

Toàn bộ 15 nhóm menu của shell `hostvn` được mirror thành **nút bấm trên Telegram** — quản trị server không cần mở SSH.

- Menu chính ghim cố định ở đáy khung chat (16 nhóm: Domain, LEMP, WordPress, SSL, Cache, Backup, Firewall, Dịch vụ, Hệ thống, VPS, Công cụ, Phân quyền, Thông tin Acc, Cronjob, Update, Ngôn ngữ).
- **Thanh tiến trình động** cho mọi tác vụ chạy lâu.
- **Phân quyền theo từng chat**: admin thấy đủ, chat khác chỉ thấy nhóm được cấp.
- Thao tác cần nhập nhiều bước (nén ảnh, deploy, đổi port admin…) bot chỉ đường sang SSH thay vì làm nửa vời.

Cài: `hostvn` → **Telegram Notify** → **5**. Script tự dựng venv Python riêng và tạo service `hostvn-telegram-bot`.
Chi tiết kỹ thuật: [PROJECT.md §15](PROJECT.md).

### 1.4. Optimization & Security & WordPress & Backup

Giữ nguyên đầy đủ tính năng bản gốc: tối ưu cấu hình theo tài nguyên VPS, chạy 2 phiên bản PHP song song, mỗi website một user riêng, Fail2ban, đổi port SSH, quản trị WordPress (cache plugin, backup GG Drive/local qua Rclone, đổi domain, update plugin...), firewall, Telegram notify... Xem menu `hostvn` sau khi cài.

## 2. Requirements

- VPS tối thiểu 512MB RAM, chưa cài dịch vụ nào.
- **Ubuntu 22.04, 24.04 hoặc 26.04 LTS** (26.04 ở chế độ experimental — PPA ondrej/php có thể chưa hỗ trợ).

## 3. Installation

### Cách 1: Cài từ repo clone (khuyến nghị)

```sh
apt update && apt install git -y
git clone https://github.com/Circling5714/hostvn-script.git hostvn-script
cd hostvn-script && bash install
```

### Cách 2: Cài online (qua GitHub Pages)

```sh
wget https://circling5714.github.io/hostvn-script/install && bash install
```

Link tải mặc định đặt tại biến `SCRIPT_LINK`/`HOSTVN_SCRIPT_LINK` trong `install` và `UPDATE_LINK` trong `menu/helpers/variable_common` — nếu fork thì đổi về repo của bạn trước khi phân phối.

### Cài trên Proxmox LXC

Script tự phát hiện môi trường container và bỏ qua tạo swap, kernel tweak, đồng thời tắt MariaDB native AIO. Yêu cầu: template Ubuntu 22.04/24.04, unprivileged OK, **bật `nesting=1`**, RAM ≥ 2GB khi cài (compile nginx). Swap cấu hình ở Proxmox → Resources.

**Lưu ý cho dev:** sau khi sửa bất kỳ file nào trong `menu/`, phải đóng gói lại: `tar -czf menu.tar.gz menu` (line-ending LF).

## 4. Software download sources

- Nginx: http://nginx.org/en/download.html
- MariaDB: https://mariadb.org/
- PHP: https://launchpad.net/~ondrej/+archive/ubuntu/php
- phpMyAdmin: https://www.phpmyadmin.net/
- ngx_cache_purge: https://github.com/nginx-modules/ngx_cache_purge
- headers-more: https://github.com/openresty/headers-more-nginx-module
- nginx-module-vts: https://github.com/vozlt/nginx-module-vts
- PECL (redis/memcached/igbinary): https://pecl.php.net/
- NodeSource: https://github.com/nodesource/distributions
- PHPMemcachedAdmin: https://github.com/elijaa/phpmemcachedadmin
- phpRedisAdmin: https://github.com/erikdubbelboer/phpRedisAdmin
- Rclone: https://rclone.org/
- WP-CLI: https://wp-cli.org/
- Composer: https://getcomposer.org/
- ClamAV: https://www.clamav.net/
- ImunifyAV: https://www.imunify360.com/antivirus

## 5. Credits

### Original Developers / Maintainers
- Sanvv (HOSTVN)
- f97

### Rebuild for modern Ubuntu
- QMV (2026)
