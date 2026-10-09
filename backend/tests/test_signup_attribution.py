"""Круг 11, зона H: как пришёл зарегистрированный (user_signups) и чистка при удалении."""
import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import (
    AuthAudit, BehaviorEvent, BehaviorSession, FrontendEvent, IdentityLink, ServerSession,
    TelegramOutbox, User, UserSignup,
)
from app.services import account_erasure
from app.services import signup_attribution as sa
from tests.conftest import csrf_headers
from tests.test_auth_oauth import fake_login


def run(auth_env, coro_fn):
    async def go():
        async with auth_env["session_maker"]() as db:
            return await coro_fn(db)
    return asyncio.run(go())


def signups(auth_env):
    return run(auth_env, lambda db: _all(db, UserSignup))


async def _all(db, model):
    return (await db.execute(select(model))).scalars().all()


# --- запись в запросе регистрации -------------------------------------------------

def test_email_registration_writes_server_fields(auth_client, auth_env):
    r = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "supersecret1", "consent": True, "newsletter": True},
        headers={"X-FE-Locale": "en"},
    )
    assert r.status_code == 201, r.text
    rows = signups(auth_env)
    assert len(rows) == 1
    row = rows[0]
    assert (row.method, row.site_locale, row.newsletter, row.source) == ("email", "en", True, "request")
    assert row.filled_at is None  # остальное добирает задача атрибуции
    assert str(row.user_id) == r.json()["user"]["id"]


def test_oauth_registration_writes_provider_and_language_from_return_url(oauth_client, auth_env):
    # язык берётся из адреса возврата (next), а не из хоста callback
    fake_login(oauth_client, sub="s-1", email="s1@example.com", next="https://ru.forecasteconomy.com/account")
    rows = signups(auth_env)
    assert len(rows) == 1
    assert rows[0].method == "fake" or rows[0].method is None  # fake-провайдер не из списка боевых
    assert rows[0].site_locale == "ru"


def test_second_oauth_login_does_not_create_second_row(oauth_client, auth_env):
    fake_login(oauth_client, sub="s-2", email="s2@example.com")
    oauth_client.post("/api/v1/auth/logout", headers=csrf_headers(oauth_client))
    fake_login(oauth_client, sub="s-2", email="s2@example.com")
    assert len(signups(auth_env)) == 1


def test_record_signup_is_idempotent_and_never_raises(auth_env):
    uid = uuid.uuid4()

    async def go(db):
        db.add(User(id=uid))
        await db.commit()
        first = await sa.record_signup(db, user_id=uid, method="Email + пароль", site_locale="ru",
                                       newsletter=False, ip="203.0.113.5")
        second = await sa.record_signup(db, user_id=uid, method="vk", site_locale="en",
                                        newsletter=True, ip=None)
        broken = await sa.record_signup(db, user_id="not-a-uuid", method="vk", site_locale="en",
                                        newsletter=True, ip=None)
        rows = await _all(db, UserSignup)
        return first, second, broken, rows

    first, second, broken, rows = run(auth_env, go)
    assert (first, second, broken) == (True, False, False)
    assert len(rows) == 1 and rows[0].method == "email" and rows[0].site_locale == "ru"


def test_me_reports_is_new_only_for_fresh_accounts(auth_client):
    auth_client.post("/api/v1/auth/register",
                     json={"email": "fresh@example.com", "password": "supersecret1", "consent": True})
    assert auth_client.get("/api/v1/auth/me").json()["user"]["is_new"] is True


# --- дополнение из первой сессии ---------------------------------------------------

