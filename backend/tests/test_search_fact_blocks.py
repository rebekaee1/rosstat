"""Ранняя остановка проверки фактов «показатель × территория» в поиске.

13.11.2026: на боевой базе (12 ГБ при 8 ГБ памяти, ~150 чтений диска в секунду)
проверка факта у каждой пары до LIMIT шла десятки секунд и упиралась в
30-секундный предел запроса. `_ordered_fact_rows` обязана вернуть ту же выдачу,
что и полная проверка, и остановиться, когда выдача набрана.
"""
import asyncio
import random

from app.services.search import _FACT_BLOCK_PAIRS, _ordered_fact_rows


def _case(seed: int):
    rng = random.Random(seed)
    indicators = rng.randint(1, 60)
    territories = rng.randint(1, 25)
    codes = rng.sample(range(1000), indicators)
    ranked_ids = [item for _code, item in sorted(zip(codes, range(1, indicators + 1)))]
    code_rank = {item: rank for rank, item in enumerate(ranked_ids)}
    candidates = rng.sample(ranked_ids, rng.randint(1, indicators))
    scores = {item: rng.choice((100, 100, 100, 250, 400, rng.randint(1, 900))) for item in candidates}
    selected = {territory: {"sort_order": rng.choice((0, 0, 1, 2, 3, territory))} for territory in range(1, territories + 1)}
    density = rng.choice((0.0, 0.02, 0.3, 0.9, 1.0))
    facts = {(item, territory) for item in candidates for territory in selected if rng.random() < density}
    need = rng.choice((1, 2, 7, 40, 101, 501))
    return scores, ranked_ids, code_rank, selected, facts, need


def _key(scores, code_rank, selected):
    # Равные (счёт, порядок территории, код) различает только территория; в SQL этот хвост произволен.
    return lambda pair: (-scores[pair[0]], selected[pair[1]]["sort_order"], code_rank[pair[0]], pair[1])


def _collect(scores, ranked_ids, code_rank, selected, facts, need):
    key = _key(scores, code_rank, selected)
    calls = []

    async def run(indicator_ids, territory_ids, limit):
        assert limit >= 1
        calls.append(len(indicator_ids) * len(territory_ids))
        block = [(item, territory) for item in indicator_ids for territory in territory_ids if (item, territory) in facts]
        return sorted(block, key=key)[:limit]

    rows = asyncio.run(_ordered_fact_rows(run, scores, ranked_ids, selected, need))
    return rows, calls


def test_blocks_return_the_same_rows_as_the_full_product():
    for seed in range(400):
        scores, ranked_ids, code_rank, selected, facts, need = _case(seed)
        rows, _calls = _collect(scores, ranked_ids, code_rank, selected, facts, need)
        assert rows == sorted(facts, key=_key(scores, code_rank, selected))[:need], seed


def test_dense_facts_stop_after_the_first_block():
    scores = {item: 100 for item in range(1, 1401)}
    ranked_ids = list(range(1, 1401))
    code_rank = {item: item for item in ranked_ids}
    selected = {territory: {"sort_order": territory} for territory in range(1, 97)}
    facts = {(item, territory) for item in scores for territory in selected}
    rows, calls = _collect(scores, ranked_ids, code_rank, selected, facts, 101)
    assert len(rows) == 101
    assert calls == [max(_FACT_BLOCK_PAIRS, 101 + 101 // 4)]


def test_sparse_facts_need_few_statements():
    scores = {item: 1000 - item for item in range(1, 901)}
    ranked_ids = list(range(1, 901))
    code_rank = {item: item for item in ranked_ids}
    selected = {territory: {"sort_order": territory} for territory in range(1, 97)}
    rows, calls = _collect(scores, ranked_ids, code_rank, selected, set(), 101)
    assert rows == []
    assert sum(calls) == 900 * 96
    assert len(calls) <= 8


def test_second_block_follows_the_share_of_facts_found():
    """13.11.2026, «инфляция» на боевом: главный ряд дал 93 строки, следующая группа — 881 цена с одним счётом.

    Прежний второй запрос проверял 2 643 пары (три территории целиком) ради 108 строк. Доля пар с фактом в первом
    куске известна, поэтому второй кусок берёт столько пар, сколько нужно при этой доле, с запасом в полтора раза.
    """
    scores = {1: 500, **{item: 100 for item in range(2, 883)}}
    ranked_ids = list(range(1, 883))
    code_rank = {item: item for item in ranked_ids}
    selected = {territory: {"sort_order": territory} for territory in range(1, 94)}
    facts = {(item, territory) for item in scores for territory in selected}
    rows, calls = _collect(scores, ranked_ids, code_rank, selected, facts, 201)
    assert rows == sorted(facts, key=_key(scores, code_rank, selected))[:201]
    assert calls == [93, 162]


def test_half_empty_facts_do_not_restart_from_a_fourfold_block():
    scores = {item: 100 for item in range(1, 1001)}
    ranked_ids = list(range(1, 1001))
    code_rank = {item: item for item in ranked_ids}
    selected = {territory: {"sort_order": territory} for territory in range(1, 11)}
    facts = {(item, territory) for item in scores for territory in selected if item % 2}
    rows, calls = _collect(scores, ranked_ids, code_rank, selected, facts, 201)
    assert rows == sorted(facts, key=_key(scores, code_rank, selected))[:201]
    assert len(calls) <= 3 and sum(calls) <= 3 * 201
