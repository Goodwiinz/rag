#!/bin/sh
set -eu

endpoint=${AZURE_OPENAI_CHAT_ENDPOINT:?AZURE_OPENAI_CHAT_ENDPOINT is required}
allowed_host=$(printf '%s' "$endpoint" | sed -E 's#^[A-Za-z][A-Za-z0-9+.-]*://([^/:]+).*#\1#')

case "$allowed_host" in
  ""|*[!A-Za-z0-9.-]*)
    echo "invalid model endpoint hostname" >&2
    exit 64
    ;;
esac

cat >/etc/squid/squid.conf <<EOF
http_port 3128
acl SSL_ports port 443
acl CONNECT method CONNECT
acl approved_model dstdomain $allowed_host
http_access deny CONNECT !SSL_ports
http_access allow approved_model
http_access deny all
access_log none
cache_log /var/log/squid/cache.log
cache deny all
shutdown_lifetime 0 seconds
EOF

exec squid -N -f /etc/squid/squid.conf
