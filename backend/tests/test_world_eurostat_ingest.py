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
