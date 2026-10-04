import asyncio
from datetime import date

from app.models import WorldDatasetState
from app.services import world_eurostat_ingest as ingest
from app.services.world_eurostat_ingest import TocEntry, parse_toc


def test_parse_toc_preserves_data_and_structure_versions():
    raw = (
        '"title"\t"code"\t"type"\t"last update of data"\t'
        '"last table structure change"\t"data start"\t"data end"\t"values"\n'
        '"Current account"\t"ei_bpm6ca_q"\t"dataset"\t"08.07.2026"\t'
        '"03.07.2026"\t"1991-Q1"\t"2026-Q1"\t"311618"\n'
        '"Database by themes"\t"data"\t"folder"\t" "\t" "\t" "\t" "\t" " "\n'
    )

    toc = parse_toc(raw)

    assert set(toc) == {"ei_bpm6ca_q"}
    entry = toc["ei_bpm6ca_q"]
    assert entry.updated_at == date(2026, 7, 8)
    assert entry.structure_changed_at == date(2026, 7, 3)


def test_quarantined_structure_change_keeps_applied_version(monkeypatch):
    """A failed DSD review must remain quarantined on the next poll."""
    state = WorldDatasetState(
        provider="eurostat", dataset_id="namq_10_gdp", status="ok",
        last_update_of_data=date(2026, 8, 1),
        last_structure_change=date(2026, 7, 1),
    )
    class Session:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        def add(self, *_):
            pass
        async def get(self, *_):
            return state
        async def commit(self):
            pass

    monkeypatch.setattr(ingest, "async_session", Session)
    entry = TocEntry("namq_10_gdp", date(2026, 9, 1), date(2026, 8, 1))
    async def check():
        assert await ingest._structure_change_requires_quarantine(entry)
        await ingest._record_dataset(
            run_id=1, entry=entry, status="quarantine", update_state=True,
            error="new structure",
        )
        assert state.last_update_of_data == date(2026, 8, 1)
        assert state.last_structure_change == date(2026, 7, 1)
        assert await ingest._structure_change_requires_quarantine(entry)
        await ingest._record_dataset(run_id=2, entry=entry, status="ok", update_state=True)
        assert state.last_update_of_data == entry.updated_at
        assert state.last_structure_change == entry.structure_changed_at
    asyncio.run(check())


def test_catalog_selection_uses_loader_frequencies():
    """Задача отбирала D/S/W наборы, а loader (--freq M,Q,A) их отбрасывал
    и выходил с кодом 1 — 29 «ошибок» Eurostat каждый прогон (2026-09)."""
    sql, params = ingest._catalog_query()
    assert "upper(frequency) IN" in sql
    freq_values = {v for k, v in params.items() if k.startswith("freq_")}
    assert freq_values == set(ingest.LOADER_FREQUENCIES) == {"M", "Q", "A"}


def test_dataset_without_country_dimension_is_skipped_not_failed(monkeypatch):
    """Наборы без geo (курсы ert_*, города tour_*, рыболовные районы sdg_14_*)
    не раскладываются по странам: это «пропуск» с применённой версией TOC,
    а не ошибка, которая повторяется каждую ночь."""
    recorded = []

    async def fake_select(_toc):
        return [TocEntry("ert_bil_eur_m", date(2026, 9, 1), date(2026, 8, 1))]

    async def fake_toc():
        return {}

    async def fake_loader(entry, **_kwargs):
        return False, "ERROR ValueError: JSON-stat missing geo/time dims: ['freq', 'currency', 'time']"

    async def fake_record(**kwargs):
        recorded.append(kwargs)

    async def no_quarantine(_entry):
        return False

    async def empty_set():
        return set()

    async def noop(*_a, **_k):
        return None

    class Run:
        id = 7
        datasets_selected = 0

    class Session:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        def add(self, obj):
            pass
        async def commit(self):
            pass
        async def refresh(self, obj):
            obj.id = 7
        async def get(self, *_):
            return Run()

    alerts = []

    async def fake_alert(*args, **kwargs):
        alerts.append(kwargs)

    monkeypatch.setattr(ingest, "async_session", Session)
    monkeypatch.setattr(ingest, "fetch_toc", fake_toc)
    monkeypatch.setattr(ingest, "select_changed_datasets", fake_select)
    monkeypatch.setattr(ingest, "_run_one_loader", fake_loader)
    monkeypatch.setattr(ingest, "_record_dataset", fake_record)
    monkeypatch.setattr(ingest, "_structure_change_requires_quarantine", no_quarantine)
    monkeypatch.setattr(ingest, "_mark_changed_states_pending", noop)
    monkeypatch.setattr(ingest, "_listed_dataset_ids", empty_set)
    monkeypatch.setattr(ingest, "_failed_dataset_ids", empty_set)
    monkeypatch.setattr("app.services.alerting.alert_world_ingest_summary", fake_alert)

    result = asyncio.run(ingest.world_eurostat_ingest_job(shadow=False, include_imf=False))
    assert result["failed"] == 0
    assert result["skipped"] == 1
    assert recorded[0]["status"] == "skipped"
    assert alerts[0]["failed"] == 0


