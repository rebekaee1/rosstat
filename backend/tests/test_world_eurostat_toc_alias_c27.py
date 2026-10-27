"""Круг починки 27.10.2026: набор переименован, старый код пропал из оглавления, но API его обслуживает.

`tec00116` → `tesem160` (значения среза `NLPR_PER` совпадают): без алиаса 33 публичные карточки не
обновлялись бы, а ночная сводка писала «нет в оглавлении».
"""
import asyncio
from datetime import date

from app.services import world_eurostat_ingest as ingest
from app.services.world_eurostat_ingest import TocEntry, toc_entry_for


def _toc():
    return {
        "tesem160": TocEntry("tesem160", date(2026, 10, 22), date(2026, 10, 21)),
        "tec00114": TocEntry("tec00114", date(2026, 7, 9), date(2026, 7, 9)),
    }


def test_renamed_dataset_gets_successor_version_under_old_code():
    entry = toc_entry_for(_toc(), "tec00116")
    assert entry == TocEntry("tec00116", date(2026, 10, 22), date(2026, 10, 21))


def test_listed_entry_wins_over_alias_and_unknown_stays_absent():
    toc = _toc()
    toc["tec00116"] = TocEntry("tec00116", date(2026, 1, 1), date(2026, 1, 1))
    assert toc_entry_for(toc, "tec00116").updated_at == date(2026, 1, 1)
    assert toc_entry_for(_toc(), "tin00999") is None


def test_alias_whose_successor_is_missing_is_still_vanished():
    assert toc_entry_for({"tec00114": _toc()["tec00114"]}, "tec00116") is None


def test_select_changed_datasets_picks_renamed_dataset(monkeypatch):
    class State:
        status = "ok"
        last_update_of_data = date(2026, 10, 21)
        last_structure_change = date(2026, 10, 20)
        dataset_id = "tec00116"

    class Result:
        def scalars(self):
            return self

        def all(self):
            return [State()]

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def execute(self, *_a, **_k):
            return Result()

    async def catalog():
        return {"tec00116"}

    monkeypatch.setattr(ingest, "async_session", Session)
    monkeypatch.setattr(ingest, "_catalog_dataset_ids", catalog)
    selected = asyncio.run(ingest.select_changed_datasets(_toc()))
    assert [e.dataset_id for e in selected] == ["tec00116"]
    assert selected[0].updated_at == date(2026, 10, 22)
