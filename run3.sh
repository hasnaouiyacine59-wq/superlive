#!/usr/bin/env bash
set -e
IMAGE="quay.io/mylastres0rt05_redhat/karlin:latest"
NAMES=("karlin1" "karlin2" "karlin3")
AUTH_VOL="$(pwd)/Fast_vpn/fast_auth:/app/Fast_vpn/fast_auth"

for name in "${NAMES[@]}"; do
    docker rm -f "$name" 2>/dev/null || true
    docker run -d --privileged --name "$name" \
        -e HEADLESS=true \
        -v "$AUTH_VOL" \
        "$IMAGE"
done

echo "--- Tailing logs (Ctrl+C to stop all) ---"
for name in "${NAMES[@]}"; do
    docker logs -f "$name" &
done
wait