#!/usr/bin/env python3
"""Exercise real nginx routing against an isolated Docker stub (never production).

Requires local Docker with nginx:alpine and python:3.12-slim. No project DB,
credentials or app containers are mounted. Containers/network removed on exit.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
STUB = '''import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  record={"path":self.path,"host":self.headers.get("Host")}
  with open("/fixture/requests.jsonl","a") as f:f.write(json.dumps(record)+"\\n")
  if self.path.split("?")[0]=="/robots.txt":
   body=Path("/fixture/robots.txt").read_text().replace("__PUBLIC_HOST__",record["host"]).replace("__PUBLIC_ORIGIN__","https://"+record["host"]).encode()
  else:body=json.dumps(record).encode()
  self.send_response(200);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass
ThreadingHTTPServer(("0.0.0.0",8000),Handler).serve_forever()
'''


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def main():
    name = "fe-routing-" + uuid.uuid4().hex[:10]
    containers = [name + "-nginx", name + "-backend"]
    passed = 0
    with tempfile.TemporaryDirectory(prefix=name) as tmp:
        fixture = Path(tmp)
        fixture.chmod(0o755)
        (fixture / "stub.py").write_text(STUB)
        (fixture / "requests.jsonl").touch()
        (fixture / "robots.txt").write_text((ROOT / "frontend/public/robots.txt").read_text())
        (fixture / "logs").mkdir()
        for host in ["forecasteconomy.com", "ru.forecasteconomy.com"]:
            directory = fixture / "www/sitemaps/current" / host
            directory.mkdir(parents=True)
            (directory / "sitemap-fixture.xml").write_text(
                f'<urlset><url><loc>https://{host}/fixture</loc></url></urlset>'
            )
        docker("network", "create", name)
        try:
            docker("run", "-d", "--name", containers[1], "--network", name,
                   "--network-alias", "backend", "-v", f"{fixture}:/fixture",
                   "python:3.12-slim", "python", "/fixture/stub.py")
            docker("run", "-d", "--name", containers[0], "--network", name,
                   "-p", "127.0.0.1::80",
                   "-v", f"{ROOT / 'frontend/nginx.conf'}:/etc/nginx/conf.d/default.conf:ro",
                   "-v", f"{ROOT / 'frontend/search-crawlers.conf'}:/etc/nginx/search-crawlers.conf:ro",
                   "-v", f"{fixture / 'www'}:/var/www:ro",
                   "-v", f"{fixture / 'logs'}:/var/log/nginx/security",
                   "nginx:alpine")
            port = docker("port", containers[0], "80/tcp").rsplit(":", 1)[1]
            def request(path, ua="Googlebot/2.1", host="forecasteconomy.com", client_ip=None):
                headers = {"User-Agent": ua, "Host": host}
                if client_ip:  # the Docker bridge peer is trusted by set_real_ip_from
                    headers["X-Forwarded-For"] = client_ip
                req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return response.status, response.read().decode()
                except urllib.error.HTTPError as exc:
                    return exc.code, exc.read().decode()
            for attempt in range(40):
                try:
                    if request("/api/v1/routing-ready")[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(.1)
            else:
                raise AssertionError("nginx did not become ready")
            def verify(condition, label):
                nonlocal passed
                assert condition, label
                passed += 1
            for ua in ["ClaudeBot/1.0", "GPTBot/1.2", "meta-externalagent/1.1", "CCBot/2.0"]:
                before = (fixture / "requests.jsonl").read_text()
                status, _ = request("/api/v1/routing-probe", ua)
                verify(status == 403, f"training agent denied: {ua}")
                verify((fixture / "requests.jsonl").read_text() == before,
                       f"training agent never reaches backend: {ua}")
                status, body = request("/robots.txt", ua)
                verify(status == 200 and "Disallow: /" in body,
                       f"training agent can retrieve robots: {ua}")
            for ua in ["Claude-User/1.0", "Claude-SearchBot/1.0", "OAI-SearchBot/1.3",
                       "ChatGPT-User/1.0", "meta-externalfetcher/1.1", "meta-webindexer/1.1", "Googlebot/2.1",
                       "YandexBot/3.0", "Mozilla/5.0 Chrome/145.0.0.0 Safari/537.36"]:
                status, body = request("/api/v1/routing-probe", ua)
                verify(status == 200 and json.loads(body)["path"] == "/api/v1/routing-probe",
                       f"search/retrieval/browser preserved: {ua}")
            for path in ["/og/world/germany/gdp/2024.png", "/og/germany/gdp/2024.png"]:
                status, body = request(path)
                verify(status == 200 and json.loads(body)["path"] == "/api/v1/og-image/world/germany/gdp/2024.png",
                       f"world annual PNG rewrite: {path}")
            for host in ["forecasteconomy.com", "ru.forecasteconomy.com"]:
                before = (fixture / "requests.jsonl").read_text()
                status, body = request("/sitemap-fixture.xml", host=host)
                verify(status == 200 and f"https://{host}/fixture" in body,
                       f"host-specific static sitemap: {host}")
                verify((fixture / "requests.jsonl").read_text() == before,
                       f"sitemap served without backend: {host}")
            # Rate limits: only a VERIFIED indexing crawler (published network AND crawler UA)
            # skips the per-IP regional-SSR budget (2 r/s, burst 10). 40 fast requests
            # exceed it for everyone else.
            import re
            ipv6 = re.search(r"^\s+([0-9a-f:]+)::/\d+ 1;", (ROOT / "frontend/search-crawlers.conf").read_text(), re.M)
            google_v6 = ipv6.group(1) + "::1" if ipv6 else None
            gbot = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
            bbot = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
            ybot = "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"
            chrome = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/145.0.0.0 Safari/537.36"
            region_paths = ["/united-states/region/ohio/bea-sagdp3-90", "/russia/region/moskva/some-code"]
            def burst(ua, ip, path):
                return [request(path, ua, client_ip=ip)[0] for _ in range(40)]
            cases = [
                ("Googlebot from Google network", gbot, "66.249.66.10", True),
                ("Googlebot from new Google range", gbot, "192.178.4.1", True),
                ("bingbot from Bing network", bbot, "157.55.39.20", True),
                ("YandexBot from verified Yandex network", ybot, "95.108.213.30", True),
                ("spoofed Googlebot from other IP", gbot, "203.0.113.7", False),
                ("spoofed Googlebot from cloud IP", gbot, "34.34.233.45", False),
                ("browser UA from Google network", chrome, "66.249.66.11", False),
                ("GoogleOther from Google network", "Mozilla/5.0 (compatible; GoogleOther)", "66.249.66.12", False),
                ("YandexBot from Google network", ybot, "66.249.66.13", False),
                ("bingbot from Yandex network", bbot, "95.108.213.31", False),
            ]
            if google_v6:
                cases.append(("Googlebot from Google IPv6", gbot, google_v6, True))
            def shift(ip, n):
                # the budget is per IP across locations: use a fresh address in the same /24 per path
                if ":" in ip:
                    return ip
                head, last = ip.rsplit(".", 1)
                return f"{head}.{(int(last) + 40 * n) % 250 + 1}"
            for index, path in enumerate(region_paths):
                for label, ua, ip, exempt in cases:
                    codes = burst(ua, shift(ip, index), path)
                    if exempt:
                        verify(429 not in codes, f"{label}: never rate-limited on {path} (got {sorted(set(codes))})")
                    else:
                        verify(429 in codes, f"{label}: still rate-limited on {path} (got {sorted(set(codes))})")
                        verify(codes[0] == 200, f"{label}: first request served on {path}")
            print(json.dumps({"passed": passed, "environment": "isolated Docker nginx + stub", "production_requests": 0}))
        except Exception:
            print(docker("logs", containers[0], check=False)[-8000:])
            print(docker("logs", containers[1], check=False)[-2000:])
            raise
        finally:
            for container in containers:
                docker("rm", "-f", container, check=False)
            docker("network", "rm", name, check=False)


if __name__ == "__main__":
    main()
