#!/usr/bin/env python
"""Показ владельцу: настоящие черновики автора канала на сегодняшних данных (ADR-0035).

Ничего не публикует и ничего не пишет в базу: соединение открывается только на чтение, запуски автора идут с
`save=False`, в Telegram ничего не отправляется. Каждый вариант — отдельный запуск модели с дополнением к заданию
(какая рубрика, какой тон); результат с разбором сторожа складывается в JSON, графики — в PNG.

Запуск (из backend/, переменные окружения RUSTATS_DATABASE_URL и RUSTATS_OPENROUTER_API_KEY заданы):
    python scripts/channel-author-preview.py --out ../.artifacts/telegram-author-2026-11-17 [--only fuel_between,week]
        [--model anthropic/claude-opus-5.5] [--list]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# (id, подпись для показа, тон, вид запуска, дополнение к заданию)
SHOW = "Это показ владельцу, а не обычный день: "
VARIANTS = [
    ("free", "Автор решает сам: что канал публикует сегодня", None, "daily", None),
    ("short_usd", "Короткая строка: курс", None, "daily",
     SHOW + "напиши короткую строку (размер short, рубрика flash) про официальный курс доллара или евро — что из них сдвинулось заметнее."),
    ("short_gold", "Короткая строка: золото со скачком", None, "daily",
     SHOW + "напиши короткую строку (размер short, рубрика flash) про золото. У ряда пометка «необычный скачок» — поступи, как велят правила."),
    ("short_rate", "Короткая строка: ключевая ставка", None, "daily",
     SHOW + "напиши короткую строку (размер short, рубрика flash) про ключевую ставку и ближайшее заседание."),
    ("short_oil", "Короткая строка: нефть", None, "daily",
     SHOW + "напиши короткую строку (размер short, рубрика flash) про нефть Brent."),
    ("infl_short", "Инфляция — короткой строкой", None, "daily",
     SHOW + "напиши про последнюю цифру инфляции за год короткой строкой (размер short, рубрика release), как если бы она вышла сегодня."),
    ("infl_medium", "Инфляция — средним постом", None, "daily",
     SHOW + "напиши про последнюю цифру инфляции за год средним постом (размер medium, рубрика release), как если бы она вышла сегодня."),
    ("infl_long", "Инфляция — большим постом", None, "daily",
     SHOW + "напиши про последнюю цифру инфляции за год большим постом (размер long, рубрика release), как если бы она вышла "
            "сегодня: что внутри цифры и чем это отличается от прошлого года."),
    ("fuel_medium", "Бензин и дизель — средним постом", None, "daily",
     SHOW + "напиши средний пост рубрики fuel по последним недельным ценам, как если бы они вышли сегодня."),
    ("noticed", "Подмечено: находка в данных", None, "daily",
     SHOW + "напиши пост рубрики noticed не про топливо и не про золото. Найди в данных настоящую находку сам — в сводке или инструментами."),
    ("week_ahead", "Неделя вперёд", None, "daily",
     SHOW + "напиши пост рубрики week_ahead на текущую неделю."),
    ("week", "Неделя в числах", None, "daily",
     SHOW + "напиши пост рубрики week, как если бы сегодня была пятница; изменения считай за последнюю неделю по данным сводки."),
    ("research", "Исследование — большим постом", None, "daily",
     SHOW + "напиши большой пост рубрики research по первому отчёту из очереди."),
    ("plan", "Неделя, собранная автором", None, "plan", None),
]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--suffix", default="", help="добавка к имени файла (сравнение моделей)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--force", action="store_true", help="переписать уже готовые варианты")
    args = ap.parse_args()
    if args.list:
        for v in VARIANTS:
            print(v[0], "—", v[1])
        return 0

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.database as dbm
    from app.config import settings

    # Только чтение: любая запись в этой сессии завершится ошибкой базы.
    engine = create_async_engine(settings.database_url, connect_args={"server_settings": {
        "default_transaction_read_only": "on", "statement_timeout": "20000"}})
    dbm.engine = engine
    dbm.async_session = async_sessionmaker(engine, expire_on_commit=False)

    from app.services import channel_author, public_bot

    public_bot.async_session = dbm.async_session
    out = Path(args.out)
    (out / "runs").mkdir(parents=True, exist_ok=True)
    (out / "charts").mkdir(parents=True, exist_ok=True)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    total = 0.0
    for vid, title, tone, kind, instruction in VARIANTS:
        if only and vid not in only:
            continue
        target = out / "runs" / f"{vid}{args.suffix}.json"
        if target.exists() and not args.force:
            print(f"{vid}: уже есть, пропускаю (--force — переписать)")
            continue
        result = await channel_author.run_author(kind, instruction=instruction, tone=tone, model=args.model or None,
                                                 save=False)
        total += result.cost_usd
        payload = {"id": vid, "title": title, "tone": tone, "kind": kind, "instruction": instruction,
                   "model": result.model, "status": result.status, "decision": result.decision,
                   "nothing": result.nothing, "plan": result.plan, "plan_days": result.plan_days, "concerns": result.concerns,
                   "steps": result.steps, "web_searches": result.web_searches, "prompt_tokens": result.prompt_tokens,
                   "completion_tokens": result.completion_tokens, "cost_usd": round(result.cost_usd, 5),
                   "seconds": result.seconds, "tool_log": result.tool_log, "web": result.web,
                   "drafts": [asdict(d) for d in result.drafts]}
        if result.decision == "error":
            print(f"{vid}: ошибка {result.status}, файл не записан (${result.cost_usd:.3f})")
            if result.status == "http_402":
                print("на счёте OpenRouter не хватает денег — остановка")
                break
            continue
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), "utf-8")
        for d in result.drafts:
            if d.chart_topic and not (out / "charts" / f"{d.chart_topic}.png").exists():
                png = await public_bot.render_topic_chart(d.chart_topic)
                if png:
                    (out / "charts" / f"{d.chart_topic}.png").write_bytes(png)
        print(f"{vid}: {result.decision} · {result.status} · шагов {result.steps} · поиск {result.web_searches} · "
              f"${result.cost_usd:.3f} · {result.seconds} с" + (" · СТОРОЖ: " + "; ".join(result.drafts[0].audit.get('issues') or [])
                                                             if result.drafts and result.drafts[0].blocked else ""))
    print(f"итого ${total:.3f}")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
