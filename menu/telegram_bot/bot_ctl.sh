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
# hostvn-bot — dieu khien bot Telegram bang mot dong lenh.
#
# Vi sao can: sau khi cap nhat ma nguon bot thi PHAI khoi dong lai, vi Python
# nap module mot lan luc chay chu khong doc lai file tren dia. Truoc day muon
# lam viec do phai vao hostvn -> Telegram Notify -> chon trong menu.
#
#   hostvn-bot restart | start | stop | status | log

source /var/hostvn/menu/helpers/environment 2>/dev/null

SERVICE_NAME="hostvn-telegram-bot"
BOT_DIR="/var/hostvn/menu/telegram_bot"
CONF="/var/hostvn/.telegram_bot.conf"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

_active() {
    if command -v _svc_active >/dev/null 2>&1; then
        _svc_active "${SERVICE_NAME}" && return 0
        return 1
    fi
    [ "$(systemctl is-active "${SERVICE_NAME}" 2>/dev/null)" = "active" ]
}

_do() {
    if command -v _svc >/dev/null 2>&1; then
        _svc "$1" "${SERVICE_NAME}"
    else
        systemctl "$1" "${SERVICE_NAME}" >/dev/null 2>&1
    fi
}

_status() {
    if _active; then
        local mode pid
        mode=$(grep -m1 '^BOT_MODE=' "${CONF}" 2>/dev/null | cut -d= -f2 | tr -d "\"'")
        pid=$(pgrep -f "telegram_bot/bot.py" | head -1)
        printf "${GREEN}%s${NC}\n" "Bot dang chay (che do: ${mode:-?}${pid:+, pid ${pid}})."
    else
        printf "${RED}%s${NC}\n" "Bot khong chay."
        [ -f "${CONF}" ] || printf "%s\n" "Chua cau hinh: hostvn -> Telegram Notify -> 5."
    fi
}

_log() {
    if [ -f /root/tgbot.log ]; then
        tail -n "${1:-30}" /root/tgbot.log
    else
        journalctl -u "${SERVICE_NAME}" -n "${1:-30}" --no-pager 2>/dev/null \
            || printf "%s\n" "Khong tim thay log."
    fi
}

case "${1:-status}" in
    restart)
        if [ ! -f "${CONF}" ]; then
            printf "${RED}%s${NC}\n" "Chua cau hinh bot. Vao: hostvn -> Telegram Notify -> 5."
            exit 1
        fi
        # Kiem cu phap TRUOC khi khoi dong lai — tranh tinh trang tat bot cu
        # roi bot moi khong len duoc vi ma nguon loi.
        if [ -x "${BOT_DIR}/venv/bin/python" ]; then
            if ! "${BOT_DIR}/venv/bin/python" -m py_compile "${BOT_DIR}"/*.py 2>/dev/null; then
                printf "${RED}%s${NC}\n" "Ma nguon bot co loi cu phap — khong khoi dong lai."
                "${BOT_DIR}/venv/bin/python" -m py_compile "${BOT_DIR}"/*.py
                exit 1
            fi
        fi
        printf "%s\n" "Dang khoi dong lai bot..."
        _do restart
        sleep 6
        _status
        ;;
    start)  _do start;  sleep 4; _status ;;
    stop)   _do stop;   sleep 2; _status ;;
    status) _status ;;
    log)    _log "${2:-30}" ;;
    *)
        printf "%s\n" "Dung: hostvn-bot {restart|start|stop|status|log [so_dong]}"
        exit 1
        ;;
esac
