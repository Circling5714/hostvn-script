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
# Helper dong bo dinh tuyen domain len Cloudflare Tunnel.
# Cach dung:
#   cf_tunnel.sh add-dns <domain>     -> tao CNAME <domain> (+www) tro vao tunnel
#   cf_tunnel.sh del-dns <domain>     -> xoa CNAME <domain> (+www)
#   cf_tunnel.sh zone-id <domain>     -> in ra zone id
#
# Cau hinh: /var/hostvn/.cf_tunnel.conf
#   CF_API_TOKEN   - token co quyen Account:Cloudflare Tunnel:Edit + Connectors:Edit, Zone:DNS:Edit
#   CF_ACCOUNT_ID  - account id
#   CF_TUNNEL_ID   - tunnel id (dung lam noi dung CNAME: <id>.cfargotunnel.com)

CONF="/var/hostvn/.cf_tunnel.conf"
[ -f "${CONF}" ] || { echo "Thieu ${CONF}"; exit 1; }
# shellcheck disable=SC1090
source "${CONF}"

API="https://api.cloudflare.com/client/v4"
AUTH="Authorization: Bearer ${CF_API_TOKEN}"

# Tim zone id cho 1 domain (thu ca domain cha neu la subdomain)
_zone_id() {
    local name="$1" zid=""
    while [ -n "${name}" ]; do
        zid=$(curl -s --max-time 15 "${API}/zones?name=${name}" -H "${AUTH}" | jq -r '.result[0].id // empty' 2>/dev/null)
        [ -n "${zid}" ] && { echo "${zid}"; return 0; }
        if [[ "${name}" == *.*.* ]]; then name="${name#*.}"; else break; fi
    done
    return 1
}

# Tao/cap nhat 1 ban ghi CNAME proxied tro vao tunnel
_upsert_cname() {
    local zone="$1" host="$2"
    local content="${CF_TUNNEL_ID}.cfargotunnel.com"
    # Neu da ton tai ban ghi -> cap nhat, chua co -> tao moi
    local rec_id
    rec_id=$(curl -s --max-time 15 "${API}/zones/${zone}/dns_records?name=${host}&type=CNAME" -H "${AUTH}" \
        | jq -r '.result[0].id // empty' 2>/dev/null)
    if [ -n "${rec_id}" ]; then
        curl -s --max-time 15 -X PUT "${API}/zones/${zone}/dns_records/${rec_id}" -H "${AUTH}" \
            -H "Content-Type: application/json" \
            --data "{\"type\":\"CNAME\",\"name\":\"${host}\",\"content\":\"${content}\",\"proxied\":true}" >/dev/null 2>&1
    else
        curl -s --max-time 15 -X POST "${API}/zones/${zone}/dns_records" -H "${AUTH}" \
            -H "Content-Type: application/json" \
            --data "{\"type\":\"CNAME\",\"name\":\"${host}\",\"content\":\"${content}\",\"proxied\":true}" >/dev/null 2>&1
    fi
}

_delete_record() {
    local zone="$1" host="$2"
    local rec_id
    rec_id=$(curl -s --max-time 15 "${API}/zones/${zone}/dns_records?name=${host}" -H "${AUTH}" \
        | jq -r '.result[0].id // empty' 2>/dev/null)
    [ -n "${rec_id}" ] && curl -s --max-time 15 -X DELETE "${API}/zones/${zone}/dns_records/${rec_id}" -H "${AUTH}" >/dev/null 2>&1
}

case "$1" in
    add-dns)
        domain="$2"; [ -z "${domain}" ] && exit 1
        zone=$(_zone_id "${domain}") || { echo "khong tim thay zone cho ${domain}"; exit 1; }
        _upsert_cname "${zone}" "${domain}"
        # them www neu la domain goc (khong phai subdomain sau nhieu cap)
        _upsert_cname "${zone}" "www.${domain}"
        echo "ok"
        ;;
    del-dns)
        domain="$2"; [ -z "${domain}" ] && exit 1
        zone=$(_zone_id "${domain}") || exit 0
        _delete_record "${zone}" "${domain}"
        _delete_record "${zone}" "www.${domain}"
        echo "ok"
        ;;
    zone-id)
        _zone_id "$2"
        ;;
    *)
        echo "usage: cf_tunnel.sh {add-dns|del-dns|zone-id} <domain>"
        exit 1
        ;;
esac
