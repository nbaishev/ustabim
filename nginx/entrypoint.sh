#!/bin/sh
set -eu

HTTPS_CONF="/etc/nginx/nginx.https.conf"
HTTP_CONF="/etc/nginx/nginx.http.conf"
TARGET_CONF="/etc/nginx/nginx.conf"
CERT_PATH="/etc/letsencrypt/live/ustabim.online/fullchain.pem"

use_http() {
  cp "$HTTP_CONF" "$TARGET_CONF"
  echo "Using HTTP-only nginx config."
}

use_https() {
  cp "$HTTPS_CONF" "$TARGET_CONF"
  echo "Using HTTPS nginx config."
}

watch_cert() {
  last_sig=""

  if [ -f "$CERT_PATH" ]; then
    last_sig="$(cksum "$CERT_PATH")"
  fi

  while :; do
    if [ -f "$CERT_PATH" ]; then
      current_sig="$(cksum "$CERT_PATH")"

      if [ "$current_sig" != "$last_sig" ]; then
        use_https
        nginx -s reload
        last_sig="$current_sig"
      fi
    fi

    sleep 60
  done
}

if [ -f "$CERT_PATH" ]; then
  use_https
else
  use_http
fi

watch_cert &

exec nginx -g 'daemon off;'
