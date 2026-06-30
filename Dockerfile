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

RUN --mount=type=cache,target=/cache/camoufox,sharing=locked set -e; \
    CACHE_DIR=/cache/camoufox; \
    INSTALL_DIR=/root/.cache/camoufox; \
    mkdir -p "$CACHE_DIR" "$INSTALL_DIR"; \
    if [ -f "$CACHE_DIR/version.json" ]; then \
        echo "Camoufox cache hit"; \
    else \
        echo "Fetching Camoufox release page..."; \
        HTML=$(curl -sL -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0" \
            https://github.com/daijro/camoufox/releases/latest); \
        REL_URL=$(echo "$HTML" | grep -oP '/daijro/camoufox/releases/download/[^"]*lin\.x86_64\.zip' | head -1); \
        NAME=$(basename "$REL_URL"); \
        echo "Downloading $NAME..."; \
        curl -L -o /tmp/cf.zip "https://github.com$REL_URL"; \
        unzip -o /tmp/cf.zip -d "$CACHE_DIR"; \
        rm /tmp/cf.zip; \
        VER=$(echo "$NAME" | sed -n 's/camoufox-\(.*\)-\(.*\)-lin\.x86_64\.zip/\1/p'); \
        REL=$(echo "$NAME" | sed -n 's/camoufox-\(.*\)-\(.*\)-lin\.x86_64\.zip/\2/p'); \
        echo "{\"version\":\"$VER\",\"release\":\"$REL\"}" > "$CACHE_DIR/version.json"; \
        echo "Camoufox cached (version=$VER, release=$REL)"; \
    fi; \
    cp -r "$CACHE_DIR"/. "$INSTALL_DIR"/; \
    echo "Camoufox ready"

COPY install-geoip.py /tmp/
RUN --mount=type=cache,target=/cache/geoip,sharing=locked python /tmp/install-geoip.py

COPY *.py ./
COPY src/ ./src/
COPY Fast_vpn/ ./Fast_vpn/
RUN mkdir -p results

CMD ["bash", "-c", "while true; do python super0container.py -n; done"]
