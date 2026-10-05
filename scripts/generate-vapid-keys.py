#!/usr/bin/env python3
"""Генерирует пару ключей VAPID для web-push и печатает строки для окружения.

Ключи НЕ записываются в файлы и НЕ коммитятся: скрипт только пишет в stdout.
Приватный ключ кладётся в окружение сервера (`RUSTATS_VAPID_PRIVATE_KEY`), публичный —
в `RUSTATS_VAPID_PUBLIC_KEY` (он отдаётся браузеру через /api/v1/pwa/config).
Потеря приватного ключа = все подписки придётся создавать заново; утечка = чужие
могут слать пуши от имени сайта. Хранить как секрет, в логи и чат не выводить.

Нужен пакет `cryptography` (приходит вместе с pywebpush):
  backend/.venv/bin/python scripts/generate-vapid-keys.py
  docker compose exec backend python /app/scripts/generate-vapid-keys.py   # если нет локального venv
"""
from __future__ import annotations

import base64
import sys


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate() -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    private_raw = key.private_numbers().private_value.to_bytes(32, "big")
    public_raw = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
    )
    return b64url(public_raw), b64url(private_raw)


def main() -> int:
    try:
        public, private = generate()
    except ImportError:
        print("Нужен пакет cryptography: pip install pywebpush", file=sys.stderr)
        return 2
    print("# Скопируйте в окружение сервера. Приватный ключ — секрет, не коммитить.")
    print(f"RUSTATS_VAPID_PUBLIC_KEY={public}")
    print(f"RUSTATS_VAPID_PRIVATE_KEY={private}")
    print("RUSTATS_VAPID_SUBJECT=mailto:admin@example.com  # замените на контактный адрес владельца")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
