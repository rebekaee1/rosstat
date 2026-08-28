"""Парсер официального графика публикаций Росстата → CalendarCandidate.

Источник (live-probe 2026-08-27): страница «План выпуска публикаций»
(rosstat.gov.ru/publications-plans) подгружает контент AJAX-эндпоинтом
``/publications-plans/getPage?type=50`` («Информационно-аналитические
материалы»). Среди позиций плана — карточка «График размещения срочных
информаций и справок на сайте Росстата» со ссылкой на документ
``/storage/mediabank/Grafik_srochn_YYYY.docx``: официальный помесячный график
выхода оперативных бюллетеней на год.

Формат документа: docx-таблица «№ | НАИМЕНОВАНИЕ ТЕМЫ | ДАТА», месяц-блоки
(«ЯНВАРЬ», «ФЕВРАЛЬ», …) между секциями; даты явные («14 января») →
date_confidence='official_explicit' (ADR-0005: на витрину идут только
explicit/rule-события с полным provenance — форма CalendarCandidate /
upsert_calendar_candidates уже её обеспечивает).

Маппинг тем на коды календаря — по стемам названия бюллетеня (_TOPIC_RULES,
порядок значим: частные раньше общих). Покрываются те же ряды, что и в
ROSSTAT_MONTHLY_RULES / ROSSTAT_GDP_RULES (ИПЦ и срезы, ИЦП, ИПП, ВВП).
Темы без ряда в календаре (просроченная задолженность по зарплате, деловая
активность, финансовые результаты, потребительские ожидания, еженедельные
оценки ИПЦ и нефтепродуктов, цены на бензин) не мапятся и пропускаются.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta

import requests

from app.services.calendar_sources.common import CalendarCandidate, stable_key

logger = logging.getLogger(__name__)

PUBLICATIONS_PLANS_PAGE = "https://rosstat.gov.ru/publications-plans"
PUBLICATIONS_PLANS_API = "https://rosstat.gov.ru/publications-plans/getPage"
PLAN_TYPE_INFO_ANALYTICS = "50"  # «Информационно-аналитические материалы»

_SCHEDULE_CARD_RE = re.compile(r"График\s+размещения\s+срочных\s+информаций", re.IGNORECASE)
_SCHEDULE_DOC_HREF_RE = re.compile(
    r"href=[\"']([^\"']*Grafik_srochn[^\"']*\.docx)[\"']", re.IGNORECASE
)

_MONTH_HEADER_RE = re.compile(
    r"^(ЯНВАРЬ|ФЕВРАЛЬ|МАРТ|АПРЕЛЬ|МАЙ|ИЮНЬ|ИЮЛЬ|АВГУСТ|СЕНТЯБРЬ|ОКТЯБРЬ|НОЯБРЬ|ДЕКАБРЬ)$"
)
_MONTH_NUM = {
    "ЯНВАРЬ": 1, "ФЕВРАЛЬ": 2, "МАРТ": 3, "АПРЕЛЬ": 4, "МАЙ": 5, "ИЮНЬ": 6,
    "ИЮЛЬ": 7, "АВГУСТ": 8, "СЕНТЯБРЬ": 9, "ОКТЯБРЬ": 10, "НОЯБРЬ": 11, "ДЕКАБРЬ": 12,
}
_MONTH_DATIVE_NUM = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_DATE_IN_ROW_RE = re.compile(
    r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)",
    re.IGNORECASE,
)
# «О промышленном производстве в январе-июле 2026 года», «в I квартале 2026 года».
_QUARTER_REF_RE = re.compile(r"(?:I{1,3}|IV)\s*квартал\w*\s*(20\d{2})", re.IGNORECASE)
# «О промышленном производстве в январе-июле 2026 года» (YTD-диапазон) —
# отчётный период ряда = последний месяц диапазона.
_MONTH_RANGE_REF_RE = re.compile(
    r"(?:в|за)\s+(январ|феврал|март|апрел|ма[ейя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*"
    r"\s*[-–—]\s*"
    r"(январ|феврал|март|апрел|ма[ейя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*"
    r"\s+(20\d{2})",
    re.IGNORECASE,
)
_MONTH_REF_RE = re.compile(
    r"(?:в|за)\s+(январ|феврал|март|апрел|ма[ейя]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*\s*(20\d{2})?",
    re.IGNORECASE,
)
_MONTH_NAMES_RU = [
    "", "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]
_MONTH_STEMS = [
    "январ", "феврал", "март", "апрел", "ма", "июн", "июл",
    "август", "сентябр", "октябр", "ноябр", "декабр",
]


@dataclass(frozen=True)
class _TopicRule:
    """Тема бюллетеня → код(ы) календаря.

    ``stems`` — все подстроки (в нижнем регистре) обязаны встретиться в
    названии; ``exclude`` — если встретилась хоть одна, тема пропускается.
    """

    stems: tuple[str, ...]
    codes: tuple[str, ...]
    title: str
    title_en: str
    importance: int = 2
    exclude: tuple[str, ...] = ()


# Порядок значим: первый совпавший блок побеждает (ИЦП раньше ИПП — иначе
# «цен производителей промышленных товаров» уйдёт в промышленное производство).
_TOPIC_RULES: tuple[_TopicRule, ...] = (
    _TopicRule(
        stems=("индекс", "потребительск", "цен"),
        codes=("cpi", "cpi-food", "cpi-nonfood", "cpi-services"),
        title="Индекс потребительских цен (ИПЦ)",
        title_en="Consumer Price Index (CPI)",
        importance=3,
        exclude=("оценк",),  # еженедельные оценки ИПЦ — недельный ритм, не календарь
    ),
    _TopicRule(
        stems=("производител", "промышленн", "цен"),
        codes=("ppi",),
        title="Индекс цен производителей промышленных товаров (ИЦП)",
        title_en="Producer Price Index (PPI)",
    ),
    _TopicRule(
        stems=("промышленн", "производ"),
        codes=("ipi",),
        title="Индекс промышленного производства (ИПП)",
        title_en="Industrial Production Index",
    ),
    _TopicRule(
        stems=("валов", "внутренн", "продукт"),
        codes=("gdp-nominal", "gdp-real"),
        title="Валовой внутренний продукт (ВВП)",
        title_en="Gross Domestic Product (GDP)",
        importance=3,
    ),
)


def _match_topic(title: str) -> tuple[list[str], _TopicRule] | None:
    low = " ".join(title.split()).lower()
    for rule in _TOPIC_RULES:
        if not all(stem in low for stem in rule.stems):
            continue
        if any(ex in low for ex in rule.exclude):
            continue
        return list(rule.codes), rule
    return None


def _topic_reference_period(title: str) -> str | None:
    """Отчётный период из названия — в формате enrichment-парсера.

    «О валовом внутреннем продукте в I квартале 2026 года» → «Q1 2026»;
    «Об индексе потребительских цен в декабре 2025 года» → «декабрь 2025».
    """
    low = " ".join(title.split()).lower()
    qm = _QUARTER_REF_RE.search(low)
    if qm:
        q_text = qm.group(0).split()[0].upper()
        q = {"I": 1, "II": 2, "III": 3, "IV": 4}.get(q_text)
        if q:
            return f"Q{q} {qm.group(1)}"
    # Диапазон («в январе-июле 2026») важнее одиночного месяца: последний
    # месяц диапазона — точка ряда (ИПП за июль в накоплении с января).
    rm = _MONTH_RANGE_REF_RE.search(low)
    if rm:
        stem = rm.group(2).lower()
        for idx, name in enumerate(_MONTH_STEMS, start=1):
            if stem.startswith(name):
                return f"{_MONTH_NAMES_RU[idx]} {rm.group(3)}"
    mm = _MONTH_REF_RE.search(low)
    if not mm:
        return None
    stem = mm.group(1).lower()
    year = mm.group(2)
    for idx, name in enumerate(_MONTH_STEMS, start=1):
        if stem.startswith(name):
            return f"{_MONTH_NAMES_RU[idx]} {year}" if year else None
    return None


def _extract_docx_table_rows(content: bytes) -> list[list[str]]:
    """Все строки всех таблиц docx как списки ячеек (текст без разметки)."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    rows: list[list[str]] = []
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", xml, re.S):
        cells: list[str] = []
        for tc in re.findall(r"<w:tc[ >].*?</w:tc>", tr, re.S):
            text = re.sub(r"<[^>]+>", "", tc)
            cells.append(" ".join(text.split()))
        rows.append(cells)
    return rows


