from datetime import date

from app.services.world_eurostat_ingest import parse_toc


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
