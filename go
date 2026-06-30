while true ; do docker run --privileged -e HEADLESS=true -v $(pwd)/Fast_vpn/fast_auth:/app/Fast_vpn/fast_auth --rm -it karlin python super0container.py -n ;done
