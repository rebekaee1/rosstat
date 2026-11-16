"""Воронка письма (ADR-0034): пиксель открытия, метки переходов, отказ от учёта, отчёт, разделы Пульса."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_mail import SECRET, _rows, _run, _subscribe, _verify_all, mail_env  # noqa: F401


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _send_issue(env, client, monkeypatch, *, tracking=True, addresses=("allowed@example.com", "rebeka.ee@yandex.ru")):
    from app.config import settings

    for a in addresses:
        client.cookies.clear()
        _subscribe(client, a)
    env["sent"].clear()
    _verify_all(env)
    monkeypatch.setattr(settings, "mail_allow_all_recipients", True)
    monkeypatch.setattr(settings, "mail_tracking_enabled", tracking)
    return _run(env, send=True)


def test_open_classes_and_provider_groups():
    from app.services.mail import tracking as t

    assert t.classify_open("Mozilla/5.0 (Windows NT 5.1; rv:11.0) Gecko Firefox/11.0 (via ggpht.com GoogleImageProxy)", 600) == ("gmail_proxy", False)
    assert t.classify_open("Mozilla/5.0", 600) == ("apple_privacy", True)          # Apple Mail грузит письмо без человека
    assert t.classify_open("", 600) == ("scanner", True)
    assert t.classify_open("Mozilla/5.0 (Macintosh) AppleWebKit/605 Thunderbird/128", 5) == ("scanner", True)   # слишком быстро
    assert t.classify_open("Mozilla/5.0 (Macintosh) AppleWebKit/605 Thunderbird/128", 600) == ("mail_client", False)
    assert t.provider_of("A@Gmail.com") == "gmail" and t.provider_of("x@list.ru") == "mailru"
    assert t.provider_of("x@company.example") == "other" and t.provider_of("") == "unknown"


def test_tracking_is_off_by_default_and_letter_is_untouched(mail_env, auth_client, monkeypatch):
    _send_issue(mail_env, auth_client, monkeypatch, tracking=False)
    html = mail_env["sent"][0].get_body(("html",)).get_content()
    assert "/mail/o/" not in html and "utm_term=" not in html
    row = _rows(mail_env)[-1]
    assert row.tracked is False and row.provider in ("other", "yandex") and row.variant == "general"
    assert row.addr_verified is True and row.opens == 0


def test_pixel_and_click_marks_added_on_send_and_open_is_recorded(mail_env, auth_client, monkeypatch):
    from app.config import settings as _settings

    monkeypatch.setattr(_settings, "mail_tracking_open_pixel", True)
    from app.models import MailEvent
    from app.services.mail import tracking
    from sqlalchemy import select

    _send_issue(mail_env, auth_client, monkeypatch)
    msg = mail_env["sent"][0]
    html = msg.get_body(("html",)).get_content()
    text = msg.get_body(("plain",)).get_content()
    assert html.count("/api/v1/mail/o/") == 1 and 'width="1" height="1"' in html
    assert "utm_term=r" in html and "utm_term=r" in text
    assert "unsubscribe?t=" in text
    for line in text.splitlines():   # ссылки отписки не тронуты
        if "unsubscribe?t=" in line:
            assert "utm_term" not in line
    rows = [r for r in _rows(mail_env) if r.kind == "newsletter"]
    assert all(r.tracked for r in rows)
    row = rows[0]
    token = tracking.open_token(row.id)

    # Запрос пикселя сразу после отправки — проверка почтового сервера, а не человек.
    r = auth_client.get(f"/api/v1/mail/o/{token}.gif", headers={"user-agent": "Mozilla/5.0 (X11) Thunderbird/128"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/gif" and r.content[:6] == b"GIF89a"
    assert "no-store" in r.headers["cache-control"]
    # Испорченная ссылка: картинка отдаётся, событий нет.
    assert auth_client.get("/api/v1/mail/o/garbage.gif").status_code == 200

    async def _human_open():
        async with mail_env["session_maker"]() as db:
            ok = await tracking.record_open(db, token, "Mozilla/5.0 (via ggpht.com GoogleImageProxy)",
                                            now=_now() + timedelta(minutes=30))
            await db.commit()
            events = (await db.scalars(select(MailEvent).order_by(MailEvent.id))).all()
            return ok, [(e.kind, e.machine, e.client) for e in events]

    ok, events = asyncio.run(_human_open())
    assert ok and events == [("open", True, "scanner"), ("open", False, "gmail_proxy")]
    row = [r for r in _rows(mail_env) if r.id == row.id][0]
    assert row.opens == 2 and row.machine_opened_at is not None and row.opened_at is not None
    assert row.open_client == "gmail_proxy"


def test_personal_opt_out_disables_tracking(mail_env, auth_client, monkeypatch):
    from app.config import settings
    from app.models import Consent
    from app.services.mail import tracking
    from sqlalchemy import select

    _subscribe(auth_client, "allowed@example.com")
    _verify_all(mail_env)

    async def _opt_out():
        async with mail_env["session_maker"]() as db:
            uid = (await db.scalars(select(Consent.user_id).where(Consent.kind == "newsletter"))).first()
            db.add(Consent(user_id=uid, kind="mail_personal_revoked", version="1"))
            await db.commit()
    asyncio.run(_opt_out())
    mail_env["sent"].clear()
    monkeypatch.setattr(settings, "mail_allow_all_recipients", True)
    monkeypatch.setattr(settings, "mail_tracking_enabled", True)
    _run(mail_env, send=True)
    html = mail_env["sent"][0].get_body(("html",)).get_content()
    assert "/mail/o/" not in html and "utm_term=" not in html
    row = [r for r in _rows(mail_env) if r.kind == "newsletter"][0]
    assert row.tracked is False

    async def _open():
        async with mail_env["session_maker"]() as db:
            return await tracking.record_open(db, tracking.open_token(row.id), "Mozilla/5.0 Thunderbird",
                                              now=_now() + timedelta(hours=1))
    assert asyncio.run(_open()) is False
    from app.models import MailEvent

    assert await_count(mail_env, MailEvent) == 0


def await_count(env, model) -> int:
    from sqlalchemy import func, select

    async def _q():
        async with env["session_maker"]() as db:
            return int(await db.scalar(select(func.count()).select_from(model)) or 0)
    return asyncio.run(_q())


def test_clicks_from_site_sessions_funnel_and_report(mail_env, auth_client, monkeypatch):
    from app.models import BehaviorSession, Consent, FrontendEvent, MailEvent
    from app.services.mail import funnel, tracking
    from app.services.newsletter_personal import ab

    _send_issue(mail_env, auth_client, monkeypatch)
    rows = [r for r in _rows(mail_env) if r.kind == "newsletter"]
    assert len(rows) == 2
    a, b = rows
    key = a.campaign

    async def _scenario():
        async with mail_env["session_maker"]() as db:
            t0 = _now()
            # Человек A открыл и перешёл под своим входом, в визите открыл показатель и скачал ряд.
            await tracking.record_open(db, tracking.open_token(a.id), "Mozilla/5.0 Thunderbird", now=t0 + timedelta(minutes=40))
            db.add(BehaviorSession(session_id_hash="s-a", user_id=str(a.user_id), started_at=t0 + timedelta(minutes=45),
                                   utm_source="email", utm_medium="newsletter", utm_campaign=key, utm_content="b1-lead"))
            db.add(FrontendEvent(event_name="indicator_view", session_id_hash="s-a", user_id=str(a.user_id),
                                 params_json={"indicator": "fuel-ai92"}, occurred_at=t0 + timedelta(minutes=46)))
            db.add(FrontendEvent(event_name="download_csv", session_id_hash="s-a", user_id=str(a.user_id),
                                 params_json={"indicator": "fuel-ai92"}, occurred_at=t0 + timedelta(minutes=47)))
            # Человек B перешёл без входа: узнаём по метке письма. Робот по той же метке — не человек.
            term = ab.click_token(str(b.user_id), key)
            db.add(BehaviorSession(session_id_hash="s-b", started_at=t0 + timedelta(hours=2), utm_medium="newsletter",
                                   utm_campaign=key, utm_content="p3-series", utm_term=term))
            db.add(BehaviorSession(session_id_hash="s-bot", started_at=t0 + timedelta(hours=3), utm_medium="newsletter",
                                   utm_campaign=key, utm_content="p3-series", utm_term=term, is_webdriver=True))
            # Визит по ссылке без известного человека.
            db.add(BehaviorSession(session_id_hash="s-x", started_at=t0 + timedelta(hours=4), utm_medium="newsletter",
                                   utm_campaign=key, utm_content="p7-table-r2", device_type="mobile"))
            db.add(FrontendEvent(event_name="indicator_view", session_id_hash="s-x",
                                 params_json={"indicator": "unemployment"}, occurred_at=t0 + timedelta(hours=4, minutes=1)))
            db.add(Consent(user_id=b.user_id, kind="newsletter_revoked", version="1", granted_at=t0 + timedelta(hours=5)))
            await db.commit()
            first = await tracking.sync_clicks(db, now=t0 + timedelta(hours=6))
            await db.commit()
            second = await tracking.sync_clicks(db, now=t0 + timedelta(hours=7))
            await db.commit()
            f = await funnel.campaign_funnel(db, key, now=t0 + timedelta(days=2))
            text = await funnel.report_text(db, None, stage="итог за первые сутки", now=t0 + timedelta(days=2))
            return first, second, f, text

    first, second, f, text = asyncio.run(_scenario())
    assert (first, second) == (3, 0)                       # повторный перенос ничего не дублирует
    assert await_count(mail_env, MailEvent) == 4           # одно открытие и три перехода (один — робот)
    assert f["accepted"] == 2 and f["delivered"] == 2 and f["tracked"] == 2
    assert f["opened_people"] == 1 and f["open_rate_pct"] == 50.0
    assert f["clicked_people"] == 2 and f["click_sessions"] == 2 and f["click_sessions_machine"] == 1
    assert f["sessions_from_mail"] == 4 and f["sessions_without_person"] == 1
    # Визит без входа тоже виден: что смотрели, куда нажали (строка таблицы — «таблица»), с какого устройства.
    assert f["visit"]["top_viewed"] == {"fuel-ai92": 1, "unemployment": 1} and f["visit"]["downloads"] == 1
    assert {(x["origin"], x["block"]): x["sessions"] for x in f["places"]} == {
        ("editorial", "lead"): 1, ("personal", "series"): 1, ("personal", "table"): 1}
    assert f["devices"].get("телефон") == 1
    assert "Куда нажимали" in text and "таблица «Ваши показатели» (личный) — 1" in text and "телефон 1" in text
    assert funnel.block_label("hdr-logo") == ("—", "logo") and funnel.block_label("ftr-settings") == ("—", "settings")
    assert funnel.block_label("cta") == ("—", "cta") and funnel.block_label("") == ("—", "none")
    assert {(x["origin"], x["block"]) for x in f["blocks"]} == {("editorial", "lead"), ("personal", "series")}
    assert f["unsubscribed"] == 1 and f["unsubscribe_pct"] == 50.0
    assert f["returned"]["d1"]["people"] == 1 and f["returned"]["d1"]["window_complete"] is True
    assert f["returned"]["d7"]["window_complete"] is False
    assert f["minutes_to_open_median"] is not None and f["cuts"]["variant"]["general"]["clicked"] == 2
    assert "Открыли: <b>1</b> из 2" in text and "Перешли на сайт: <b>2</b>" in text
    assert "@" not in text and "срок не истёк" in text and "отписок больше 2 %" in text


def test_report_says_no_data_before_first_issue(mail_env):
    from app.services.mail import funnel

    async def _q():
        async with mail_env["session_maker"]() as db:
            return await funnel.report_text(db, None), await funnel.campaign_funnel(db, "nope")
    text, f = asyncio.run(_q())
    assert "Нет данных" in text and f == {"campaign": "nope", "letters": 0, "statuses": {}, "accepted": 0, "has_data": False}


def test_pulse_extra_sections_are_sums_only(mail_env, auth_client, monkeypatch):
    from app.services import pulse_extra

    _send_issue(mail_env, auth_client, monkeypatch)

    async def _q():
        async with mail_env["session_maker"]() as db:
            now = _now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return await pulse_extra.build_extra(db, now.date(), start, start + timedelta(days=1))
    extra = asyncio.run(_q())
    assert set(extra) == {"mail", "consents", "cabinet", "public_bot", "research", "world_ingest", "freshness",
                          "telegram", "calendar"}
    assert not [k for k, v in extra.items() if "error" in v], extra
    assert extra["mail"]["letters_by_kind"]["newsletter"]["sent"] == 2 and extra["mail"]["last_campaign"]["delivered"] == 2
    assert extra["consents"]["newsletter_opt_in"] == 2
    blob = str(extra)
    assert "@" not in blob and "example.com" not in blob
    lines = pulse_extra.digits_lines({**extra})
    assert any(line.startswith("Почта за день") for line in lines) and any("Согласия" in line for line in lines)


def test_sent_notice_text_is_sums_only():
    """Сообщение «рассылка прошла»: сколько ушло, что пропущено, остановка сервером — без адресов."""
    from app.services.mail import funnel

    text = funnel.format_sent_notice(
        {"key": "fe-weekly-01", "dry_run": False, "audience": 103, "no_address": 21, "unverified_skipped": 74,
         "already_sent": 0, "statuses": {"sent": 28, "suppressed": 1}, "stopped": None}, {"sent": 28, "suppressed": 1})
    assert "отправка прошла" in text and "Ушло сейчас: <b>28</b>" in text and "в стоп-листе — 1" in text
    assert "адрес не подтверждён — 74" in text and "нет адреса — 21" in text and "@" not in text
    stopped = funnel.format_sent_notice({"key": "k", "statuses": {"sent": 3, "failed": 1}, "stopped": "server_limit:554"},
                                        {"sent": 3})
    assert "остановлена почтовым сервером" in stopped
