"""Персональный выпуск рассылки (ADR-0033): предметы, профиль, отбор, сборка, отправка, приватность.

Сквозной сценарий: события сайта и кабинет → профиль → личные блоки с числами из базы → выпуск в
формате почты → рендер письма (HTML с метками блоков, без диапазона, без адреса).
"""
import asyncio
import json
import logging
import uuid
from datetime import date, datetime, timedelta

import pytest

SECRET = "test-mail-secret-0123456789abcdef"
EMAIL = "reader@example.com"

BASE_ISSUE = {
    "key": "fe-weekly-test-01",
    "ru": {
        "subject": "Бензин подешевел", "preheader": "Коротко о неделе.", "title": "Топливо дешевеет",
        "intro": "Вступление редакции.", "masthead": "Неделя в цифрах · № 1",
        "blocks": [
            {"type": "lead", "kicker": "Число недели", "title": "Бензин АИ-92", "value": "70,01 ₽",
             "text": "Цена литра.", "source": "Росстат", "url": "https://ru.forecasteconomy.com/russia/indicator/fuel-ai92"},
            {"type": "story", "kicker": "Мир", "title": "Нефть Brent", "value": "92,14 $", "source": "EIA",
             "url": "https://ru.forecasteconomy.com/russia/indicator/brent"},
            {"type": "story", "kicker": "Рубль", "title": "Доллар", "value": "82,15 ₽", "source": "Банк России",
             "url": "https://ru.forecasteconomy.com/currencies/indicator/usd-rub"},
            {"type": "calendar", "kicker": "Календарь", "title": "Что выйдет дальше",
             "url": "https://ru.forecasteconomy.com/russia/calendar",
             "entries": [{"date": "18 декабря", "title": "решение Банка России", "date_iso": "2099-12-18"}]},
        ],
        "cta_label": "Открыть", "cta_url": "https://ru.forecasteconomy.com/", "outro": "Пишите нам.",
        "signoff": "Редакция Forecast Economy",
    },
    "en": {
        "subject": "Oil fell", "title": "The week", "intro": "Editorial intro.",
        "blocks": [{"type": "lead", "kicker": "Number of the week", "title": "Brent", "value": "$92.14",
                    "source": "EIA", "url": "https://forecasteconomy.com/russia/indicator/brent"}],
    },
}


# --- чистые функции -----------------------------------------------------------------------

def test_subject_keys_and_event_parsing():
    from app.services.newsletter_personal.subjects import (
        normalize_query, parse_key, subjects_from_event, subjects_from_path,
    )

    assert parse_key("ru:cpi").key == "ru:cpi"
    assert parse_key("w:russia:cpi").key == "ru:cpi"          # Россия в ключе мира — свой показатель
    assert parse_key("w:united-states:us-cpi-all").place == "united-states"
    assert parse_key("r:moskva:ceni-ai95").kind == "r"
    assert parse_key("ru:<script>") is None and parse_key("x:y") is None and parse_key("t:nope") is None
    kind, subs = subjects_from_event("download_excel", {"indicator": "region:primorskiy-kray:invest", "region": "primorskiy-kray"})
    assert kind == "download" and [s.key for s in subs] == ["r:primorskiy-kray:invest", "reg:primorskiy-kray"]
    kind, subs = subjects_from_event("indicator_view", {"indicator": "fuel-diesel", "category": "prices"})
    assert kind == "view" and {s.key for s in subs} == {"ru:fuel-diesel", "t:prices"}
    kind, subs = subjects_from_event("search_select", {"q": "x", "code": "us-cpi-all", "scope": "world", "country": "united-states"})
    assert [s.key for s in subs][:1] == ["w:united-states:us-cpi-all"]
    kind, subs = subjects_from_event("compare_open", {"codes": "w:united-states:hicp-index,w:china:hicp-index"})
    assert kind == "compare" and len(subs) == 2
    assert [s.key for s in subjects_from_path("https://ru.forecasteconomy.com/russia/region/moskva/ceni-dt?x=1")] == \
        ["r:moskva:ceni-dt", "reg:moskva"]
    assert subjects_from_path("/currencies/indicator/usd-rub")[0].key == "ru:usd-rub"
    assert normalize_query("  Цена БЕНЗИНА, 2025!! ") == "цена бензина 2025"