def parse_schedule_docx(content: bytes, *, year: int) -> list[tuple[date, str]]:
    """docx графика → [(дата, название темы)].

    Месяц берётся из заголовка-блока («ЯНВАРЬ»), день — из ячейки даты
    («14 января»); строка может быть и без колонки № (2 ячейки). Дата ищется
    с конца строки — чтобы не схватить «18 августа» из названия еженедельника.
    """
    out: list[tuple[date, str]] = []
    current_month: int | None = None
    for cells in _extract_docx_table_rows(content):
        if not cells:
            continue
        stripped = [c.strip() for c in cells]
        # Месяц-блок может стоять в любой ячейке строки (в реальном документе
        # он в колонке темы с пустыми соседями).
        month_hit = next((c.upper() for c in stripped if c.upper() in _MONTH_NUM), None)
        if month_hit:
            current_month = _MONTH_NUM[month_hit]
            continue
        if current_month is None or len(stripped) < 2:
            continue
        title = " ".join(c for c in stripped[:-1] if c and not c.isdigit())
        if not title:
            continue
        matched = None
        for cell in reversed(stripped):
            dm = _DATE_IN_ROW_RE.search(cell)
            if dm:
                matched = dm
                break
        if not matched:
            continue
        day = int(matched.group(1))
        month = _MONTH_DATIVE_NUM[matched.group(2).lower()]
        if not 1 <= day <= 31:
            continue
        # Дата документа всегда согласована с месяцем блока; если документ
        # склеил соседние секции — доверяем явной дате в ячейке.
        if month != current_month:
            current_month = month
        try:
            scheduled = date(year, month, day)
        except ValueError:
            continue
        out.append((scheduled, title))
    return out


