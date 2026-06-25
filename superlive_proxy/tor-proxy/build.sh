#!/bin/bash
set -e

IMAGE="tor-proxy"
NAME="tor-proxy"
API_PORT="${API_PORT:-5000}"
SOCKS_PORT="${SOCKS_PORT:-9050}"

echo "==> Building $IMAGE..."
docker build -t "$IMAGE" .

echo "==> Removing old container if exists..."
docker rm -f "$NAME" 2>/dev/null || true

echo "==> Running $NAME..."
docker run -d \
    --name "$NAME" \
    -p "$API_PORT:5000" \
    -p "$SOCKS_PORT:9050" \
    --restart unless-stopped \
    "$IMAGE"

echo "==> Waiting for API..."
for i in $(seq 1 15); do
    if curl -sf "http://127.0.0.1:$API_PORT/status" >/dev/null 2>&1; then
        echo "  [*] API ready on port $API_PORT"
        curl -s "http://127.0.0.1:$API_PORT/ip"
        echo ""
        echo "==> Done. Tor SOCKS5 on 127.0.0.1:$SOCKS_PORT, API on 127.0.0.1:$API_PORT"
        exit 0
    fi
    sleep 2
done

echo "  [!] Timed out waiting for API"
exit 1
