"""Защита от фермы без вреда полезным роботам (08.11.2026, дополнение ADR-0026).

Живой замер 08.11.2026 06:14–08:21 UTC: 55 тысяч запросов без Referer на глубокие страницы с 53,5 тысяч IP, 99 % адресов
не загрузили ни одного скрипта; Applebot, OAI-SearchBot, ChatGPT-User, PerplexityBot, DuckDuckBot пришли только из своих
официальных сетей. Поведение nginx проверяет deploy/test-bot-classes.sh, здесь — backend: класс goodbot/human, пропуск,
сводка по роботам.
"""

import asyncio
import base64
import hashlib
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.seo_pages as seo_pages
from app.api import human_pass
from app.services import bot_traffic, host_pressure, load_priority

SECRET = "test_secret_0123456789abcdefghijklmnopqrstuv"


# --- классы ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, low, good", [
    ("goodbot", False, True), ("human", False, False), ("anon", True, False), ("robot", True, False),
])
def test_new_classes_priority(raw, low, good):
    token = load_priority.bind(raw)
    try:
        assert load_priority.current() == raw
        assert load_priority.is_low_priority() is low
        assert load_priority.is_good_bot() is good
    finally:
        load_priority.reset(token)


@pytest.fixture
def slots(monkeypatch):
    monkeypatch.setattr(seo_pages, "_RENDER_SEM", asyncio.Semaphore(4))
    monkeypatch.setattr(seo_pages, "_LOW_PRIORITY_SEM", asyncio.Semaphore(1))
    monkeypatch.setattr(seo_pages, "_GOODBOT_SEM", asyncio.Semaphore(1))
    monkeypatch.setattr(seo_pages.settings, "ssr_render_queue_timeout_seconds", 0.15)
    monkeypatch.setattr(seo_pages.settings, "ssr_low_priority_queue_timeout_seconds", 0.1)
    monkeypatch.setattr(host_pressure, "io_degraded", lambda: False)


async def _hold(cls: str, seconds: float, out: list):
    token = load_priority.bind(cls)
    loop = asyncio.get_running_loop()
    try:
        release = await seo_pages._acquire_render_slot(loop.time())
    except seo_pages._RenderQueueTimeout:
        out.append((cls, "shed"))
        return
    finally:
        load_priority.reset(token)
    out.append((cls, "slot"))
    try:
        await asyncio.sleep(seconds)
    finally:
        release()


def test_farm_cannot_take_good_bot_slots_and_good_bots_do_not_take_all(slots):
    async def run():
        out: list = []
        tasks = [asyncio.create_task(_hold("anon", 0.4, out)) for _ in range(3)]
        await asyncio.sleep(0.02)
        tasks += [asyncio.create_task(_hold("goodbot", 0.4, out)) for _ in range(3)]
        await asyncio.sleep(0.02)
        tasks += [asyncio.create_task(_hold("referred", 0.05, out)) for _ in range(2)]
        await asyncio.gather(*tasks)
        return out

    out = asyncio.run(run())
    by = lambda c: [r for k, r in out if k == c]  # noqa: E731
    assert by("anon").count("slot") == 1, "ферма держит только свой потолок"
    assert by("goodbot").count("slot") == 1, "полезный робот получает свой слот, ферма его не заняла"
    assert by("referred") == ["slot", "slot"], "людям остаются слоты"


def test_good_bot_is_shed_when_disk_overloaded_but_human_pass_is_not(slots, monkeypatch):
    monkeypatch.setattr(host_pressure, "io_degraded", lambda: True)

    async def run():
        out: list = []
        await asyncio.gather(_hold("goodbot", 0.01, out), _hold("human", 0.01, out), _hold("crawler", 0.01, out))
        return dict(out)

    assert asyncio.run(run()) == {"goodbot": "shed", "human": "slot", "crawler": "slot"}


# --- пропуск -------------------------------------------------------------------------------------------------------

def _client(monkeypatch, secret):
    monkeypatch.setattr(human_pass.settings, "fe_human_pass_secret", secret)
    app = FastAPI()
    app.include_router(human_pass.router, prefix="/api/v1")
    return TestClient(app, base_url="https://forecasteconomy.com")


def test_pass_disabled_without_secret(monkeypatch):
    assert _client(monkeypatch, "").post("/api/v1/human-pass", headers={"X-FE-Pass-Request": "1"}).status_code == 404
    assert _client(monkeypatch, "short").post("/api/v1/human-pass", headers={"X-FE-Pass-Request": "1"}).status_code == 404


def test_pass_needs_javascript_header(monkeypatch):
    assert _client(monkeypatch, SECRET).post("/api/v1/human-pass").status_code == 400


