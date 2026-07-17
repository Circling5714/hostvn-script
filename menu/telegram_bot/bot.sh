#!/bin/bash

######################################################################
#           Auto Install & Optimize LEMP Stack on Ubuntu             #
#                                                                    #
#                Author: Sanvv - HOSTVN Technical                    #
#                  Website: https://hostvn.vn                        #
#                                                                    #
#              Please do not remove copyright. Thank!                #
#  Please do not copy under any circumstance for commercial reason!  #
######################################################################
#
# Telegram bot dieu khien server. Chay boi systemd (hostvn-telegram-bot.service).
# Cau hinh: /var/hostvn/.telegram_bot.conf
#   BOT_TOKEN          - token cua bot
#   ALLOWED_CHAT_IDS   - danh sach chat id duoc phep (cach nhau boi dau phay)
#   BOT_MODE           - notify | menu | shell
#
# BAO MAT: chi chat id nam trong ALLOWED_CHAT_IDS moi duoc xu ly. Moi tin nhan
# tu chat id khac deu bi bo qua. Che do "shell" cho phep chay lenh bat ky nen
# chi bat khi ban hieu ro rui ro (token lo = toan quyen server).

CONF="/var/hostvn/.telegram_bot.conf"
[ -f "${CONF}" ] || { echo "Thieu ${CONF}"; exit 1; }
# shellcheck disable=SC1090
source "${CONF}"

API="https://api.telegram.org/bot${BOT_TOKEN}"
OFFSET_FILE="/var/hostvn/.telegram_bot.offset"
STATE_FILE="/var/hostvn/.telegram_bot.state"

tg_send() {
    local chat="$1" text="$2"
    # Cat bot output qua dai (gioi han Telegram ~4096 ky tu)
    text="${text:0:3900}"
    curl -s --max-time 20 -o /dev/null \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${text}" \
        "${API}/sendMessage" >/dev/null 2>&1
}

_is_allowed() {
    local id="$1"
    IFS=',' read -ra allow <<< "${ALLOWED_CHAT_IDS}"
    for a in "${allow[@]}"; do
        [ "$(echo "$a" | tr -d ' ')" == "${id}" ] && return 0
    done
    return 1
}

_broadcast() {
    IFS=',' read -ra allow <<< "${ALLOWED_CHAT_IDS}"
    for a in "${allow[@]}"; do
        tg_send "$(echo "$a" | tr -d ' ')" "$1"
    done
}

_help_text() {
    local t="HOSTVN Bot - che do: ${BOT_MODE}
/status  - Tong quan he thong
/services- Trang thai Nginx/MariaDB/PHP
/disk    - Dung luong o dia
/ram     - Bo nho
/uptime  - Thoi gian hoat dong"
    if [[ "${BOT_MODE}" == "menu" || "${BOT_MODE}" == "shell" ]]; then
        t="${t}
/restart_nginx
/restart_php
/restart_mariadb
/reboot  - Khoi dong lai (can xac nhan)"
    fi
    if [[ "${BOT_MODE}" == "shell" ]]; then
        t="${t}
/sh <lenh> - Chay lenh shell bat ky"
    fi
    echo "${t}"
}

_php_fpm_unit() {
    systemctl list-units --type=service --all 2>/dev/null | grep -oE 'php[0-9.]+-fpm.service' | head -1
}

_status_text() {
    local php_unit; php_unit=$(_php_fpm_unit)
    echo "=== HOSTVN Server ===
Host: $(hostname)
Uptime: $(uptime -p 2>/dev/null)
Nginx: $(systemctl is-active nginx 2>/dev/null)
MariaDB: $(systemctl is-active mariadb 2>/dev/null)
PHP-FPM: $(systemctl is-active "${php_unit}" 2>/dev/null)
--- Disk ---
$(df -h / | tail -1 | awk '{print $3" / "$2" ("$5")"}')
--- RAM ---
$(free -h | awk '/Mem:/{print $3" / "$2}')"
}

# Xu ly 1 tin nhan lenh
_handle() {
    local chat="$1" text="$2"
    local cmd arg
    cmd=$(echo "${text}" | awk '{print $1}')
    arg=$(echo "${text}" | cut -s -d' ' -f2-)

    case "${cmd}" in
        /start|/help) tg_send "${chat}" "$(_help_text)" ;;
        /status)   tg_send "${chat}" "$(_status_text)" ;;
        /services)
            local php_unit; php_unit=$(_php_fpm_unit)
            tg_send "${chat}" "Nginx: $(systemctl is-active nginx)
