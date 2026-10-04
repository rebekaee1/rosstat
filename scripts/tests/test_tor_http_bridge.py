"""F10: the bridge keeps credentials out of the file and out of the log, and compares them safely."""
import asyncio
import base64
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "tor_http_bridge", Path(__file__).resolve().parents[2] / "deploy/tor-http-bridge/tor_http_bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

USER, PASSWORD = "relay", "x" * 32
EXPECTED = bridge.expected_auth(USER, PASSWORD)


def request(auth: bytes | None, line: bytes = b"CONNECT openrouter.ai:443 HTTP/1.1") -> bytes:
    head = line + b"\r\nHost: openrouter.ai:443\r\n"
    if auth is not None:
        head += b"Proxy-Authorization: " + auth + b"\r\n"
    return head + b"\r\n"


def test_source_contains_no_credentials():
    text = (Path(bridge.__file__)).read_text()
    assert "pulse_relay" not in text and "AUTH_PASS =" not in text


def test_credentials_must_come_from_environment():
    with pytest.raises(SystemExit):
        bridge.load_expected_auth({})
    with pytest.raises(SystemExit):
        bridge.load_expected_auth({"BRIDGE_AUTH_USER": "u", "BRIDGE_AUTH_PASS": "short"})
    assert bridge.load_expected_auth({"BRIDGE_AUTH_USER": USER, "BRIDGE_AUTH_PASS": PASSWORD}) == EXPECTED


def test_authorization_is_exact():
    assert bridge.is_authorized(request(EXPECTED), EXPECTED)
    assert not bridge.is_authorized(request(None), EXPECTED)
    assert not bridge.is_authorized(request(b"Basic " + base64.b64encode(b"relay:wrong")), EXPECTED)
    assert not bridge.is_authorized(request(EXPECTED + b"x"), EXPECTED)


class _Writer:
    def __init__(self):
        self.data = b""
        self.closed = False

    def get_extra_info(self, _name):
        return ("172.18.0.2", 4242)

    def write(self, chunk):
        self.data += chunk

    async def drain(self):
        pass

    def close(self):
        self.closed = True


async def _handle(head: bytes):
    reader = asyncio.StreamReader()
    reader.feed_data(head)
    reader.feed_eof()
    writer = _Writer()
    await bridge.make_handler(EXPECTED)(reader, writer)
    return writer


def _run_handler(head: bytes):
    return asyncio.run(_handle(head))


def test_rejected_and_unsupported_requests_never_log_headers(capsys):
    assert b"407" in _run_handler(request(b"Basic " + base64.b64encode(b"relay:wrong"))).data
    assert b"501" in _run_handler(request(EXPECTED, b"GET http://example.com/ HTTP/1.1")).data
    logged = capsys.readouterr().out
    assert "Proxy-Authorization" not in logged and "Basic" not in logged
    assert base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode() not in logged
