"""Ежедневная проверка рядов в базе (08.11.2026): ищет точки, которых не может быть, и сообщает в утреннюю сводку.

Пара к сторожу записи (`upsert.point_rejection`): сторож не пускает новые невозможные точки, а эта проверка находит то,
что уже лежит в базе (записано до сторожа, вставлено в обход, испорчено вручную). Повод — 05.11.2026: 194 точки цен на
топливо с датами 0001-… три дня роняли годовые страницы, и узнали об этом только по всплескам 5xx.

Что ищет в `indicator_data` (лёгкие запросы по всей таблице раз в сутки, 08:20 МСК, до утренней сводки 09:10):
* даты раньше `upsert.DATE_MIN` или дальше `upsert.FUTURE_DAYS` от сегодня, `±infinity`;
* значения `NaN`.
Мировые и региональные таблицы (десятки миллионов строк) не сканирует: проверка 08.11.2026 нашла их чистыми, а
полный проход по ним тяжёл для диска хоста. Новые точки туда защищает тот же сторож записи (`world_imf_ingest` пишет
через `bulk_upsert`).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from html import escape

from sqlalchemy import text

from app.services.upsert import DATE_MIN, FUTURE_DAYS

logger = logging.getLogger(__name__)

_QUERY = text("""
    select i.code, count(*) as n, min(d.date)::text as first, max(d.date)::text as last
    from indicator_data d join indicators i on i.id = d.indicator_id
    where d.date < :date_min or d.date > :date_max or d.value = 'NaN'::numeric
    group by i.code order by n desc, i.code
""")


def format_findings(rows: list[tuple[str, int, str, str]]) -> str | None:
    """Текст алерта или None, если всё чисто."""
    if not rows:
        return None
    total = sum(n for _c, n, _f, _l in rows)
    head = ", ".join(f"{escape(code)} ({n})" for code, n, _f, _l in rows[:8])
    more = f" и ещё {len(rows) - 8}" if len(rows) > 8 else ""
    sample = rows[0]
    return (
        "🟡 <b>В базе есть точки, которых не может быть</b>\n"
        f"{total} точек у {len(rows)} рядов: {head}{more}. "
        f"Например, {escape(sample[0])}: даты от {escape(sample[2])} до {escape(sample[3])}.\n"
        "Сайт их не показывает в ссылках на годы, но графики и данные могут быть искажены. "
        "Что сделать: напиши Claude «почисти битые точки»."
    )


async def data_sanity_job() -> list[tuple[str, int, str, str]]:
    """Проверка и алерт `data_sanity` (в спокойном режиме — в утреннюю сводку). Возвращает найденное."""
    from app.database import async_session
    from app.services.alerting import send_telegram

    params = {"date_min": DATE_MIN, "date_max": date.today() + timedelta(days=FUTURE_DAYS)}
    try:
        async with async_session() as db:
            rows = [tuple(r) for r in (await db.execute(_QUERY, params)).all()]
    except Exception:  # noqa: BLE001
        logger.warning("data sanity check failed", exc_info=True)
        return []
    message = format_findings(rows)
    if message:
        logger.error("Проверка данных: %d рядов с невозможными точками: %s", len(rows), rows[:5])
        await send_telegram(message, kind="data_sanity")
    else:
        logger.info("Проверка данных: невозможных точек нет")
    return rows