def test_profile_weights_decay_dedupe_tiers_and_fatigue():
    from app.services.newsletter_personal.profile import Signal, build_profile, decay
    from app.services.newsletter_personal.subjects import parse_key

    now = datetime(2026, 11, 15, 12)
    assert decay(4.0, 30, 30) == pytest.approx(2.0)
    assert decay(10.0, None, 400) == 10.0
    s = lambda kind, key, days: Signal(kind, parse_key(key), now - timedelta(days=days))  # noqa: E731
    sigs = [s("view", "ru:cpi", 1), s("view", "ru:cpi", 1)]  # тот же день — один раз
    p = build_profile("u", sigs, now=now)
    assert p.subjects[0]["signals"] == {"view": 1} and p.tier == "light"
    rich = [s("download", "ru:fuel-diesel", 2), s("search_select", "ru:key-rate", 3), s("watch", "ru:cpi", 100),
            s("view", "ru:usd-rub", 200)]
    p = build_profile("u", rich, now=now)
    assert p.tier == "rich"
    assert p.subjects[0]["key"] == "ru:cpi"          # колокольчик без затухания
    old_view = next(x for x in p.subjects if x["key"] == "ru:usd-rub")
    # 200 дней при полураспаде 30: интерес слабеет до нижней границы, но не исчезает (16.11.2026).
    assert old_view["score"] == pytest.approx(0.3001, abs=1e-3)
    assert decay(1.0, 30, 200) < 0.02 and decay(1.0, 30, 200, 0.35) == pytest.approx(0.35)
    tired = build_profile("u", rich, now=now, fatigue={"ru:cpi": 5})
    assert tired.score("ru:cpi") < p.score("ru:cpi")
    assert build_profile("u", [], now=now).tier == "cold"
    pre = build_profile("u", [Signal("download", parse_key("ru:cpi"), now, pre_signup=True)], now=now)
    post = build_profile("u", [Signal("download", parse_key("ru:cpi"), now)], now=now)
    assert pre.score("ru:cpi") < post.score("ru:cpi")


def test_pick_diversity_one_topic_and_three_per_generator():
    from app.services.newsletter_personal.compose import Candidate, pick

    cands = [Candidate("series", f"ru:a{i}", {}, 10 - i, topic="prices") for i in range(3)]
    cands += [Candidate("series", "ru:b", {}, 5, topic="rates"), Candidate("search", "ru:c", {}, 4, topic="fuel")]
    chosen = pick(cands, 3)
    assert [c.subject for c in chosen] == ["ru:a0", "ru:b", "ru:c"]
    chosen = pick(cands, 5)
    assert sum(1 for c in chosen if c.gen == "series") == 3   # предел на генератор — три (16.11.2026)


def test_block_check_rules():
    from app.services.newsletter_personal.build import check_block

    fc = {"type": "forecast", "title": "Инфляция", "value": "5–6 %", "source": "Росстат"}
    assert check_block(fc, "ru").startswith("invalid")
    fc2 = {"type": "forecast", "title": "Инфляция", "value": "5,7 %", "source": "Росстат", "lower": 5}
    assert check_block(fc2, "ru").startswith("invalid")
    assert check_block({"type": "story", "title": "X", "value": "1", "source": "Росстат"}, "ru") is None
    assert check_block({"type": "story", "title": "X", "value": "1"}, "ru") == "no_source"
    assert check_block({"type": "story", "title": "Инфляция", "value": "1", "source": "Rosstat"}, "en") == "cyrillic_in_en"
    assert check_block({"type": "story", "title": "Данные по API", "value": "1", "source": "Р"}, "ru") == "forbidden_words"


def test_ab_buckets_are_stable_and_holdout_respected(monkeypatch):
    from app.config import settings
    from app.services.newsletter_personal import ab

    monkeypatch.setattr(settings, "mail_token_secret", SECRET)
    uid = str(uuid.uuid4())
    assert ab.arm(uid, 0) == "personal" and ab.arm(uid, 100) == "control"
    assert ab.arm(uid, 50) == ab.arm(uid, 50)
    share = sum(ab.arm(str(uuid.uuid4()), 20) == "control" for _ in range(2000)) / 2000
    assert 0.15 < share < 0.25
    t1 = ab.click_token(uid, "k")
    assert t1 and t1.startswith("r") and len(t1) == 11 and t1 == ab.click_token(uid, "k") != ab.click_token(uid, "k2")


# --- база ---------------------------------------------------------------------------------

@pytest.fixture
def nl_env(auth_env, monkeypatch):
    from app.config import settings
    from app.services.newsletter_personal import store

    monkeypatch.setattr(settings, "mail_token_secret", SECRET)
    monkeypatch.setattr(settings, "newsletter_personal_batch_pause_seconds", 0)
    store.reset_ready_cache()
    return auth_env


