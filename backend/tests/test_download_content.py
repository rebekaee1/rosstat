"""Что скачивают и где упираются в лимит (14.11.2026): содержание, роботы, регистрации после упора,
текст для Telegram, файл Excel, кнопки служебного бота."""
import asyncio
import io
import uuid
from datetime import date, datetime, timedelta

from app.config import settings
from app.models import (
    BehaviorSession, FrontendEvent, IdentityLink, Indicator, Region, RegionIndicator, ServerSession, User,
    UserSignup, WorldCountry, WorldIndicator,
)
from app.services import download_content as dc

from tests.test_analytics2 import _run_with_db

SITE = "https://ru.forecasteconomy.com"


def test_content_from_address_matches_real_events():
    """Образцы — события боевого 11–14.11.2026: у половины только `source: table-range`."""
    cases = [
        ("download_limit", {"source": "table-range"}, f"{SITE}/russia/indicator/key-rate",
         ("russia", "ru", "key-rate", "")),
        ("download_excel", {"source": "table-range"}, f"{SITE}/currencies/indicator/usd-rub",
         ("currency", "ru", "usd-rub", "")),
        ("download_limit", {"indicator": "fuel-diesel-eop-month"}, f"{SITE}/russia/indicator/fuel-diesel?mode=eop-month",
         ("russia", "ru", "fuel-diesel", "")),
        ("chart_image_blocked", {"indicator": "region:kaluzhskaya-oblast:dohody"},
         f"{SITE}/russia/region/kaluzhskaya-oblast/dohody", ("region", "region", "dohody", "kaluzhskaya-oblast")),
        ("download_excel", {"indicator": "regions-leaders:zabolevaemost"},
         f"{SITE}/russia/region/map/zabolevaemost?year=2018", ("region", "region_map", "zabolevaemost", "")),
        ("download_csv", {"indicator": "mk-weo-lp", "world": True}, f"{SITE}/north-macedonia/indicator/mk-weo-lp",
         ("world", "world", "mk-weo-lp", "north-macedonia")),
        ("chart_image_download", {}, f"{SITE}/united-states/region/california/unemployment",
         ("world_region", "world_region", "unemployment", "united-states/california")),
        ("download_csv", {}, f"{SITE}/russia/region-rating/vrp", ("rating", "region_rating", "vrp", "")),
        ("download_csv", {}, f"{SITE}/world/rating/gdp-usd/2025", ("rating", "world_rating", "gdp-usd", "")),
        # Адрес ничего не говорит — берём параметр.
        ("download_limit", {"indicator": "region:moskva:cpi"}, None, ("region", "region", "cpi", "moskva")),
        ("download_csv", {"source": "calc-mortgage"}, f"{SITE}/calculator/mortgage", ("calculator", "page", "mortgage", "")),
    ]
    for name, params, url, (section, kind, code, place) in cases:
        ref = dc.content_ref(name, params, url)
        assert (ref.section, ref.kind, ref.code, ref.place) == (section, kind, code, place), (name, url)

    cmp = dc.content_ref("compare_image_download", {"count": 2}, f"{SITE}/compare?codes=cpi,de-weo-pcpipch&rep=cpi:yoy")
    assert cmp.kind == "compare" and cmp.codes == ("cpi", "de-weo-pcpipch")
    assert dc.content_ref("download_ical", {}, f"{SITE}/russia/calendar").section == "calendar"
    assert dc.content_ref("research_download", {"report": "inflyatsiya-2026"}, f"{SITE}/research").code == "inflyatsiya-2026"
    assert dc.content_ref("download_csv", {}, f"{SITE}/login").kind == "page"
    w = dc.content_ref("download_csv", {"indicator": "world:estonia:ee-gdp"}, None)
    assert (w.kind, w.code, w.place) == ("world", "ee-gdp", "estonia")