def resolve_schedule_doc_url(html: str) -> str | None:
    """Ссылка на docx графика из HTML страницы плана публикаций."""
    if not _SCHEDULE_CARD_RE.search(html):
        return None
    m = _SCHEDULE_DOC_HREF_RE.search(html)
    if not m:
        return None
    url = m.group(1)
    if url.startswith("http"):
        return url
    return "https://rosstat.gov.ru" + (url if url.startswith("/") else "/" + url)


def fetch_schedule_docx(
    *,
    year: int | None = None,
    session: requests.Session | None = None,
) -> tuple[bytes, str, int] | None:
    """Скачать docx графика срочных информаций.

    Возвращает ``(content, doc_url, year)``; год извлекается из имени файла
    (Grafik_srochn_2026.docx), иначе — текущий. None — источник недоступен или
    графика на странице нет (Росстат сменил схему публикации → обновить
    resolve_schedule_doc_url по факту live-probe).
    """
    from app.config import settings
    from app.services.http_client import create_session

    sess = session or create_session(timeout=30)
    # rosstat.gov.ru подписан российским trusted CA — паттерн всех rosstat-парсеров.
    if not session:
        sess.verify = settings.rosstat_ca_cert
    try:
        resp = sess.get(
            PUBLICATIONS_PLANS_API,
            params={"type": PLAN_TYPE_INFO_ANALYTICS, "page": "1"},
            timeout=30,
        )
        resp.raise_for_status()
        try:
            payload = resp.json()
            html = payload.get("html") or payload.get("content") or "" if isinstance(payload, dict) else ""
        except ValueError:
            html = resp.text
    except requests.RequestException:
        logger.warning("Rosstat publications-plans getPage failed", exc_info=True)
        return None

    doc_url = resolve_schedule_doc_url(html)
    if not doc_url:
        logger.info("Rosstat plan: schedule docx link not found on publications page")
        return None

    if year is None:
        ym = re.search(r"(20\d{2})\.docx$", doc_url, re.IGNORECASE)
        year = int(ym.group(1)) if ym else date.today().year

    try:
        doc = sess.get(doc_url, timeout=30)
        doc.raise_for_status()
    except requests.RequestException:
        logger.warning("Rosstat plan schedule docx download failed: %s", doc_url)
        return None
    if doc.content[:2] != b"PK":  # docx = zip; HTML-заглушка/404-страница отсекается
        logger.warning("Rosstat plan: %s is not a docx file", doc_url)
        return None
    return doc.content, doc_url, year


