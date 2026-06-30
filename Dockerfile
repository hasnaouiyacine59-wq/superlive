FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libegl1 \
    libxkbcommon-x11-0 \
    aria2 \
    curl \
    git \
    openvpn \
    && rm -rf /var/lib/apt/lists/*

RUN git config --global user.email "builder@karlin.local" \
    && git config --global user.name "Karlin Builder"

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile minimal

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m playwright install chromium

COPY install-camoufox.py /tmp/
RUN --mount=type=cache,target=/cache/camoufox,sharing=locked python /tmp/install-camoufox.py

COPY install-geoip.py /tmp/
RUN --mount=type=cache,target=/cache/geoip,sharing=locked python /tmp/install-geoip.py

COPY *.py ./
COPY src/ ./src/
COPY Fast_vpn/ ./Fast_vpn/
RUN mkdir -p results

CMD ["python", "base.py"]
