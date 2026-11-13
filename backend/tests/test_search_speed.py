"""Скорость поиска без изменения выдачи (13.11.2026).

Правка `perf/search-speed-2026-11-13` меняет способ счёта, а не результат. Здесь прежние способы записаны как
образец, и новый код обязан совпасть с ними на случайных данных:

- счёт строки (`match_score`): образец — прежний разбор по словам с регулярными выражениями;
- допуск одной опечатки: образец — `edit_distance_one`;
- вхождения географических названий: образец — регулярное выражение на каждое название;
- кандидаты мирового каталога: образец — один запрос «факт + порядок + предел».
"""
import asyncio
import random
import re
from datetime import date

from sqlalchemy import case, literal, select
from sqlalchemy.dialects import postgresql

from app.models import WorldCountry, WorldDataPoint, WorldIndicator
from app.services import search_intent
from app.services.search import _world_fact, _world_top_with_facts
from app.services.search_dimensions import dimension_constraints, native_dimension_match_clause
from app.services.search_intent import (
    CONCEPTS_ALTERNATIVES, EXACT_ONLY_WORDS, _alias_occurrences, _control_neighbour, _typo_pattern,
    complete_nominal_alternative, edit_distance_one, match_score, matching_alternatives, normalize, parse_intent,
    phrase, tokens,
)

GEOMETRY = [
    dict(key="country:germany", kind="country", slug="germany", name_ru="Германия", name_en="Germany",
        country_slug="germany", country_code="DE"),
    dict(key="region:russia:moskva", kind="region", slug="moskva", name_ru="г. Москва", name_en="Moscow",
        country_slug="russia"),
]


def _reference_score(intent, *, code="", names=(), metadata=""):
    """`match_score` до 13.11.2026, без памяти процесса и без подстрочных проверок."""
    if not intent.terms:
        return 20
    code_norm, name_norms = normalize(code), tuple(normalize(n) for n in names if n)
    exact_code = intent.literal == code_norm or intent.content == code_norm or intent.query == code_norm
    exact_name = phrase(intent.literal) in tuple(phrase(n) for n in name_norms) if intent.literal else False
    exact = 1000 if exact_code else 900 if exact_name or intent.content in name_norms or intent.content in tuple(
        phrase(n) for n in name_norms) else 0
    hay = phrase(" ".join((code, *names, metadata)))
    hay_tokens = tokens(hay)
    identity_tokens = tokens(" ".join((code, *names)))
    score = 0
    for source_group in intent.terms:
        best = None
        alternatives = matching_alternatives(source_group, literal=intent.literal)
        for alternative in alternatives:
            nominal_group = complete_nominal_alternative(source_group, alternatives, alternative)
            alt = normalize(alternative)
            p = phrase(alt)
            unresolved = alternatives not in CONCEPTS_ALTERNATIVES and intent.literal != alt
            control_neighbour = unresolved and " " not in p and _control_neighbour(p)
            bounded = re.compile(r"(?<![a-zа-я0-9])" + re.escape(p) + r"(?![a-zа-я0-9])")
            typo_allowed = p not in EXACT_ONLY_WORDS
            if len(p) < 3 and len(intent.terms) == 1 and not intent.literal and (
                    phrase(code).startswith(p) or any(phrase(name).startswith(p) for name in name_norms)):
                value = 35
            elif intent.literal == alt and len(p) >= 24 and len(p.split()) >= 4 and any(
                    phrase(name).startswith(p) for name in name_norms):
                value = 70
            elif bounded.search(phrase(code)):
                value = 100 if code_norm == alt else 80
            elif any(bounded.search(phrase(name)) for name in name_norms):
                value = 70
            elif not nominal_group and len(p) >= 3 and " " not in p and any(t.startswith(p) for t in identity_tokens):
                value = 15
            elif bounded.search(hay):
                value = 20
            elif not nominal_group and not control_neighbour and len(p) >= 3 and " " not in p and any(
                    t.startswith(p) for t in hay_tokens):
                value = 15
            elif typo_allowed and not nominal_group and not control_neighbour and len(p) >= (
                    5 if unresolved else 4) and " " not in p and any(
                    len(t) >= 4 and edit_distance_one(p, t) for t in hay_tokens):
                value = 5
            else:
                continue
            best = max(best or 0, value)
        if best is None:
            return None
        score += best
    return max(score, exact)


