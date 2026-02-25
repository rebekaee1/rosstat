FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV RUSTATS_ROSSTAT_CA_CERT=/app/certs/russiantrustedca2024.pem

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
