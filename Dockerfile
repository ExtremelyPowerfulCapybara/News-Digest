FROM python:3.12-slim

# System deps for Pillow, wordcloud, lxml, and imagehash
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    libxml2-dev \
    libxslt-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/   ./bot/
COPY lib/   ./lib/
COPY config/ ./config/