def _utcnow():
    from app.services.newsletter_personal.build import _utcnow as now

    return now()


def _run(coro):
    return asyncio.run(coro)


async def _seed(sm, *, today: date, behavior_user: bool = True, locale: str = "ru") -> uuid.UUID:
    """Подписчик с адресом, показатели с данными, регион и события сайта."""
    from app.models import (
        BehaviorSession, Consent, EmailCredential, FrontendEvent, Indicator, IndicatorData, Region,
        RegionIndicator, RegionMonthlyPoint, User, UserSignup,
    )

    async with sm() as db:
        user = User(status="active", created_at=datetime(2026, 9, 1))
        db.add(user)
        await db.flush()
        db.add(EmailCredential(user_id=user.id, email=EMAIL, password_hash="x", email_verified=True))
        db.add(Consent(user_id=user.id, kind="newsletter", version="1", granted_at=datetime(2026, 9, 1)))
        db.add(UserSignup(user_id=user.id, site_locale=locale, country_code="RU" if locale == "ru" else "US",
                          landing_page="/russia/indicator/wages-nominal", created_at=datetime(2026, 9, 1)))
        specs = [
            ("fuel-ai92", "Цены на бензин АИ-92", "Gasoline AI-92", "руб./л", "weekly", "Цены",
             [(today - timedelta(days=7 * i), 70.0 + i * 0.5) for i in range(6)]),
            ("fuel-diesel", "Цены на дизельное топливо", "Diesel fuel", "руб./л", "weekly", "Цены",
             [(today - timedelta(days=7 * i), 86.0 + i * 0.1) for i in range(6)]),
            ("key-rate", "Ключевая ставка ЦБ РФ", "Key rate", "%", "daily", "Ставки",
             [(today - timedelta(days=i), 14.0 if i < 5 else 15.0) for i in range(30)]),
            ("wages-nominal", "Средняя заработная плата", "Average wage", "руб.", "monthly", "Рынок труда",
             [(date(2026, m, 1), 100000.0 + m * 1000) for m in range(1, (today.month - 1) or 1)]),
            ("usd-rub", "Курс доллара США", "USD/RUB", "руб.", "daily", "Валюты",
             [(today - timedelta(days=i), 82.0 + i * 0.01) for i in range(20)]),
            ("brent", "Нефть Brent", "Brent crude", "USD/баррель", "daily", "Товарные рынки",
             [(today - timedelta(days=i), 92.0) for i in range(20)]),
        ]
        for code, name, name_en, unit, freq, cat, pts in specs:
            ind = Indicator(code=code, name=name, name_en=name_en, unit=unit, frequency=freq, category=cat,
                            source="Росстат" if code != "key-rate" else "Банк России", is_active=True, is_listed=True)
            db.add(ind)
            await db.flush()
            for d, v in pts:
                db.add(IndicatorData(indicator_id=ind.id, date=d, value=v))
        russia = Region(slug="russia", name="Российская Федерация", kind="country")
        sverd = Region(slug="sverdlovskaya-oblast", name="Свердловская область", kind="region")
        db.add_all([russia, sverd])
        ri = RegionIndicator(code="ceni-ai95", table_code="p", section_num=1, section_name="Цены",
                             name="Потребительские цены на бензин АИ-95, рублей за литр", unit="рублей за литр",
                             is_listed=True)
        db.add(ri)
        await db.flush()
        for m, (a, b) in {202609: (74.0, 76.0), 202610: (75.6, 77.1)}.items():
            db.add(RegionMonthlyPoint(indicator_id=ri.id, region_id=sverd.id, month=m, value=a))
            db.add(RegionMonthlyPoint(indicator_id=ri.id, region_id=russia.id, month=m, value=b))
        if behavior_user:
            uid = str(user.id)
            now = datetime.combine(today, datetime.min.time()) + timedelta(hours=10)
            events = [
                ("download_excel", {"indicator": "fuel-diesel", "category": "prices"}, 20),
                ("indicator_view", {"indicator": "fuel-diesel", "category": "prices"}, 3),
                ("search_select", {"q": "ключевая ставка", "code": "key-rate", "scope": "russia"}, 4),
                ("indicator_view", {"indicator": "key-rate", "category": "rates"}, 4),
                ("indicator_view", {"indicator": "wages-nominal", "category": "labor"}, 6),
                ("search_select", {"q": "зарплата", "code": "wages-nominal", "scope": "russia"}, 6),
                ("region_indicator_view", {"region": "sverdlovskaya-oblast", "code": "ceni-ai95"}, 2),
                ("search_select", {"q": "бензин екатеринбург", "code": "ceni-ai95", "scope": "region_indicator",
                                   "region": "sverdlovskaya-oblast"}, 2),
                ("indicator_view", {"indicator": "usd-rub", "category": "currencies"}, 1),
                ("search_query", {"q": "секретный запрос про налоги", "results": 0}, 1),
            ]
            for name, params, days in events:
                db.add(FrontendEvent(event_name=name, user_id=uid, visitor_id_hash="v1", session_id_hash="s1",
                                     params_json=params, occurred_at=now - timedelta(days=days)))
            db.add(BehaviorSession(session_id_hash="s1", visitor_id_hash="v1", user_id=uid, started_at=now,
                                   timezone="Asia/Yekaterinburg"))
        await db.commit()
        return user.id