def test_skipped_dataset_applies_toc_version():
    """Пропущенный набор не перевыбирается до следующей смены TOC."""
    state = WorldDatasetState(provider="eurostat", dataset_id="ert_bil_eur_m", status="error")

    class Session:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        def add(self, *_):
            pass
        async def get(self, *_):
            return state
        async def commit(self):
            pass

    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(ingest, "async_session", Session)
    try:
        entry = TocEntry("ert_bil_eur_m", date(2026, 9, 1), date(2026, 8, 1))
        asyncio.run(ingest._record_dataset(
            run_id=1, entry=entry, status="skipped", update_state=True, error="no geo",
        ))
    finally:
        mp.undo()
    assert state.status == "skipped"
    assert state.last_update_of_data == date(2026, 9, 1)
    assert state.last_structure_change == date(2026, 8, 1)


def _job_env(monkeypatch, loader_result, *, structure_changed=True):
    recorded, alerts, loader_calls = [], [], []

    async def fake_select(_toc):
        return [TocEntry("nrg_stk_oem", date(2026, 9, 28), date(2026, 9, 25))]

    async def fake_toc():
        return {}

    async def fake_loader(entry, **kwargs):
        loader_calls.append(kwargs)
        return loader_result

    async def fake_record(**kwargs):
        recorded.append(kwargs)

    async def changed(_entry):
        return structure_changed

    async def empty_set():
        return set()

    async def noop(*_a, **_k):
        return None

    async def rows(*_a, **_k):
        return 126

    class Run:
        id = 7
        datasets_selected = 0

    class Session:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            pass
        def add(self, obj):
            pass
        async def commit(self):
            pass
        async def refresh(self, obj):
            obj.id = 7
        async def get(self, *_):
            return Run()

    async def fake_alert(*args, **kwargs):
        alerts.append(kwargs)

    monkeypatch.setattr(ingest, "async_session", Session)
    monkeypatch.setattr(ingest, "fetch_toc", fake_toc)
    monkeypatch.setattr(ingest, "select_changed_datasets", fake_select)
    monkeypatch.setattr(ingest, "_run_one_loader", fake_loader)
    monkeypatch.setattr(ingest, "_record_dataset", fake_record)
    monkeypatch.setattr(ingest, "_structure_change_requires_quarantine", changed)
    monkeypatch.setattr(ingest, "_mark_changed_states_pending", noop)
    monkeypatch.setattr(ingest, "_listed_dataset_ids", empty_set)
    monkeypatch.setattr(ingest, "_failed_dataset_ids", empty_set)
    monkeypatch.setattr(ingest, "_persisted_rows", rows)
    monkeypatch.setattr("app.services.alerting.alert_world_ingest_summary", fake_alert)
    return recorded, alerts, loader_calls


def test_structure_change_is_verified_and_accepted_automatically(monkeypatch):
    """Смена структуры больше не означает вечный карантин: loader сверяет
    срезы и при успехе набор обновляется, версия структуры применяется."""
    verdict = '{"dataset_id": "nrg_stk_oem", "accept": true, "kept": 126, "remapped": 2, "orphans": 0, "orphans_listed": 0, "reason": "ok"}'
    recorded, alerts, calls = _job_env(
        monkeypatch, (True, "... DONE\nSTRUCTURE_VERDICT " + verdict + "\n"),
    )
    result = asyncio.run(ingest.world_eurostat_ingest_job(shadow=False, include_imf=False))
    assert calls == [{"structure_check": True}]
    assert result["succeeded"] == 1 and result["failed"] == 0
    assert result["structure_accepted"] == 1
    assert recorded[0]["status"] == "ok"
    assert "переподключено рядов: 2" in alerts[0]["details"]


