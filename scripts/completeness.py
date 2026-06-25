"""Аудит полноты семейств индикаторов — «паспорт полноты».

Детерминированный (импорт backend-источников истины, без догадок) расчёт для
каждого КОРНЯ-семейства его матрицы представлений {тип × частота} и сравнение с
«максимальным» шаблоном по природе ряда. Плюс 4 измерения паспорта: тексты,
прогноз, группировка, SEO.

Доменная модель (см. CONTEXT.md::Матрица представлений):

  Полнота индикатора — это МАТРИЦА из двух осей, эталон — двухуровневый
  переключатель ИПЦ (`frontend/src/lib/cpiViewModeGroups.js`):

    верхняя ось (ТИП представления) ─ что показываем:
      value  — уровень / средняя / на конец / за период (величина ряда)
      pop    — к прошлому периоду (Н/н · М/м · Кв/Кв · Г/г-календарный)
      yoy    — к соотв. периоду пред. года (rolling / same-period)
      index  — индекс (rebase к базе)
    нижняя ось (ЧАСТОТА) ─ за какой промежуток: week · month · quarter · year

  Каждая «ячейка» (тип × частота) либо есть у индикатора (режим/sibling), либо
  пуста. Пустые ячейки относительно ожидаемого по ПРИРОДЕ ряда — это пробелы.

Источник «present»: generic-движок (`view_model_families.FAMILIES`, авторитетно)
+ bespoke-реестры (cpi/ppi/housing). Источник «expected»: функция
`expected_matrix(nature, native)` ниже — единая точка истины «что положено
типу». Меняешь ожидания — правишь её, а не разбрасываешь по коду.

ВАЖНО: это АУДИТ-карта (read-only), а не правка данных. Пробел = кандидат на
добавление, а не дефект: владелец решает, осмыслен ли режим для конкретной
природы (для ставки индекс не нужен, для годового счётного ряда нет М/м).
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONT_LIB = ROOT / "frontend" / "src" / "lib"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# --- Каноническая модель осей -------------------------------------------------

TOP_VALUE, TOP_POP, TOP_YOY, TOP_INDEX = "value", "pop", "yoy", "index"
TOP_ORDER = [TOP_VALUE, TOP_POP, TOP_YOY, TOP_INDEX]
TOP_LABEL = {
    TOP_VALUE: "Уровень/значение",
    TOP_POP: "К прошлому периоду",
    TOP_YOY: "К соотв. периоду пред. года",
    TOP_INDEX: "Индекс",
}

FREQ_ORDER = ["day", "week", "month", "quarter", "year"]
FREQ_LABEL = {"day": "дн", "week": "нед", "month": "мес", "quarter": "кв", "year": "год"}

# group-id билдера → каноническая верхняя ось
_GROUP_TO_TOP = {
    "level": TOP_VALUE, "avg": TOP_VALUE, "flow": TOP_VALUE, "eop": TOP_VALUE,
    "pop": TOP_POP, "yoy": TOP_YOY, "index": TOP_INDEX,
}
# Mode.frequency / seed.frequency → частотный tier
_FREQ_OF = {
    "daily": "day", "weekly": "week", "monthly": "month",
    "quarterly": "quarter", "annual": "year",
}

# template билдера → природа ряда (если unit=="индекс" → index, перекрывает)
_NATURE_BY_TEMPLATE = {
    "T1": "rate", "T2": "rate", "T2y": "rate",
    "T3": "stock", "T4": "stock", "T5": "stock",
    "T6": "flow", "T7": "signed-flow", "T8": "avg-level",
    "T9": "gdp", "T9s": "signed-flow",
    "T10": "annual-count", "T10a": "annual-signed", "T12": "ratio-index",
}


def _cells(*pairs: tuple[str, str]) -> set[tuple[str, str]]:
    return set(pairs)


def _coarser_or_equal(native: str) -> list[str]:
    return FREQ_ORDER[FREQ_ORDER.index(native):]


def expected_matrix(nature: str, native: str) -> set[tuple[str, str]]:
    """«Максимальный» ожидаемый набор ячеек (тип × частота) по природе ряда.

    Единая точка истины ожиданий. Правила (созвучны эталону ИПЦ и билдерам):
    - VALUE — на всех частотах от нативной до года;
    - POP — на month/quarter (+ year только для индексных рядов, как у ИПЦ);
    - YOY — на month/quarter/year (нативный sub-annual ряд имеет годовой темп);
    - INDEX — на всех частотах, только для индексной природы.
    Для годовых/квартальных природ — усечено (нет sub-year POP и т.п.).
    """
    tiers = _coarser_or_equal(native)
    sub = [t for t in tiers if t in ("month", "quarter", "year")]
    out: set[tuple[str, str]] = set()

    if nature in ("rate", "stock", "flow", "avg-level", "ratio-index"):
        out |= {(TOP_VALUE, t) for t in tiers}
        out |= {(TOP_POP, t) for t in tiers if t in ("month", "quarter")}
        out |= {(TOP_YOY, t) for t in sub}
    elif nature == "index":
        # «Уровень» индексного ряда = сам индекс → величину закрывает группа
        # INDEX (на всех частотах); отдельный VALUE ждём только на нативной (ряд
        # по умолчанию). Это убирает ложный двойной учёт value vs index.
        out |= {(TOP_VALUE, native)}
        out |= {(TOP_POP, t) for t in tiers if t in ("month", "quarter", "year")}
        out |= {(TOP_YOY, t) for t in sub}
        out |= {(TOP_INDEX, t) for t in sub}
    elif nature == "signed-flow":
        out |= {(TOP_VALUE, t) for t in tiers}
        out |= {(TOP_POP, t) for t in tiers if t == "quarter"}
        out |= {(TOP_YOY, t) for t in sub}
    elif nature == "gdp":
        out |= {(TOP_VALUE, "quarter"), (TOP_VALUE, "year")}
        out |= {(TOP_POP, "quarter")}
        out |= {(TOP_YOY, "quarter"), (TOP_YOY, "year")}
    elif nature == "annual-count":
        out |= {(TOP_VALUE, "year"), (TOP_YOY, "year"), (TOP_INDEX, "year")}
    elif nature == "annual-signed":
        out |= {(TOP_VALUE, "year"), (TOP_YOY, "year")}
    return out


# --- Парсинг bespoke-режимов (cpi/ppi/housing) — детерминированно -------------

def _parse_bespoke_modes() -> dict[str, list[str]]:
    """URL-режимы bespoke-карточек из их resolve-файлов / групп ИПЦ."""
    out: dict[str, list[str]] = {}
    # ИПЦ — из CPI_VIEW_MODES_FLAT (cpiViewModeGroups.js)
    cpi_txt = (FRONT_LIB / "cpiViewModeGroups.js").read_text(encoding="utf-8")
    block = re.search(r"CPI_VIEW_MODES_FLAT\s*=\s*\[(.*?)\];", cpi_txt, re.DOTALL)
    out["cpi"] = re.findall(r"mode:\s*'([a-z0-9-]+)'", block.group(1)) if block else []
    # ИЦП / жильё — массивы *_URL_MODES
    for key, fname, var in (
        ("ppi", "ppiViewModeResolve.js", "PPI_URL_MODES"),
        ("housing", "housingViewModeResolve.js", "HOUSING_URL_MODES"),
    ):
        txt = (FRONT_LIB / fname).read_text(encoding="utf-8")
        m = re.search(rf"{var}\s*=\s*\[(.*?)\]", txt, re.DOTALL)
        out[key] = re.findall(r"'([a-z0-9-]+)'", m.group(1)) if m else []
    return out


def _bespoke_cells(reg: str, modes: list[str], native: str) -> set[tuple[str, str]]:
    """URL-режим bespoke → каноническая ячейка (тип × частота).

    Семантика режима `yoy` различается по реестру: у ИПЦ это календарный шаг
    Дек/Дек (= pop:year), а rolling-YoY вынесен в отдельную группу `inflation`;
    у ИЦП/жилья `yoy` — это сам rolling-YoY, а календарный год — `annual`.
    """
    out: set[tuple[str, str]] = {(TOP_VALUE, native)}  # нативный уровень-ряд
    for mo in modes:
        if mo == "inflation":  # ИПЦ: верхняя группа = rolling YoY (12 мес.)
            out.add((TOP_YOY, native))
        elif mo == "yoy":
            if reg == "cpi":  # лист «Г/г» в «К прошлому периоду» = Дек/Дек
                out.add((TOP_POP, "year"))
            else:  # ИЦП/жильё: rolling YoY на нативной частоте
                out.add((TOP_YOY, native))
        elif mo == "yoy-annual":  # жильё: годовой YoY
            out.add((TOP_YOY, "year"))
        elif mo == "annual":  # ИЦП: календарный Г/г = pop:year
            out.add((TOP_POP, "year"))
        elif mo == "step-weekly":
            out.add((TOP_POP, "week"))
        elif mo in ("step-monthly", "mom"):
            out.add((TOP_POP, "month"))
        elif mo == "qoq":
            out.add((TOP_POP, "quarter"))
        elif mo == "index":
            out.add((TOP_INDEX, native))
        elif mo == "index-quarterly":
            out.add((TOP_INDEX, "quarter"))
        elif mo == "index-annual":
            out.add((TOP_INDEX, "year"))
    return out


# --- Основной расчёт ----------------------------------------------------------

def build_completeness() -> dict:
    import seed_data
    from app.data.view_model_families import FAMILIES, FAMILY_BY_BASE
    from app.services.calculation_engine import DERIVED_SPECS
    from app.data import indicator_seo as iseo

    inds = {i["code"]: i for i in seed_data.INDICATORS}
    hidden = set(seed_data.INDICATOR_HIDDEN_FROM_LISTING)
    monthly_auto = set(seed_data.MONTHLY_AUTO_FORECAST_CODES)
    seo = iseo.INDICATOR_SEO

    # variant-группы (frontend) для измерения «группировка»
    iv = (FRONT_LIB / "indicatorVariants.js").read_text(encoding="utf-8")
    variant_of: dict[str, str] = {}
    for gm in re.finditer(
        r"\{\s*label:\s*'([^']+)',\s*codes:\s*\[(.*?)\]\s*,?\s*\}", iv, re.DOTALL
    ):
        for cm in re.finditer(r"code:\s*'([a-z0-9-]+)'", gm.group(2)):
            variant_of[cm.group(1)] = gm.group(1)

    bespoke_modes = _parse_bespoke_modes()
    bespoke_roots = {
        "cpi": ("cpi", "index"), "cpi-food": ("cpi", "index"),
        "cpi-nonfood": ("cpi", "index"), "cpi-services": ("cpi", "index"),
        "ppi": ("ppi", "index"),
        "housing-price-primary": ("housing", "index"),
        "housing-price-secondary": ("housing", "index"),
    }

    # production children: всё, что генерится семьями / является derived dst
    gen_children: dict[str, str] = {}  # child → base
    for fam in FAMILIES:
        for m in fam.modes:
            if m.code != fam.base:
                gen_children[m.code] = fam.base
    derived_dst = {s.dst_code for s in DERIVED_SPECS}

    def dims(code: str, *, system: str, native: str, forecastable: bool) -> dict:
        ind = inds.get(code, {})
        has_desc = bool((ind.get("description") or "").strip())
        has_meth = bool((ind.get("methodology") or "").strip())
        texts = "full" if (has_desc and has_meth) else (
            "partial" if (has_desc or has_meth) else "missing")
        fc = forecastable or code in monthly_auto or bool(
            (ind.get("model_config_json") or {}).get("forecast_strategy"))
        if system == "bespoke":
            grouping = "bespoke"
        elif code in variant_of:
            grouping = f"variant: {variant_of[code]}"
        elif system == "generic":
            grouping = "family"
        else:
            grouping = "standalone"
        s = seo.get(code, {})
        seo_lvl = "curated" if (s.get("seo_title") and s.get("seo_description")) else (
            "partial" if (s.get("seo_title") or s.get("seo_description")) else "generic")
        return {
            "texts": texts, "forecast": "yes" if fc else "no",
            "grouping": grouping, "seo": seo_lvl,
            "is_listed": code not in hidden,
        }

    roots: dict[str, dict] = {}

    # 1) generic-семьи (present = что выдаёт билдер; authoritative)
    for fam in FAMILIES:
        ind = inds.get(fam.base, {})
        base_nature = _NATURE_BY_TEMPLATE[fam.template]
        # unit «индекс» → индексная природа (ipi-подобные), КРОМЕ ratio-index
        # (T12): отношение двух индексов — это уровень-ряд, а не rebase-карточка.
        nature = ("index" if ind.get("unit") == "индекс"
                  and base_nature != "ratio-index" else base_nature)
        native = _FREQ_OF.get(ind.get("frequency") or "monthly", "month")
        present = {
            (_GROUP_TO_TOP[m.group], _FREQ_OF.get(m.frequency, native))
            for m in fam.modes
        }
        forecastable = any(getattr(m, "forecastable", False) for m in fam.modes)
        roots[fam.base] = _passport(
            fam.base, "generic", fam.template, nature, native, present,
            dims(fam.base, system="generic", native=native, forecastable=forecastable),
        )

    # 2) bespoke-карточки (cpi/ppi/housing)
    for code, (reg, nature) in bespoke_roots.items():
        ind = inds.get(code, {})
        native = _FREQ_OF.get(ind.get("frequency") or "monthly", "month")
        present = _bespoke_cells(reg, bespoke_modes.get(reg, []), native)
        roots[code] = _passport(
            code, "bespoke", reg.upper(), nature, native, present,
            dims(code, system="bespoke", native=native, forecastable=True),
        )

    # 3) орфаны: source-ряды (parser_type) вне generic/bespoke/gen-child/derived
    for code, ind in inds.items():
        if code in roots or code in gen_children or code in derived_dst:
            continue
        if not ind.get("parser_type"):
            continue
        if code.startswith("inflation-weekly"):
            # недельный ИПЦ — данные за недельным режимом bespoke-карточки cpi
            roots[code] = _passport(
                code, "bespoke-data", "CPI-weekly", "index", "week",
                {(TOP_POP, "week")},
                dims(code, system="bespoke", native="week", forecastable=False),
                note="недельный ряд ИПЦ — backs режим «Н/н» карточки ИПЦ",
            )
            continue
        native = _FREQ_OF.get(ind.get("frequency") or "monthly", "month")
        unit = ind.get("unit") or ""
        nature = ("index" if unit == "индекс"
                  else "rate" if unit == "%"
                  else "annual-count" if native == "year"
                  else "avg-level")
        roots[code] = _passport(
            code, "orphan", None, nature, native, {(TOP_VALUE, native)},
            dims(code, system="orphan", native=native, forecastable=False),
            note="source-ряд без обёртки представлений (только нативный уровень)",
        )

    return _assemble(roots)


def _passport(code, system, template, nature, native, present, dims, note=None):
    present = set(present)
    if nature == "index":
        # У индексного ряда «уровень» = сам индекс: VALUE-ячейка на частоте f
        # эквивалентна INDEX-ячейке (ipi обёрнут value-билдером T3, но величина —
        # это индекс). Зачитываем, чтобы не штрафовать за способ обёртки.
        present |= {(TOP_INDEX, f) for (t, f) in present if t == TOP_VALUE}
    expected = expected_matrix(nature, native)
    missing = expected - present
    extra = present - expected  # есть, но шаблон не ждал (информативно)
    score = round(len(present & expected) / len(expected), 3) if expected else 1.0
    return {
        "code": code, "coverage_system": system, "template": template,
        "nature": nature, "native_freq": native,
        "present": _fmt_cells(present), "expected": _fmt_cells(expected),
        "missing": _fmt_cells(missing), "extra": _fmt_cells(extra),
        "matrix_score": score, "dims": dims,
        **({"note": note} if note else {}),
    }


def _fmt_cells(cells: set[tuple[str, str]]) -> list[str]:
    def key(c):
        return (TOP_ORDER.index(c[0]), FREQ_ORDER.index(c[1]))
    return [f"{t}:{f}" for t, f in sorted(cells, key=key)]


def _assemble(roots: dict) -> dict:
    by_type: dict[str, dict] = {}
    for r in roots.values():
        key = f"{r['coverage_system']}/{r['template'] or '-'}/{r['nature']}/{r['native_freq']}"
        slot = by_type.setdefault(key, {
            "coverage_system": r["coverage_system"], "template": r["template"],
            "nature": r["nature"], "native_freq": r["native_freq"],
            "members": [], "shared_missing": None,
        })
        slot["members"].append(r["code"])
        miss = set(r["missing"])
        slot["shared_missing"] = miss if slot["shared_missing"] is None else (slot["shared_missing"] & miss)
    for slot in by_type.values():
        slot["shared_missing"] = sorted(slot["shared_missing"] or [])
        slot["count"] = len(slot["members"])
        slot["members"].sort()

    incomplete = sorted(
        (r for r in roots.values() if r["missing"]),
        key=lambda r: (-len(r["missing"]), r["code"]),
    )
    summary = {
        "roots_total": len(roots),
        "roots_complete_matrix": sum(1 for r in roots.values() if not r["missing"]),
        "roots_with_gaps": len(incomplete),
        "by_coverage": _count(roots, "coverage_system"),
        "texts_missing": sorted(
            r["code"] for r in roots.values() if r["dims"]["texts"] != "full"),
        "no_forecast": sorted(
            r["code"] for r in roots.values() if r["dims"]["forecast"] == "no"),
        "seo_not_curated": sorted(
            r["code"] for r in roots.values() if r["dims"]["seo"] != "curated"),
    }
    return {
        "summary": summary,
        "by_type": dict(sorted(by_type.items())),
        "roots": dict(sorted(roots.items())),
    }


def _count(roots: dict, field: str) -> dict:
    out: dict[str, int] = defaultdict(int)
    for r in roots.values():
        out[r[field]] += 1
    return dict(sorted(out.items()))


# --- Человекочитаемый срез ----------------------------------------------------

def render_md(data: dict) -> str:
    s = data["summary"]
    out: list[str] = []
    out.append("# Аудит полноты семейств — паспорт полноты")
    out.append("")
    out.append(
        "> Генерируется `scripts/build-indicator-index.py` (модуль "
        "`scripts/completeness.py`). НЕ редактировать руками. Read-only аудит: "
        "пробел = КАНДИДАТ на добавление режима, не дефект — владелец решает, "
        "осмыслен ли он для природы ряда. Ожидания — таблица `MAXIMAL_BY_NATURE` "
        "в `completeness.py` (единая точка истины). Доменная модель — "
        "`CONTEXT.md::Матрица представлений`.")
    out.append("")
    out.append("## Оси матрицы")
    out.append("")
    out.append("- **Тип** (верх, эталон — переключатель ИПЦ): " + " · ".join(
        f"`{t}` {TOP_LABEL[t]}" for t in TOP_ORDER))
    out.append("- **Частота** (низ): " + " · ".join(
        f"`{f}` {FREQ_LABEL[f]}" for f in FREQ_ORDER))
    out.append("")
    out.append(
        f"Корней-семейств: **{s['roots_total']}** · с полной матрицей: "
        f"**{s['roots_complete_matrix']}** · с пробелами: **{s['roots_with_gaps']}**. "
        f"Покрытие: {s['by_coverage']}.")
    out.append("")
    out.append("## Систематические пробелы по типам")
    out.append("")
    out.append("Семьи одного типа делят матрицу. `shared_missing` — ячейки, "
               "которых нет НИ У ОДНОГО члена типа (системный пробел типа).")
    out.append("")
    out.append("| тип | природа | нативная | членов | общий пробел (shared_missing) |")
    out.append("|---|---|---|---|---|")
    for slot in data["by_type"].values():
        miss = ", ".join(f"`{c}`" for c in slot["shared_missing"]) or "—"
        out.append(
            f"| {slot['coverage_system']}/{slot['template'] or '-'} | "
            f"{slot['nature']} | {slot['native_freq']} | {slot['count']} | {miss} |")
    out.append("")
    out.append("## Корни с пробелами матрицы")
    out.append("")
    out.append("| код | покрытие | природа | нативная | score | missing | тексты | прогноз | seo |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    incomplete = sorted(
        (r for r in data["roots"].values() if r["missing"]),
        key=lambda r: (-len(r["missing"]), r["code"]))
    for r in incomplete:
        miss = ", ".join(f"`{c}`" for c in r["missing"])
        out.append(
            f"| `{r['code']}` | {r['coverage_system']}/{r['template'] or '-'} | "
            f"{r['nature']} | {r['native_freq']} | {r['matrix_score']} | {miss} | "
            f"{r['dims']['texts']} | {r['dims']['forecast']} | {r['dims']['seo']} |")
    out.append("")
    out.append("## Измерения паспорта (агрегат)")
    out.append("")
    out.append(f"- **Без полных текстов** ({len(s['texts_missing'])}): "
               + (", ".join(f"`{c}`" for c in s["texts_missing"]) or "—"))
    out.append(f"- **Без прогноза** ({len(s['no_forecast'])}): "
               + (", ".join(f"`{c}`" for c in s["no_forecast"]) or "—"))
    out.append(f"- **SEO не curated** ({len(s['seo_not_curated'])}): "
               + (", ".join(f"`{c}`" for c in s["seo_not_curated"]) or "—"))
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    import json
    d = build_completeness()
    print(json.dumps(d["summary"], ensure_ascii=False, indent=2))