def build_rosstat_plan_candidates(
    content: bytes,
    *,
    doc_url: str,
    year: int,
    today: date,
    months_ahead: int,
) -> list[CalendarCandidate]:
    """События официального графика → CalendarCandidate (official_explicit).

    Окно — как у остальных официальных источников: [today−14 дней,
    today+months_ahead], чтобы ежедневный синк не плодил хвост прошедших дат.
    """
    horizon = today + timedelta(days=months_ahead * 31)
    cutoff = today - timedelta(days=14)

    candidates: list[CalendarCandidate] = []
    # Порядковый номер выпуска внутри (код, ref-период): у ВВП на один квартал
    # приходится два выпуска (первая оценка + уточнение), у остальных — один.
    # Ключ = (код, ref, ordinal): перенос даты в графике обновляет ту же строку
    # (reschedule_audit в upsert), а не плодит дубликат по новой дате.
    ordinal: dict[tuple[str, str | None], int] = {}
    for scheduled, title in parse_schedule_docx(content, year=year):
        if not (cutoff <= scheduled <= horizon):
            continue
        matched = _match_topic(title)
        if not matched:
            continue
        codes, rule = matched
        ref = _topic_reference_period(title)
        for code in codes:
            n = ordinal[(code, ref)] = ordinal.get((code, ref), 0) + 1
            uid = f"rosstat-plan-{code}-{ref or 'na'}-r{n}-{scheduled.isoformat()}"
            candidates.append(CalendarCandidate(
                event_key=stable_key("rosstat", "plan", code, ref, f"r{n}"),
                title=rule.title,
                title_en=rule.title_en,
                event_type="data_release",
                source="rosstat",
                indicator_code=code,
                scheduled_date=scheduled,
                date_confidence="official_explicit",
                reference_period=ref,
                importance=rule.importance,
                source_url=doc_url,
                source_event_uid=uid,
                description=_plan_description(code),
                metadata={
                    "bulletin_title": title,
                    "schedule_doc": doc_url,
                    "schedule_year": year,
                    "release_ordinal": n,
                },
            ))
    return candidates


def _plan_description(code: str) -> str | None:
    from app.services.calendar_sources.official_calendar import _event_description

    return _event_description(
        code,
        "Дата публикации по официальному графику размещения публикаций Росстата.",
    )


def fetch_rosstat_plan_candidates(
    *,
    today: date,
    months_ahead: int,
    session: requests.Session | None = None,
) -> list[CalendarCandidate]:
    """Точка входа конвейера: fetch + parse + candidates. Ошибки — не фатальны."""
    try:
        got = fetch_schedule_docx(session=session)
        if not got:
            return []
        content, doc_url, year = got
        return build_rosstat_plan_candidates(
            content, doc_url=doc_url, year=year, today=today, months_ahead=months_ahead,
        )
    except Exception:
        logger.exception("Failed to fetch Rosstat publication plan")
        return []