def test_explicit_subject_params_win_over_the_address():
    """С 14.11.2026 фронт пишет `code/country/region/codes/regions` (lib/downloadSubject.js); адрес — запасной."""
    ref = dc.content_ref
    page = f"{SITE}/russia/indicator/fuel-diesel?mode=eop-month"
    r = ref("download_limit", {"indicator": "fuel-diesel-eop-month", "code": "fuel-diesel-eop-month"}, page)
    assert (r.kind, r.code) == ("ru", "fuel-diesel-eop-month")  # точный ряд, а не страница
    r = ref("download_excel", {"source": "table-range", "indicator": "usd-rub", "code": "usd-rub"},
            f"{SITE}/currencies/indicator/usd-rub")
    assert (r.section, r.code) == ("currency", "usd-rub")
    r = ref("download_csv", {"indicator": "de-gdp", "code": "de-gdp", "country": "germany", "world": True}, None)
    assert (r.kind, r.code, r.place) == ("world", "de-gdp", "germany")
    r = ref("chart_image_blocked", {"indicator": "region:moskva:vrp", "code": "vrp", "region": "moskva"}, None)
    assert (r.kind, r.code, r.place) == ("region", "vrp", "moskva")
    r = ref("download_csv", {"indicator": "world-region:california:ur", "code": "ur", "region": "california",
                             "country": "united-states"}, None)
    assert (r.kind, r.place) == ("world_region", "united-states/california")
    r = ref("download_excel", {"indicator": "regions-leaders:vrp", "code": "vrp"}, None)
    assert r.kind == "region_map"
    r = ref("chart_image_download", {"indicator": "world-regions-map:ur", "code": "ur", "country": "united-states"}, None)
    assert (r.kind, r.place) == ("world_region_map", "united-states")
    r = ref("download_limit", {"indicator": "rating:gdp-usd", "code": "gdp-usd"}, None)
    assert (r.kind, r.code) == ("world_rating", "gdp-usd")
    r = ref("compare_image_blocked", {"count": 2, "codes": "cpi,de-gdp"}, f"{SITE}/compare")
    assert r.codes == ("cpi", "de-gdp")
    r = ref("download_limit", {"indicator": "regions-compare", "regions": "moskva,tatarstan"}, None)
    assert (r.kind, r.codes) == ("regions_compare", ("moskva", "tatarstan"))
    assert dc.content_title(r, dc.Names(regions={"moskva": "Москва"})) == "Сравнение регионов: Москва, tatarstan"
    # Старые события без новых полей разбираются как раньше.
    assert ref("download_limit", {"indicator": "rating:gdp-usd"}, None).kind == "world_rating"
    assert ref("download_limit", {"indicator": "regions-compare"}, None).code == "сравнение регионов"


def test_titles_are_plain_names_not_codes():
    names = dc.Names(
        ru={"cpi": "Инфляция"}, world={"de-gdp": ("ВВП", "Германия")}, region_ind={"vrp": "ВРП"},
        regions={"moskva": "Москва"}, concepts={"gdp-usd": "ВВП в долларах"},
    )
    t = dc.content_title
    assert t(dc.ContentRef("russia", "ru", code="cpi"), names) == "Инфляция"
    assert t(dc.ContentRef("world", "world", code="de-gdp", place="germany"), names) == "ВВП — Германия"
    assert t(dc.ContentRef("region", "region", code="vrp", place="moskva"), names) == "ВРП — Москва"
    assert t(dc.ContentRef("region", "region_map", code="vrp"), names) == "ВРП — карта регионов"
    assert t(dc.ContentRef("rating", "world_rating", code="gdp-usd"), names) == "ВВП в долларах — рейтинг стран"
    assert t(dc.ContentRef("compare", "compare", codes=("cpi", "de-gdp")), names) == "Сравнение: Инфляция, ВВП (Германия)"
    # Неизвестный код не теряется: показываем код.
    assert t(dc.ContentRef("russia", "ru", code="new-code"), names) == "new-code"