def test_pass_cookie_matches_nginx_secure_link(monkeypatch):
    resp = _client(monkeypatch, SECRET).post("/api/v1/human-pass", headers={"X-FE-Pass-Request": "1"})
    assert resp.status_code == 204
    header = resp.headers["set-cookie"]
    assert "HttpOnly" in header and "Secure" in header and "SameSite=lax" in header.replace("Lax", "lax")
    value = resp.cookies.get("fe_pass") or header.split("fe_pass=", 1)[1].split(";", 1)[0]
    digest, expires, pass_id = value.split(".")
    assert len(digest) == 22 and len(expires) == 10 and len(pass_id) == 16
    # secure_link_md5 "$fe_pass_expires$fe_pass_id $fe_pass_secret" + base64url без '='
    want = base64.urlsafe_b64encode(hashlib.md5(f"{expires}{pass_id} {SECRET}".encode()).digest()).decode().rstrip("=")
    assert digest == want


def test_bound_pass_signs_exactly_what_nginx_passes(monkeypatch):
    """14.11.2026: secure_link_md5 "$fe_pass_expires$fe_pass_id $fe_pass_bind$fe_pass_secret", bind = "<сеть>|<UA> "."""
    bind = "93.1.1|Mozilla/5.0 (X11; Linux x86_64) Chrome/157.0.0.0 Safari/537.36 "
    resp = _client(monkeypatch, SECRET).post("/api/v1/human-pass",
                                             headers={"X-FE-Pass-Request": "1", "X-FE-Pass-Bind": bind})
    assert resp.status_code == 204
    value = resp.cookies.get("fe_pass") or resp.headers["set-cookie"].split("fe_pass=", 1)[1].split(";", 1)[0]
    digest, expires, pass_id = value.split(".")
    raw = f"{expires}{pass_id} {bind}{SECRET}".encode()
    assert digest == base64.urlsafe_b64encode(hashlib.md5(raw).digest()).decode().rstrip("=")
    # Без заголовка (FE_PASS_BIND=0) - прежняя подпись; не-ASCII байты UA подписываются как их видит nginx.
    assert human_pass.sign(1, "a" * 16, SECRET) == human_pass.sign(1, "a" * 16, SECRET, "")
    raw_ua = "1.2.3|Mozilla \xe9 "
    expected = hashlib.md5(b"1" + b"a" * 16 + b" " + raw_ua.encode("latin-1") + SECRET.encode()).digest()
    assert human_pass.sign(1, "a" * 16, SECRET, raw_ua) == base64.urlsafe_b64encode(expected).decode().rstrip("=")


def test_observe_mode_remembers_issue_network_in_cookie(monkeypatch):
    """Приёмка 14.11.2026: при наблюдении nginx шлёт сеть выдачи, backend кладёт её в cookie fe_pass_net."""
    client = _client(monkeypatch, SECRET)
    resp = client.post("/api/v1/human-pass", headers={"X-FE-Pass-Request": "1", "X-FE-Pass-Net": "93.1.1"})
    cookies = resp.headers.get_list("set-cookie")
    net = [c for c in cookies if c.startswith("fe_pass_net=")]
    assert len(net) == 1 and net[0].startswith("fe_pass_net=93.1.1;") and "HttpOnly" in net[0]
    ipv6 = client.post("/api/v1/human-pass", headers={"X-FE-Pass-Request": "1", "X-FE-Pass-Net": "2a00:1fa0:4:a1b2"})
    assert any(c.startswith("fe_pass_net=2a00:1fa0:4:a1b2;") for c in ipv6.headers.get_list("set-cookie"))
    # Нет заголовка (FE_PASS_BIND=0) или мусор - cookie сети нет.
    for headers in ({}, {"X-FE-Pass-Net": "1.2.3; evil=1"}):
        r = client.post("/api/v1/human-pass", headers={"X-FE-Pass-Request": "1", **headers})
        assert not any(c.startswith("fe_pass_net=") for c in r.headers.get_list("set-cookie"))


