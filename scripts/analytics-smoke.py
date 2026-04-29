#!/usr/bin/env python3
"""Smoke checks for Forecast Analytics OS.

The script intentionally uses only the protected backend API. It does not read
Yandex tokens directly and is safe to run in CI with a test backend token.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def request(base_url: str, token: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Analytics-Token": token,
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", "replace")
        raise SystemExit(f"HTTP {exc.code}: {payload}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=["health", "pages", "anomalies"])
    parser.add_argument("--base-url", default=os.environ.get("FORECAST_ANALYTICS_API_URL", "http://127.0.0.1:8000/api/v1/analytics"))
    parser.add_argument("--token", default=os.environ.get("FORECAST_ANALYTICS_API_TOKEN", ""))
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("FORECAST_ANALYTICS_API_TOKEN or --token is required")

    path = {
        "health": "/health",
        "pages": "/pages?limit=10",
        "anomalies": "/anomalies",
    }[args.check]
    payload = request(args.base_url, args.token, path)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