def _seed(now: datetime):
    uid = uuid.uuid4()
    return [
        Indicator(code="fuel-diesel", name="Цена дизельного топлива"),
        Indicator(code="key-rate", name="Ключевая ставка ЦБ РФ"),
        Region(slug="moskva", name="Москва"),
        RegionIndicator(code="vrp", table_code="1.1", section_num=1, section_name="Экономика", name="ВРП"),
        WorldCountry(id=1, code="DE", slug="germany", name_ru="Германия", name_en="Germany"),
        WorldIndicator(country_id=1, code="de-gdp", name_ru="ВВП", name_en="GDP", provider="imf",
                       dataset_id="weo", slice_hash="x", frequency="annual"),
        # Робот и своя активность.
        ServerSession(day=(now + timedelta(hours=3)).date(), visitor_id_hash="v-bot",
                      started_at=now, ended_at=now, is_bot=True),
        BehaviorSession(session_id_hash="s1", visitor_id_hash="v1", started_at=now, channel="search",
                        device_type="mobile", country="Россия"),
        # Люди: v1 скачал дизель дважды Excel и упёрся в лимит на ставке, потом зарегистрировался;
        # v2 упёрся на дизеле и ушёл; v3 скачал карту ВРП; v-bot скачал дизель (не считается).
        FrontendEvent(event_name="download_limit", occurred_at=now - timedelta(minutes=30), session_id_hash="s1",
                      visitor_id_hash="v1", url=f"{SITE}/russia/indicator/key-rate",
                      params_json={"source": "table-range", "authed": 0}),
        FrontendEvent(event_name="download_excel", occurred_at=now - timedelta(minutes=10), session_id_hash="s1",
                      visitor_id_hash="v1", authed=True, url=f"{SITE}/russia/indicator/fuel-diesel",
                      params_json={"source": "table-range", "authed": 1}),
        FrontendEvent(event_name="download_excel", occurred_at=now - timedelta(minutes=9), session_id_hash="s1",
                      visitor_id_hash="v1", authed=True, url=f"{SITE}/russia/indicator/fuel-diesel?mode=mom",
                      params_json={"indicator": "fuel-diesel", "authed": 1}),
        FrontendEvent(event_name="download_limit", occurred_at=now - timedelta(minutes=20), session_id_hash="s2",
                      visitor_id_hash="v2", url=f"{SITE}/russia/indicator/fuel-diesel", params_json={}),
        FrontendEvent(event_name="chart_image_blocked", occurred_at=now - timedelta(minutes=19), session_id_hash="s2",
                      visitor_id_hash="v2", url=f"{SITE}/russia/indicator/fuel-diesel", params_json={}),
        FrontendEvent(event_name="download_csv", occurred_at=now - timedelta(minutes=5), session_id_hash="s3",
                      visitor_id_hash="v3", url=f"{SITE}/russia/region/map/vrp?year=2020",
                      params_json={"indicator": "regions-leaders:vrp"}),
        FrontendEvent(event_name="download_excel", occurred_at=now - timedelta(minutes=4), session_id_hash="sb",
                      visitor_id_hash="v-bot", url=f"{SITE}/russia/indicator/fuel-diesel", params_json={}),
        # Не скачивание — не попадает.
        FrontendEvent(event_name="indicator_view", occurred_at=now, session_id_hash="s3", visitor_id_hash="v3",
                      url=f"{SITE}/russia/indicator/cpi", params_json={"indicator": "cpi"}),
        User(id=uid, created_at=now - timedelta(minutes=12)),
        IdentityLink(user_id=str(uid), visitor_id_hash="v1"),
    ]


def test_collect_counts_people_excludes_robots_and_links_signups():
    now = datetime.utcnow().replace(microsecond=0)

    async def scenario(maker):
        async with maker() as db:
            db.add_all(_seed(now))
            await db.commit()
        today = (now + timedelta(hours=3)).date()
        async with maker() as db:
            return await dc.collect(db, dc.period_for_window("7", today))

    data = _run_with_db(scenario)
    s = data["summary"]
    d, w = s["downloads"], s["walls"]
    assert d["count"] == 3 and d["people"] == 2  # робот не считается
    assert d["top"][0]["title"] in ("Цена дизельного топлива", "ВРП — карта регионов")
    diesel = next(i for i in d["top"] if i["title"] == "Цена дизельного топлива")
    assert diesel["count"] == 2 and diesel["people"] == 1 and diesel["what"] == {"Excel": 2}
    assert w["count"] == 3 and w["people"] == 2 and w["signed_up"] == 1
    rate = next(i for i in w["top"] if i["title"] == "Ключевая ставка ЦБ РФ")
    assert rate["signed_up"] == 1
    diesel_wall = next(i for i in w["top"] if i["title"] == "Цена дизельного топлива")
    assert diesel_wall["people"] == 1 and diesel_wall["signed_up"] == 0
    assert d["by_channel"].get("search") == 2
    row = next(r for r in data["rows"] if r["event"] == "download_limit" and r["person"] == "v1")
    assert row["signed_up_after"] is True and row["channel"] == "search"

    text = dc.format_report(s, "7 дней")
    assert "Цена дизельного топлива" in text and "Ключевая ставка ЦБ РФ" in text
    assert "зарегистрировались 1 (50 %), ушли без регистрации 1" in text
    long = dc.format_report(dc.summarize([{**data["rows"][0], "title": "Я" * 300}]), "x")
    assert "Я" * 89 + "…" in long and "Я" * 90 not in long  # длинное название обрезано
    assert "v1" not in text and "v-bot" not in text  # хэши посетителей в текст не идут

    book = dc.build_xlsx(data)
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(book))
    assert wb.sheetnames == ["Сводка", "Что скачивали", "Где упёрлись", "Все события"]
    assert wb["Все события"].max_row == 1 + 6


