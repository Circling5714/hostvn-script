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
# Duoc Fail2ban goi khi ban/unban de dong bo len Cloudflare WAF
# (IP Access Rules, muc zone). Cach dung: cf_waf.sh <ban|unban> <ip>
# Cau hinh: /var/hostvn/.cf_waf.conf  (CF_WAF_TOKEN, CF_WAF_ZONE)

CONF="/var/hostvn/.cf_waf.conf"
[ -f "${CONF}" ] || exit 0
# shellcheck disable=SC1090
source "${CONF}"
[[ -z "${CF_WAF_TOKEN}" || -z "${CF_WAF_ZONE}" ]] && exit 0

action="$1"
ip="$2"
[ -z "${ip}" ] && exit 0

API="https://api.cloudflare.com/client/v4/zones/${CF_WAF_ZONE}/firewall/access_rules/rules"

case "${action}" in
    ban)
        curl -s --max-time 15 -X POST "${API}" \
            -H "Authorization: Bearer ${CF_WAF_TOKEN}" \
            -H "Content-Type: application/json" \
            --data "{\"mode\":\"block\",\"configuration\":{\"target\":\"ip\",\"value\":\"${ip}\"},\"notes\":\"fail2ban-hostvn\"}" \
            >/dev/null 2>&1
        ;;
    unban)
        rule_id=$(curl -s --max-time 15 -G "${API}" \
            -H "Authorization: Bearer ${CF_WAF_TOKEN}" \
            --data-urlencode "configuration.value=${ip}" \
            --data-urlencode "notes=fail2ban-hostvn" \
            | jq -r '.result[0].id // empty' 2>/dev/null)
        if [ -n "${rule_id}" ]; then
            curl -s --max-time 15 -X DELETE "${API}/${rule_id}" \
                -H "Authorization: Bearer ${CF_WAF_TOKEN}" >/dev/null 2>&1
        fi
        ;;
esac

exit 0
