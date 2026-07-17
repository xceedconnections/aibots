#!/bin/bash
set -euo pipefail

PUBLIC_IP="${PUBLIC_IP:-127.0.0.1}"
VICIDIAL_IP="${ASTERISK_AMI_HOST:-${VICIDIAL_IP:-127.0.0.1}}"
SIP_PASS="${AIBOTS_SIP_PASSWORD:-aibotsSipPass123}"
AMI_SECRET="${ASTERISK_AMI_SECRET:-ami_secret}"

echo "==> Rendering Asterisk configs (PUBLIC_IP=$PUBLIC_IP VICIDIAL_IP=$VICIDIAL_IP)"

sed -i "s|PUBLIC_IP|${PUBLIC_IP}|g" /etc/asterisk/pjsip.conf
sed -i "s|VICIDIAL_IP|${VICIDIAL_IP}|g" /etc/asterisk/pjsip.conf
sed -i "s|AIBOTS_SIP_PASSWORD|${SIP_PASS}|g" /etc/asterisk/pjsip.conf
sed -i "s|AIBOTS_AMI_SECRET|${AMI_SECRET}|g" /etc/asterisk/manager.conf

# Ensure curl works inside dialplan (asterisk may need curl binary)
command -v curl >/dev/null || true

exec asterisk -f -vvv