def _issue():
    from app.services.mail import campaign

    return campaign.parse_issue(json.loads(json.dumps(BASE_ISSUE)))


def _build(env, uid, **kw):
    from app.services.newsletter_personal.build import Builder
    from app.services.newsletter_personal.signals import collect

    async def _q():
        async with env["session_maker"]() as db:
            b = Builder(db, _issue(), behavior=kw.pop("behavior", True), holdout_pct=kw.pop("holdout", 0),
                        subject_ab_pct=kw.pop("subject_ab", 0), **kw)
            us = (await collect(db, [uid], now=b.now, behavior=b.behavior))[str(uid)]
            return await b.build(us, "ru")
    return _run(_q())


def test_end_to_end_profile_issue_render(nl_env, caplog):
    """Сквозной: события → профиль → личные блоки (числа из базы) → рендер письма почтой."""
    from app.services.mail import campaign

    today = date.today()
    uid = _run(_seed(nl_env["session_maker"], today=today))
    caplog.set_level(logging.DEBUG, logger="app.services.newsletter_personal")
    res = _build(nl_env, uid)
    assert res.status == "built" and res.tier == "rich"
    personal = [m for m in res.blocks_meta if m.get("origin") == "personal" and m.get("pos")]
    gens = {m.get("gen") for m in personal}
    assert {"download", "search", "region"} <= gens, gens
    blocks = res.payload["blocks"]
    assert blocks[0]["type"] == "lead"                     # «Число недели» редакции — первым
    by_subject = {m.get("subject"): blocks[m["pos"] - 1] for m in personal if m.get("subject")}
    diesel = by_subject["ru:fuel-diesel"]
    assert diesel["value"] == "86\u00a0руб./л"                  # последнее значение ряда из базы
    assert "Вы скачивали" in diesel["why"] or diesel["kicker"] == "Вы скачивали"
    region = by_subject["r:sverdlovskaya-oblast:ceni-ai95"]
    assert region["value"] == "75,6\u00a0₽/л" and "77,1\u00a0₽/л" in region["text"]
    # Блок о долларе редакции остаётся, личного дубля нет; Brent — редакции.
    assert any(d.get("reason") == "covered_by_editorial" and d["subject"] == "ru:usd-rub"
               for d in res.blocks_meta if d.get("origin") == "dropped")
    # Доля редакции при уровне «много» — не меньше трети содержательных блоков.
    content = [m for m in res.blocks_meta if m.get("pos") and m.get("type") not in ("section", "calendar")]
    editorial = [m for m in content if m["origin"] == "editorial"]
    assert len(editorial) * 3 >= len(content)
    # Метки блоков: свои p<N>-<генератор>, у редакции прежние b<N>-<тип>.
    assert all(f"utm_content=p{m['pos']}-" in blocks[m["pos"] - 1]["url"] for m in personal if blocks[m["pos"] - 1].get("url"))
    # Личная строка стоит в начале главы «Для вас», вступление редакции не меняется (16.11.2026).
    section = next(b for b in res.payload["blocks"] if b.get("type") == "section")
    assert res.payload["personal_note"] and "по вашим темам" in section["text"]
    assert "по вашим темам" not in res.payload["intro"]
    # Рендер почтой.
    digest = campaign.personal_digest(_issue(), "ru", res.payload)
    rendered, _ = campaign.render_for(_issue(), "ru", str(uid), digest)
    assert "utm_content=p" in rendered.html and "86" in rendered.html and "руб./л" in rendered.html
    assert "Для вас".upper() in rendered.text or "Для вас" in rendered.text
    assert EMAIL not in rendered.html
    # Текст запроса не выходит ни в письмо, ни в журнал, ни в разметку блоков.
    blob = json.dumps(res.payload, ensure_ascii=False) + json.dumps(res.blocks_meta, ensure_ascii=False, default=str)
    assert "налоги" not in blob and "екатеринбург" not in blob and EMAIL not in blob
    assert "налоги" not in caplog.text and EMAIL not in caplog.text