_WORDS = ("инфляция", "инфляции", "цена", "цены", "цен", "безработица", "безработицы", "уровень", "зарплата",
    "зарплаты", "средняя", "ввп", "импорт", "импорта", "экспорт", "товаров", "население", "ставка", "ключевая",
    "ипотека", "бензин", "бензина", "топливо", "дизельное", "акциз", "акции", "индекс", "потребительских",
    "inflation", "price", "prices", "unemployment", "rate", "wage", "wages", "average", "gdp", "import", "imports",
    "export", "exports", "goods", "population", "index", "indices", "consumer", "fuel", "full", "fat", "sport",
    "transport", "per", "capita", "usd", "percent", "monthly", "annual", "2020", "i15", "ai", "95", "search-mode-level",
    "search-freq-monthly", "search-unit-percent", "R&D", "Ёлка", "нефть", "Brent", "USD/RUB", "п.п.")
_QUERIES = ("инфляция", "инфляцыя", "цена бензина", "цены", "безработица", "уровень безработицы", "зарплата",
    "средняя зарплата", "ввп", "импорт", "импорт товаров", "экспорт", "население", "ключевая ставка", "ипотека",
    "акциз", "inflation", "price", "prices", "unemployment rate", "unemploymnet", "wage", "wages", "wagse", "gdp",
    "gdp per capita", "import", "exports of goods", "population", "index", "fuel", "sport", "transport", "ин",
    "p", "ца", "consumer price index", "индекс потребительских цен", "cpi", "нефть", "brent", "usd", "imp",
    "monthly inflation", "инфляция в процентах", "wages 2020", "de-cpi", "fuel-ai95", "топлив", "дизельное топливо",
    "Индекс потребительских цен на товары и услуги")


def _random_row(rng):
    def text(low, high):
        return " ".join(rng.choice(_WORDS) for _ in range(rng.randint(low, high)))
    code = "-".join(phrase(rng.choice(_WORDS)).replace(" ", "-") or "x" for _ in range(rng.randint(1, 3)))
    return code, (text(1, 6), rng.choice(("", text(1, 5)))), text(0, 12)


def test_score_is_the_same_as_before_on_random_rows():
    rng = random.Random(20261113)
    rows = [_random_row(rng) for _ in range(700)]
    rows += [("cpi", ("Индекс потребительских цен на товары и услуги", "Consumer price index"), "Цены инфляция %"),
        ("fuel-ai95", ("Цена бензина АИ-95", "AI-95 petrol price"), "топливо бензин руб/л search-subject-price"),
        ("de-cpi", ("Consumer price index", ""), ""), ("", ("",), ""), ("x", (), "")]
    checked = matched = 0
    for query in _QUERIES:
        intent = parse_intent(query, GEOMETRY)
        for code, names, metadata in rows:
            expected = _reference_score(intent, code=code, names=names, metadata=metadata)
            assert match_score(intent, code=code, names=names, metadata=metadata) == expected, (query, code, names, metadata)
            checked += 1
            matched += expected is not None
    # Образец обязан проходить обе ветви: строка подошла и строка отброшена.
    assert checked > 30000 and 500 < matched < checked - 500


def test_score_accepts_a_list_of_names_and_repeats_the_cached_answer():
    intent = parse_intent("инфляция", GEOMETRY)
    first = match_score(intent, code="cpi", names=["Инфляция", "Inflation"], metadata="цены")
    assert first == match_score(intent, code="cpi", names=("Инфляция", "Inflation"), metadata="цены") == 900
    assert first == _reference_score(intent, code="cpi", names=("Инфляция", "Inflation"), metadata="цены")
    assert match_score(intent, code="cpi", names=("Инфляция", "Inflation"), metadata="цены") == first


def test_row_memory_is_bounded():
    """Память процесса на строки каталога ограничена: backend живёт под потолком контейнера (см. _TEXT_CACHE_SIZE)."""
    assert search_intent._row_evidence.cache_info().maxsize == search_intent._ROW_CACHE_SIZE <= 8192