def _seed_visit(db, uid, created, *, visitor="vis-1", trigger_event=None, trigger_param=None):
    first = created - timedelta(days=3, hours=1)
    db.add(User(id=uid, created_at=created))
    db.add(UserSignup(user_id=uid, created_at=created, method="email", site_locale=None, source="request"))
    db.add(IdentityLink(user_id=str(uid), visitor_id_hash=visitor, first_seen=created, last_seen=created))
    db.add(BehaviorSession(
        session_id_hash="s-first", visitor_id_hash=visitor, started_at=first, channel="search",
        referrer_host="yandex.ru", utm_source=None, device_type="mobile", browser="Safari", os="iOS",
        language="ru-RU", entry_page="/indicator/cpi", country="Германия", geo_region="Berlin",
        site_locale="en", is_synthetic=False))
    db.add(BehaviorSession(
        session_id_hash="s-second", visitor_id_hash=visitor, started_at=created - timedelta(minutes=10),
        channel="direct", device_type="desktop", is_synthetic=False))
    for i in range(3):
        db.add(BehaviorEvent(event_type="pageview", visitor_id_hash=visitor, session_id_hash="s-first",
                             occurred_at=first + timedelta(minutes=i), page="/indicator/cpi"))
    db.add(BehaviorEvent(event_type="pageview", visitor_id_hash=visitor, session_id_hash="s-second",
                         occurred_at=created - timedelta(minutes=5), page="/register"))
    # после регистрации — не считается «до»
    db.add(BehaviorEvent(event_type="pageview", visitor_id_hash=visitor, session_id_hash="s-second",
                         occurred_at=created + timedelta(minutes=5), page="/account"))
    if trigger_event:
        db.add(FrontendEvent(event_name=trigger_event, visitor_id_hash=visitor,
                             occurred_at=created - timedelta(minutes=3), params_json=trigger_param or {}))


def test_attribution_fills_channel_device_landing_trigger_and_counts(auth_env):
    uid = uuid.uuid4()
    created = datetime.utcnow() - timedelta(hours=2)

    async def go(db):
        _seed_visit(db, uid, created, trigger_event="download_limit")
        await db.commit()
        n = await sa.ensure_signup_attribution(db)
        return n, (await _all(db, UserSignup))[0]

    n, row = run(auth_env, go)
    assert n == 1
    assert (row.channel, row.referrer_host, row.device_type, row.browser, row.os) == (
        "search", "yandex.ru", "mobile", "Safari", "iOS")
    assert row.landing_page == "/indicator/cpi"
    assert row.browser_lang == "ru-RU"
    assert row.trigger == "gate_download"
    assert (row.sessions_before, row.pageviews_before, row.days_to_signup) == (2, 4, 3)
    # страна и язык сайта дополняются из первой сессии, только если сервер не знал их сам
    assert row.country == "Германия" and row.site_locale == "en"
    assert row.filled_at is not None


def test_attribution_is_not_repeated_for_filled_rows(auth_env):
    uid = uuid.uuid4()
    created = datetime.utcnow() - timedelta(hours=2)

    async def go(db):
        _seed_visit(db, uid, created)
        await db.commit()
        return await sa.ensure_signup_attribution(db), await sa.ensure_signup_attribution(db)

    assert run(auth_env, go) == (1, 0)


def test_fresh_signup_waits_for_identity_links(auth_env):
    """Регистрация моложе 15 минут ещё не обрабатывается (identity_links появляются позже)."""
    uid = uuid.uuid4()

    async def go(db):
        db.add(User(id=uid))
        db.add(UserSignup(user_id=uid, created_at=datetime.utcnow() - timedelta(minutes=2), method="email"))
        await db.commit()
        return await sa.ensure_signup_attribution(db)

    assert run(auth_env, go) == 0


def test_visitor_without_analytics_keeps_only_server_fields(auth_env):
    """Нет ни identity_links, ни сессий: остаются метод и язык, остальное пусто (не ноль)."""
    uid = uuid.uuid4()
    created = datetime.utcnow() - timedelta(hours=2)

    async def go(db):
        db.add(User(id=uid, created_at=created))
        db.add(UserSignup(user_id=uid, created_at=created, method="yandex", site_locale="ru",
                          country="Россия", source="request"))
        await db.commit()
        await sa.ensure_signup_attribution(db)
        return (await _all(db, UserSignup))[0]

    row = run(auth_env, go)
    assert (row.method, row.site_locale, row.country) == ("yandex", "ru", "Россия")
    assert row.channel is None and row.device_type is None and row.landing_page is None
    assert row.sessions_before is None and row.days_to_signup is None
    # без следов посетителя «что подтолкнуло» неизвестно: это не «direct»
    assert row.trigger is None and row.filled_at is not None


