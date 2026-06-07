"""Временный аудит: ВСЕ группы переключателя × их уникальные подрежимы.

Печатает:
  1. Реестр групп (id → label) и какие токены-подрежимы встречаются в каждой.
  2. Канонический набор подрежимов на группу для каждой нативной частоты
     (то, что generic-движок строит по шаблону = «как должно быть заполнено»).
  3. Матрица «карточка × группа × подрежимы» (generic + bespoke).
  4. Дырки: группы, где не хватает гранулярностей (по месяцам/кварталам/годам)
     или приростов (М/м, Кв/Кв, Г/г), которые осмысленны для частоты, но ряда нет.

Read-only. Никаких записей в БД.
"""
from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")

from app.data.view_model_families import (  # noqa: E402
    FAMILIES, GRAN_ORDER, GRAN_LABEL, NATIVE_GRAN,
)
from seed_data import INDICATORS  # noqa: E402

ACTIVE = {i["code"] for i in INDICATORS if i.get("is_active")}
NAME = {i["code"]: i["name"] for i in INDICATORS}

GROUP_LABELS = {
    "level": "На конец периода / Уровень",
    "avg": "Средняя за период",
    "flow": "За период (сумма потока)",
    "pop": "К прошлому периоду (М/м · Кв/Кв)",
    "yoy": "К соотв. периоду пред. года (Г/г)",
    "index": "Индекс",
    # bespoke (ИПЦ/ИЦП/жильё) group ids
    "inflation": "Инфляция за год (bespoke)",
    "step": "К прошлому периоду / шаг (bespoke)",
}


def line(ch="-", n=78):
    return ch * n


out: list[str] = []
w = out.append

w(line("="))
w("АУДИТ ГРУПП И ПОДРЕЖИМОВ — все переключатели карточек индикаторов")
w("Цель: где внутри группы не хватает гранулярностей/приростов (ряд не посчитан)")
w(line("="))

# ---------------------------------------------------------------------------
# 1. Реестр групп → встречающиеся подрежимы (по generic-движку)
# ---------------------------------------------------------------------------
group_tokens: dict[str, set[str]] = defaultdict(set)
for fam in FAMILIES:
    for m in fam.modes:
        group_tokens[m.group].add(m.mode)

w("\n1) РЕЕСТР ГРУПП (generic-движок) → уникальные токены-подрежимы")
w(line())
for gid, toks in group_tokens.items():
    w(f"  [{gid}] {GROUP_LABELS.get(gid, gid)}")
    w(f"      подрежимы: {', '.join(sorted(toks))}")

# ---------------------------------------------------------------------------
# 2. Канонический набор на группу по нативной частоте
# ---------------------------------------------------------------------------
def coarser(native_gran: str) -> list[str]:
    i = GRAN_ORDER.index(native_gran)
    return list(GRAN_ORDER[i + 1:])

w("\n2) КАНОНИЧЕСКИЙ НАБОР ПОДРЕЖИМОВ НА ГРУППУ (как «должно быть заполнено»)")
w(line())
for freq in ("daily", "weekly", "monthly", "quarterly", "annual"):
    ng = NATIVE_GRAN[freq]
    cg = coarser(ng)
    w(f"  Нативная частота: {freq} (нативная гранулярность = {ng})")
    w(f"    level/eop : level(={GRAN_LABEL[ng]}) + " + ", ".join(f"eop-{g}" for g in cg))
    w(f"    avg       : " + (", ".join(f"avg-{g}" for g in cg) or "(нет — нативная и так уровень)"))
    w(f"    flow/sum  : level(={GRAN_LABEL[ng]}) + " + ", ".join(f"sum-{g}" for g in cg))
    pop = (["mom"] if ng == "month" else []) + (["qoq"] if ng in ("day", "week", "month", "quarter") and ng != "quarter" else [])
    if ng in ("day", "week", "month"):
        pop = (["mom"] if ng == "month" else []) + ["qoq"]
    elif ng == "quarter":
        pop = ["qoq"]
    else:
        pop = []
    w(f"    pop       : " + (", ".join(pop) or "(нет)"))
    w(f"    yoy       : yoy")
    w(f"    index     : index (+ index-quarter/-year где осмысленно для price/index)")
    w("")

