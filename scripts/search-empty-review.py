#!/usr/bin/env python3
"""Разбор пустых поисков: почему ничего не нашлось и какие слова каталога предложить словарю (18.11.2026).

Языковая модель здесь — вне сервера и вне выдачи: она только предлагает, как тот же смысл назван в каталоге. Каждое
предложение проверяется настоящим поиском по базе, а в код (`backend/app/services/search_rewrite.py::REWRITES`)
попадает только руками, после чтения строк выдачи. ADR-0016: поиск не выдумывает ряд, похожий по смыслу.

Запуск — из папки backend, с базой каталога (локальная копия или контейнер backend; только чтение):

    RUSTATS_DATABASE_URL=postgresql+asyncpg://… python ../scripts/search-empty-review.py --days 30
    python ../scripts/search-empty-review.py --csv пустые.csv            # строки «контекст,запрос,раз»
    python ../scripts/search-empty-review.py --days 30 --propose         # + предложения модели (OpenRouter)
    python ../scripts/search-empty-review.py --proposals предложения.json # проверить готовые [{q, rewrite, why}]

Классы причин:
  найдено   — сейчас запрос что-то находит (исправлено раньше или была ошибка/таймаут, записанные как пусто);
  мусор     — нет букв, одна-две буквы, «unsupported_query»;
  период    — несколько лет («unsupported_period») или год, за который у найденного ряда нет данных;
  пробел    — есть слово, которого нет ни в одном названии ряда (каталог этого не знает);
  промах    — все слова есть в названиях, но ни один ряд не собирает их вместе: кандидат для словаря.
Только поле поиска на главной (`context=global`); локальные поля ищут в своём наборе и разбираются отдельно.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import or_, select, text  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models import Indicator, RegionIndicator  # noqa: E402
from app.services.search import federated_search  # noqa: E402
from app.services.search_intent import normalize  # noqa: E402
from app.services.search_unknown_word import word_in_names  # noqa: E402

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CLASSES = ("найдено", "мусор", "период", "пробел", "промах")


async def phrases_from_db(days: int) -> list[tuple[str, int]]:
    async with async_session() as db:
        rows = await db.execute(text(
            "select params_json->>'q' as q, count(*) from frontend_events "
            "where event_name = 'search_query' and params_json->>'results' = '0' "
            "and coalesce(params_json->>'context', 'global') = 'global' "
            "and occurred_at > now() - make_interval(days => :days) group by 1 order by 2 desc"), {"days": days})
        return [(q, n) for q, n in rows.all() if q]


def phrases_from_csv(path: str) -> list[tuple[str, int]]:
    out = []
    with open(path, encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if len(row) == 3 and row[2].isdigit() and row[0] == "global":
                out.append((row[1], int(row[2])))
    return out


async def classify(q: str) -> dict:
    async with async_session() as db:
        body = await federated_search(db, q, limit=5)
        rows = body.get("results") or []
        item = {"q": q, "found": len(rows), "reason": body.get("reason"),
                "top": [row.get("name") for row in rows[:3]], "corrected": body.get("corrected_query")}
        if rows:
            item["class"] = "найдено"
        elif body.get("reason") == "unsupported_period":
            item["class"] = "период"
        elif body.get("reason") == "unsupported_query" or len(re.sub(r"[^a-zа-яё]", "", normalize(q))) < 3:
            item["class"] = "мусор"
        else:
            from app.services.search import _geometry
            from app.services.search_intent import CONCEPTS_ALTERNATIVES, parse_intent

            geometry, _countries = await _geometry(db)
            intent = parse_intent(q, geometry)
            # Обычные слова от трёх букв («сои» тоже): есть ли каждое хоть в одном названии ряда.
            words = [group[0] for group in intent.terms if len(group) == 1 and group not in CONCEPTS_ALTERNATIVES
                     and group[0].isalpha() and len(group[0]) >= 3]
            unknown = [word for word in words if not await word_in_names(db, word, intent)]
            item["unknown_words"] = unknown
            item["class"] = "пробел" if unknown else "период" if intent.year else "промах"
        return item


async def catalogue_context(q: str, limit: int = 8) -> list[str]:
    """Названия рядов России и регионов, где встречается хотя бы одно длинное слово запроса: подсказка модели."""
    words = [w for w in re.findall(r"[a-zа-я]{5,}", normalize(q))][:4]
    if not words:
        return []
    names: list[str] = []
    async with async_session() as db:
        for column in (Indicator.name, RegionIndicator.name):
            condition = or_(*(column.ilike(f"%{word[:-2]}%") for word in words))
            names.extend((await db.execute(select(column).where(condition).distinct().limit(limit))).scalars())
    return list(dict.fromkeys(names))[:limit * 2]


PROMPT = """Ты помогаешь поиску сайта официальной экономической статистики (Росстат, ЦБ, Евростат и др.).
Посетители писали запросы, которые ничего не нашли. Для каждого запроса предложи, как ТОТ ЖЕ смысл назван в каталоге,
используя слова из списка названий рядов рядом с запросом. Если в списке нет ряда с тем же смыслом — rewrite пустой:
похожий, но другой показатель предлагать нельзя (например, «закредитованность» ≠ «кредиты физическим лицам»).
Регион, страну и год из запроса сохраняй. Ответ — только JSON-массив объектов {"q": ..., "rewrite": ..., "why": ...}."""


async def propose(items: list[dict]) -> list[dict]:
    import httpx

    if not settings.openrouter_api_key:
        print("Нет RUSTATS_OPENROUTER_API_KEY — предложения модели пропущены.", file=sys.stderr)
        return []
    batch = []
    for item in items:
        batch.append({"q": item["q"], "unknown_words": item.get("unknown_words", []),
                      "catalogue": await catalogue_context(item["q"])})
    payload = {"model": settings.openrouter_model, "messages": [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": json.dumps(batch, ensure_ascii=False)}]}
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}", "X-Title": "Forecast Economy search review"}
    async with httpx.AsyncClient(timeout=180, proxy=settings.openrouter_proxy_url or None) as client:
        response = await client.post(OPENROUTER_URL, json=payload, headers=headers)
    if response.status_code != 200:
        print(f"OpenRouter ответил {response.status_code}: {response.text[:200]} — предложений нет.", file=sys.stderr)
        return []
    content = (response.json()["choices"][0]["message"].get("content") or "").strip()
    match = re.search(r"\[.*\]", content, re.S)
    return json.loads(match.group(0)) if match else []


async def verify(proposals: list[dict]) -> list[dict]:
    """Проверка каталогом: исходный запрос пуст, замена что-то находит. Смысл строк проверяет человек."""
    checked = []
    for proposal in proposals:
        rewrite = (proposal.get("rewrite") or "").strip()
        if not rewrite:
            continue
        async with async_session() as db:
            before = await federated_search(db, proposal["q"], limit=5)
            body = await federated_search(db, rewrite, limit=5)
        rows = body.get("results") or []
        checked.append({**proposal, "found": len(rows), "was_empty": not before.get("results"),
                        "top": [row.get("name") for row in rows[:3]]})
    return checked


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--csv", help="строки «контекст,запрос,раз» вместо чтения frontend_events")
    parser.add_argument("--propose", action="store_true", help="предложения языковой модели для промахов и пробелов")
    parser.add_argument("--proposals", help="проверить готовые предложения из JSON-файла [{q, rewrite, why}] без разбора")
    parser.add_argument("--json", help="сохранить разбор в файл")
    args = parser.parse_args()
    items: list[dict] = []
    proposals: list[dict] = []
    if args.proposals:
        proposals = json.loads(Path(args.proposals).read_text(encoding="utf-8"))
    else:
        phrases = phrases_from_csv(args.csv) if args.csv else await phrases_from_db(args.days)
        for q, count in phrases:
            item = await classify(q)
            item["count"] = count
            items.append(item)
        tally = Counter(item["class"] for item in items)
        events = Counter()
        for item in items:
            events[item["class"]] += item["count"]
        print(f"Фраз: {len(items)}, поисков: {sum(item['count'] for item in items)}")
        for name in CLASSES:
            print(f"  {name:8s} фраз {tally[name]:4d}, поисков {events[name]:4d}")
        for name in ("промах", "период", "пробел", "найдено"):
            print(f"\n## {name}")
            for item in (i for i in items if i["class"] == name):
                extra = item.get("unknown_words") or item.get("top") or ""
                print(f"  {item['count']:3d}  {item['q'][:90]}  — {extra}")
        if args.propose:
            proposals = await propose([i for i in items if i["class"] in ("промах", "пробел")])
    if proposals:
        checked = await verify(proposals)
        print("\n## Предложения (проверены поиском; в словарь — только руками, после чтения строк)")
        for proposal in checked:
            mark = "находит" if proposal["found"] else "ПУСТО"
            if not proposal["was_empty"]:
                mark += ", исходный запрос и так находит"
            print(f"  {proposal['q'][:60]!r} → {proposal['rewrite']!r} [{mark}] {proposal.get('why', '')[:80]}")
            for name in proposal["top"]:
                print(f"        {name}")
        items.append({"proposals": checked})
    if args.json:
        Path(args.json).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    os.environ.setdefault("RUSTATS_SCHEDULER_ENABLED", "false")
    asyncio.run(main())
