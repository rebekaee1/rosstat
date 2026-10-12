"""Аудит охвата прогнозов world_*: почему у ряда нет публичного прогноза (круг 13, R-FCST). Только чтение.

Для каждого показателя M/Q/A с ``is_listed`` определяется ОДНА главная причина из списка в порядке проверки:

  published            есть публичный прогноз (passed, is_current); у провайдера imf это официальный прогноз фонда
  imf_projection_only  ряд МВФ без официального прогноза (у фонда нет проекции или она не прошла согласованность)
  policy:<причина>     политика не допускает ряд к обучению (``forecast_eligibility_for``): история короче порога
                       (месячный 72, квартальный 32, годовой 14), ряд устарел, имя не отредактировано, провайдер не утверждён
  source_not_ready     Евростат: источник не подтверждён (``world_dataset_state``)
  queue_never_tried    допустим, ни разу не считался (очередь и лимит дневных пакетов)
  queue_retrain_due    допустим, последняя запись устарела или отпечаток данных сменился (ждёт очереди)
  gate:<причина>       считался и не прошёл порог качества (MASE >= 1, не лучше наивного на 2 %, дыра в данных, константа…);
                       такой прогноз НЕ показывается, порог не снижается
  skipped              запись «skipped»

Запуск (в контейнере scheduler; ``--today`` — дата снимка данных, чтобы возраст ряда считался от неё)::

    docker compose exec -T -e PYTHONPATH=/app scheduler python /app/scripts/world-forecast-gap-audit.py \\
        --out /tmp/gap.json [--today 2026-10-03]
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.data.world_forecast_policy import forecast_eligibility_for  # noqa: E402
from app.database import async_session, set_local_statement_timeout  # noqa: E402
from app.config import settings  # noqa: E402
from app.services.world_forecast_pipeline import forecast_fingerprint  # noqa: E402

try:  # срок по частотам есть в коде круга 13; на более старой сборке — общий срок
    from app.services.world_forecast_pipeline import effective_max_age_days
except ImportError:  # pragma: no cover
    def effective_max_age_days(frequency, default):
        return int(default)

FIRST_LINE = ("united-states", "china", "japan", "india", "brazil", "turkey", "germany", "france", "united-kingdom")

SQL = text(
    """
    with last as (
        select distinct on (world_indicator_id) world_indicator_id, gate_status, gate_reason, strategy, created_at,
               model_params->>'history_end' as p_end, model_params->>'points_count' as p_pts,
               (model_params->>'method_version' is not null) as p_mv
        from world_forecasts order by world_indicator_id, created_at desc, id desc),
    pub as (select distinct world_indicator_id from world_forecasts where is_current and gate_status = 'passed')
    select i.id, c.slug, c.region_ru, i.provider, i.dataset_id, i.frequency, i.unit, i.name_quality,
           i.points_count, i.history_end, i.category_ru,
           s.status as src_status, s.last_success_at as src_ok,
           l.gate_status, l.gate_reason, l.strategy, l.created_at as f_created, l.p_end, l.p_pts, l.p_mv,
           (p.world_indicator_id is not null) as has_public
    from world_indicators i
    join world_countries c on c.id = i.country_id
    left join world_dataset_state s on s.provider = i.provider and s.dataset_id = i.dataset_id
    left join last l on l.world_indicator_id = i.id
    left join pub p on p.world_indicator_id = i.id
    where i.is_listed and i.frequency in ('monthly', 'quarterly', 'annual')
    """
)


def classify(row, today: date, now: datetime) -> str:
    if row.has_public:
        return "published"
    provider = str(row.provider or "").lower()
    if provider == "imf":
        return "imf_projection_only"
    eligible, reason = forecast_eligibility_for(SimpleNamespace(
        provider=row.provider, dataset_id=row.dataset_id, unit=row.unit, frequency=row.frequency, is_listed=True,
        name_quality=row.name_quality, points_count=row.points_count, history_end=row.history_end,
    ), today=today)
    if eligible is None:
        return f"policy:{reason}"
    if provider == "eurostat" and not (row.src_status == "ok" and row.src_ok is not None):
        return "source_not_ready"
    if row.gate_status is None:
        return "queue_never_tried"
    if row.gate_status == "skipped":
        return "skipped"
    created = row.f_created
    stale = created is None or (now - created) > timedelta(
        days=effective_max_age_days(row.frequency, int(settings.world_forecast_max_age_days)))
    expected_end = row.history_end.isoformat() if row.history_end else None
    changed = (row.p_end != expected_end or int(row.p_pts or 0) != int(row.points_count or 0))
    if stale or changed or not row.p_mv:
        return "queue_retrain_due"
    return f"gate:{row.gate_reason or row.gate_status}"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--today", default=None, help="YYYY-MM-DD, по умолчанию сегодня")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    by_country: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    by_country_freq: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    by_country_class: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    total = collections.Counter()
    count = 0
    async with async_session() as db:
        await set_local_statement_timeout(db, 600_000)
        stream = await db.stream(SQL.execution_options(yield_per=5000))
        async for chunk in stream.partitions(5000):
            for row in chunk:
                count += 1
                bucket = classify(row, today, now)
                slug = row.slug if row.slug in FIRST_LINE else ("europe-rest" if row.region_ru == "Европа" else "world-rest")
                by_country[slug][bucket] += 1
                by_country_freq[slug][f"{row.frequency}:{bucket.split(':')[0]}"] += 1
                if row.slug in FIRST_LINE:
                    by_country_class[row.slug][f"{row.category_ru}|{bucket}"] += 1
                total[bucket] += 1
    result = {
        "today": today.isoformat(),
        "indicators": count,
        "total": dict(total.most_common()),
        "by_country": {k: dict(v.most_common()) for k, v in by_country.items()},
        "by_country_freq": {k: dict(v.most_common()) for k, v in by_country_freq.items()},
        "by_country_class": {k: dict(v.most_common()) for k, v in by_country_class.items()},
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"indicators": count, "total": dict(total.most_common(14))}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
