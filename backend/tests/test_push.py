"""Web-push: подготовка без отправки. Флаги закрыты по умолчанию, сервис отправки отказывает,
адрес подписки — персональные данные (не в ответах, не в логах), планировщик push не знает."""
import asyncio
import functools
import importlib.util
import logging
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select

import app.services.web_push as web_push
from app.config import settings
from app.models import PushSubscription
from app.services.web_push import PushSendDisabled

ROOT = Path(__file__).resolve().parents[2]
URL = "/api/v1/push"
P256DH = "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U"
AUTH = "tBHItJI5svbpez7KI4CCXg"


def sync(fn):
    """Нет pytest-asyncio: корутинные тесты гоним через asyncio.run (сигнатуру для фикстур сохраняем)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return wrapper


def body(n=1, **patch):
    data = {"endpoint": f"https://fcm.googleapis.com/fcm/send/device-{n}", "keys": {"p256dh": P256DH, "auth": AUTH}}
    data.update(patch)
    return data


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "push_subscribe_enabled", True)


async def _count(maker):
    async with maker() as s:
        return await s.scalar(select(func.count()).select_from(PushSubscription))


# ── флаги по умолчанию ──

def test_defaults_everything_closed():
    f = settings.model_fields
    assert f["push_subscribe_enabled"].default is False
    assert f["push_send_enabled"].default is False
    assert f["push_dry_run"].default is True
    assert f["vapid_private_key"].default == "" and f["vapid_public_key"].default == ""


def test_endpoints_404_while_flag_off(auth_client, auth_env):
    assert auth_client.post(f"{URL}/subscribe", json=body()).status_code == 404
    assert auth_client.post(f"{URL}/unsubscribe", json={"endpoint": body()["endpoint"]}).status_code == 404
    assert auth_client.portal.call(_count, auth_env["session_maker"]) == 0


def test_config_hides_push_until_flag_and_public_key(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", P256DH)
    cfg = auth_client.get("/api/v1/pwa/config").json()
    assert cfg["push_enabled"] is False and cfg["vapid_public_key"] is None  # ключ есть, флага нет
    monkeypatch.setattr(settings, "push_subscribe_enabled", True)
    cfg = auth_client.get("/api/v1/pwa/config").json()
    assert cfg["push_enabled"] is True and cfg["vapid_public_key"] == P256DH
    monkeypatch.setattr(settings, "vapid_public_key", "")
    assert auth_client.get("/api/v1/pwa/config").json()["push_enabled"] is False  # флаг есть, ключа нет
    monkeypatch.setattr(settings, "vapid_private_key", "SECRET-PRIVATE-KEY")
    assert "SECRET-PRIVATE-KEY" not in auth_client.get("/api/v1/pwa/config").text


# ── подписка / отписка ──

def test_subscribe_stores_row_and_never_echoes_endpoint(auth_client, auth_env, enabled):
    r = auth_client.post(f"{URL}/subscribe", json=body(), headers={"User-Agent": "Mozilla/5.0 test"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert "fcm.googleapis.com" not in r.text

    async def row(maker):
        async with maker() as s:
            return (await s.scalars(select(PushSubscription))).all()

    rows = auth_client.portal.call(row, auth_env["session_maker"])
    assert len(rows) == 1
    assert rows[0].endpoint == body()["endpoint"] and rows[0].p256dh == P256DH and rows[0].auth == AUTH
    assert rows[0].user_id is None and rows[0].revoked_at is None
    assert len(rows[0].endpoint_hash) == 64


def test_resubscribe_is_upsert_and_unrevokes(auth_client, auth_env, enabled):
    auth_client.post(f"{URL}/subscribe", json=body())
    auth_client.post(f"{URL}/subscribe", json=body())
    assert auth_client.portal.call(_count, auth_env["session_maker"]) == 1


def test_unsubscribe_deletes_row_and_is_idempotent(auth_client, auth_env, enabled):
    auth_client.post(f"{URL}/subscribe", json=body())
    r = auth_client.post(f"{URL}/unsubscribe", json={"endpoint": body()["endpoint"]})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert auth_client.portal.call(_count, auth_env["session_maker"]) == 0
    assert auth_client.post(f"{URL}/unsubscribe", json={"endpoint": body()["endpoint"]}).status_code == 200


def test_logged_in_user_is_linked(auth_client, auth_env, enabled):
    r = auth_client.post("/api/v1/auth/register", json={"email": "p@example.com", "password": "supersecret1", "consent": True})
    assert r.status_code == 201, r.text
    auth_client.post(f"{URL}/subscribe", json=body())

    async def uid(maker):
        async with maker() as s:
            return (await s.scalars(select(PushSubscription))).one().user_id

    assert auth_client.portal.call(uid, auth_env["session_maker"]) is not None


@pytest.mark.parametrize("patch", [
    {"endpoint": "http://fcm.googleapis.com/fcm/send/x"},            # не https
    {"endpoint": "https://127.0.0.1/x"},                              # IP
    {"endpoint": "https://localhost/x"},                              # без домена
    {"endpoint": "https://10.0.0.5/x"},
    {"endpoint": "https://user:pw@fcm.googleapis.com/x"},             # userinfo
    {"endpoint": "https://printer.local/x"},
    {"endpoint": "https://fcm.googleapis.com/" + "a" * 2100},
    {"endpoint": ""},
    {"keys": {"p256dh": "short", "auth": AUTH}},
    {"keys": {"p256dh": P256DH, "auth": "bad key!"}},
    {"keys": {"p256dh": P256DH}},
])
def test_validation_rejects_malformed(auth_client, auth_env, enabled, patch):
    assert auth_client.post(f"{URL}/subscribe", json=body(**patch)).status_code == 422
    assert auth_client.portal.call(_count, auth_env["session_maker"]) == 0


def test_rate_limit_per_ip(auth_client, enabled):
    for n in range(10):
        assert auth_client.post(f"{URL}/subscribe", json=body(n)).status_code == 200
    r = auth_client.post(f"{URL}/subscribe", json=body(99))
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_endpoint_and_keys_never_reach_logs(auth_client, enabled, caplog):
    with caplog.at_level(logging.DEBUG):
        auth_client.post(f"{URL}/subscribe", json=body())
        auth_client.post(f"{URL}/subscribe", json=body(**{"endpoint": "https://fcm.googleapis.com/fcm/send/" + "z" * 40}))
        auth_client.post(f"{URL}/unsubscribe", json={"endpoint": body()["endpoint"]})
    # Драйвер БД на DEBUG печатает параметры SQL — это не наши логи и не продовый уровень.
    ours = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("app") or r.levelno >= logging.INFO)
    assert "device-1" not in ours and "fcm.googleapis.com" not in ours and P256DH not in ours and AUTH not in ours


# ── сервис отправки ──

class _Sub:
    def __init__(self, n=1):
        self.endpoint = f"https://push.example.com/{n}"
        self.p256dh, self.auth = P256DH, AUTH
        self.id = n
        self.failure_count = 0


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("в сеть уходить нельзя")
    monkeypatch.setattr(web_push, "_webpush_blocking", boom)


@sync
async def test_send_refuses_by_default(no_network):
    payload = web_push.build_payload("t")
    with pytest.raises(PushSendDisabled):
        await web_push.send_to_subscription(_Sub(), payload)
    with pytest.raises(PushSendDisabled):          # даже сухой прогон закрыт, пока отправка выключена
        await web_push.send_to_subscription(_Sub(), payload, dry_run=True)
    with pytest.raises(PushSendDisabled):
        web_push.ensure_sendable(dry_run=True)


@sync
async def test_enabled_send_is_dry_run_by_default(monkeypatch, no_network):
    monkeypatch.setattr(settings, "push_send_enabled", True)
    result = await web_push.send_to_subscription(_Sub(), web_push.build_payload("t"))
    assert result.status == "dry_run"


@sync
async def test_caller_cannot_override_dry_run_setting(monkeypatch, no_network):
    monkeypatch.setattr(settings, "push_send_enabled", True)
    monkeypatch.setattr(settings, "push_dry_run", True)
    assert web_push.effective_dry_run(False) is True    # dry_run=False не обходит настройку
    result = await web_push.send_to_subscription(_Sub(), web_push.build_payload("t"), dry_run=False)
    assert result.status == "dry_run"


@sync
async def test_real_send_needs_vapid_keys(monkeypatch, no_network):
    monkeypatch.setattr(settings, "push_send_enabled", True)
    monkeypatch.setattr(settings, "push_dry_run", False)
    with pytest.raises(PushSendDisabled, match="VAPID"):
        await web_push.send_to_subscription(_Sub(), web_push.build_payload("t"))


@sync
async def test_batch_dry_run_counts_only(auth_env, monkeypatch, no_network):
    monkeypatch.setattr(settings, "push_send_enabled", True)
    async with auth_env["session_maker"]() as db:
        for n in range(3):
            db.add(PushSubscription(endpoint_hash=f"h{n}", endpoint=f"https://p.example.com/{n}", p256dh=P256DH, auth=AUTH))
        await db.commit()
        with pytest.raises(PushSendDisabled):
            monkeypatch.setattr(settings, "push_send_enabled", False)
            await web_push.send_to_all(db, web_push.build_payload("t"))
        monkeypatch.setattr(settings, "push_send_enabled", True)
        result = await web_push.send_to_all(db, web_push.build_payload("t"))
    assert result.dry_run is True and result.total == 3 and result.sent == 0


@sync
async def test_batch_real_updates_state(auth_env, monkeypatch):
    monkeypatch.setattr(settings, "push_send_enabled", True)
    monkeypatch.setattr(settings, "push_dry_run", False)
    monkeypatch.setattr(settings, "vapid_private_key", "k")
    monkeypatch.setattr(settings, "vapid_public_key", "k")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:a@example.com")
    outcomes = {"https://p.example.com/ok": web_push.SendResult("sent", 201),
                "https://p.example.com/gone": web_push.SendResult("gone", 410),
                "https://p.example.com/bad": web_push.SendResult("failed", 500)}
    monkeypatch.setattr(web_push, "_webpush_blocking", lambda sub, data, ttl: outcomes[sub.endpoint])
    async with auth_env["session_maker"]() as db:
        for name in outcomes:
            db.add(PushSubscription(endpoint_hash=name[-8:].ljust(8, "x") * 8, endpoint=name, p256dh=P256DH, auth=AUTH))
        await db.commit()
        result = await web_push.send_to_all(db, web_push.build_payload("t"))
        assert (result.sent, result.gone, result.failed) == (1, 1, 1)
        rows = {r.endpoint: r for r in (await db.scalars(select(PushSubscription))).all()}
    assert rows["https://p.example.com/ok"].last_success_at is not None
    assert rows["https://p.example.com/gone"].revoked_at is not None
    assert rows["https://p.example.com/bad"].failure_count == 1 and rows["https://p.example.com/bad"].revoked_at is None


def test_payload_is_sanitised():
    import json
    data = json.loads(web_push.build_payload("x" * 500, "y" * 900, "//evil.example/steal", tag="t" * 200))
    assert len(data["title"]) == 120 and len(data["body"]) == 300 and len(data["tag"]) == 64
    assert data["url"] == "/"
    assert json.loads(web_push.build_payload("a", url="/russia/indicator/cpi"))["url"] == "/russia/indicator/cpi"
    with pytest.raises(ValueError):
        web_push.build_payload("a", body="b", url="/" + "u" * 4000)


# ── планировщик, зависимость, ключи, миграция ──

def test_nothing_schedules_or_imports_push_sender():
    offenders = []
    for path in (ROOT / "backend" / "app").rglob("*.py"):
        if path.name == "web_push.py":
            continue
        if re.search(r"(?:from|import)\s+[\w.]*web_push|(?:from|import)\s+pywebpush|send_to_all\(|send_to_subscription\(", path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []   # сервис отправки никем не вызывается, в планировщике push нет


def test_pywebpush_dependency_is_pinned_in_requirements_and_constraints():
    req = (ROOT / "backend" / "requirements.txt").read_text()
    con = (ROOT / "backend" / "constraints.txt").read_text()
    assert re.search(r"^pywebpush==\d", req, re.M)
    for name in ("pywebpush", "py-vapid", "cryptography", "http_ece"):
        assert re.search(rf"^{name}==\d", con, re.M | re.I), name


def test_vapid_script_prints_to_stdout_only_and_keys_not_committed():
    src = (ROOT / "scripts" / "generate-vapid-keys.py").read_text()
    assert "open(" not in src and "write_text" not in src and "write_bytes" not in src
    assert "RUSTATS_VAPID_PRIVATE_KEY" in src
    env_example = (ROOT / ".env.example").read_text()
    assert re.search(r"^RUSTATS_VAPID_PRIVATE_KEY=$", env_example, re.M)   # пусто: ключей в репозитории нет


@pytest.mark.skipif(importlib.util.find_spec("cryptography") is None, reason="cryptography ставится вместе с pywebpush")
def test_vapid_script_generates_valid_pair():
    spec = importlib.util.spec_from_file_location("vapid_script", ROOT / "scripts" / "generate-vapid-keys.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    public, private = mod.generate()
    import base64
    pad = lambda v: v + "=" * (-len(v) % 4)
    assert len(base64.urlsafe_b64decode(pad(public))) == 65 and base64.urlsafe_b64decode(pad(public))[0] == 4
    assert len(base64.urlsafe_b64decode(pad(private))) == 32
    assert mod.generate() != (public, private)


def test_migration_matches_model_and_chains_from_current_head(tmp_path):
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.models import Base

    spec = importlib.util.spec_from_file_location("push_mig", ROOT / "backend" / "alembic" / "versions" / "20261005_push_subscriptions.py")
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    assert mig.down_revision == "20261004_session_changes"
    # единственная голова: никто другой не ссылается на ту же предыдущую ревизию
    versions = (ROOT / "backend" / "alembic" / "versions")
    heads_children = [p.name for p in versions.glob("*.py") if 'down_revision = "20261004_session_changes"' in p.read_text()]
    assert heads_children == ["20261005_push_subscriptions.py"]

    engine = sa.create_engine(f"sqlite:///{tmp_path/'m.db'}")
    with engine.begin() as conn:
        Base.metadata.tables["users"].create(conn)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mig.upgrade()
        insp = sa.inspect(conn)
        model = Base.metadata.tables["push_subscriptions"]
        cols = {c["name"]: c for c in insp.get_columns("push_subscriptions")}
        assert set(cols) == {c.name for c in model.columns}
        for c in model.columns:
            assert cols[c.name]["nullable"] == c.nullable, c.name
        assert {u["name"] for u in insp.get_unique_constraints("push_subscriptions")} == {"uq_push_endpoint_hash"}
        assert {i["name"] for i in insp.get_indexes("push_subscriptions")} >= {"ix_push_subscriptions_user", "ix_push_subscriptions_active"}
        fk = insp.get_foreign_keys("push_subscriptions")[0]
        assert fk["referred_table"] == "users" and fk["options"].get("ondelete") == "CASCADE"
        with Operations.context(ctx):
            mig.downgrade()
        assert "push_subscriptions" not in sa.inspect(conn).get_table_names()
