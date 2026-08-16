"""Нормализация единиц измерения регионального каталога.

Парсер `extract_unit()` берёт последний фрагмент примечания таблицы — туда
часто попадает момент учёта («на конец года») или «тысяч» без существительного.
Этот модуль приводит unit к читаемой единице и переносит оговорки в note.

Потребители:
  - `parse_pril_2025.py` — при пересборке артефакта;
  - `python scripts/regional/unit_normalize.py --apply-artifact` — патч
    закоммиченного `backend/app/data/regional/indicators.json`.
"""
from __future__ import annotations

import re

# Голые «тысяч» без объекта — восстанавливаем по коду показателя.
BARE_THOUSANDS_BY_CODE: dict[str, str] = {
    "predostavlenie-grazhdanam-zhilyh-pomescheniy-chislo-semey-sostoyavshih": "тысяч семей",
    "predostavlenie-grazhdanam-zhilyh-pomescheniy-chislo-semey-poluchivshih": "тысяч семей",
    "predostavlenie-grazhdanam-subsidiy-na-oplatu-zhilogo-pomescheniya": "тысяч семей",
    "turistskie-firmy-chislo-turpaketov-realizovannyh-naseleniyu": "тысяч турпакетов",
    "itogi-sploshnyh-nablyudeniy-chislo-malyh-predpriyatiy-v": "тысяч предприятий",
    "itogi-vyborochnyh-obsledovaniy-chislennost-fakticheski-deystvuyuschih-individualnyh": (
        "тысяч человек"
    ),
    "itogi-sploshnyh-nablyudeniy-chislo-individualnyh-predprinimateley-v": (
        "тысяч предпринимателей"
    ),
}

# Когда в unit оказался только момент учёта — подставляем счётную единицу.
TIMING_ONLY_UNIT_BY_CODE: dict[str, str] = {
    "chislo-organizatsiy": "единиц",
    "osnovnye-pokazateli-po-vidu-deyatelnosti-lesozagotovki-chislo": "единиц",
    "osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybolovstvo": "единиц",
    "osnovnye-pokazateli-po-vidu-ekonomicheskoy-deyatelnosti-rybovodstvo": "единиц",
    "chislo-zdaniy-i-sooruzheniy-nahodyaschihsya-v-nezavershennom": "единиц",
    "chislo-deystvuyuschih-kreditnyh-organizatsiy": "единиц",
    "chislo-deystvuyuschih-filialov-kreditnyh-organizatsiy-v-subekte": "единиц",
}

_TIMING_ONLY_RE = re.compile(
    r"^на\s+(?:конец|начало)\s+(?:года|учебного\s+года|отч[её]тного\s+периода)$",
    re.IGNORECASE,
)
_TIMING_PREFIX_RE = re.compile(
    r"^(?P<timing>на\s+(?:конец|начало)\s+(?:года|учебного\s+года|"
    r"отч[её]тного\s+периода))"
    r"(?:\s*,\s*|\s+)(?P<rest>.+)$",
    re.IGNORECASE,
)

_SINGULAR_MAP = {
    "тысяча гектаров": "тысяч гектаров",
    "тысяч га": "тысяч гектаров",
    "гектар": "гектаров",
    "килограмм": "килограммов",
    "млн руб.": "миллионов рублей",
    "млн руб": "миллионов рублей",
}

_PCT_EXACT = {"в процентах", "процентов"}
_PCT_PREFIX_RE = re.compile(r"^в\s+процентах\s+", re.IGNORECASE)
_PCT_DECEMBER_RE = re.compile(
    r"^к\s+декабрю\s+предыдущего\s+года\s*,\s*в\s+процентах$",
    re.IGNORECASE,
)

# Эхо единиц в note — убираем после нормализации.
# Момент учёта («на конец года») сюда НЕ входит: его сохраняем в note.
_UNIT_ECHO = frozenset(
    {
        "в процентах",
        "процентов",
        "тысяч",
        "тысяча",
        "тысяча гектаров",
        "тысяч га",
        "тысяч гектаров",
        "гектар",
        "килограмм",
        "млн руб.",
        "млн руб",
        "единиц",
        "миллионов рублей",
        "килограммов",
        "гектаров",
        "%",
    }
)


