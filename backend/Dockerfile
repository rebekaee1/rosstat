FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt constraints.txt ./
# -c constraints.txt лочит транзитивные зависимости (Э-1): сборка воспроизводима
RUN pip install --no-cache-dir --timeout 120 -r requirements.txt -c constraints.txt

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

# /app/geoip — mountpoint тома geoip_data: создаём заранее, чтобы docker
# проинициализировал том с владельцем appuser (иначе root и загрузка mmdb падает).
# /app/og-cache — то же для дискового OG-кэша (П-16): пустой named volume при
# первом маунте копирует владельца точки монтирования из образа.
RUN mkdir -p /app/geoip /app/og-cache && chmod +x /app/entrypoint.sh && chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1
ENV RUSTATS_ROSSTAT_CA_CERT=/app/certs/russiantrustedca2024.pem

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
