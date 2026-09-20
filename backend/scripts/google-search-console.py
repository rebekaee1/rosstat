#!/usr/bin/env python3
"""Local OAuth authorization and read-only Search Console exports. See --help."""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlencode, urlsplit
import webbrowser
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.gsc_client import (  # noqa: E402
    DEFAULT_CREDENTIALS_FILE, GSC_SCOPE, GSC_TOKEN_URL, GscClient, GscError,
    configured_site, read_credentials,
)


def private_write(path: Path, value: str) -> None:
    """Atomic replacement; temporary and final files are private from creation."""
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".gsc-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def authorization_url(client_id: str, redirect_uri: str, state: str, verifier: str) -> str:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri,
        "response_type": "code", "scope": GSC_SCOPE,
        "access_type": "offline", "prompt": "consent",
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })


def callback_handler(state: str, result: dict):
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # HTTP access logs would expose the authorization code.

        def do_GET(self):
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            valid = parsed.path == "/oauth/callback" and secrets.compare_digest(params.get("state", [""])[0].encode(), state.encode())
            if valid and params.get("code"):
                result["code"] = params["code"][0]
                status, message = 200, "Authorization received. You can close this tab."
            elif valid and params.get("error"):
                result["denied"] = True
                status, message = 400, "Authorization was not granted. You can close this tab."
            else:
                status, message = 400, "Invalid OAuth callback. Return to the Google authorization window."
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()
            self.wfile.write(message.encode())
    return Callback


def authorize(args) -> None:
    client = json.loads(args.client_secrets.expanduser().read_text()).get("installed", {})
    if not all(client.get(key) for key in ("client_id", "client_secret")):
        raise GscError("Provide a Google OAuth Desktop client JSON (installed), not a web/service-account client")
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    result: dict = {}
    with HTTPServer(("127.0.0.1", args.port), callback_handler(state, result)) as server:
        server.timeout = 1
        redirect = f"http://127.0.0.1:{server.server_port}/oauth/callback"
        url = authorization_url(client["client_id"], redirect, state, verifier)
        if args.authorization_url_file:
            private_write(args.authorization_url_file, url + "\n")
            print(f"Authorization URL saved to {args.authorization_url_file}", flush=True)
        else:
            print(url, flush=True)
        if not args.no_open:
            webbrowser.open(url)
        deadline = time.monotonic() + 600
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if not result.get("code"):
        raise GscError("Google authorization denied or timed out; no credentials saved")
    with httpx.Client(timeout=30) as http:
        response = http.post(GSC_TOKEN_URL, data={
            "grant_type": "authorization_code", "code": result["code"],
            "client_id": client["client_id"], "client_secret": client["client_secret"],
            "redirect_uri": redirect, "code_verifier": verifier,
        })
    if response.status_code != 200:
        raise GscError(f"Google authorization exchange failed (HTTP {response.status_code}); no credentials saved")
    payload = response.json()
    if not payload.get("refresh_token"):
        raise GscError("Google returned no refresh token; no credentials saved")
    if payload.get("scope", "").split() != [GSC_SCOPE]:
        raise GscError("Google did not return precisely webmasters.readonly; no credentials saved")
    credentials = {
        "type": "authorized_user", "client_id": client["client_id"],
        "client_secret": client["client_secret"], "refresh_token": payload["refresh_token"],
        "scopes": [GSC_SCOPE], "token_uri": GSC_TOKEN_URL,
    }
    private_write(args.credentials, json.dumps(credentials, indent=2) + "\n")
    print(f"Read-only OAuth credentials saved to {args.credentials} (0600). Verify with sites.")


async def export(args) -> dict:
    credentials = read_credentials(args.credentials)
    async with httpx.AsyncClient(timeout=60) as http:
        api = GscClient(http, credentials=credentials)
        if args.command == "sites":
            return await api.sites()
        if args.command == "sitemaps":
            return await api.sitemaps(args.site)
        if args.command == "inspect":
            urls = [line.strip() for line in args.urls.read_text().splitlines() if line.strip()]
            return {"site": args.site, "inspections": await api.inspect_sample(args.site, urls)}
        if args.command == "search":
            end = args.end or (datetime.now(ZoneInfo("America/Los_Angeles")).date() - timedelta(days=3))
            start = args.start or (end - timedelta(days=27))
            days = (end - start).days + 1
            if not 1 <= days <= 93:
                raise GscError("Choose an export window of 1..93 days")
            reports = [await api.search_day(args.site, start + timedelta(days=offset),
                       dimensions=tuple(args.dimensions.split(",")), search_type=args.type,
                       max_rows=args.max_rows) for offset in range(days)]
            return {"site": args.site, "type": args.type, "dimensions": args.dimensions.split(","),
                    "data_state": "final", "timezone": "America/Los_Angeles", "days": reports,
                    "coverage_note": "Search Console returns top rows, not every query or indexed URL."}
    raise GscError("Unknown command")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS_FILE)
    parser.add_argument("--site", default=configured_site())
    parser.add_argument("--output", type=Path, help="Save a private JSON export instead of printing data")
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("authorize", help="Desktop OAuth, localhost callback, read-only scope")
    auth.add_argument("--client-secrets", type=Path, required=True)
    auth.add_argument("--no-open", action="store_true")
    auth.add_argument("--authorization-url-file", type=Path)
    auth.add_argument("--port", type=int, default=0)
    commands.add_parser("sites", help="List properties and permission levels")
    commands.add_parser("sitemaps", help="Read submitted sitemap status")
    search = commands.add_parser("search", help="Export finalized daily search data (default last 28 days)")
    search.add_argument("--start", type=date.fromisoformat)
    search.add_argument("--end", type=date.fromisoformat)
    search.add_argument("--type", choices=["web", "image", "video", "news", "discover", "googleNews"], default="web")
    search.add_argument("--dimensions", default="query,page,date")
    search.add_argument("--max-rows", type=int, default=50_000)
    inspect = commands.add_parser("inspect", help="Read Google index snapshots, max 20 URLs; does not request indexing")
    inspect.add_argument("--urls", type=Path, required=True, help="Text file with one URL per line")
    args = parser.parse_args()
    try:
        if args.command == "authorize":
            authorize(args)
        else:
            report = asyncio.run(export(args))
            value = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                private_write(args.output, value)
                print(f"Read-only export saved to {args.output}")
            else:
                print(value)
    except (GscError, ValueError, OSError, httpx.HTTPError) as exc:
        # httpx's full exception may contain callback code in a URL. Never print it.
        print(f"GSC: {exc if isinstance(exc, GscError) else type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
