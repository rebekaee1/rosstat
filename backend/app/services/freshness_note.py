"""Блок «Актуальные данные» на странице устаревшего ряда без живого двойника (круг 12).

Зачем. Значок «Устарело: данные до …» (frontend/src/lib/dataFreshness.js) говорит, что
ряд отстал, но не объясняет почему и не показывает, где искать свежее. Если у ряда есть
живой двойник (остановленный дубль, смена базы индекса), страница отвечает 301 на него.
Если двойника нет, сервер добавляет в API поле ``freshness`` (мир: ``indicator.freshness``,
Россия: ``freshness`` у IndicatorDetail) со структурой:

    {
      "level": "stale",                # всегда stale: у свежих и «стареющих» рядов поля нет
      "last_period": "2023-12-01",     # дата последней точки (ISO)
      "age_days": 1015,                # от конца периода, как в значке
      "reason": "source_stopped" | "series_lag" | "update_delayed" | "retired",
      "source_updated_at": "2026-03-20" | null,   # когда источник последний раз менял набор
      "lead": "Источник не обновлял ряд с декабря 2023.",   # первая фраза (причина), без ссылки
      "message": "Источник не обновлял ряд с декабря 2023. Ближайший актуальный показатель: …",
      "nearest": {"code": "...", "name": "...", "url": "/germany/indicator/...",
                  "last_period": "2026-08-01", "frequency": "monthly"} | null
    }

Причины (``reason``): ``source_stopped`` набор давно не обновляется у источника;
``series_lag`` источник обновляет набор, но по этому ряду (стране, срезу) позже данных
нет; ``update_delayed`` обновление ряда на нашей стороне идёт с задержкой (ошибка или
карантин набора); ``retired`` набор исчез из оглавления источника. Текст ``message``
готов к показу на языке запроса (ru/en); контракт для фронтенда не требует разбора
``reason``, но по нему можно выбрать значок.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from app.services.freshness import age_days, normalize_frequency, period_end, is_stale

_MONTHS_RU = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)
_MONTHS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

# Набор давно не менялся у источника, если дата его обновления старше этого.
SOURCE_QUIET_DAYS = 150


def period_label(last: date, frequency: str | None, locale: str = "ru") -> str:
    """«декабря 2023» / «IV квартала 2023» / «2023» — период, а не день."""
    freq = normalize_frequency(frequency)
    ru = locale != "en"
    if freq == "annual":
        return str(last.year)
    if freq == "quarterly":
        q = (last.month - 1) // 3 + 1
        roman = ("I", "II", "III", "IV")[q - 1]
        return f"{roman} квартала {last.year}" if ru else f"Q{q} {last.year}"
    if freq in ("daily", "weekly"):
        return last.strftime("%d.%m.%Y") if ru else last.isoformat()
    month = (_MONTHS_RU if ru else _MONTHS_EN)[last.month - 1]
    return f"{month} {last.year}"


def build_message(
    *, reason: str, last: date, frequency: str | None, source_updated_at: date | None,
    nearest_name: str | None, locale: str = "ru",
) -> str:
    """Готовая строка блока. Без жаргона парсеров и кодов наборов."""
    head = build_lead(reason=reason, last=last, frequency=frequency, locale=locale)
    if nearest_name:
        tail = (
            f" Ближайший актуальный показатель: {nearest_name}."
            if locale != "en" else f" The closest up-to-date measure: {nearest_name}."
        )
        return head + tail
    return head


def build_lead(*, reason: str, last: date, frequency: str | None, locale: str = "ru") -> str:
    """Первая фраза блока: причина без предложения про ближайший показатель (круг 13: ссылка рисуется отдельно)."""
    ru = locale != "en"
    when = period_label(last, frequency, locale)
    if reason == "retired":
        head = (
            f"Источник больше не публикует этот ряд: последние данные за {when}."
            if ru else f"The source no longer publishes this series: the latest data are for {when}."
        )
    elif reason == "series_lag":
        head = (
            f"Источник обновляет набор, но по этому ряду данных позже {when} нет."
            if ru else f"The source keeps updating the dataset, but has no data for this series after {when}."
        )
    elif reason == "update_delayed":
        head = (
            f"Обновление ряда идёт с задержкой: у нас данные до {when}."
            if ru else f"The update of this series is delayed: our data run to {when}."
        )
    else:
        head = (
            f"Источник не обновлял ряд с {when}."
            if ru else f"The source has not updated this series since {when}."
        )
    return head


def decide_reason(
    *, dataset_newest_is_stale: bool, source_updated_at: date | None, today: date,
    state_status: str | None, retired: bool,
) -> str:
    if retired:
        return "retired"
    if state_status in {"error", "quarantine"}:
        return "update_delayed"
    quiet = source_updated_at is None or (today - source_updated_at).days > SOURCE_QUIET_DAYS
    if dataset_newest_is_stale or quiet:
        return "source_stopped"
    return "series_lag"


# Измерения среза, которые меняют представление ряда, но не его предмет: единица (база
# индекса, процент или уровень), сезонная корректировка, частота. Остальные (отрасль,
# возраст, пол, партнёр…) определяют, о чём ряд, поэтому «ближайшим актуальным
# показателем» считается только тот же предмет в другом представлении.
_REPRESENTATION_DIMS = frozenset({"unit", "s_adj", "freq", "currency"})


# Измерения, переименованные Евростатом при смене классификации (ECOICOP/COICOP 1999 → 2018):
# одно и то же измерение под новым именем. Заголовочное значение CP00 («все товары и услуги»)
# в ver.2 называется TOTAL. Подгруппы (CP01…) не переименовываются в общем виде, поэтому
# остаются разными предметами.
_RENAMED_DIMS = {"coicop18": "coicop", "ppp_cat18": "ppp_cat", "indic_ppp": "na_item"}


def _subject_key(sl: dict | None) -> dict:
    out: dict = {}
    for k, v in (sl or {}).items():
        if k in _REPRESENTATION_DIMS:
            continue
        key = _RENAMED_DIMS.get(k, k)
        if key == "coicop" and str(v).upper() == "TOTAL":
            v = "CP00"
        out[key] = v
    return out


def _same_subject(a: dict | None, b: dict | None) -> bool:
    a, b = a or {}, b or {}
    return bool(a or b) and _subject_key(a) == _subject_key(b)


async def world_freshness_note(
    db, ind, *, locale: str = "ru", today: date | None = None, country_slug: str | None = None,
) -> dict[str, Any] | None:
    """Блок для мировой карточки; None — ряд не устарел, говорить нечего."""
    from sqlalchemy import select

    from app.data.world_superseded import successor_dataset_of
    from app.models import WorldCountry, WorldDatasetState, WorldIndicator
    from app.services import site_paths as paths

    today = today or date.today()
    last = ind.history_end
    freq = normalize_frequency(ind.frequency)
    if last is None or not is_stale(last, freq, today):
        return None

    # Набор остановлен у источника и заменён преемником (ECOICOP ver.1 → ver.2): живой
    # двойник того же предмета лежит в наборе-преемнике той же страны.
    successor = successor_dataset_of(ind.dataset_id)
    datasets = [ind.dataset_id] + ([successor] if successor else [])
    siblings = (await db.execute(
        select(WorldIndicator).where(
            WorldIndicator.provider == ind.provider,
            WorldIndicator.dataset_id.in_(datasets),
            WorldIndicator.is_listed.is_(True),
            WorldIndicator.points_count > 0,
        )
    )).scalars().all()
    newest = max(
        (s.history_end for s in siblings if s.history_end and s.dataset_id == ind.dataset_id),
        default=last,
    )
    dataset_newest_is_stale = is_stale(newest, freq, today)
    state = await db.get(WorldDatasetState, (ind.provider, ind.dataset_id))
    source_updated_at = state.last_update_of_data if state else None
    state_status = state.status if state else None

    mates = [
        s for s in siblings
        if s.country_id == ind.country_id and s.id != ind.id
        and s.history_end is not None and not is_stale(s.history_end, s.frequency, today)
        and normalize_frequency(s.frequency) == freq
        and _same_subject(ind.slice_json, s.slice_json)
    ]
    nearest = None
    if mates:
        best = max(mates, key=lambda s: (s.history_end, s.points_count or 0, s.code))
        slug = country_slug
        if slug is None:
            slug = (await db.execute(
                select(WorldCountry.slug).where(WorldCountry.id == ind.country_id)
            )).scalar_one_or_none()
        if slug:
            nearest = {
                "code": best.code,
                "name": (best.name_en if locale == "en" and best.name_en else best.name_ru),
                "url": paths.indicator(slug, best.code),
                "last_period": best.history_end.isoformat(),
                "frequency": normalize_frequency(best.frequency),
            }
    reason = decide_reason(
        dataset_newest_is_stale=dataset_newest_is_stale and not mates,
        source_updated_at=source_updated_at, today=today, state_status=state_status,
        retired=False,
    )
    return {
        "level": "stale",
        "last_period": last.isoformat(),
        "age_days": age_days(last, freq, today),
        "reason": reason,
        "source_updated_at": source_updated_at.isoformat() if source_updated_at else None,
        "lead": build_lead(reason=reason, last=last, frequency=freq, locale=locale),
        "message": build_message(
            reason=reason, last=last, frequency=freq, source_updated_at=source_updated_at,
            nearest_name=nearest["name"] if nearest else None, locale=locale,
        ),
        "nearest": nearest,
    }


_WORD_RE = re.compile(r"[а-яёa-z]{4,}", re.IGNORECASE)


def _stems(text: str) -> set[str]:
    return {w.lower()[:5] for w in _WORD_RE.findall(text or "")}


async def ru_freshness_note(
    db, indicator, last: date | None, *, locale: str = "ru", today: date | None = None,
) -> dict[str, Any] | None:
    """Блок для российского показателя: причина по журналу загрузки, ближайший свежий в категории."""
    from sqlalchemy import func, select

    from app.models import FetchLog, Indicator, IndicatorData

    today = today or date.today()
    freq = normalize_frequency(indicator.frequency)
    if last is None or not is_stale(last, freq, today):
        return None
    status = (await db.execute(
        select(FetchLog.status).where(FetchLog.indicator_id == indicator.id)
        .order_by(FetchLog.started_at.desc()).limit(1)
    )).scalar_one_or_none()
    failing = status in {"failed", "timeout", "interrupted", "parsed_zero"}
    reason = "update_delayed" if failing else "source_stopped"

    rows = (await db.execute(
        select(Indicator.code, Indicator.name, Indicator.name_en, Indicator.frequency, func.max(IndicatorData.date))
        .join(IndicatorData, IndicatorData.indicator_id == Indicator.id)
        .where(
            Indicator.is_active.is_(True), Indicator.is_listed.is_(True),
            Indicator.category == indicator.category, Indicator.id != indicator.id,
        )
        .group_by(Indicator.id)
    )).all()
    own = _stems(indicator.name)
    best, best_score = None, 0
    for code, name, name_en, rfreq, rlast in rows:
        if rlast is None or is_stale(rlast, rfreq, today):
            continue
        score = len(own & _stems(name))
        if score > best_score:
            best, best_score = (code, name, name_en, rlast), score
    nearest = None
    if best is not None:
        from app.services import site_paths as paths

        code, name, name_en, rlast = best
        nearest = {
            "code": code,
            "name": name_en if locale == "en" and name_en else name,
            "url": paths.russia_indicator(code),
            "last_period": rlast.isoformat(),
            "frequency": normalize_frequency(rfreq),
        }
    return {
        "level": "stale",
        "last_period": last.isoformat(),
        "age_days": age_days(last, freq, today),
        "reason": reason,
        "source_updated_at": None,
        "lead": build_lead(reason=reason, last=last, frequency=freq, locale=locale),
        "message": build_message(
            reason=reason, last=last, frequency=freq, source_updated_at=None,
            nearest_name=nearest["name"] if nearest else None, locale=locale,
        ),
        "nearest": nearest,
    }