def test_empty_period_says_so():
    empty = dc.summarize([])
    assert "никто ничего не скачивал" in dc.format_report(empty, "сегодня")
    assert dc.digest_lines(empty) == []


def test_period_windows():
    day = date(2026, 11, 14)
    assert dc.period_for_window("0", day).start_date == day
    y = dc.period_for_window("1", day)
    assert y.start_date == y.end_date == date(2026, 11, 13)
    p = dc.period_for_window("7", day)
    assert (p.start_date, p.end_date) == (date(2026, 11, 8), day)
    assert dc.period_for_window("900", day).days == dc.MAX_DAYS


def test_bot_menu_and_buttons(monkeypatch):
    from app.services import telegram_bot as tb

    data = {b["callback_data"] for row in tb.main_menu_keyboard()["inline_keyboard"] for b in row}
    assert {"dl:7", "export"} <= data
    kb = {b["callback_data"] for row in tb.export_keyboard()["inline_keyboard"] for b in row}
    assert {"dlx:7", "dlx:30", "dlx:90", "exs:30", "exv:1", "exv:30", "users_csv", "menu"} <= kb
    for row in tb.downloads_keyboard("30")["inline_keyboard"] + tb.export_keyboard()["inline_keyboard"]:
        for b in row:
            assert len(b["callback_data"].encode()) <= 64

    calls = []

    async def fake_report(chat_id, window):
        calls.append(("report", window))

    async def fake_file(chat_id, window):
        calls.append(("file", window))

    async def fake_export(chat_id, kind, window):
        calls.append((kind, window))

    async def fake_api(method, payload, files=None):
        return {"ok": True, "result": []}

    monkeypatch.setattr(tb, "_send_downloads_report", fake_report)
    monkeypatch.setattr(tb, "_send_downloads_file", fake_file)
    monkeypatch.setattr(tb, "_send_export_file", fake_export)
    monkeypatch.setattr(tb, "_api", fake_api)
    monkeypatch.setattr(settings, "telegram_chat_id", "42", raising=False)

    def press(value):
        asyncio.run(tb._handle_callback({"id": "1", "data": value, "message": {"chat": {"id": 42}}}))

    for value in ("dl:30", "dlx:1", "exs:90", "exv:7", "exv:90", "dl:abc", "dlx:9999"):
        press(value)
    assert calls == [("report", "30"), ("file", "1"), ("exs", "90"), ("exv", "7")]

    calls.clear()
    for text in ("/downloads", "/downloads 30", "скачивания"):
        asyncio.run(tb._handle_message({"chat": {"id": 42}, "text": text}))
    assert calls == [("report", "7"), ("report", "30"), ("report", "7")]
    assert tb._is_public_message("42", "/downloads 30") is False
    assert tb._is_public_message("42", "/export") is False


def test_exports_have_no_personal_data():
    now = datetime.utcnow().replace(microsecond=0)
    uid = uuid.uuid4()

    async def scenario(maker):
        from app.services import bot_exports

        async with maker() as db:
            db.add_all(_seed(now) + [
                FrontendEvent(event_name="search_query", occurred_at=now, session_id_hash="s3", visitor_id_hash="v3",
                              url=f"{SITE}/", params_json={"q": "ivan@example.com инфляция", "results": 3}),
                User(id=uid, created_at=now),
                UserSignup(user_id=uid, created_at=now, method="yandex", site_locale="ru", country="Россия",
                           channel="search", trigger="gate_download", landing_page="/russia/indicator/fuel-diesel"),
            ])
            await db.commit()
        today = (now + timedelta(hours=3)).date()
        async with maker() as db:
            period = dc.period_for_window("7", today)
            return await bot_exports.events_csv(db, period), await bot_exports.signups_csv(db, period)

    (events, n_events, cut), (signups, n_signups) = _run_with_db(scenario)
    text = events.decode("utf-8-sig")
    assert not cut and n_events == 8  # 9 событий минус робот
    assert "ivan@example.com" not in text and "инфляция" in text
    assert "v-bot" not in text
    s_text = signups.decode("utf-8-sig")
    assert n_signups == 1 and "Яндекс" in s_text and "упёрся в лимит скачиваний" in s_text
    assert str(uid) not in s_text