def test_refill_picks_up_late_identity_links(auth_env):
    uid = uuid.uuid4()
    created = datetime.utcnow() - timedelta(hours=2)

    async def go(db):
        db.add(User(id=uid, created_at=created))
        db.add(UserSignup(user_id=uid, created_at=created, method="email"))
        await db.commit()
        await sa.ensure_signup_attribution(db)       # ничего не нашли
        first = (await _all(db, UserSignup))[0].channel
        db.add(IdentityLink(user_id=str(uid), visitor_id_hash="late", first_seen=created, last_seen=created))
        db.add(BehaviorSession(session_id_hash="late-s", visitor_id_hash="late",
                               started_at=created - timedelta(hours=1), channel="social", device_type="desktop",
                               is_synthetic=False))
        await db.commit()
        changed = await sa.refill_empty_attribution(db, since=created - timedelta(days=1))
        return first, changed, (await _all(db, UserSignup))[0].channel

    assert run(auth_env, go) == (None, 1, "social")


def test_trigger_prefers_client_value_then_latest_wall():
    now = datetime(2026, 10, 9, 12, 0)
    events = [
        ("register_nudge_cta", {}, now - timedelta(minutes=20)),
        ("chart_image_blocked", {}, now - timedelta(minutes=2)),
    ]
    assert sa.trigger_from_events(events, now) == "gate_chart_image"
    events.append(("signup", {"trigger": "header"}, now))
    assert sa.trigger_from_events(events, now) == "header"
    assert sa.trigger_from_events([("scroll_depth", {}, now)], now) is None


@pytest.mark.parametrize("country,code,expected", [
    ("Россия", None, True), ("Russia", None, True), ("Германия", None, False),
    (None, "RU", True), (None, "DE", False), (None, None, None), ("", "", None),
])
def test_is_russia(country, code, expected):
    assert sa.is_russia(country, code) is expected


# --- восстановление истории из архива Telegram ------------------------------------

NEW_USER_TEXT = (
    "🆕 <b>Новый пользователь</b>\nВерсия сайта: английская\nСпособ входа: OAuth (yandex)\n"
    "Email: x@example.com\nТелефон: —\nИмя: X\nРассылка: да\nIP: 1.2.3.4\nUser-Agent: Mozilla\n"
    "ID: <code>{uid}</code>"
)


def test_parse_new_user_message_reads_language_method_newsletter_and_id():
    uid = uuid.uuid4()
    info = sa.parse_new_user_message(NEW_USER_TEXT.format(uid=uid))
    assert info == {"user_id": uid, "site_locale": "en", "method": "yandex", "newsletter": True}
    # старое сообщение без строки «Версия сайта»: язык не угадываем
    old = "🆕 <b>Новый пользователь</b>\nСпособ входа: Email + пароль\nРассылка: нет\nID: <code>%s</code>" % uid
    assert sa.parse_new_user_message(old) == {"user_id": uid, "method": "email", "newsletter": False}
    assert sa.parse_new_user_message(None) == {}
    assert sa.parse_new_user_message("мусор") == {}


def test_backfill_from_outbox_creates_rows_for_all_users_without_touching_the_archive(auth_env):
    u_en, u_old, u_none = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    async def go(db):
        for uid in (u_en, u_old, u_none):
            db.add(User(id=uid, created_at=datetime(2026, 9, 1)))
        # одно сообщение пришло двум получателям: строк в архиве две, человек один
        for chat in ("1", "2"):
            db.add(TelegramOutbox(chat_id=chat, method="sendMessage", kind="new_user", ok=True,
                                  text=NEW_USER_TEXT.format(uid=u_en)))
        db.add(TelegramOutbox(chat_id="1", method="sendMessage", kind="new_user", ok=True,
                              text="🆕 <b>Новый пользователь</b>\nСпособ входа: Email + пароль\nID: <code>%s</code>" % u_old))
        db.add(TelegramOutbox(chat_id="1", method="sendMessage", kind="digest", ok=True, text="дайджест"))
        await db.commit()
        stats = await sa.backfill_from_outbox(db)
        again = await sa.backfill_from_outbox(db)
        rows = {r.user_id: r for r in await _all(db, UserSignup)}
        archive = (await db.scalar(select(func.count()).select_from(TelegramOutbox)))
        return stats, again, rows, archive

    stats, again, rows, archive = run(auth_env, go)
    assert stats["created"] == 3 and stats["without_locale"] == 2
    assert again["created"] == 0 and again["already_present"] == 3
    assert (rows[u_en].site_locale, rows[u_en].method, rows[u_en].source) == ("en", "yandex", "backfill")
    assert rows[u_old].site_locale is None and rows[u_old].method == "email"
    assert rows[u_none].site_locale is None and rows[u_none].method is None
    assert archive == 4  # архив не тронут: строки new_user не удалены и не очищены