def test_behavior_flag_off_gives_honest_general_issue(nl_env):
    uid = _run(_seed(nl_env["session_maker"], today=date.today()))
    res = _build(nl_env, uid, behavior=False)
    # Остаётся только посадочная страница регистрации: мало данных, личный блок — зарплата.
    assert res.status in ("built", "general")
    assert all(m.get("gen") not in ("download", "search", "region") for m in res.blocks_meta)


def test_cold_user_gets_editorial_issue_unchanged(nl_env):
    from app.services.newsletter_personal.build import digest_to_dict

    async def _q():
        from app.models import UserSignup

        uid = await _seed(nl_env["session_maker"], today=date.today(), behavior_user=False)
        async with nl_env["session_maker"]() as db:
            s = await db.get(UserSignup, uid)
            s.landing_page = None
            await db.commit()
        return uid
    uid = _run(_q())
    res = _build(nl_env, uid)
    assert res.status == "general" and res.tier == "cold"
    assert res.payload["blocks"] == digest_to_dict(_issue().by_locale["ru"])["blocks"]


def test_opt_out_and_control_group(nl_env):
    from app.services.newsletter_personal.signals import personal_off, set_mail_personalization

    uid = _run(_seed(nl_env["session_maker"], today=date.today()))

    async def _off():
        async with nl_env["session_maker"]() as db:
            assert await set_mail_personalization(db, uid, False, source="test") is True
            assert await set_mail_personalization(db, uid, False, source="test") is False
            await db.commit()
            return await personal_off(db, uid)
    assert _run(_off()) is True
    assert _build(nl_env, uid).status == "off"

    async def _on():
        async with nl_env["session_maker"]() as db:
            await set_mail_personalization(db, uid, True)
            await db.commit()
    _run(_on())
    assert _build(nl_env, uid).status == "built"
    assert _build(nl_env, uid, holdout=100).status == "control"


def test_anti_repeat_and_fallback(nl_env, monkeypatch):
    from app.models import NewsletterPersonalIssue
    from app.services.newsletter_personal import compose

    uid = _run(_seed(nl_env["session_maker"], today=date.today()))
    first = _build(nl_env, uid)
    shown = {(m["subject"], m["as_of"]) for m in first.blocks_meta if m.get("origin") == "personal" and m.get("subject")}

    async def _save():
        async with nl_env["session_maker"]() as db:
            db.add(NewsletterPersonalIssue(campaign="old", user_id=uid, locale="ru", arm="personal", tier="rich",
                                           status="built", payload={}, blocks_meta=first.blocks_meta,
                                           built_at=_utcnow() - timedelta(days=7)))
            await db.commit()
    _run(_save())
    second = _build(nl_env, uid)
    again = {(m["subject"], m["as_of"]) for m in second.blocks_meta if m.get("origin") == "personal" and m.get("subject")}
    assert not ({s for s in shown if not s[0].startswith("fc:")} & again)   # тот же факт не повторяется

    def _boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(compose, "check_candidates", _boom)
    res = _build(nl_env, uid)
    assert res.status == "fallback" and res.error.startswith("compose:")
    assert res.payload["subject"] == "Бензин подешевел"


def test_personal_subject_arm_respects_editorial_rules(nl_env):
    uid = _run(_seed(nl_env["session_maker"], today=date.today()))
    res = _build(nl_env, uid, subject_ab=100)
    assert res.subject_arm == "subj_personal"
    assert len(res.payload["subject"]) <= 50 and len(res.payload["preheader"]) <= 111


