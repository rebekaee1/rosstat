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

    async def fake_loader(entry):
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