def test_one_typo_expression_is_edit_distance_one():
    rng = random.Random(7)
    alphabet = "abcdeинфляцё0159"
    words = ["инфляция", "цена", "wage", "wages", "fuel", "акции", "безработица", "aaaa", "abab", "импорт2020"]
    words += ["".join(rng.choice(alphabet.replace("ё", "")) for _ in range(rng.randint(4, 9))) for _ in range(60)]
    checked = 0
    for word in words:
        pattern = _typo_pattern(word)
        candidates = {word, word[:-1], word[1:], word + "s", "x" + word}
        for index in range(len(word) + 1):
            for char in "abинф0":
                candidates.add(word[:index] + char + word[index:])
                candidates.add(word[:index] + char + word[index + 1:])
                candidates.add(word[:index] + char + char + word[index + 1:])
            candidates.add(word[:index] + word[index + 1:])
            candidates.add(word[:index] + word[index + 2:])
            if index + 1 < len(word):
                candidates.add(word[:index] + word[index + 1] + word[index] + word[index + 2:])
            if index + 2 < len(word):
                candidates.add(word[:index] + word[index + 2] + word[index + 1] + word[index] + word[index + 3:])
        candidates.update("".join(rng.choice(alphabet.replace("ё", "")) for _ in range(rng.randint(1, 10))) for _ in range(300))
        for token in candidates:
            if not token:
                continue
            expected = len(token) >= 4 and edit_distance_one(word, token)
            assert bool(pattern.search(" " + token + " ")) == expected, (word, token)
            # Слово внутри другого слова — не целое слово.
            assert not pattern.search(" zz" + token + "zz ") or edit_distance_one(word, "zz" + token + "zz")
            checked += 1
    assert checked > 10000


def test_long_single_word_keeps_the_plain_token_walk():
    word = "а" * (search_intent._TYPO_PATTERN_MAX_WORD + 5)
    intent = parse_intent(word, GEOMETRY)
    assert match_score(intent, code="x", names=(word[:-1] + "б",)) == _reference_score(intent, code="x", names=(word[:-1] + "б",))
    assert match_score(intent, code="x", names=("другое",)) is None


def test_alias_occurrences_are_the_same_as_one_expression_per_alias():
    rng = random.Random(3)
    aliases = ("Москва", "г. Москва", "Moscow", "moscow oblast", "Германия", "germany", "de", "США", "us", "a", "",
        "Санкт-Петербург", "new york", "york", "Ёлка", "R&D", "..", "марий эл", "эл")
    words = ("москва", "г", "moscow", "oblast", "германия", "germany", "de", "сша", "us", "a", "санкт", "петербург",
        "new", "york", "newyork", "елка", "r", "d", "марий", "эл", "эля", "usa", "germanyx", "xgermany")
    for _ in range(600):
        text = " ".join(rng.choice(words) for _ in range(rng.randint(0, 9)))
        expected = [(match.start(), match.end(), phrase(alias)) for alias in aliases if phrase(alias)
            for match in re.finditer(r"(?<!\w)" + re.escape(phrase(alias)) + r"(?!\w)", text)]
        assert list(_alias_occurrences(text, aliases)) == expected, text


def _seed_world(session_maker, count, with_fact):
    async def seed():
        async with session_maker() as db:
            country = WorldCountry(code="DE", slug="germany", name_ru="Германия", name_en="Germany")
            db.add(country)
            await db.flush()
            rows = [WorldIndicator(country_id=country.id, code=f"de-speed-{index:04}", name_ru="Скорость", name_en="Speed",
                dataset_id="speed", slice_hash=f"speed-{index}", unit="%", frequency="monthly", is_listed=index % 3 == 0)
                for index in range(count)]
            db.add_all(rows)
            await db.flush()
            for index, row in enumerate(rows):
                if index in with_fact:
                    db.add(WorldDataPoint(indicator_id=row.id, date=date(2024, 5, 1), value=index + 1))
                elif index % 5 == 0:
                    db.add(WorldDataPoint(indicator_id=row.id, date=date(2024, 5, 1), value=0))  # ноль — не факт
            await db.commit()
    asyncio.run(seed())