# --- удаление аккаунта ------------------------------------------------------------

def test_delete_account_removes_signup_links_and_unlinks_events(auth_client, auth_env):
    r = auth_client.post("/api/v1/auth/register",
                         json={"email": "gone@example.com", "password": "supersecret1", "consent": True})
    uid = r.json()["user"]["id"]

    async def seed(db):
        db.add(IdentityLink(user_id=uid, visitor_id_hash="v-gone"))
        db.add(FrontendEvent(event_name="indicator_view", user_id=uid, authed=True, visitor_id_hash="v-gone"))
        db.add(FrontendEvent(event_name="indicator_view", user_id=str(uuid.uuid4()), authed=True))
        db.add(BehaviorEvent(event_type="click", user_id=uid, visitor_id_hash="v-gone"))
        db.add(BehaviorSession(session_id_hash="s-gone", user_id=uid, started_at=datetime.utcnow()))
        db.add(ServerSession(day=datetime.utcnow().date(), visitor_id_hash="v-gone", user_id=uid,
                             started_at=datetime.utcnow(), ended_at=datetime.utcnow()))
        await db.commit()

    run(auth_env, seed)
    assert len(signups(auth_env)) == 1

    d = auth_client.delete("/api/v1/auth/account", headers=csrf_headers(auth_client))
    assert d.status_code == 200, d.text

    async def after(db):
        return {
            "signups": len(await _all(db, UserSignup)),
            "links": len(await _all(db, IdentityLink)),
            "fe_with_user": await db.scalar(select(func.count()).select_from(FrontendEvent)
                                            .where(FrontendEvent.user_id == uid)),
            "fe_total": await db.scalar(select(func.count()).select_from(FrontendEvent)),
            "behavior_user": await db.scalar(select(func.count()).select_from(BehaviorEvent)
                                             .where(BehaviorEvent.user_id == uid)),
            "pending": [a.detail for a in await _all(db, AuthAudit) if a.event == account_erasure.PENDING_EVENT],
        }

    state = run(auth_env, after)
    assert state["signups"] == 0 and state["links"] == 0
    assert state["fe_with_user"] == 0 and state["fe_total"] == 2   # события не удалены, связь с человеком снята
    assert state["behavior_user"] == 1                              # большие таблицы чистит ночная уборка
    assert state["pending"] == [uid]


def test_nightly_erasure_nulls_user_id_in_big_tables_and_clears_marker(auth_env):
    uid = str(uuid.uuid4())
    other = str(uuid.uuid4())

    async def go(db):
        now = datetime.utcnow()
        for i, who in enumerate((uid, uid, other)):
            db.add(BehaviorEvent(event_type="click", user_id=who))
            db.add(BehaviorSession(session_id_hash=f"s{i}", user_id=who, started_at=now - timedelta(days=i * 10)))
            db.add(ServerSession(day=now.date(), visitor_id_hash=f"v{i}", user_id=who, started_at=now + timedelta(seconds=i),
                                 ended_at=now + timedelta(seconds=i)))
        db.add(AuthAudit(user_id=None, event=account_erasure.PENDING_EVENT, detail=uid))
        await db.commit()
        stats = await account_erasure.process_pending_erasures(db)
        left = {
            "events": await db.scalar(select(func.count()).select_from(BehaviorEvent).where(BehaviorEvent.user_id == uid)),
            "sessions": await db.scalar(select(func.count()).select_from(BehaviorSession).where(BehaviorSession.user_id == uid)),
            "server": await db.scalar(select(func.count()).select_from(ServerSession).where(ServerSession.user_id == uid)),
            "other_events": await db.scalar(select(func.count()).select_from(BehaviorEvent).where(BehaviorEvent.user_id == other)),
            "markers": [(a.event, a.detail) for a in await _all(db, AuthAudit)],
        }
        again = await account_erasure.process_pending_erasures(db)
        return stats, left, again

    stats, left, again = run(auth_env, go)
    assert (stats["behavior_events"], stats["behavior_sessions"], stats["server_sessions"]) == (2, 2, 2)
    assert left["events"] == left["sessions"] == left["server"] == 0
    assert left["other_events"] == 1  # чужие события не тронуты
    assert left["markers"] == [(account_erasure.DONE_EVENT, None)]  # идентификатор из журнала исчез
    assert again["pending"] == 0
