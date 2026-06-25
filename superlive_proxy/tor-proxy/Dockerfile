FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y tor tor-geoipdb python3 python3-pip --no-install-recommends \
    && pip3 install flask requests[socks] --break-system-packages \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash customer \
    && echo 'customer:baba123A*' | chpasswd \
    && usermod -aG debian-tor customer

COPY torrc.template /etc/tor/torrc.template
COPY api.py /app/api.py
COPY start.sh /start.sh

RUN chmod +x /start.sh \
    && mkdir -p /var/lib/tor /var/log/tor /run/tor /home/customer/.tor \
    && chown -R customer:customer /etc/tor /app /start.sh /var/lib/tor /var/log/tor /run/tor /home/customer \
    && chmod -R g+rwX /etc/tor /app /start.sh /var/lib/tor /var/log/tor /run/tor /home/customer

ENV SOCKS_PORT=9050
ENV CONTROL_PORT=9051
ENV API_PORT=5000
ENV HOME=/home/customer

EXPOSE 9050 9051 5000

USER customer
CMD ["/start.sh"]
