#!/usr/bin/env python3
"""Исправить предлог места в сохранённых русских текстах мировых карточек (круг 13).

Загрузчик писал в `world_indicators` описание, заголовок и ключевые слова с жёстким «в {страна}»:
«… в Франции», «… в Кипре», «… в Мальте» (около 30 тыс. строк). `<title>`, мета и `<h1>` страницы
считаются на лету и уже верны, а видимый абзац описания берётся из столбца. Здесь та же функция
`country_in` (`app/data/eurostat_titles_ru.py`), что и в SSR: «во Франции», «на Кипре», «на Мальте».

Что трогает: столбцы `description`, `seo_description`, `seo_title`, `seo_keywords`, `methodology`
только у стран, для которых фраза не равна «в {предложный падеж}» (по таблице `world_countries`);
только вхождения «в {форма}» как отдельное слово; английские тексты (`name_en` и производные)
и все остальные столбцы не затрагиваются. Идемпотентно: исправленное «во Франции» шаблон не находит.

Безопасность:
* по умолчанию сухой прогон: счётчики до/после, ничего не пишется; запись только с ``--apply``;
* запись пачками по ``--batch`` строк (500), каждая пачка своей короткой транзакцией по первичному ключу,
  между пачками пауза ``--pause`` секунд: таблица не блокируется надолго;
* прежние значения перед каждой пачкой дописываются в файл ``--backup-file`` (JSON Lines, по строке на ряд;
  по умолчанию ``/tmp/world-country-prep-backup.jsonl``). Файл, а не таблица: роль приложения
  (``rustats_app``) не вправе создавать таблицы в схеме public (проверено на стенде). Файл копировать
  с хоста до пересоздания контейнера: ``docker cp <контейнер>:/tmp/world-country-prep-backup.jsonl .``;
* ``--rollback`` возвращает прежние значения только там, где столбец ещё равен результату исправления
  (чужие правки не затираются); перед откатом вернуть файл на место тем же путём;
* после ``--apply`` и ``--rollback`` сбрасываются кэши ``world``, ``world-catalog``, ``ssr-world``
  (как в ``unlist-superseded-world.py``).

    docker compose exec backend python /app/scripts/fix-world-country-prepositions.py            # покажет
    docker compose exec backend python /app/scripts/fix-world-country-prepositions.py --apply    # применит
    docker compose exec backend python /app/scripts/fix-world-country-prepositions.py --rollback --apply
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys

from sqlalchemy import text

sys.path.insert(0, "/app")

from app.data.eurostat_titles_ru import country_in, country_prepositional  # noqa: E402
from app.database import async_session  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("fix-country-prep")

COLUMNS = ("description", "seo_description", "seo_title", "seo_keywords", "methodology")
DEFAULT_BACKUP = "/tmp/world-country-prep-backup.jsonl"
_CYR = "А-Яа-яЁё"


def country_rules(countries: list[tuple[str, str]]) -> dict[str, tuple[re.Pattern[str], str, str]]:
    """slug -> (шаблон, замена, подстрока для предфильтра SQL) только там, где фраза меняется."""
    rules: dict[str, tuple[re.Pattern[str], str, str]] = {}
    for slug, name_ru in countries:
        prep = country_prepositional(slug, name_ru)
        good = country_in(slug, name_ru)
        wrong = f"в {prep}"
        if not prep or good == wrong:
            continue
        pattern = re.compile(rf"(?<![{_CYR}]){re.escape(wrong)}(?![{_CYR}])")
        rules[slug] = (pattern, good, f" {wrong}")
    return rules


def fix_text(value: str | None, rule: tuple[re.Pattern[str], str, str]) -> str | None:
    if not value:
        return value
    return rule[0].sub(rule[1], value)


def read_backup(path: str) -> dict[int, dict]:
    """Файл копий -> {id ряда: прежние значения}; первая запись по ряду главная."""
    out: dict[int, dict] = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out.setdefault(int(row["id"]), row)
    return out


def append_backup(path: str, rows: list[dict]) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


async def candidates(db, country_id: int, needle: str) -> list[int]:
    like = " OR ".join(f"{c} LIKE :n" for c in COLUMNS)
    rows = await db.execute(
        text(f"SELECT id FROM world_indicators WHERE country_id = :c AND ({like}) ORDER BY id"),
        {"c": country_id, "n": f"%{needle}%"},
    )
    return [r[0] for r in rows]


async def count_wrong(db, countries, rules) -> dict[str, int]:
    """Сколько строк у страны ещё содержит неверную фразу (хотя бы в одном столбце)."""
    out: dict[str, int] = {}
    for cid, slug in countries:
        rule = rules.get(slug)
        if not rule:
            continue
        n = 0
        ids = await candidates(db, cid, rule[2])
        for i in range(0, len(ids), 2000):
            chunk = ids[i:i + 2000]
            rows = await db.execute(
                text(f"SELECT {', '.join(COLUMNS)} FROM world_indicators WHERE id IN ({','.join(str(x) for x in chunk)})")
            )
            for row in rows:
                if any(v and rule[0].search(v) for v in row):
                    n += 1
        out[slug] = n
    return out


async def apply_fix(batch: int, pause: float, apply: bool, backup_file: str = DEFAULT_BACKUP) -> dict[str, int]:
    async with async_session() as db:
        pairs = (await db.execute(text("SELECT id, slug, name_ru FROM world_countries ORDER BY id"))).all()
    countries = [(r[0], r[1]) for r in pairs]
    rules = country_rules([(r[1], r[2]) for r in pairs])
    if not rules:
        log.info("нет стран с особым предлогом")
        return {}
    async with async_session() as db:
        before = await count_wrong(db, countries, rules)
    log.info("до: %s (строк с неверным предлогом)", before)
    if not apply:
        log.info("сухой прогон: ничего не записано, для записи --apply")
        return before

    changed = 0
    saved = read_backup(backup_file)
    log.info("копии прежних значений: %s (уже сохранено рядов: %d)", backup_file, len(saved))
    for cid, slug in countries:
        rule = rules.get(slug)
        if not rule:
            continue
        async with async_session() as db:
            ids = await candidates(db, cid, rule[2])
        for i in range(0, len(ids), batch):
            chunk = ids[i:i + batch]
            async with async_session() as db:
                rows = (await db.execute(
                    text(f"SELECT id, {', '.join(COLUMNS)} FROM world_indicators WHERE id IN ({','.join(str(x) for x in chunk)})")
                )).all()
                backups, updates = [], []
                for row in rows:
                    old = dict(zip(COLUMNS, row[1:]))
                    new = {c: fix_text(v, rule) for c, v in old.items()}
                    if new == old:
                        continue
                    backups.append({"indicator_id": row[0], **old})
                    updates.append({"id": row[0], **new})
                if updates:
                    # сначала копия на диск, потом запись в базу: сбой между ними не теряет прежнее значение
                    fresh = [{"id": b["indicator_id"], **{c: b[c] for c in COLUMNS}}
                             for b in backups if b["indicator_id"] not in saved]
                    append_backup(backup_file, fresh)
                    saved.update({r["id"]: r for r in fresh})
                    await db.execute(
                        text(f"UPDATE world_indicators SET {', '.join(c + ' = :' + c for c in COLUMNS)} WHERE id = :id"),
                        updates,
                    )
                await db.commit()
                changed += len(updates)
            if pause:
                await asyncio.sleep(pause)
        log.info("%s: обработано", slug)
    async with async_session() as db:
        after = await count_wrong(db, countries, rules)
    log.info("после: %s; изменено строк: %d", after, changed)
    if changed:
        await _bump()
    return after


async def rollback(batch: int, pause: float, apply: bool, backup_file: str = DEFAULT_BACKUP) -> int:
    saved = read_backup(backup_file)
    if not saved:
        log.info("файла копий %s нет или он пуст: откатывать нечего", backup_file)
        return 0
    async with async_session() as db:
        pairs = (await db.execute(text(
            "SELECT i.id, c.slug, c.name_ru FROM world_indicators i JOIN world_countries c ON c.id = i.country_id "
            f"WHERE i.id IN ({','.join(str(x) for x in sorted(saved))}) ORDER BY i.id"
        ))).all()
    rules = country_rules(sorted({(r[1], r[2]) for r in pairs}))
    by_slug = {r[0]: r[1] for r in pairs}
    restored = 0
    ids = [r[0] for r in pairs]
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        async with async_session() as db:
            cur = {r[0]: r[1:] for r in (await db.execute(
                text(f"SELECT id, {', '.join(COLUMNS)} FROM world_indicators WHERE id IN ({','.join(str(x) for x in chunk)})")
            )).all()}
            updates = []
            for iid in chunk:
                rule = rules.get(by_slug[iid])
                if rule is None or iid not in cur:
                    continue
                values = {}
                for col, now in zip(COLUMNS, cur[iid]):
                    old = saved[iid].get(col)
                    # возвращаем только если столбец всё ещё равен результату исправления
                    values[col] = old if now == fix_text(old, rule) else now
                if tuple(values.values()) != tuple(cur[iid]):
                    updates.append({"id": iid, **values})
            if updates and apply:
                await db.execute(
                    text(f"UPDATE world_indicators SET {', '.join(c + ' = :' + c for c in COLUMNS)} WHERE id = :id"),
                    updates,
                )
                await db.commit()
            restored += len(updates)
        if pause and apply:
            await asyncio.sleep(pause)
    log.info("%s: %d строк", "возвращено" if apply else "вернулось бы", restored)
    if apply and restored:
        await _bump()
    return restored


async def _bump() -> None:
    from app.core.cache import bump_namespaces

    await bump_namespaces("world", "world-catalog", "ssr-world")
    log.info("кэши world, world-catalog, ssr-world сброшены")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="записать (без флага сухой прогон)")
    ap.add_argument("--rollback", action="store_true", help="вернуть прежние значения из таблицы копий")
    ap.add_argument("--backup-file", default=DEFAULT_BACKUP, help="файл копий прежних значений (JSON Lines)")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--pause", type=float, default=0.2)
    args = ap.parse_args()
    if args.rollback:
        asyncio.run(rollback(args.batch, args.pause, args.apply, args.backup_file))
    else:
        asyncio.run(apply_fix(args.batch, args.pause, args.apply, args.backup_file))
