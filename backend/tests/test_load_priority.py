"""Приоритет холодного рендера, режим экономии и монитор хоста (ADR-0026).

Инцидент 2026-11-05: диск хоста отвечал по 0,5–1,5 с, ферма без Referer (46 тысяч запросов с 39,7 тысяч IP за 53 минуты)
заняла все 6 слотов холодного рендера, Googlebot и Bing получали 503/504 вместе с ней, а алерты не называли причину.
"""

import asyncio

import pytest

import app.api.seo_pages as seo_pages
from app.services import host_pressure, load_priority
from app.services import http_error_monitor as monitor

PSI_IO = (
    "some avg10=61.60 avg60=71.60 avg300=80.35 total=301395832609\n"
    "full avg10=38.40 avg60=44.40 avg300=53.56 total=245106854477\n"
)


def _snap(io_full10=1.0, io_full60=1.0, mem=0.0, free=40 * 1024 ** 3, total=77 * 1024 ** 3):
    return host_pressure.Snapshot(io_some10=io_full10, io_full10=io_full10, io_full60=io_full60,
                                  mem_full60=mem, disk_free=free, disk_total=total)


# --- класс клиента -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected, low", [
    ("anon", "anon", True), ("robot", "robot", True), (" ANON ", "anon", True),
    ("crawler", "crawler", False), ("referred", "referred", False), ("internal", "internal", False),
    (None, "unknown", False), ("", "unknown", False), ("vip", "unknown", False),
])
def test_classify_and_priority(raw, expected, low):
    token = load_priority.bind(raw)
    try:
        assert load_priority.current() == expected
        assert load_priority.is_low_priority() is low
    finally:
        load_priority.reset(token)


# --- PSI -----------------------------------------------------------------------------------------------------------

def test_parse_psi_reads_some_and_full():
    parsed = host_pressure._parse_psi(PSI_IO)
    assert parsed["some"]["avg10"] == 61.6
    assert parsed["full"]["avg60"] == 44.4


def test_describe_mentions_io_memory_and_free_space():
    line = host_pressure.describe(_snap(io_full60=72.4, mem=3.0, free=int(4.1 * 1024 ** 3)))
    assert line.startswith("Хост: ожидание ввода-вывода 72% (1 мин)")
    assert "нехватка памяти 3%" in line
    assert "свободно 4,1 из 77,0 ГБ (5%)" in line


def test_describe_empty_without_data():
    empty = host_pressure.Snapshot(None, None, None, None, None, None)
    assert host_pressure.describe(empty) == ""


def test_io_degraded_threshold_and_off_switch(monkeypatch):
    monkeypatch.setattr(host_pressure, "snapshot", lambda **_: _snap(io_full10=45.0))
    monkeypatch.setattr(host_pressure.settings, "host_brownout_io_full_pct", 40.0)
    assert host_pressure.io_degraded()
    monkeypatch.setattr(host_pressure.settings, "host_brownout_io_full_pct", 50.0)
    assert not host_pressure.io_degraded()
    monkeypatch.setattr(host_pressure.settings, "host_brownout_io_full_pct", 0)
    assert not host_pressure.io_degraded()


def test_no_psi_means_not_degraded(monkeypatch):
    monkeypatch.setattr(host_pressure, "_PSI_DIR", "/nonexistent-psi")
    monkeypatch.setattr(host_pressure, "_cached", None)
    assert host_pressure.snapshot(fresh=True).io_full10 is None
    assert not host_pressure.io_degraded()


# --- монитор хоста -------------------------------------------------------------------------------------------------

@pytest.fixture
def telegram(monkeypatch):
    import app.services.alerting as alerting

    sent: list[tuple[str, str]] = []
    muted: set[str] = set()

    async def fake_send(message, chat_id=None, reply_markup=None, kind="alert"):
        sent.append((kind, message))
        return True

    async def fake_muted(key, ttl):
        if key in muted:
            return True
        muted.add(key)
        return False

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    monkeypatch.setattr(alerting, "alert_muted", fake_muted)
    monkeypatch.setattr(host_pressure, "_bad", 0)
    monkeypatch.setattr(host_pressure, "_ok", 0)
    monkeypatch.setattr(host_pressure, "_alerted_at", None)
    monkeypatch.setattr(host_pressure.settings, "host_alert_io_full_pct", 25.0)
    monkeypatch.setattr(host_pressure.settings, "host_alert_disk_free_pct", 10.0)
    return sent


def _run_minutes(monkeypatch, snaps):
    seq = iter(snaps)
    monkeypatch.setattr(host_pressure, "snapshot", lambda **_: next(seq))

    async def run():
        for _ in snaps:
            await host_pressure.host_health_job()

    asyncio.run(run())