def test_build_campaign_snapshots_hook_quiet_hours_and_metrics(nl_env, monkeypatch):
    from app.config import settings
    from app.models import BehaviorSession, NewsletterPersonalIssue, NewsletterProfile
    from app.services.mail import audience, campaign
    from app.services.newsletter_personal import build, metrics

    uid = _run(_seed(nl_env["session_maker"], today=date.today()))
    issue = _issue()

    async def _go():
        async with nl_env["session_maker"]() as db:
            rep = await build.build_campaign(db, issue, persist=True, behavior=True)
            snap = (await db.execute(__import__("sqlalchemy").select(NewsletterPersonalIssue))).scalars().one()
            prof = await db.get(NewsletterProfile, uid)
            return rep, snap, prof
    rep, snap, prof = _run(_go())
    assert rep.users == 1 and rep.statuses.get("built") == 1 and rep.fact_reads >= 3
    assert prof.tier == "rich" and prof.timezone == "Asia/Yekaterinburg"
    assert EMAIL not in json.dumps([snap.payload, snap.blocks_meta, prof.subjects, prof.geo], ensure_ascii=False, default=str)

    hook = build.per_recipient_hook(issue)

    async def _hook(enabled: bool, hour_ok: bool):
        monkeypatch.setattr(settings, "newsletter_personal_enabled", enabled)
        monkeypatch.setattr(build, "in_send_window", lambda tz, now: hour_ok)
        async with nl_env["session_maker"]() as db:
            rec = await audience.resolve(db, uid)
            return await hook(db, rec, issue)
    assert _run(_hook(False, True))["blocks"] == build.digest_to_dict(issue.by_locale["ru"])["blocks"]
    assert _run(_hook(True, False)) is campaign.DEFER
    sent_payload = _run(_hook(True, True))
    assert sent_payload["blocks"] == snap.payload["blocks"]       # снимок — то, что уходит

    # Клик по личному блоку → метрика по генератору.
    first_personal = next(m for m in snap.blocks_meta if m.get("origin") == "personal" and m.get("utm_content")
                          and m.get("gen") not in ("section",))

    async def _click():
        from app.models import MailMessage

        async with nl_env["session_maker"]() as db:
            db.add(MailMessage(kind="newsletter", campaign=issue.key, user_id=uid, to_email=EMAIL, locale="ru",
                               subject="s", status="sent", sent_at=_utcnow()))
            db.add(BehaviorSession(session_id_hash="s2", user_id=str(uid), started_at=_utcnow() + timedelta(minutes=5),
                                   utm_medium="newsletter", utm_campaign=issue.key,
                                   utm_content=first_personal["utm_content"]))
            await db.commit()
            m = await metrics.campaign_metrics(db, issue.key)
            summary = await metrics.block_effect_summary(db, days=7)
            return m, summary
    m, summary = _run(_click())
    assert m["arms"]["personal"]["clicked"] == 1 and m["arms"]["personal"]["sent"] == 1
    row = next(b for b in m["blocks"] if b["pos"] == first_personal["pos"])
    assert row["clicked"] == 1 and row["ctr"] == 1.0
    gen_row = next(r for r in summary if r["generator"] == first_personal["gen"])
    assert gen_row["clicks"] == 1 and gen_row["label"]


def test_aggregates_query_map_and_related(nl_env):
    from app.models import FrontendEvent
    from app.services.newsletter_personal import store
    from app.services.newsletter_personal.signals import q_hash

    async def _q():
        now = _utcnow()
        async with nl_env["session_maker"]() as db:
            for i in range(6):
                v = f"v{i}"
                db.add(FrontendEvent(event_name="indicator_view", visitor_id_hash=v, session_id_hash=v,
                                     params_json={"indicator": "cpi"}, occurred_at=now))
                db.add(FrontendEvent(event_name="indicator_view", visitor_id_hash=v, session_id_hash=v,
                                     params_json={"indicator": "key-rate"}, occurred_at=now))
            for _ in range(3):
                db.add(FrontendEvent(event_name="search_select", params_json={"q": "Ставка ЦБ", "code": "key-rate",
                                     "scope": "russia"}, occurred_at=now))
            await db.commit()
            qn = await store.rebuild_query_map(db, now=now)
            rn = await store.rebuild_related(db, now=now)
            await db.commit()
            rel = await store.related_for(db, ["ru:cpi"])
            from app.models import NewsletterQueryMap

            row = await db.get(NewsletterQueryMap, q_hash("ставка цб"))
            return qn, rn, rel, row
    qn, rn, rel, row = _run(_q())
    assert qn == 1 and row.subject == "ru:key-rate"
    assert rn == 2 and rel == {"ru:cpi": ["ru:key-rate"]}


