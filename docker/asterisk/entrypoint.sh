#!/bin/bash
set -euo pipefail

PUBLIC_IP="${PUBLIC_IP:-127.0.0.1}"
VICIDIAL_IP="${ASTERISK_AMI_HOST:-${VICIDIAL_IP:-127.0.0.1}}"
AMI_SECRET="${ASTERISK_AMI_SECRET:-ami_secret}"

echo "==> Rendering Asterisk configs (PUBLIC_IP=$PUBLIC_IP VICIDIAL_IP=$VICIDIAL_IP SIP_MODE=ip)"

sed -i "s|PUBLIC_IP|${PUBLIC_IP}|g" /etc/asterisk/pjsip.conf
sed -i "s|VICIDIAL_IP|${VICIDIAL_IP}|g" /etc/asterisk/pjsip.conf
sed -i "s|AIBOTS_AMI_SECRET|${AMI_SECRET}|g" /etc/asterisk/manager.conf

# Ensure identify file exists (mounted from host data/asterisk)
if [[ ! -f /etc/asterisk/pjsip_identify.conf ]]; then
  cat > /etc/asterisk/pjsip_identify.conf <<EOF
; IP-based VICIdial peers — no SIP registration
[vicidial-identify]
type=identify
endpoint=vicidial
match=${VICIDIAL_IP}
EOF
fi

command -v curl >/dev/null || true

echo "==> Dialplan AudioSocket check:"
grep -n "AudioSocket\|new-uuid\|from-vicidial" /etc/asterisk/extensions.conf | head -20 || true

# Quick DNS check for AI worker (AudioSocket target)
getent hosts worker 2>/dev/null || ping -c1 -W1 worker 2>/dev/null || echo "WARN: cannot resolve worker"

exec asterisk -f -vvv
