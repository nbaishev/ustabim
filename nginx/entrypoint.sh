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

if [ -f "$CERT_PATH" ]; then
  use_https
else
  use_http
  # When cert appears, swap config and reload.
  (
    while [ ! -f "$CERT_PATH" ]; do
      sleep 5
    done
    use_https
    nginx -s reload
  ) &
fi

exec nginx -g 'daemon off;'