# Примечание о дособранной истории — законченное предложение в конце note.
# Его отделяем перед чисткой: иначе эхо единицы склеено с ним точкой
# («тысяч человек. История до 2000 года…») и фильтром сегментов не ловится.
_NOTE_TAIL_RE = re.compile(r"\s*(История\s+до\s+\d{4}\s+года\s+дособрана.*)$", re.DOTALL)

# Регистр в названии страны: в источнике встречается строчная «федерация».
_COUNTRY_CASE = (("Российской федерации", "Российской Федерации"),)


def _split_note(note: str) -> list[str]:
    return [p.strip() for p in (note or "").split(";") if p.strip()]


def _join_note(parts: list[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        key = p.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return "; ".join(out)


def _strip_unit_echoes(parts: list[str], *extra: str) -> list[str]:
    ban = {e.casefold() for e in _UNIT_ECHO}
    for e in extra:
        if e:
            ban.add(e.casefold())
    result: list[str] = []
    for p in parts:
        if p.casefold() in ban:
            continue
        stripped = re.sub(
            r"(?:,\s*)?(?:в\s+процентах|процентов|тысяч|тысяча\s+гектаров|тысяч\s+га)$",
            "",
            p,
            flags=re.IGNORECASE,
        ).strip(" ;,")
        if stripped:
            result.append(stripped)
    return result


def _normalize_percent_unit(u: str) -> str:
    if u.casefold() in _PCT_EXACT:
        return "%"
    if _PCT_DECEMBER_RE.match(u):
        return "% к декабрю предыдущего года"
    m = _PCT_PREFIX_RE.match(u)
    if m:
        rest = u[m.end() :].strip()
        return f"% {rest}" if rest else "%"
    return u


def normalize_unit(code: str, unit: str, note: str = "", name: str = "") -> tuple[str, str]:
    """Вернуть (unit, note) с исправленной единицей и сохранёнными оговорками."""
    del name  # зарезервировано для эвристик по названию
    raw_unit = (unit or "").strip()
    head, tail = (note or "").strip(), ""
    m_tail = _NOTE_TAIL_RE.search(head)
    if m_tail:
        tail = m_tail.group(1).strip()
        head = head[: m_tail.start()].strip().rstrip(".").strip()
    note_parts = _split_note(head)
    timing_bits: list[str] = []
    u = raw_unit

    m = _TIMING_PREFIX_RE.match(u)
    if m:
        timing_bits.append(m.group("timing").strip())
        u = m.group("rest").strip()
    elif _TIMING_ONLY_RE.match(u):
        timing_bits.append(u)
        u = TIMING_ONLY_UNIT_BY_CODE.get(code, "единиц")

    if u.casefold() in {"тысяч", "тысяча", "тыс.", "тыс"}:
        u = BARE_THOUSANDS_BY_CODE.get(code, "тысяч единиц")

    u = _SINGULAR_MAP.get(u, u)
    u = _normalize_percent_unit(u)

    if _TIMING_ONLY_RE.match(u):
        timing_bits.append(u)
        u = TIMING_ONLY_UNIT_BY_CODE.get(code, "единиц")

    cleaned = _strip_unit_echoes(note_parts, raw_unit, u)
    for t in reversed(timing_bits):
        if not any(t.casefold() in p.casefold() for p in cleaned):
            cleaned.insert(0, t)

    out_note = _join_note(cleaned)
    if tail:
        out_note = f"{out_note}. {tail}" if out_note else tail
    for wrong, right in _COUNTRY_CASE:
        out_note = out_note.replace(wrong, right)

    return u, out_note


def normalize_indicator(ind: dict) -> dict:
    """Вернуть копию записи показателя с нормализованными unit/note."""
    out = dict(ind)
    unit, note = normalize_unit(
        out.get("code", ""),
        out.get("unit") or "",
        out.get("note") or "",
        out.get("name") or "",
    )
    out["unit"] = unit
    out["note"] = note
    return out


# --- дефектные шаблоны для тестов / аудита ---------------------------------

_DEFECT_BARE_THOUSANDS = re.compile(r"^(тысяч|тысяча|тыс\.?)$", re.IGNORECASE)
_DEFECT_TIMING_IN_UNIT = re.compile(
    r"на\s+(конец|начало)\s+(года|учебного\s+года|отч[её]тного\s+периода)",
    re.IGNORECASE,
)
_DEFECT_SINGULAR_THOUSAND_HA = re.compile(r"^тысяча\s+гектаров$", re.IGNORECASE)
_DEFECT_V_PROCENTAKH = re.compile(r"^в\s+процентах$|^процентов$", re.IGNORECASE)
_DEFECT_V_PROCENTAKH_PREFIX = re.compile(r"^в\s+процентах\b", re.IGNORECASE)
_DEFECT_K_DEKABRYU = re.compile(
    r"^к\s+декабрю\s+предыдущего\s+года\s*,\s*в\s+процентах$", re.IGNORECASE
)
_DEFECT_THOUSAND_GA_ABBREV = re.compile(r"^тысяч\s+га$", re.IGNORECASE)
_DEFECT_SINGULAR_HA_KG = re.compile(r"^(гектар|килограмм)$", re.IGNORECASE)
_DEFECT_MLN_RUB_ABBREV = re.compile(r"^млн\s+руб\.?$", re.IGNORECASE)


def unit_defect(unit: str) -> str | None:
    """Вернуть код дефекта или None, если единица допустима."""
    u = (unit or "").strip()
    if not u:
        return "empty"
    if _DEFECT_BARE_THOUSANDS.match(u):
        return "bare_thousands"
    if _DEFECT_TIMING_IN_UNIT.search(u):
        return "timing_in_unit"
    if _DEFECT_SINGULAR_THOUSAND_HA.match(u):
        return "singular_thousand_ha"
    if _DEFECT_V_PROCENTAKH.match(u):
        return "v_procentakh"
    if _DEFECT_K_DEKABRYU.match(u):
        return "k_dekabryu_pct"
    if _DEFECT_V_PROCENTAKH_PREFIX.match(u):
        return "v_procentakh_prefix"
    if _DEFECT_THOUSAND_GA_ABBREV.match(u):
        return "thousand_ga_abbrev"
    if _DEFECT_SINGULAR_HA_KG.match(u):
        return "singular_ha_kg"
    if _DEFECT_MLN_RUB_ABBREV.match(u):
        return "mln_rub_abbrev"
    return None


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    if "--apply-artifact" not in sys.argv:
        print("usage: python scripts/regional/unit_normalize.py --apply-artifact")
        raise SystemExit(2)

    artifact = (
        Path(__file__).resolve().parents[2] / "backend/app/data/regional/indicators.json"
    )
    indicators = json.loads(artifact.read_text(encoding="utf-8"))
    patched = 0
    samples: list[tuple[str, str, str]] = []
    for ind in indicators:
        old_u = ind.get("unit") or ""
        old_n = ind.get("note") or ""
        new_ind = normalize_indicator(ind)
        if new_ind["unit"] != old_u or (new_ind.get("note") or "") != old_n:
            if new_ind["unit"] != old_u and len(samples) < 40:
                samples.append((ind["code"], old_u, new_ind["unit"]))
            ind["unit"] = new_ind["unit"]
            ind["note"] = new_ind["note"]
            patched += 1
    artifact.write_text(
        json.dumps(indicators, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    defects = [
        (i["code"], i["unit"], unit_defect(i["unit"]))
        for i in indicators
        if unit_defect(i.get("unit") or "")
    ]
    print(f"patched: {patched}; remaining defects: {len(defects)}")
    for code, old, new in samples[:30]:
        print(f"  {code}: {old!r} → {new!r}")
    for code, u, d in defects[:20]:
        print(f"  DEFECT {d}: {code} unit={u!r}")
