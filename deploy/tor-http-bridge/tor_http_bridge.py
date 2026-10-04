#!/usr/bin/env python3
"""HTTP CONNECT bridge -> local Tor SOCKS5 (egress for rosstat containers).

Hardened replacement of the host script /opt/tor-http-bridge/tor_http_bridge.py (F10, 2026-10-04):

* credentials come from the environment (systemd ``EnvironmentFile``, mode 0600), never from the file;
* request headers are never logged — only peer, request line and result (the old script logged the first
  400 bytes of every request, i.e. ``Proxy-Authorization``);
* constant-time comparison of the credential.

Binds only to the docker bridge gateway so it is not reachable from the internet. Clients keep sending
``Proxy-Authorization: Basic`` from RUSTATS_OPENROUTER_PROXY_URL.
"""
import asyncio
import base64
import hmac
import os
import sys

LISTEN_HOST = os.environ.get("BRIDGE_LISTEN_HOST", "172.18.0.1")
LISTEN_PORT = int(os.environ.get("BRIDGE_LISTEN_PORT", "8888"))
TOR_HOST = os.environ.get("BRIDGE_TOR_HOST", "127.0.0.1")
TOR_PORT = int(os.environ.get("BRIDGE_TOR_PORT", "9050"))

_SOCKS_ADDR_LEN = {1: 4, 4: 16}


def expected_auth(user: str, password: str) -> bytes:
    return b"Basic " + base64.b64encode(f"{user}:{password}".encode()).strip()


def load_expected_auth(environ=os.environ) -> bytes:
    user, password = environ.get("BRIDGE_AUTH_USER", ""), environ.get("BRIDGE_AUTH_PASS", "")
    if not user or len(password) < 24:
        raise SystemExit("BRIDGE_AUTH_USER / BRIDGE_AUTH_PASS (>= 24 chars) must be set in the environment")
    return expected_auth(user, password)


def is_authorized(head: bytes, expected: bytes) -> bool:
    """True when the request carries exactly the expected Proxy-Authorization value."""
    for header in head.split(b"\r\n")[1:]:
        if b":" not in header:
            continue
        key, value = header.split(b":", 1)
        if key.strip().lower() == b"proxy-authorization":
            return hmac.compare_digest(value.strip(), expected)
    return False


def _log(message: str) -> None:
    print(f"[tor-http-bridge] {message}", flush=True)


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _socks_connect(host: str, port: int):
    reader, writer = await asyncio.open_connection(TOR_HOST, TOR_PORT)
    writer.write(b"\x05\x01\x00")
    await writer.drain()
    greeting = await reader.readexactly(2)
    if greeting != b"\x05\x00":
        raise RuntimeError(f"tor refused handshake: {greeting.hex()}")
    host_bytes = host.encode()
    writer.write(b"\x05\x01\x00\x03" + bytes([len(host_bytes)]) + host_bytes + port.to_bytes(2, "big"))
    await writer.drain()
    head = await reader.readexactly(4)
    if head[1] != 0:
        raise RuntimeError(f"socks5 reply code {head[1]}")
    atyp = head[3]
    if atyp == 3:
        length = (await reader.readexactly(1))[0]
        await reader.readexactly(length + 2)
    elif atyp in _SOCKS_ADDR_LEN:
        await reader.readexactly(_SOCKS_ADDR_LEN[atyp] + 2)
    else:
        raise RuntimeError(f"socks5 odd ATYP {atyp}")
    return reader, writer


async def _respond(writer: asyncio.StreamWriter, status_line: bytes, extra: bytes = b"") -> None:
    writer.write(status_line + extra + b"Content-Length: 0\r\nConnection: close\r\n\r\n")
    try:
        await writer.drain()
    except Exception:
        pass
    writer.close()


def make_handler(expected: bytes):
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        try:
            head = await reader.readuntil(b"\r\n\r\n")
        except Exception:
            writer.close()
            return
        request_line = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        parts = request_line.split()
        # Only the method and the target host are logged; headers (credentials) never are.
        if not is_authorized(head, expected):
            _log(f"{peer} -> 407 ({request_line[:60]})")
            await _respond(writer, b"HTTP/1.1 407 Proxy Authentication Required\r\n",
                           b'Proxy-Authenticate: Basic realm="tor"\r\n')
            return
        if len(parts) < 3 or parts[0].upper() != "CONNECT":
            _log(f"{peer} -> 501 ({request_line[:60]})")
            await _respond(writer, b"HTTP/1.1 501 Not Implemented\r\n")
            return
        host, _, port_text = parts[1].rpartition(":")
        try:
            port = int(port_text)
        except ValueError:
            port = 443
        try:
            socks_reader, socks_writer = await _socks_connect(host, port)
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()
            _log(f"{peer} tunnel {host}:{port}")
            up = asyncio.create_task(_pipe(reader, socks_writer))
            down = asyncio.create_task(_pipe(socks_reader, writer))
            _done, pending = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
        except Exception as exc:
            _log(f"{peer} FAIL {host}:{port}: {exc}")
            await _respond(writer, b"HTTP/1.1 502 Bad Gateway\r\n")
        finally:
            try:
                writer.close()
            except Exception:
                pass
    return handle


async def main() -> int:
    handler = make_handler(load_expected_auth())
    server = await asyncio.start_server(handler, LISTEN_HOST, LISTEN_PORT)
    _log(f"listening {LISTEN_HOST}:{LISTEN_PORT} -> tor {TOR_HOST}:{TOR_PORT}")
    async with server:
        await server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