def test_english_issue_has_no_cyrillic_in_personal_blocks(nl_env):
    from app.services.display import contains_cyrillic
    from app.services.newsletter_personal.build import Builder
    from app.services.newsletter_personal.signals import collect

    uid = _run(_seed(nl_env["session_maker"], today=date.today(), locale="en"))

    async def _q():
        async with nl_env["session_maker"]() as db:
            b = Builder(db, _issue(), behavior=True, holdout_pct=0, subject_ab_pct=0)
            us = (await collect(db, [uid], now=b.now, behavior=True))[str(uid)]
            return await b.build(us, "en")
    res = _run(_q())
    for m in res.blocks_meta:
        if m.get("origin") == "personal" and m.get("pos"):
            blk = res.payload["blocks"][m["pos"] - 1]
            assert not contains_cyrillic(json.dumps(blk, ensure_ascii=False)), blk
    assert res.payload["personal_note"].startswith("We picked")


def test_personas_preview_build(nl_env):
    from app.services.newsletter_personal.build import Builder
    from app.services.newsletter_personal.personas import persona_signals

    _run(_seed(nl_env["session_maker"], today=date.today(), behavior_user=False))

    async def _q(name):
        async with nl_env["session_maker"]() as db:
            b = Builder(db, _issue(), behavior=True, holdout_pct=0, subject_ab_pct=0)
            us, loc = persona_signals(name, now=b.now)
            return await b.build(us, loc)
    assert _run(_q("rich")).status == "built"
    assert _run(_q("cold")).status == "general"


def test_personalization_shim_for_mail():
    from app.services import personalization

    assert callable(personalization.set_mail_personalization)
    assert callable(personalization.block_effect_summary)


def test_scale_fact_reads_do_not_grow_with_subscribers(nl_env):
    """Масштаб: факты читаются один раз на ряд за запуск, а не на подписчика."""
    from app.models import Consent, EmailCredential, FrontendEvent, User
    from app.services.newsletter_personal.build import build_campaign

    _run(_seed(nl_env["session_maker"], today=date.today()))

    async def _more():
        async with nl_env["session_maker"]() as db:
            for i in range(40):
                u = User(status="active", created_at=datetime(2026, 9, 1))
                db.add(u)
                await db.flush()
                db.add(EmailCredential(user_id=u.id, email=f"u{i}@example.com", password_hash="x", email_verified=True))
                db.add(Consent(user_id=u.id, kind="newsletter", version="1", granted_at=datetime(2026, 9, 1)))
                for code in ("fuel-diesel", "key-rate", "wages-nominal"):
                    db.add(FrontendEvent(event_name="download_excel", user_id=str(u.id), params_json={"indicator": code},
                                         occurred_at=_utcnow() - timedelta(days=2)))
            await db.commit()
            return await build_campaign(db, _issue(), persist=True, behavior=True)
    rep = _run(_more())
    assert rep.users == 41 and rep.statuses.get("built", 0) >= 40
    assert rep.fact_reads <= 12, rep.fact_reads


def test_account_export_and_delete_cover_personal_tables(nl_env, auth_client):
    """152-ФЗ: профиль и снимки — в «Моих данных» и удаляются с аккаунтом."""
    from sqlalchemy import func, select

    from app.models import NewsletterPersonalIssue, NewsletterProfile
    from app.services.newsletter_personal import build
    from tests.conftest import csrf_headers

    r = auth_client.post("/api/v1/auth/register", json={"email": "me@example.com", "password": "Very-strong-pass-1",
                                                       "consent": True, "newsletter": True})
    assert r.status_code in (200, 201), r.text
    me = auth_client.get("/api/v1/auth/me").json()["user"]

    async def _snap():
        async with nl_env["session_maker"]() as db:
            await build.build_campaign(db, _issue(), persist=True, behavior=True)
    _run(_snap())
    data = auth_client.get("/api/v1/auth/account/export").json()
    assert data["newsletter_personal"]["profile"] is not None and data["newsletter_personal"]["issues"]
    assert auth_client.delete("/api/v1/auth/account", headers=csrf_headers(auth_client)).json()["ok"] is True

    async def _count():
        async with nl_env["session_maker"]() as db:
            a = await db.scalar(select(func.count()).select_from(NewsletterProfile))
            b = await db.scalar(select(func.count()).select_from(NewsletterPersonalIssue))
            return a, b
    assert _run(_count()) == (0, 0), me


