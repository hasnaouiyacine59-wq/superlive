#!/bin/bash
SOCKS_PORT=${SOCKS_PORT:-9050}
CONTROL_PORT=${CONTROL_PORT:-9051}

sed "s/\${SOCKS_PORT}/$SOCKS_PORT/g; s/\${CONTROL_PORT}/$CONTROL_PORT/g" \
    /etc/tor/torrc.template > /tmp/torrc

tor -f /tmp/torrc &
sleep 5
python3 /app/api.py
