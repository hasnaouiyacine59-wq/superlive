#!/usr/bin/env bash
set -e

mkdir -p Fast_vpn/
echo 'ncphasnaouiyacine59@namecheap' > Fast_vpn/fast_auth
echo 'nZRC8Re5Mb' >> Fast_vpn/fast_auth
chmod 600 Fast_vpn/fast_auth

IMAGE="quay.io/mylastres0rt05_redhat/karlin:latest"
NAMES=("karlin1" "karlin2" "karlin3")
AUTH_VOL="$(pwd)/Fast_vpn/fast_auth:/app/Fast_vpn/fast_auth"

echo "--- Pulling latest image ---"
docker pull "$IMAGE"

echo "--- Removing old containers ---"
docker rm -f $(docker ps -a --filter name=karlin -q) 2>/dev/null || true

for name in "${NAMES[@]}"; do
    docker run -d --privileged --name "$name" \
        -e HEADLESS=true \
        -v "$AUTH_VOL" \
        --entrypoint bash \
        "$IMAGE" -c "while true; do python super0container.py -n; done"
done

echo "--- Tailing logs (Ctrl+C to stop all) ---"
for name in "${NAMES[@]}"; do
    docker logs -f "$name" &
done
wait
