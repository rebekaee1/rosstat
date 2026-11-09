"""R10-C: накопленный индекс ИПЦ России для длинной истории цены."""
from app.api.regions import _cpi_chain


def test_chain_starts_at_100_and_multiplies():
    rows = [(1999, 12, 101.0), (2000, 1, 102.0), (2000, 2, 101.0), (2000, 3, 100.5)]
    out = _cpi_chain(rows, 200001)
    assert out[0] == [200001, 100.0]
    assert out[1] == [200002, 101.0]
    assert out[2][0] == 200003 and abs(out[2][1] - 101.505) < 0.01


def test_chain_stops_at_gap():
    rows = [(2000, 1, 101.0), (2000, 2, 101.0), (2000, 4, 101.0)]
    assert [p[0] for p in _cpi_chain(rows, 200001)] == [200001, 200002]


def test_chain_needs_start_month():
    assert _cpi_chain([(2000, 2, 101.0)], 200001) == []
