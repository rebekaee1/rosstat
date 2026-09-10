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
                   "-v", f"{fixture / 'www'}:/var/www:ro",
                   "-v", f"{fixture / 'logs'}:/var/log/nginx/security",
                   "nginx:alpine")
            port = docker("port", containers[0], "80/tcp").rsplit(":", 1)[1]
            def request(path, ua="Googlebot/2.1", host="forecasteconomy.com"):
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}{path}",
                    headers={"User-Agent": ua, "Host": host},
                )
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
