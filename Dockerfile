FROM python:3.11-slim

# Playwright/Chromium system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libnss3 libnspr4 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium \
    && playwright uninstall firefox webkit

COPY src/ src/
COPY run_web.py .

RUN mkdir -p data covers

ENV JAV_WEB_HOST=0.0.0.0
ENV JAV_WEB_PORT=8000

EXPOSE 8000

CMD ["python", "run_web.py"]