MariaDB: $(systemctl is-active mariadb)
${php_unit}: $(systemctl is-active "${php_unit}")" ;;
        /disk)   tg_send "${chat}" "$(df -h / | sed -n '1,2p')" ;;
        /ram)    tg_send "${chat}" "$(free -h)" ;;
        /uptime) tg_send "${chat}" "$(uptime)" ;;
        /restart_nginx)
            [[ "${BOT_MODE}" == "notify" ]] && { tg_send "${chat}" "Che do notify khong cho phep dieu khien."; return; }
            systemctl restart nginx && tg_send "${chat}" "Da restart Nginx: $(systemctl is-active nginx)" ;;
        /restart_php)
            [[ "${BOT_MODE}" == "notify" ]] && { tg_send "${chat}" "Che do notify khong cho phep dieu khien."; return; }
            local php_unit; php_unit=$(_php_fpm_unit)
            systemctl restart "${php_unit}" && tg_send "${chat}" "Da restart ${php_unit}: $(systemctl is-active "${php_unit}")" ;;
        /restart_mariadb)
            [[ "${BOT_MODE}" == "notify" ]] && { tg_send "${chat}" "Che do notify khong cho phep dieu khien."; return; }
            systemctl restart mariadb && tg_send "${chat}" "Da restart MariaDB: $(systemctl is-active mariadb)" ;;
        /reboot)
            [[ "${BOT_MODE}" == "notify" ]] && { tg_send "${chat}" "Che do notify khong cho phep dieu khien."; return; }
            tg_send "${chat}" "Xac nhan khoi dong lai server? Gui /reboot_yes trong 60 giay." ;;
        /reboot_yes)
            [[ "${BOT_MODE}" == "notify" ]] && return
            tg_send "${chat}" "Server dang khoi dong lai..."; ( sleep 2; reboot ) & ;;
        /sh)
            if [[ "${BOT_MODE}" != "shell" ]]; then
                tg_send "${chat}" "Lenh /sh chi kha dung o che do shell."
            elif [ -z "${arg}" ]; then
                tg_send "${chat}" "Cu phap: /sh <lenh>"
            else
                local out; out=$(timeout 30 bash -c "${arg}" 2>&1)
                tg_send "${chat}" "\$ ${arg}
${out:-（khong co output）}"
            fi ;;
        *) tg_send "${chat}" "Lenh khong ho tro. Go /help de xem danh sach." ;;
    esac
}

# Vong giam sat dich vu + o dia (chay nen), gui canh bao qua bot
_monitor_loop() {
    local disk_alerted=0
    declare -A svc_down
    while true; do
        local php_unit; php_unit=$(_php_fpm_unit)
        for svc in nginx mariadb "${php_unit}"; do
            [ -z "${svc}" ] && continue
            if [ "$(systemctl is-active "${svc}" 2>/dev/null)" != "active" ]; then
                if [ -z "${svc_down[$svc]}" ]; then
                    _broadcast "CANH BAO: dich vu ${svc} KHONG hoat dong tren $(hostname)."
                    svc_down[$svc]=1
                fi
            else
                svc_down[$svc]=""
            fi
        done
        local usage; usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
        if [ "${usage}" -ge 90 ]; then
            [ "${disk_alerted}" -eq 0 ] && { _broadcast "CANH BAO: o dia da dung ${usage}% tren $(hostname)."; disk_alerted=1; }
        else
            disk_alerted=0
        fi
        sleep 300
    done
}

# ============ MAIN ============
_broadcast "HOSTVN Bot da khoi dong (che do: ${BOT_MODE}). Go /help."

_monitor_loop &
MON_PID=$!
trap 'kill ${MON_PID} 2>/dev/null' EXIT

offset=$(cat "${OFFSET_FILE}" 2>/dev/null || echo 0)

while true; do
    resp=$(curl -s --max-time 60 "${API}/getUpdates?timeout=50&offset=${offset}")
    [ -z "${resp}" ] && { sleep 3; continue; }
    echo "${resp}" | jq -e '.ok == true' >/dev/null 2>&1 || { sleep 3; continue; }

    count=$(echo "${resp}" | jq '.result | length')
    [ "${count}" -eq 0 ] && continue

    for i in $(seq 0 $((count - 1))); do
        update_id=$(echo "${resp}" | jq -r ".result[$i].update_id")
        chat_id=$(echo "${resp}" | jq -r ".result[$i].message.chat.id // empty")
        text=$(echo "${resp}" | jq -r ".result[$i].message.text // empty")
        offset=$((update_id + 1))
        echo "${offset}" > "${OFFSET_FILE}"

        [ -z "${chat_id}" ] && continue
        if ! _is_allowed "${chat_id}"; then
            # Bo qua tin nhan tu chat id khong duoc phep
            continue
        fi
        [ -n "${text}" ] && _handle "${chat_id}" "${text}"
    done
done
