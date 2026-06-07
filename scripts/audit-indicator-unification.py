#!/usr/bin/env python3
"""Полный аудит индикаторов → temp-файл.

Цель — выгрузить ВСЁ, что есть в системе, на четырёх уровнях декомпозиции
(ADR-0006):

  КАРТОЧКА каталога  →  СРЕЗ (variant)  →  РЕЖИМ (view-mode)  →  ряд данных.

Для каждой пользовательской карточки (листингуемой или скрытого среза variant-
группы) печатаются:
  - категория, код, имя, частота, единица, источник;
  - принадлежность к variant-группе и все её срезы;
  - ВСЕ режимы отображения с конкретным backend-кодом ряда, единицей, частотой
    и признаком «прогнозируемый» — для generic-семей это точные данные из
    `view_model_families.py` (единый источник истины), для bespoke-семей
    (ИПЦ/ИЦП/жильё/срезы ставок ЦБ) — активные режимы их переключателей;
  - прогноз карточки (steps + strategy) и число SEO-блоков.

В конце — ПОЛНЫЙ РЕЕСТР всех активных кодов индикаторов по ролям
(generic-база / bespoke-база / срез / производный ряд режима), чтобы ни один
код БД не выпал из аудита.

Bespoke-наборы режимов — Python-зеркало фронтенд-реестров:
  frontend/src/lib/{cpi,ppi,housing,cbrTermSliceRate}ViewMode*.js
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.data.indicator_seo import INDICATOR_HIDDEN_FROM_LISTING, INDICATOR_SEO_BLOCKS  # noqa: E402
from app.data.view_model_families import FAMILY_BY_BASE, iter_sibling_indicators  # noqa: E402
from seed_data import INDICATORS  # noqa: E402

OUT = ROOT / "indicator-unification-audit.temp.txt"


# --- Bespoke-семьи: активные режимы переключателей (зеркало frontend) ---------
# Формат строки режима: (mode_token, label, series_code, unit, frequency).
# series_code — что грузит фронт (dataMode/derived-код), пустая строка = базовый
# ряд карточки.

def _cpi_modes(base: str) -> list[tuple[str, str, str, str, str]]:
    # cpiViewModeGroups.js::CPI_VIEW_MODES_FLAT (активный двухуровневый пикер).
    # Недельный шаг есть только у составов с недельным бюллетенем.
    food_weekly = {
        "cpi": "inflation-weekly",
        "cpi-food": "inflation-weekly-food",
        "cpi-nonfood": "inflation-weekly-nonfood",
        "cpi-services": "inflation-weekly-services",
    }
    p = "" if base == "cpi" else base[len("cpi"):]  # "" | "-food" | ...
    return [
        ("inflation", "Инфляция за год (скользящие 12 мес.)", f"inflation{p}" if base != "cpi" else "inflation", "%", "monthly"),
        ("step-weekly", "К прошлому периоду: Н/н", food_weekly[base], "%", "weekly"),
        ("step-monthly", "К прошлому периоду: М/м", base if base == "cpi" else base, "%", "monthly"),
        ("qoq", "К прошлому периоду: Кв/Кв", f"{base}-qoq", "%", "quarterly"),
        ("yoy", "К прошлому периоду: Г/г", f"{base}-yoy", "%", "monthly"),
        ("index", "Индекс — по месяцам", base, "индекс", "monthly"),
        ("index-quarterly", "Индекс — по кварталам", base, "индекс", "quarterly"),
        ("index-annual", "Индекс — по годам", base, "индекс", "annual"),
    ]


def _ppi_modes(base: str) -> list[tuple[str, str, str, str, str]]:
    # ppiViewModeGroups.js::PPI_VIEW_MODES_FLAT
    return [
        ("yoy", "Инфляция за год", "ppi-yoy", "%", "monthly"),
        ("mom", "К прошлому периоду (м/м)", "ppi", "%", "monthly"),
        ("index", "Индекс — по месяцам", "ppi", "индекс", "monthly"),
        ("index-quarterly", "Индекс — по кварталам", "ppi", "индекс", "quarterly"),
        ("index-annual", "Индекс — по годам", "ppi-annual", "индекс", "annual"),
    ]


def _housing_modes(base: str) -> list[tuple[str, str, str, str, str]]:
    # housingViewModeGroups.js + housingViewModeResolve.js::housingCanonicalTarget
    slice_ = "primary" if base.endswith("primary") else "secondary"
    return [
        ("qoq", "К прошлому периоду: Кв/Кв", f"housing-qoq-{slice_}", "%", "quarterly"),
        ("yoy", "К прошлому периоду: Г/г", f"housing-yoy-{slice_}", "%", "quarterly"),
        ("index", "Индекс (2010=100)", base, "индекс", "quarterly"),
    ]


def _cbr_term_slice_modes(base: str) -> list[tuple[str, str, str, str, str]]:
    # cbrTermSliceRateResolve.js::CBR_TERM_SLICE_URL_MODES = ['level'].
    return [("level", "Уровень ставки", base, "%", "monthly")]


CPI_BESPOKE = {"cpi", "cpi-food", "cpi-nonfood", "cpi-services"}
PPI_BESPOKE = {"ppi"}
HOUSING_BESPOKE = {"housing-price-primary", "housing-price-secondary"}
# Срезы ставок ЦБ, которых НЕТ в generic-движке (corp-short/ind-short/deposit-rate
# заведены как generic T2y) — только «уровень ставки», скрыты из листинга.
CBR_TERM_SLICE_BESPOKE = {
    "credit-rate-corp-1to3y", "credit-rate-corp-over3y",
    "credit-rate-ind-1to3y", "credit-rate-ind-over3y",
    "deposit-rate-medium", "deposit-rate-long",
}


# --- Variant-группы (зеркало frontend/src/lib/indicatorVariants.js) -----------

VARIANT_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Состав индекса потребительских цен", [
        ("cpi", "Все товары и услуги"), ("cpi-food", "Продовольствие"),
        ("cpi-nonfood", "Непродовольственные"), ("cpi-services", "Услуги")]),
    ("ВВП по использованию", [
        ("gdp-consumption", "Домохозяйства"), ("gdp-government", "Государство"),
        ("gdp-investment", "Инвестиции")]),
    ("Индекс промышленного производства", [
        ("ipi-yoy", "Год к году"), ("ipi", "Помесячно")]),
    ("Рынок жилья", [
        ("housing-price-primary", "Первичное жильё"),
        ("housing-price-secondary", "Вторичное жильё")]),
    ("Ставки по кредитам юридическим лицам", [
        ("credit-rate-corp-short", "До 1 года"),
        ("credit-rate-corp-1to3y", "От 1 до 3 лет"),
        ("credit-rate-corp-over3y", "Свыше 3 лет")]),
    ("Ставки по кредитам физическим лицам", [
        ("credit-rate-ind-short", "До 1 года"),
        ("credit-rate-ind-1to3y", "От 1 до 3 лет"),
        ("credit-rate-ind-over3y", "Свыше 3 лет")]),
    ("Ставки по вкладам физических лиц", [
        ("deposit-rate", "До 1 года"), ("deposit-rate-medium", "От 1 до 3 лет"),
        ("deposit-rate-long", "Свыше 3 лет")]),
    ("Федеральный бюджет", [
        ("budget-revenue", "Доходы"), ("budget-expenditure", "Расходы"),
        ("budget-deficit", "Дефицит/профицит")]),
    ("Кредиты и вклады населения", [
        ("consumer-credit", "Кредиты физлицам"),
        ("deposits-individual", "Вклады физлицам")]),
    ("Денежные агрегаты", [("m0", "М0"), ("m1", "М1"), ("m2", "М2")]),
    ("Рынок труда: занятость", [
        ("labor-force", "Рабочая сила"), ("employment", "Занятое население")]),
]

VARIANT_GROUP_BY_CODE: dict[str, tuple[str, list[tuple[str, str]]]] = {}
for _label, _codes in VARIANT_GROUPS:
    for _c, _ in _codes:
        VARIANT_GROUP_BY_CODE[_c] = (_label, _codes)


# --- Индекс seed по коду ------------------------------------------------------

BY_CODE: dict[str, dict] = {i["code"]: i for i in INDICATORS}
SIBLING_INFO: dict[str, dict] = {s["code"]: s for s in iter_sibling_indicators()}
# Коды, которые являются производным РЯДОМ режима какой-либо generic-семьи
# (например, ipi-yoy = режим «Г/г» семьи ipi, gdp-yoy = режим ВВП). Такой код —
# не самостоятельная карточка, даже если засветился в variant-группе как pill.
DERIVED_MODE_CODES: set[str] = set(SIBLING_INFO)


def modes_for(code: str) -> tuple[str, list[tuple[str, str, str, str, str]]]:
    """(механизм, [(mode, label, series_code, unit, freq)])."""
    fam = FAMILY_BY_BASE.get(code)
    if fam:
        rows = []
        for m in fam.modes:
            rows.append((m.mode, f"{m.group}/{m.label}", m.code, m.unit, m.frequency))
        return f"generic({fam.template})", rows
    if code in CPI_BESPOKE:
        return "bespoke-cpi", _cpi_modes(code)
    if code in PPI_BESPOKE:
        return "bespoke-ppi", _ppi_modes(code)
    if code in HOUSING_BESPOKE:
        return "bespoke-housing", _housing_modes(code)
    if code in CBR_TERM_SLICE_BESPOKE:
        return "bespoke-cbr-term-slice", _cbr_term_slice_modes(code)
    return "НЕТ (только уровень)", []


def is_card(ind: dict) -> bool:
    """Карточка = страница, на которую попадает пользователь: листингуемая ИЛИ
    скрытый срез variant-группы (доступен через переключатель/поиск)."""
    if not ind.get("is_active", False):
        return False
    code = ind["code"]
    listed = ind.get("is_listed", True) is not False and code not in INDICATOR_HIDDEN_FROM_LISTING
    if listed:
        return True
    if code in DERIVED_MODE_CODES:
        return False  # derived-ряд режима семьи (ipi-yoy и т.п.), не карточка
    return code in VARIANT_GROUP_BY_CODE or code in CBR_TERM_SLICE_BESPOKE


def main() -> int:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for ind in INDICATORS:
        if is_card(ind):
            by_cat[ind.get("category", "?")].append(ind)

    lines: list[str] = []
    lines.append("# Полный аудит индикаторов (temp)")
    lines.append("# Уровни: КАРТОЧКА (каталог) → СРЕЗ (variant) → РЕЖИМ → ряд данных")
    lines.append("# Для каждой карточки: режимы с конкретным кодом ряда, ед., частотой, прогнозом.")
    lines.append("# В конце — ПОЛНЫЙ РЕЕСТР всех активных кодов по ролям (ничего не скрыто).")

    total_cards = 0
    gaps_modes: list[str] = []
    gaps_seo: list[str] = []
    thin_seo: list[str] = []

    for cat in sorted(by_cat):
        inds = sorted(by_cat[cat], key=lambda i: i["code"])
        lines.append(f"\n{'='*78}\nКАТЕГОРИЯ: {cat}  ({len(inds)} карточек)\n{'='*78}")
        for ind in inds:
            total_cards += 1
            code = ind["code"]
            cfg = ind.get("model_config_json") or {}
            steps = int(cfg.get("forecast_steps", 0) or 0)
            strat = cfg.get("forecast_strategy") or "—"
            mech, rows = modes_for(code)
            nblocks = len(INDICATOR_SEO_BLOCKS.get(code, []))
            hidden = (ind.get("is_listed", True) is False) or code in INDICATOR_HIDDEN_FROM_LISTING
            if mech.startswith("НЕТ"):
                gaps_modes.append(f"{cat} :: {code}")
            if nblocks == 0:
                gaps_seo.append(f"{cat} :: {code}")
            elif nblocks < 8:
                thin_seo.append(f"{cat} :: {code} ({nblocks})")

            tag = " [СРЕЗ, скрыт из каталога]" if hidden else ""
            lines.append(f"\n  • {code}  «{ind.get('name','')}»{tag}")
            lines.append(f"      частота={ind.get('frequency')}  ед.={ind.get('unit')}  источник={ind.get('source','')}")

            grp = VARIANT_GROUP_BY_CODE.get(code)
            if grp:
                label, members = grp
                srez = ", ".join(f"{c} ({lbl})" for c, lbl in members)
                lines.append(f"      variant-группа: «{label}» → срезы: {srez}")

            lines.append(f"      механизм режимов: {mech}  (всего режимов: {len(rows)})")
            if rows:
                for mode, label, series, unit, freq in rows:
                    fc = "да" if series in SIBLING_INFO and SIBLING_INFO[series].get("forecastable") else (
                        "да" if (mode in ("level", "inflation") and steps > 0) else "нет")
                    same = " (базовый ряд)" if series == code else ""
                    lines.append(
                        f"        - mode={mode:<16} «{label}»  → ряд={series}{same}  ед.={unit}  частота={freq}  прогноз={fc}"
                    )
            else:
                lines.append("        - только уровень (нативный ряд), режимов нет")
            lines.append(f"      прогноз карточки: steps={steps} strategy={strat}")
            lines.append(f"      seo_blocks={nblocks}")

    # --- Полный реестр всех активных кодов по ролям --------------------------
    active = [i for i in INDICATORS if i.get("is_active", False)]
    role_generic, role_bespoke, role_card_other, role_series = [], [], [], []
    bespoke_bases = CPI_BESPOKE | PPI_BESPOKE | HOUSING_BESPOKE | CBR_TERM_SLICE_BESPOKE
    card_codes = {i["code"] for lst in by_cat.values() for i in lst}
    for ind in sorted(active, key=lambda i: (i.get("category", "?"), i["code"])):
        code = ind["code"]
        if code in FAMILY_BY_BASE:
            role_generic.append(code)
        elif code in bespoke_bases:
            role_bespoke.append(code)
        elif code in SIBLING_INFO:
            s = SIBLING_INFO[code]
            role_series.append(f"{code}  ← режим карточки {s['parent']}  [{s['frequency']}, {s['unit']}]")
        elif code in card_codes:
            role_card_other.append(code)
        else:
            # bespoke-ряды режима (cpi-yoy, housing-yoy-*, ppi-yoy, wages-real, …)
            role_series.append(f"{code}  ← bespoke-ряд режима  [{ind.get('frequency')}, {ind.get('unit')}]")

    lines.append(f"\n\n{'#'*78}\nПОЛНЫЙ РЕЕСТР АКТИВНЫХ КОДОВ ({len(active)})\n{'#'*78}")
    lines.append(f"\nGeneric-базы карточек ({len(role_generic)}):")
    lines += [f"   - {c}" for c in sorted(role_generic)]
    lines.append(f"\nBespoke-базы карточек (ИПЦ/ИЦП/жильё/срезы ставок) ({len(role_bespoke)}):")
    lines += [f"   - {c}" for c in sorted(role_bespoke)]
    if role_card_other:
        lines.append(f"\nПрочие карточки ({len(role_card_other)}):")
        lines += [f"   - {c}" for c in sorted(role_card_other)]
    lines.append(f"\nПроизводные ряды режимов (data-серии за режимами) ({len(role_series)}):")
    lines += [f"   - {r}" for r in sorted(role_series)]

    inactive = [i for i in INDICATORS if not i.get("is_active", False)]
    lines.append(f"\nНеактивные коды (в БД есть, пользователю НЕ отдаются) ({len(inactive)}):")
    lines += [f"   - {i['code']}  «{i.get('name','')}»  [{i.get('category','?')}]" for i in inactive] or ["   (нет)"]

    lines.append(f"\n\n{'#'*78}\nСВОДКА\n{'#'*78}")
    lines.append(f"Всего карточек (каталог + срезы): {total_cards}")
    lines.append(f"Всего активных кодов в БД: {len(active)}")
    lines.append(f"Неактивных кодов (депрекейт): {len(inactive)}")
    lines.append(f"Всего кодов в seed/БД: {len(INDICATORS)}")
    lines.append(f"\nДЫРА ПО РЕЖИМАМ (нет режимов, только уровень) — {len(gaps_modes)}:")
    lines += [f"   - {g}" for g in gaps_modes]
    lines.append(f"\nДЫРА ПО SEO (0 блоков) — {len(gaps_seo)}:")
    lines += [f"   - {g}" for g in gaps_seo]
    lines.append(f"\nТОНКИЙ SEO (1–7 блоков, дом.стандарт=8) — {len(thin_seo)}:")
    lines += [f"   - {g}" for g in thin_seo]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}  (cards={total_cards}, active={len(active)}, "
          f"mode-gaps={len(gaps_modes)}, seo-zero={len(gaps_seo)}, seo-thin={len(thin_seo)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