def test_io_alert_after_three_bad_minutes_then_recovery(telegram, monkeypatch):
    bad, good = _snap(io_full60=70.0), _snap(io_full60=2.0)
    _run_minutes(monkeypatch, [bad, bad] )
    assert telegram == [], "две минуты - ещё не повод будить владельца"
    _run_minutes(monkeypatch, [bad, bad, bad])
    assert [k for k, _ in telegram] == ["host_pressure"]
    assert "Диск хоста тормозит" in telegram[0][1] and "ожидание ввода-вывода 70%" in telegram[0][1]
    _run_minutes(monkeypatch, [good] * 4)
    assert len(telegram) == 1, "в норме - только после пяти спокойных минут"
    _run_minutes(monkeypatch, [good])
    assert "снова в норме" in telegram[1][1]


def test_short_spike_is_silent(telegram, monkeypatch):
    _run_minutes(monkeypatch, [_snap(io_full60=70.0), _snap(io_full60=70.0), _snap(io_full60=5.0)] * 3)
    assert telegram == []


def test_low_disk_alert_once(telegram, monkeypatch):
    low = _snap(free=int(3.8 * 1024 ** 3))
    _run_minutes(monkeypatch, [low, low, low])
    kinds = [k for k, _ in telegram]
    assert kinds == ["disk_space"]
    assert "Мало места" in telegram[0][1] and "(5%)" in telegram[0][1]


# --- приоритет в очереди рендера -----------------------------------------------------------------------------------

@pytest.fixture
def slots(monkeypatch):
    monkeypatch.setattr(seo_pages, "_RENDER_SEM", asyncio.Semaphore(3))
    monkeypatch.setattr(seo_pages, "_LOW_PRIORITY_SEM", asyncio.Semaphore(1))
    monkeypatch.setattr(seo_pages.settings, "ssr_render_queue_timeout_seconds", 1.0)
    monkeypatch.setattr(seo_pages.settings, "ssr_low_priority_queue_timeout_seconds", 0.1)
    monkeypatch.setattr(host_pressure, "io_degraded", lambda: False)


async def _hold(cls: str, seconds: float, outcome: list):
    token = load_priority.bind(cls)
    try:
        loop = asyncio.get_running_loop()
        release = await seo_pages._acquire_render_slot(loop.time())
    except seo_pages._RenderQueueTimeout:
        outcome.append((cls, "shed"))
        return
    finally:
        load_priority.reset(token)
    outcome.append((cls, "slot"))
    try:
        await asyncio.sleep(seconds)
    finally:
        release()


def test_low_priority_gets_only_its_slots_people_keep_the_rest(slots):
    async def run():
        out: list = []
        tasks = [asyncio.create_task(_hold("anon", 0.3, out)) for _ in range(4)]
        await asyncio.sleep(0.02)
        tasks += [asyncio.create_task(_hold("referred", 0.05, out)) for _ in range(2)]
        tasks.append(asyncio.create_task(_hold("crawler", 0.05, out)))
        await asyncio.gather(*tasks)
        return out

    out = asyncio.run(run())
    anon = [r for c, r in out if c == "anon"]
    assert anon.count("slot") == 1 and anon.count("shed") == 3
    assert all(r == "slot" for c, r in out if c != "anon"), "люди и проверенные роботы не теряют слотов из-за фермы"


def test_brownout_sheds_low_priority_immediately_but_not_people(slots, monkeypatch):
    monkeypatch.setattr(host_pressure, "io_degraded", lambda: True)

    async def run():
        out: list = []
        await _hold("anon", 0, out)
        await _hold("robot", 0, out)
        await _hold("referred", 0, out)
        await _hold("unknown", 0, out)
        return out

    assert asyncio.run(run()) == [("anon", "shed"), ("robot", "shed"), ("referred", "slot"), ("unknown", "slot")]


def test_low_priority_slots_are_released(slots):
    async def run():
        out: list = []
        for _ in range(3):
            await _hold("anon", 0, out)
        return out, seo_pages._LOW_PRIORITY_SEM._value, seo_pages._RENDER_SEM._value

    out, low_left, all_left = asyncio.run(run())
    assert [r for _, r in out] == ["slot"] * 3
    assert (low_left, all_left) == (1, 3)


# --- причина в алерте 5xx ------------------------------------------------------------------------------------------

def test_5xx_alert_carries_host_line_and_path_stays_parseable(monkeypatch):
    from app.services.analytics_marts import _SPIKE_PATH_RE

    monkeypatch.setattr(host_pressure, "snapshot", lambda **_: _snap(io_full60=72.0))
    text = monitor._error_text(452, "/api/v1/regions")
    assert text.splitlines()[-1].startswith("Хост: ожидание ввода-вывода 72%")
    assert _SPIKE_PATH_RE.search(text).group(1) == "/api/v1/regions"
    assert "Хост:" in monitor._shed_text(60, "/seo/x")