def test_first_issue_rules_no_default_fuel_and_skip_forecasts(monkeypatch):
    """16.11.2026: регион без «бензина по умолчанию»; прогноз по теме не вытесняет свои ряды и снимается списком."""
    import asyncio
    from types import SimpleNamespace

    from app.config import settings
    from app.services.newsletter_personal import compose as C
    from app.services.newsletter_personal.profile import Profile

    class NoFacts:
        async def get(self, key):
            raise AssertionError(f"ряд по умолчанию не должен запрашиваться: {key}")

    profile = Profile(user_id="u", tier="light", topics={"population": 2.0, "labor": 1.5},
                      geo={"country": "russia", "region": "respublika-mariy-el"})
    us = SimpleNamespace(signals=[], history=[], gaps=[], last_visit=None)
    item = {"id": "russia-unemployment", "theme": "unemployment", "country": {"slug": "russia"},
            "path": "/russia/indicator/unemployment", "title": "Россия: безработица", "unit": "%",
            "frequency": "monthly", "source": "Росстат",
            "forecast_end": {"date": "2027-09-01", "value": 1.77}, "last_actual": {"date": "2026-09-01", "value": 2.2}}
    ctx = C.Context(profile=profile, us=us, cache=NoFacts(), locale="ru", today=date(2026, 11, 16),
                    issue_key="k", showcase=[item], related={}, query_map={})
    assert asyncio.run(C.region_candidates(ctx, set())) == []
    fc = C.forecast_candidates(ctx, set())
    assert len(fc) == 1 and fc[0].why == "topic"
    assert fc[0].score == pytest.approx(1.5 * C.TOPIC_FORECAST_FACTOR)
    monkeypatch.setattr(settings, "newsletter_personal_skip_forecasts", "russia-inflation, russia-unemployment")
    assert C.forecast_candidates(ctx, set()) == []
    assert C.MAX_PER_GEN == 3 and C.LIMITS["light"][0] == 3


def test_change_text_rules_quarter_to_year_ago_and_percentage_points():
    """16.11.2026: квартал сравнивается с тем же кварталом год назад; доли и темпы — в п. п."""
    from app.services.newsletter_personal.facts import _change, _fit, _is_share_unit

    q = [(date(2025, 6, 1), 30000.0), (date(2025, 9, 1), 37000.0), (date(2025, 12, 1), 41000.0),
         (date(2026, 3, 1), 32000.0), (date(2026, 6, 1), 33000.0)]
    prev, text, direction = _change(q, "quarterly", "млрд руб.", "ru", 1)
    assert prev == (date(2025, 6, 1), 30000.0) and direction == "up"
    assert "к тому же кварталу прошлого года" in text and "+10,0" in text
    assert _change(q[-2:], "quarterly", "млрд руб.", "ru", 1) == (None, "", "flat")   # года назад нет — молчим
    _p, text, _d = _change([(date(2024, 1, 1), 1.02), (date(2025, 1, 1), 1.98)], "annual", "изменение за год, %", "ru", 2)
    assert "п.\xa0п." in text and "(" not in text                                   # без «процента от процента»
    _p, text, _d = _change([(date(2025, 9, 1), 2135.86), (date(2026, 9, 1), 16949.24)], "quarterly", "млн $", "ru", 2)
    assert "(" not in text                                                          # +693 % у сальдо не пишем
    assert _is_share_unit("% of GDP") and _is_share_unit("Percentage of total population") and not _is_share_unit("руб.")
    long_name = "Численность активных абонентов фиксированного и мобильного широкополосного доступа к сети Интернет на 100 человек населения"
    assert _fit(long_name, 96).endswith("…") and len(_fit(long_name, 96)) <= 97 and _fit("Бензин АИ-95", 96) == "Бензин АИ-95"


def test_signup_block_formats_then_and_now_alike():
    """17.11.2026: блок «было и стало» от даты регистрации — одинаковое число знаков, ставка без «14,0»."""
    from types import SimpleNamespace

    from app.services.newsletter_personal import compose as C

    nb = " "
    assert C._signup_pair(84.9, 82.51, "₽", "ru") == (f"84,90{nb}₽", f"82,51{nb}₽")
    assert C._signup_pair(14.5, 14.0, "%", "ru") == (f"14,5{nb}%", f"14{nb}%")
    assert C._signup_pair(14.0, 14.0, "%", "en") == ("14%", "14%")
    assert C._signup_pair(11259.4, 10322.01, "₽/г", "ru")[1].endswith("322" + nb + "₽/г")
    assert C._signup_pair(2511.1, 2475.7, "", "ru") == ("2\u202f511", "2\u202f476")
    rate = SimpleNamespace(unit="%", value=14.0)
    assert C._signup_move(rate, 14.0, "ru") == (0.0, "")
    assert C._signup_move(rate, 14.5, "ru")[1] == f"−0,5{nb}п. п."
    oil = SimpleNamespace(unit="USD/баррель", value=92.14)
    assert C._signup_move(oil, 130.03, "ru")[1] == f"−29,1{nb}%"