def test_structural_break_stays_in_quarantine_with_reason(monkeypatch):
    verdict = '{"dataset_id": "nrg_stk_oem", "accept": false, "kept": 3, "remapped": 0, "orphans": 90, "orphans_listed": 88, "reason": "88 из 120 публичных карточек не нашли срез в новой структуре"}'
    recorded, alerts, _calls = _job_env(
        monkeypatch, (False, "STRUCTURE_VERDICT " + verdict),
    )
    result = asyncio.run(ingest.world_eurostat_ingest_job(shadow=False, include_imf=False))
    assert result["failed"] == 1 and result["structure_blocked"] == 1
    assert recorded[0]["status"] == "quarantine"
    assert "88 из 120" in recorded[0]["error"]


def test_unchanged_structure_runs_plain_loader(monkeypatch):
    recorded, _alerts, calls = _job_env(monkeypatch, (True, "DONE"), structure_changed=False)
    asyncio.run(ingest.world_eurostat_ingest_job(shadow=False, include_imf=False))
    assert calls == [{}]
    assert recorded[0]["status"] == "ok"


def test_dataset_list_names_datasets_with_reasons():
    text = ingest.format_dataset_list(
        "Разлом структуры, оставлено в карантине",
        [("nrg_stk_oem", "88 из 120 публичных карточек не нашли срез"), ("une_rt_m", "")],
    )
    assert text == (
        "Разлом структуры, оставлено в карантине: 2 — "
        "nrg_stk_oem (88 из 120 публичных карточек не нашли срез); une_rt_m. "
    )
    assert ingest.format_dataset_list("x", []) == ""


def test_dataset_list_truncates_long_tail_and_reasons():
    items = [(f"ds_{n}", "причина " * 40) for n in range(15)]
    text = ingest.format_dataset_list("Пропущено", items, limit=3, reason_chars=20)
    assert text.count("ds_") == 3
    assert "…ещё 12" in text
    assert "причина " * 5 not in text  # причина обрезана до одной строки


def test_summary_names_quarantined_and_skipped_datasets(monkeypatch):
    """Сводка называет наборы поимённо, чтобы разбирать их по одному."""
    entries = [
        TocEntry("nrg_stk_oem", date(2026, 9, 28), date(2026, 9, 25)),
        TocEntry("ert_bil_eur_m", date(2026, 9, 28), date(2026, 9, 25)),
    ]
    verdict = (
        '{"dataset_id": "nrg_stk_oem", "accept": false, "kept": 3, "remapped": 0, '
        '"orphans": 9, "orphans_listed": 8, '
        '"reason": "8 из 10 публичных карточек не нашли срез в новой структуре"}'
    )

    async def fake_select(_toc):
        return entries

    async def fake_loader(entry, **_kwargs):
        if entry.dataset_id == "nrg_stk_oem":
            return False, "STRUCTURE_VERDICT " + verdict
        return False, "ERROR ValueError: JSON-stat missing geo/time dims: ['freq']"

    recorded, alerts, _calls = _job_env(monkeypatch, (True, ""))
    monkeypatch.setattr(ingest, "select_changed_datasets", fake_select)
    monkeypatch.setattr(ingest, "_run_one_loader", fake_loader)

    result = asyncio.run(ingest.world_eurostat_ingest_job(shadow=False, include_imf=False))
    assert result["structure_blocked"] == 1 and result["skipped"] == 1
    details = alerts[0]["details"]
    assert "Разлом структуры, оставлено в карантине: 1 — nrg_stk_oem (8 из 10 публичных" in details
    assert "Без разреза по странам (пропущено): 1 — ert_bil_eur_m (" in details
    assert alerts[0]["failed"] == 1


def test_world_summary_details_limit_fits_named_lists(monkeypatch):
    """Поимённые списки не режутся прежним лимитом 1000 символов."""
    import app.services.alerting as alerting

    sent = []

    async def fake_send(message, **kwargs):
        sent.append(message)
        return True

    monkeypatch.setattr(alerting, "send_telegram", fake_send)
    asyncio.run(alerting.alert_world_ingest_summary(
        "Европа: Eurostat", status="partial", checked=1, changed=0, failed=1,
        details="x" * 1800,
    ))
    assert "x" * 1800 in sent[0]