# ---------------------------------------------------------------------------
# 3. Матрица generic-карточек
# ---------------------------------------------------------------------------
w("\n3) GENERIC-КАРТОЧКИ — группы × подрежимы (token → series | freq | unit | fcast)")
w(line())
for fam in sorted(FAMILIES, key=lambda f: (f.template, f.base)):
    w(f"\n  {fam.base}  «{fam.name}»  [{fam.template}]")
    by_group: dict[str, list] = defaultdict(list)
    for m in fam.modes:
        by_group[m.group].append(m)
    for g in fam.groups:
        rows = by_group.get(g.id, [])
        w(f"    [{g.id}] {g.label}:")
        for m in rows:
            miss = "" if (m.is_native or m.code in ACTIVE) else "  <<< РЯД ОТСУТСТВУЕТ В seed/active"
            w(f"        {m.mode:<12} {m.label:<14} {m.code:<34} {m.frequency:<9} {m.unit:<10} fcast={int(m.forecastable)}{miss}")

# ---------------------------------------------------------------------------
# 4. Bespoke-карточки (ИПЦ/ИЦП/жильё/срезы ставок) — вручную
# ---------------------------------------------------------------------------
w("\n\n4) BESPOKE-КАРТОЧКИ (вне generic-движка) — фактические группы и подрежимы")
w(line())

bespoke = {
    "cpi (+food/nonfood/services)": {
        "inflation": ["yoy (помесячный г/г)"],
        "step": ["period-weekly (нед.)", "period-monthly (мес.)", "qoq (кв/кв)"],
        "index": ["index (мес.)", "index-quarterly (кв.)", "index-annual (год)"],
    },
    "ppi «Индекс цен производителей»": {
        "inflation": ["yoy (ppi-yoy)"],
        "step": ["mom (client-side)  <<< нет qoq (Кв/Кв)"],
        "index": ["index (мес., base)", "index-quarterly (client bucket)", "index-annual (client bucket)"],
    },
    "housing-price-primary/secondary": {
        "step": ["yoy (housing-yoy-*)", "qoq (housing-qoq-*)"],
        "index": ["index (кв., base)  <<< нет index-annual (по годам)"],
    },
    "срезы ставок: corp-1to3y/over3y, ind-1to3y/over3y, deposit-medium/long": {
        "level": ["level ТОЛЬКО  <<< нет eop-quarter/eop-year, всей avg, pop(mom/qoq), yoy — у sibling *-short полный T2y"],
    },
}
for card, groups in bespoke.items():
    w(f"\n  {card}")
    for gid, items in groups.items():
        w(f"    [{gid}] {GROUP_LABELS.get(gid, gid)}:")
        for it in items:
            w(f"        - {it}")

# ---------------------------------------------------------------------------
# 5. Дырки и решение
# ---------------------------------------------------------------------------
w("\n\n5) ДЫРКИ (где не хватает подрежимов внутри группы) И РЕШЕНИЕ")
w(line("="))
w("""
  A. 6 срезов ставок (credit-rate-corp-1to3y, credit-rate-corp-over3y,
     credit-rate-ind-1to3y, credit-rate-ind-over3y, deposit-rate-medium,
     deposit-rate-long): сейчас ТОЛЬКО уровень. Sibling *-short/deposit-rate —
     полный T2y (eop-quarter/eop-year, avg-quarter/avg-year, mom, qoq, yoy).
     -> ДОБАВИТЬ их в _FAMILY_DEFS как T2y (generic-движок даст полный набор
        режимов + сгенерит derived-ряды). Срок-variant остаётся.

  B. ppi, группа «К прошлому периоду» (step): есть только М/м (mom), нет Кв/Кв.
     -> ДОБАВИТЬ qoq (client-side transform по квартальным точкам индекса),
        кнопку Кв/Кв в ppiViewModeGroups + текст.

  C. housing primary/secondary, группа «Индекс»: одна кнопка (квартальная база),
     нет годовой гранулярности.
     -> ДОБАВИТЬ index-annual (client-side bucket last-of-year), кнопку
        «По годам» в housingViewModeGroups + bucket-обработку в хуке.

  ВНЕ scope (по решению созвона / не «дозаполнение внутри группы»):
   - budget-deficit (T7): группа «За период» полна (sum-quarter/sum-year);
     приростов нет ПО РЕШЕНИЮ (дефицит = только сумма). Новые группы не добавляем.
   - Индекс уровневым семьям, real/index у зарплаты, индекс для T10a —
     это НОВЫЕ группы/оси, а не дозаполнение существующих.
""")

print("\n".join(out))