def test_staff_pass_is_a_regular_signed_pass_with_staff_prefix():
    """15.11.2026: служебный пропуск наших агентов - тот же формат и подпись, id с префиксом 57aff000 (класс staff)."""
    value = human_pass.issue_staff(SECRET, 7, now=1_800_000_000)
    digest, expires, pass_id = value.split(".")
    assert len(digest) == 22 and expires == str(1_800_000_000 + 7 * 86400) and len(pass_id) == 16
    assert pass_id.startswith(human_pass.STAFF_ID_PREFIX) and int(pass_id, 16) >= 0
    assert digest == base64.urlsafe_b64encode(hashlib.md5(f"{expires}{pass_id} {SECRET}".encode()).digest()).decode().rstrip("=")
    bind = "93.1.1|curl/8.7.1 "
    bound = human_pass.issue_staff(SECRET, 1, bind=bind, now=1_800_000_000)
    d, e, i = bound.split(".")
    assert d == base64.urlsafe_b64encode(hashlib.md5(f"{e}{i} {bind}{SECRET}".encode()).digest()).decode().rstrip("=")
    for bad in (0, 31, -1):
        with pytest.raises(ValueError):
            human_pass.issue_staff(SECRET, bad)


def test_staff_pass_cli_refuses_without_secret_and_half_binding(monkeypatch, capsys):
    monkeypatch.setattr(human_pass.settings, "fe_human_pass_secret", "")
    assert human_pass._staff_main([]) == 2
    monkeypatch.setattr(human_pass.settings, "fe_human_pass_secret", SECRET)
    assert human_pass._staff_main(["--net", "1.2.3"]) == 2
    assert human_pass._staff_main(["--days", "40"]) == 2
    capsys.readouterr()
    assert human_pass._staff_main(["--days", "3"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("fe_pass=") and out[0].split(".")[2].startswith("57aff000")
    assert "привязка: нет" in out[1]


# --- сводка по роботам -------------------------------------------------------------------------------------------

LINES = [
    '2026-11-07T06:00:00+00:00 1.1.1.1 429 "GET /united-states/region/x/y/2008 HTTP/1.1" "Mozilla/5.0" cls=anon',
    '2026-11-07T06:00:01+00:00 1.1.1.2 200 "GET /united-states/region/x/y/2008 HTTP/1.1" "Mozilla/5.0" cls=anon',
    '2026-11-07T06:00:02+00:00 66.249.66.1 200 "GET / HTTP/1.1" "Googlebot/2.1" cls=crawler',
    '2026-11-07T06:00:03+00:00 66.249.66.1 503 "GET / HTTP/1.1" "Googlebot/2.1" cls=crawler',
    '2026-11-07T06:00:04+00:00 9.9.9.9 200 "GET / HTTP/1.1" "Googlebot \\x22fake\\x22" cls=fake',
    '2026-11-07T06:00:05+00:00 17.241.208.161 200 "GET / HTTP/1.1" "Applebot" cls=goodbot',
    '2026-11-07T06:00:06+00:00 5.5.5.5 200 "GET / HTTP/1.1" "Mozilla/5.0" cls=human',
    '2026-11-07T06:00:07+00:00 5.5.5.6 200 "GET / HTTP/1.1" "Mozilla/5.0"',  # строка до выпуска: без класса
]


def test_batch_counts_by_class_and_outcome():
    batch = bot_traffic.Batch()
    assert [batch.add_line(line) for line in LINES] == [True] * 7 + [False]
    day = batch.counts["2026-11-07"]
    assert day["anon:429"] == 1 and day["anon:ok"] == 1 and day["crawler:5xx"] == 1
    assert batch.fake_ips["2026-11-07"] == {"9.9.9.9": 1}


def test_format_lines_plain_words():
    counts = {"anon:429": 72, "anon:ok": 28, "crawler:ok": 999, "crawler:5xx": 1, "goodbot:ok": 50, "human:ok": 3}
    lines = bot_traffic.format_lines(counts, [], __import__("datetime").date(2026, 11, 7))
    text = "\n".join(lines)
    assert "Роботы за 07.11" in text
    assert "100 запросов, отрезано 72 %" in text
    assert "поисковики Google, Яндекс, Bing: 1\u00a0000 запросов, отказов 1 (0,1 %)" in text
    assert "полезные роботы" in text and "без отказов" in text
    assert "люди по пропуску (страница отказа сама пропустила): 3 запроса" in text
    assert "parser" not in text.lower() and "nginx" not in text.lower()


def test_google_referer_farm_has_its_own_summary_line():
    """14.11.2026: класс gfarm (ферма с подставленным Referer Google) считается отдельно от anon."""
    batch = bot_traffic.Batch()
    line = ('2026-11-14T08:48:28+00:00 170.23.19.211 429 "GET /finland/indicator/x HTTP/1.1" '
            '"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36" '
            'cls=gfarm')
    assert batch.add_line(line)
    assert batch.counts["2026-11-14"] == {"gfarm:429": 1}
    text = "\n".join(bot_traffic.format_lines({"gfarm:429": 90, "gfarm:ok": 10}, [],
                                              __import__("datetime").date(2026, 11, 14)))
    assert "с поддельным переходом из Google (ферма): 100 запросов, отрезано 90 %" in text


def test_batch_counts_people_by_pass_path_and_minted_passes():
    """15.11.2026: люди - адреса класса human (отказ -> пропуск -> страница); ферма с JS возвращается классом referred."""
    batch = bot_traffic.Batch()
    lines = [
        '2026-11-14T03:48:57+00:00 5.130.190.167 429 "GET /russia/indicator/fuel-diesel/2026 HTTP/1.1" "Firefox" cls=anon',
        '2026-11-14T03:48:57+00:00 5.130.190.167 204 "POST /api/v1/human-pass HTTP/1.1" "Firefox" cls=referred',
        '2026-11-14T03:48:57+00:00 5.130.190.167 200 "GET /russia/indicator/fuel-diesel/2026 HTTP/1.1" "Firefox" cls=human',
        '2026-11-14T03:49:00+00:00 5.130.190.167 200 "GET /russia/indicator/fuel-diesel HTTP/1.1" "Firefox" cls=human',
        '2026-11-14T02:53:04+00:00 1.92.192.87 429 "GET /russia/region/a/b/2021 HTTP/1.1" "Chrome/148" cls=anon',
        '2026-11-14T02:53:04+00:00 1.92.192.87 204 "POST /api/v1/human-pass HTTP/1.1" "Chrome/148" cls=referred',
        '2026-11-14T02:53:05+00:00 1.92.192.87 200 "GET /russia/region/a/b/2021 HTTP/1.1" "Chrome/148" cls=referred',
        '2026-11-14T05:00:00+00:00 9.9.9.9 200 "GET /russia/region/a/b HTTP/1.1" "curl/8.7.1" cls=staff',
    ]
    assert all(batch.add_line(line) for line in lines)
    assert batch.pass_ips == {"2026-11-14": {"5.130.190.167"}}
    day = batch.counts["2026-11-14"]
    assert day["pass_minted"] == 2 and day["staff:ok"] == 1 and day["human:ok"] == 2


def test_pass_line_and_staff_line_plain_words():
    from datetime import date
    line = bot_traffic.pass_line(15, 0, 6984, date(2026, 11, 13))
    assert line == ("Люди по пропуску за 13.11: 15 адресов (отказ → пропуск → страница), отказов после пропуска 0; "
                    "выдано пропусков 6\u00a0984")
    assert len(line) < 140
    assert bot_traffic.pass_line(1, 0, 0, date(2026, 11, 13)).startswith("Люди по пропуску за 13.11: 1 адрес (")
    assert bot_traffic.pass_line(0, 0, 0, date(2026, 11, 13)) == "Люди по пропуску за 13.11: не было"
    text = "\n".join(bot_traffic.format_lines({"staff:ok": 40, "staff:429": 0}, [], date(2026, 11, 13)))
    assert "наши агенты по служебному пропуску: 40 запросов, без отказов" in text


def test_format_lines_warns_about_genuine_robot_outside_lists():
    lines = bot_traffic.format_lines({"fake:ok": 5}, [("1.2.3.4", "crawl-1-2-3-4.googlebot.com")],
                                     __import__("datetime").date(2026, 11, 7))
    assert any("обновить списки сетей" in line for line in lines)


def test_read_new_starts_at_end_then_follows_and_handles_rotation(tmp_path):
    log = tmp_path / "security.log"
    log.write_text(LINES[0] + "\n")
    lines, state = bot_traffic.read_new(str(log), None)
    assert lines == [] and state.endswith(f":{log.stat().st_size}"), "первый запуск не пересчитывает старое"
    with log.open("a") as fh:
        fh.write(LINES[1] + "\n" + "half-written")
    lines, state = bot_traffic.read_new(str(log), state)
    assert lines == [LINES[1]], "незаконченная строка ждёт следующего запуска"
    with log.open("a") as fh:
        fh.write(" line\n")
    os.rename(log, tmp_path / "security.log.1")
    log.write_text(LINES[2] + "\n")
    lines, state = bot_traffic.read_new(str(log), state)
    assert lines == ["half-written line", LINES[2]], "хвост старого файла дочитан после ротации"
    assert bot_traffic.read_new(str(tmp_path / "missing.log"), state) == ([], state)


# --- люди, получившие 429, и пропуск (14.11.2026) --------------------------------------------------------------------

HUMAN_LINES = [
    "2026-11-13T08:00:00+00:00 st=429 pass=0 ym=11111111 cls=anon",     # отказ, потом прошёл по пропуску
    "2026-11-13T08:00:05+00:00 st=200 pass=1 ym=11111111 cls=human",
    "2026-11-13T08:01:00+00:00 st=429 pass=0 ym=22222222 cls=anon",     # отказ, не прошёл
    "2026-11-13T08:02:00+00:00 st=429 pass=0 ym=33333333 cls=gfarm",    # ферма с подставленным Referer - не считаем
    "2026-11-13T08:03:00+00:00 st=200 pass=1 ym=44444444 cls=human",    # с пропуском без отказа - не в знаменателе
    "garbage",
]


def test_human_batch_counts_refused_and_passed_without_farm():
    batch = bot_traffic.HumanBatch()
    assert [batch.add_line(line) for line in HUMAN_LINES] == [True, True, True, False, True, False]
    assert batch.refused == {"2026-11-13": {"11111111", "22222222"}}
    assert batch.passed == {"2026-11-13": {"11111111", "44444444"}}


def test_human_line_shows_numerator_and_denominator():
    from datetime import date
    line = bot_traffic.human_line(2, 1, date(2026, 11, 13))
    # 15.11.2026: cookie Метрики - не доказательство человека (ферма с JavaScript её несёт): строка так и называется.
    assert line == ("Браузеры с Метрикой за 13.11: отказ 2, прошли по пропуску 1, не прошли 1 (50 %); "
                    "среди них и ферма с JavaScript")
    assert len(line) < 140
    assert bot_traffic.human_line(0, 0, date(2026, 11, 13)).endswith("отказов не было")


def test_collect_and_morning_note_once_per_day(tmp_path, monkeypatch):
    import fakeredis.aioredis
    from datetime import datetime, timezone

    from app.core import cache as cache_mod
    from app.services import telegram_calm

    sec = tmp_path / "security.log"
    hum = tmp_path / "human429.log"
    sec.write_text("")
    hum.write_text("")
    sec_lines = [
        '2026-11-13T08:00:00+00:00 5.5.5.5 429 "GET /russia/region/a/b HTTP/1.1" "Firefox" cls=anon',
        '2026-11-13T08:00:00+00:00 5.5.5.5 204 "POST /api/v1/human-pass HTTP/1.1" "Firefox" cls=referred',
        '2026-11-13T08:00:01+00:00 5.5.5.5 200 "GET /russia/region/a/b HTTP/1.1" "Firefox" cls=human',
        '2026-11-13T08:00:09+00:00 5.5.5.6 200 "GET /russia/region/a/c HTTP/1.1" "Safari" cls=human',
    ]
    monkeypatch.setattr(bot_traffic.settings, "bot_traffic_log_path", str(sec))
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache_mod, "_state_redis", redis)
    sent = []

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent.append((kind, message))
        return True

    monkeypatch.setattr("app.services.alerting.send_telegram", fake_send)
    monkeypatch.setattr(bot_traffic, "check_genuine", lambda ips, timeout=3.0: [])
    # collect_job сам зовёт отчёт по текущему времени - здесь время задаём явно.
    monkeypatch.setattr(bot_traffic, "REPORT_AFTER_UTC_HOUR", 25)

    async def scenario():
        await bot_traffic.collect_job()                      # первый прогон: запоминает конец файлов
        hum.write_text("\n".join(HUMAN_LINES) + "\n")
        sec.write_text("\n".join(sec_lines) + "\n")
        await bot_traffic.collect_job()
        monkeypatch.setattr(bot_traffic, "REPORT_AFTER_UTC_HOUR", 5.75)
        early = await bot_traffic._maybe_report(redis, datetime(2026, 11, 14, 5, 0, tzinfo=timezone.utc))
        first = await bot_traffic._maybe_report(redis, datetime(2026, 11, 14, 5, 50, tzinfo=timezone.utc))
        again = await bot_traffic._maybe_report(redis, datetime(2026, 11, 14, 6, 0, tzinfo=timezone.utc))
        return early, first, again

    early, first, again = asyncio.run(scenario())
    assert (early, first, again) == (False, True, False)
    assert [k for k, _ in sent] == ["bot_traffic"]
    text = sent[0][1]
    first, second = text.splitlines()[:2]
    assert first == ("Люди по пропуску за 13.11: 2 адреса (отказ → пропуск → страница), отказов после пропуска 0; "
                     "выдано пропусков 1")
    assert second.startswith("Браузеры с Метрикой за 13.11: отказ 2, прошли по пропуску 1, не прошли 1 (50 %)")
    assert "Человек здесь" not in text
    assert "bot_traffic" in telegram_calm.HELD_KINDS
    summary = telegram_calm.build_summary([("bot_traffic", text)], day=datetime(2026, 11, 14).date())
    assert "Люди по пропуску за 13.11: 2 адреса" in summary