def test_world_candidates_with_facts_equal_one_statement_with_limit(auth_env):
    """Ряды без факта пропускаются, порядок и предел те же, что у прежнего запроса «факт + порядок + LIMIT»."""
    rng = random.Random(11)
    count = 420
    with_fact = {index for index in range(count) if rng.random() < 0.35}
    _seed_world(auth_env["session_maker"], count, with_fact)
    intent = parse_intent("speed", GEOMETRY)
    rank = case((WorldIndicator.code.like("%7"), 0), (WorldIndicator.code.like("%3_"), 2), else_=3)
    order = (rank, WorldIndicator.is_listed.desc(), WorldIndicator.code)
    columns = (WorldIndicator.id, WorldIndicator.code, WorldIndicator.is_listed)

    async def check():
        async with auth_env["session_maker"]() as db:
            statement = select(WorldIndicator.id, rank.label("fe_rank")).where(WorldIndicator.code.like("de-speed-%")).order_by(*order)
            for need in (1, 2, 7, 50, 101, 146, 147, 400, 1000):
                expected = (await db.execute(select(WorldIndicator.code, rank).where(
                    WorldIndicator.code.like("de-speed-%"), _world_fact(intent)).order_by(*order).limit(need))).all()
                picked = await _world_top_with_facts(db, statement, intent, columns, need, {}, postgres=False)
                assert [(row.code, row_rank) for row_rank, row in picked] == [tuple(item) for item in expected], need
            # Общая память фактов: второй запрос того же поиска не проверяет ряд повторно.
            facts = {}
            first = await _world_top_with_facts(db, statement, intent, columns, 20, facts, postgres=False)
            probed = len(facts)
            again = await _world_top_with_facts(db, statement, intent, columns, 20, facts, postgres=False)
            assert [row.code for _rank, row in first] == [row.code for _rank, row in again] and len(facts) == probed
    asyncio.run(check())


def test_world_fact_is_checked_only_for_the_head_of_the_order(auth_env):
    """При плотных фактах проверяется нужное число рядов плюс четверть, а не каждый совпавший ряд."""
    count = 900
    _seed_world(auth_env["session_maker"], count, set(range(count)))
    intent = parse_intent("speed", GEOMETRY)
    columns = (WorldIndicator.id, WorldIndicator.code, WorldIndicator.is_listed)

    async def check():
        async with auth_env["session_maker"]() as db:
            statement = select(WorldIndicator.id, literal(3).label("fe_rank")).where(
                WorldIndicator.code.like("de-speed-%")).order_by(WorldIndicator.is_listed.desc(), WorldIndicator.code)
            facts = {}
            picked = await _world_top_with_facts(db, statement, intent, columns, 201, facts, postgres=False)
            assert len(picked) == 201
            assert len(facts) == 201 + 201 // 4 + 8
    asyncio.run(check())


def _postgres_sql(clause) -> str:
    return str(clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_slice_index_condition_is_added_to_the_exact_one_never_instead():
    """Индекс срезов только находит кандидатов; состав строк по-прежнему решает точное условие."""
    alternatives = (("женщины", True),)
    exact = native_dimension_match_clause(WorldIndicator.provider, WorldIndicator.slice_json, alternatives)
    indexed = native_dimension_match_clause(WorldIndicator.provider, WorldIndicator.slice_json, alternatives, indexed=True)
    exact_sql, indexed_sql = _postgres_sql(exact), _postgres_sql(indexed)
    assert "fe_world_slice_members" not in exact_sql
    assert indexed_sql.startswith("(fe_world_slice_members(world_indicators.provider, CAST(world_indicators.slice_json AS JSONB)) && ")
    assert indexed_sql.endswith(" AND " + exact_sql)
    assert "'sex=F'" in indexed_sql

    terms = (("search-dim-sex-total",), ("search-dim-income-groups-total",), ("cpi",))
    plain = dimension_constraints(terms, WorldIndicator.provider, WorldIndicator.slice_json)
    fast = dimension_constraints(terms, WorldIndicator.provider, WorldIndicator.slice_json, indexed=True)
    assert len(plain) == 2 and len(fast) == 4
    assert [_postgres_sql(clause) for clause in fast[0::2]] == [_postgres_sql(clause) for clause in plain]
    assert "'quant_inc=TOTAL'" in _postgres_sql(fast[3]) and "'rskpovth=TOTAL'" in _postgres_sql(fast[3])
    # Неизвестная метка среза остаётся запретом и без индекса, и с ним.
    assert [_postgres_sql(c) for c in dimension_constraints((("search-dim-magical",),), WorldIndicator.provider,
        WorldIndicator.slice_json, indexed=True)] == ["false"]
