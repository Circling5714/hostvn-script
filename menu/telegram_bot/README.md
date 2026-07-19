# Telegram Control Bot cho HostVN Scripts

Bot Telegram cung cấp giao diện quản trị HostVN bằng nút bấm, chạy được cả trên
máy dùng `systemd`. Backend chính viết bằng
Python bất đồng bộ (`python-telegram-bot`); `bot.sh` là bản dự phòng khi môi
trường Python chưa cài được.

## Cài đặt và cấu hình

Trong menu `hostvn`, đi theo đường dẫn `13` → `8` → `5`:

```text
hostvn
 └─ 13. Công cụ
     └─ 8. Enable/Disable Telegram notify
         └─ 5. Telegram Bot điều khiển server
```

rồi chọn **Cài đặt / Cấu hình lại**.

Bạn cần:

- Bot Token tạo bởi [@BotFather](https://t.me/BotFather).
- Ít nhất một Chat ID được phép sử dụng. Trình cài đặt có thể tự dò sau khi bạn
  gửi một tin nhắn cho bot; nhiều ID được phân cách bằng dấu phẩy.
- Kết nối Internet để cài `python-telegram-bot>=20,<22` vào virtual environment
  riêng ở `/var/hostvn/menu/telegram_bot/venv`.

Cấu hình được lưu tại `/var/hostvn/.telegram_bot.conf`, quyền `600`:

```sh
BOT_TOKEN="123456:token"
ALLOWED_CHAT_IDS="123456789,-1001234567890"
BOT_MODE="menu"
```

Sau khi cài, mở bot và dùng `/start`, `/menu` hoặc nút **MENU HOSTVN**.

## Chế độ hoạt động

| Chế độ | Quyền |
|---|---|
| `notify` | Nhận cảnh báo và xem thông tin; mọi thao tác ghi bị chặn. |
| `menu` | Xem và thực hiện các thao tác quản trị định sẵn; khuyến nghị. |
| `shell` | Tên chế độ tương thích cấu hình cũ; backend Python hiện xử lý quyền như `menu`. |

Backend hiện tại chỉ đăng ký `/start`, `/menu` và `/cancel`; **không cung cấp
`/sh`**. Trình cấu hình vẫn hiển thị lựa chọn `shell` để tương thích cấu hình cũ,
nhưng nên dùng `menu` để thể hiện đúng quyền đang có. Nếu bổ sung lại tính năng
chạy lệnh root trong tương lai, cần xem Bot Token như một thông tin đăng nhập root.

`ALLOWED_CHAT_IDS` là whitelist bắt buộc. Có thể thêm `ADMIN_IDS` vào file cấu
hình nếu chỉ muốn một số Chat ID trong whitelist được thực hiện thao tác ghi;
nếu không khai báo, toàn bộ `ALLOWED_CHAT_IDS` được xem là admin.

## Nhóm chức năng

Menu chính có **16 nút**, ánh xạ 1:1 với 15 mục của menu shell `hostvn`:

| Nút trên bot | Mục shell tương ứng |
|---|---|
| 🌐 Domain | 1. Quản lý tên miền (13 mục) |
| 🧱 LEMP | 4. Quản lý LEMP → Nginx / **PHP** / **Database** / Log |
| 📝 WordPress | 7. Quản lý WordPress (10 + 2 plugins + 11 nâng cao) |
| 🔒 SSL | 2. Quản lý SSL |
| ⚡ Cache | 3. Quản lý Cache |
| 💾 Backup | 8. Sao lưu / Khôi phục |
| 🛡️ Firewall | 5. Quản lý Firewall |
| 🔧 Dịch vụ | điều khiển service (rộng hơn shell: thêm redis, memcached, cloudflared…) |
| 🖥️ Hệ thống | trạng thái tổng quan (bot bổ sung) |
| ⚙️ VPS | 10. Quản lý VPS |
| 🛠️ Công cụ | 13. Công cụ **+ 9. Admin Tool** (submenu) |
| 🔐 Phân quyền | 6. Phân quyền Chown/Chmod |
| 👤 Thông tin Acc | 11. Xem thông tin tài khoản |
| ⏰ Cronjob | 12. Cronjob / Auto Backup |
| 🔄 Update HostVN | 14. Cập nhật HostVN Scripts |
| 🌐 Change language | 15. Change language |

> **PHP và Database không phải nút riêng** — chúng nằm trong 🧱 **LEMP**, đúng như
> cách menu shell gom nhóm.

Mọi thao tác đều hiển thị **thanh tiến trình động** (`▰▰▰▰▱▱▱▱ 52%`) trong lúc chờ.
Vì các lệnh nền không báo phần trăm thật, thanh chạy tiệm cận tới ~96% rồi nhảy
100% khi xong; tác vụ dài (tạo domain, backup, restore) còn hiện tên bước đang chạy.

Các thao tác có khả năng phá huỷ hoặc ảnh hưởng dịch vụ đều có bước xác nhận.
Một số luồng cần nhập nhiều dữ liệu hoặc dễ gây lỗi vẫn được hướng dẫn thực hiện
qua SSH; bot không giả lập những chức năng đó.

Lưu ý bảo mật:

- Màn hình thông tin tài khoản có thể hiển thị mật khẩu SFTP, database và Admin
  Tool. Hãy xoá tin nhắn sau khi xem.
- Nút xoá cronjob xoá toàn bộ crontab của root, kể cả lịch đồng bộ MariaDB tmpfs.
- Cập nhật HostVN Scripts thay toàn bộ thư mục `menu/`, sau đó bot tự khởi động
  lại để nạp mã mới.
- Đổi ngôn ngữ chỉ tác động menu shell khi chạy `hostvn`; giao diện bot hiện dùng
  tiếng Việt.

## Vận hành và xử lý sự cố

```sh
# Kiểm tra trạng thái qua lớp service tương thích của HostVN
hostvn        # 13. Công cụ → 8. Telegram notify → 5. Telegram Bot → Xem trạng thái

# Hoặc qua systemctl
source /var/hostvn/menu/helpers/environment
systemctl is-active hostvn-telegram-bot
systemctl restart  hostvn-telegram-bot

# Máy có systemd
systemctl status hostvn-telegram-bot
journalctl -u hostvn-telegram-bot -n 100 --no-pager

# Log của bot
tail -n 50 /root/tgbot.log

# Chạy thử ở foreground để xem lỗi ngay (Ctrl+C để dừng).
# LƯU Ý: dừng bot đang chạy trước, nếu không Telegram trả lỗi 409 Conflict
# vì hai tiến trình cùng poll một token.
systemctl stop hostvn-telegram-bot
cd /var/hostvn/menu/telegram_bot && venv/bin/python bot.py
```

Trình cài đặt tạo service `hostvn-telegram-bot` trên systemd, trỏ thẳng vào
`venv/bin/python bot.py`. Không cần tự tạo
unit giả.

Nếu bot rơi về bản Bash, kiểm tra virtual environment:

```sh
/var/hostvn/menu/telegram_bot/venv/bin/python -c "import telegram; print(telegram.__version__)"
```

Không commit hoặc gửi cho người khác file `.telegram_bot.conf`. Khi nghi ngờ lộ
token, thu hồi token tại BotFather, cấu hình lại bot và kiểm tra danh sách Chat ID.

## Sao lưu lên cloud

Khi backup, bot hỏi **nơi lưu** trước khi chạy:

```
💽 Lưu trên máy (Local)
☁️ <tên remote>          ← mỗi kết nối rclone một nút
```

Đẩy lên cloud xong thì bản trên máy được xoá (giống shell). Nếu đẩy thất bại,
bản trên máy **được giữ nguyên** để không mất dữ liệu.

Màn hình khôi phục hiện cả hai nguồn:

```
💽 2026-07-19                        ← bản trên máy
☁️ 2026-07-19_090725 · <remote>      ← bản trên cloud
```

### Sổ mục lục backup

Một số gateway S3 (ví dụ loại lưu qua Telegram) **không hỗ trợ liệt kê theo
prefix** — đọc file theo đường dẫn chính xác thì được, nhưng liệt kê thư mục
luôn trả về rỗng. Với loại đó, cách dựng menu bằng `rclone lsf` sẽ báo "không
có backup" dù dữ liệu vẫn còn.

Nên mỗi lần backup, hostvn ghi lại **đã lưu gì ở đâu** vào sổ mục lục:

- ở máy: `/var/hostvn/.backup_index.<remote>`
- trên remote: `hostvn_backup_index_<IP>.txt` ở gốc remote

Mỗi dòng: `<ngày>|<domain>|<file1>,<file2>`. Restore đọc sổ này rồi tải từng
file theo đường dẫn chính xác. Nhờ sổ nằm cả trên remote nên cài lại VPS vẫn
khôi phục được.

## Điều khiển bot

```bash
hostvn-bot restart | start | stop | status | log [số_dòng]
```

`restart` kiểm cú pháp Python trước khi khởi động lại, tránh tắt bot cũ rồi
bot mới không lên được.

> **Sau khi sửa mã nguồn bot phải restart.** Python nạp module một lần lúc
> khởi chạy, không đọc lại file trên đĩa — sửa file xong mà không restart thì
> bot vẫn chạy mã cũ.

## Phân quyền

Xét theo **ID người bấm** (`effective_user.id`), không phải ID phòng chat.
Trong nhóm thì mọi thành viên đều bấm được nút của tin nhắn bot gửi, nên nếu
chỉ kiểm phòng chat thì ai ở trong nhóm cũng điều khiển được máy chủ bằng
quyền root.

Muốn dùng bot trong nhóm: thêm **ID người dùng** của từng người vào
`ALLOWED_CHAT_IDS` (hoặc `ADMIN_IDS`), không chỉ ID nhóm.

## Chạy thử không đụng cấu hình thật

`config.py` đọc đường dẫn cấu hình từ biến môi trường `HOSTVN_TGBOT_CONF`
(mặc định `/var/hostvn/.telegram_bot.conf`). Khi viết test, trỏ nó sang file
tạm — đừng ghi đè file thật, làm vậy sẽ mất token và bot crash-loop.

```bash
HOSTVN_TGBOT_CONF=/tmp/test.conf venv/bin/python your_test.py
```
