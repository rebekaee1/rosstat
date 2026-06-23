"""Canonical view-mode family config — единый источник истины.

Из этого модуля детерминированно выводятся:

- backend derived-ряды (`calculation_engine.DERIVED_SPECS`) и seed-строки
  sibling-индикаторов (`seed_data`) — через `iter_derived_specs()` и
  `iter_sibling_indicators()`;
- frontend generic view-mode движок — через JSON-зеркало, которое печатает
  `scripts/export-view-models.py` в
  `frontend/src/lib/viewModelFamilies.generated.json`.

Один источник → backend-коды режимов и UI-режимы физически не рассинхронятся
(см. план «Indicator view-mode unification», ADR-0001 и ADR-0006).

Модель:

- **Family** = одна карточка каталога (видимый пользователю индикатор `base`).
- **Mode** = один выбираемый ряд внутри карточки. Каждый режим, кроме
  «нативного уровня», подкреплён backend-derived sibling-рядом с верной
  `frequency`. Нативный уровень рендерит сам source-ряд.
- **Pipeline** = список чистых шагов `(op_name, kwargs)` из `derived_ops`.
  Композиция (а не один op) позволяет единообразно выразить и «кв/кв на
  суммах потока», и «г/г на месячных уровнях недельного ряда».

Решения созвона (2026-06-06), зашитые в шаблоны ниже:

1. Дефицит бюджета (T7) — «За период» = сумма + приросты в АБСОЛЮТЕ
   (млрд руб.): «К прошлому периоду» и «Г/г» в рублях, т.к. поток со знаком
   делает %-прирост бессмысленным (уточнение к решению созвона).
2. Зарплата (T8) — 4-групповый шаблон как у запасов; real/index НЕ режимы
   карточки (остаются отдельными derived-рядами / API).
3. Годовой режим у НЕ-ценовых = «К соотв. периоду пред. года» (для ИПЦ/ИЦП
   остаётся «Инфляция за год» — те семьи живут отдельно, T11).
4. Без дубль-линий: на нативной частоте «среднее = уровню», поэтому группа
   «Средняя за период» начинается с гранулярности на шаг крупнее нативной.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Гранулярности -----------------------------------------------------------

GRAN_ORDER: tuple[str, ...] = ("day", "week", "month", "quarter", "year")

GRAN_LABEL: dict[str, str] = {
    "day": "По дням",
    "week": "По неделям",
    "month": "По месяцам",
    "quarter": "По кварталам",
    "year": "По годам",
}

# Частота seed-индикатора, соответствующая гранулярности bucket'а.
GRAN_FREQUENCY: dict[str, str] = {
    "day": "daily",
    "week": "weekly",
    "month": "monthly",
    "quarter": "quarterly",
    "year": "annual",
}

# Нативная гранулярность source-ряда по его частоте.
NATIVE_GRAN: dict[str, str] = {
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
    "quarterly": "quarter",
    "annual": "year",
}

Pipeline = tuple[tuple[str, dict], ...]


# --- Структуры ---------------------------------------------------------------


@dataclass
class Mode:
    """Один выбираемый ряд карточки.

    `code` — backend-код, чьи точки рендерятся. Для нативного уровня это сам
    source (`pipeline == ()`); иначе — derived sibling. `pipeline` — цепочка
    чистых шагов из `derived_ops`, применяемых к source-ряду.
    """

    mode: str               # токен ?mode=… (уникален внутри семьи)
    group: str              # id верхней группы переключателя
    label: str              # подпись кнопки нижнего уровня
    code: str               # source или derived-код
    pipeline: Pipeline      # () для нативного уровня
    unit: str               # единица ряда (для % режимов — "%")
    frequency: str          # фактическая частота ряда
    forecastable: bool      # строим ли прогноз для этого режима

    @property
    def is_native(self) -> bool:
        return not self.pipeline


@dataclass
class Group:
    """Верхняя группа двухуровневого переключателя."""

    id: str
    label: str
    leaf: bool = False      # одиночная кнопка (например, «Г/г») без подменю


@dataclass
class Family:
    base: str               # source-код = код карточки в каталоге
    name: str               # публичное имя индикатора (для имён siblings)
    template: str           # T1…T11
    unit: str               # базовая единица source
    category: str           # категория каталога (для seed)
    default_mode: str
    groups: list[Group]
    modes: list[Mode]
    variant_axis: str | None = None  # код variant-группы, если есть


# --- Человеческие суффиксы для имён sibling-индикаторов -----------------------

_SUFFIX_NAME: dict[str, str] = {
    "eop-week": "на конец недели",
    "eop-month": "на конец месяца",
    "eop-quarter": "на конец квартала",
    "eop-year": "на конец года",
    "avg-week": "средняя за неделю",
    "avg-month": "средняя за месяц",
    "avg-quarter": "средняя за квартал",
    "avg-year": "средняя за год",
    "sum-month": "за месяц",
    "sum-quarter": "за квартал",
    "sum-year": "за год",
    "mom": "к предыдущему месяцу",
    "qoq": "к предыдущему кварталу",
    "yoy": "к соответствующему периоду прошлого года",
    "index": "индекс (первый период = 100)",
    "rolling-12m": "скользящая средняя за 12 месяцев",
}


# --- Сборка режимов по шаблонам ----------------------------------------------


def _coarser_than(gran: str) -> list[str]:
    """Гранулярности строго крупнее `gran` (для правила «без дубль-линий»)."""
    i = GRAN_ORDER.index(gran)
    return list(GRAN_ORDER[i + 1:])


def _code(base: str, token: str, overrides: dict[str, str]) -> str:
    return overrides.get(token, f"{base}-{token}")


def _level_modes(
    base: str, freq: str, unit: str, overrides: dict[str, str],
    *, group_id: str, forecastable: bool,
) -> list[Mode]:
    """Группа «На конец периода» (eop): нативная гранулярность = source-уровень,
    далее period_last по крупным гранулярностям."""
    native = NATIVE_GRAN[freq]
    modes = [Mode(
        mode="level", group=group_id, label=GRAN_LABEL[native],
        code=base, pipeline=(), unit=unit, frequency=freq, forecastable=forecastable,
    )]
    for g in _coarser_than(native):
        token = f"eop-{g}"
        modes.append(Mode(
            mode=token, group=group_id, label=GRAN_LABEL[g],
            code=_code(base, token, overrides),
            pipeline=(("period_last", {"granularity": g}),),
            unit=unit, frequency=GRAN_FREQUENCY[g], forecastable=forecastable,
        ))
    return modes


def _avg_modes(
    base: str, freq: str, unit: str, overrides: dict[str, str], *, forecastable: bool = False,
) -> list[Mode]:
    """Группа «Средняя за период»: только гранулярности крупнее нативной
    (на нативной среднее = уровню → дубль-линия, запрещено)."""
    native = NATIVE_GRAN[freq]
    out = []
    for g in _coarser_than(native):
        token = f"avg-{g}"
        out.append(Mode(
            mode=token, group="avg", label=GRAN_LABEL[g],
            code=_code(base, token, overrides),
            pipeline=(("period_avg", {"granularity": g}),),
            unit=unit, frequency=GRAN_FREQUENCY[g], forecastable=forecastable,
        ))
    return out


def _sum_modes(base: str, freq: str, unit: str, overrides: dict[str, str], *, forecastable: bool) -> list[Mode]:
    """Группа «За период» (потоки): нативная гранулярность = source (поток уже
    «за месяц»), далее period_sum по крупным гранулярностям."""
    native = NATIVE_GRAN[freq]
    modes = [Mode(
        mode="level", group="flow", label=GRAN_LABEL[native],
        code=base, pipeline=(), unit=unit, frequency=freq, forecastable=forecastable,
    )]
    for g in _coarser_than(native):
        token = f"sum-{g}"
        modes.append(Mode(
            mode=token, group="flow", label=GRAN_LABEL[g],
            code=_code(base, token, overrides),
            pipeline=(("period_sum", {"granularity": g}),),
            unit=unit, frequency=GRAN_FREQUENCY[g], forecastable=forecastable,
        ))
    return modes


def _pop_modes(base: str, freq: str, overrides: dict[str, str], *, flow: bool) -> list[Mode]:
    """Группа «К прошлому периоду»: М/м и Кв/Кв.

    Для месячного ряда М/м = mom. Кв/Кв считается на квартальном bucket'е:
    last для запасов/уровней, sum для потоков.
    """
    method = "sum" if flow else "last"
    out: list[Mode] = []
    if NATIVE_GRAN[freq] == "month":
        out.append(Mode(
            mode="mom", group="pop", label="М/м",
            code=_code(base, "mom", overrides), pipeline=(("mom", {}),),
            unit="%", frequency="monthly", forecastable=False,
        ))
    out.append(Mode(
        mode="qoq", group="pop", label="Кв/Кв",
        code=_code(base, "qoq", overrides),
        pipeline=(("period_over_period", {"granularity": "quarter", "method": method}),),
        unit="%", frequency="quarterly", forecastable=False,
    ))
    return out


def _pop_modes_gen(
    base: str, freq: str, overrides: dict[str, str],
    *, flow: bool = False, abs_delta: bool = False, abs_unit: str = "п.п.",
) -> list[Mode]:
    """Группа «К прошлому периоду» (общая): М/м + Кв/Кв, с поддержкой дневной
    агрегации и абсолютных приростов.

    - day/week → М/м считается на месячных уровнях (period_last → mom[_abs]);
    - month → М/м напрямую; quarter/annual → М/м отсутствует;
    - abs_delta=True → приросты в единицах источника / п.п. (для ставок/курсов
      ставочного типа), иначе в процентах.
    """
    native = NATIVE_GRAN[freq]
    unit = abs_unit if abs_delta else "%"
    mom_op = "mom_abs" if abs_delta else "mom"
    pop_op = "period_over_period_abs" if abs_delta else "period_over_period"
    method = "sum" if flow else "last"
    out: list[Mode] = []
    if native == "month":
        mom_pipe: Pipeline | None = ((mom_op, {}),)
    elif native in ("week", "day"):
        mom_pipe = (("period_last", {"granularity": "month"}), (mom_op, {}))
    else:
        mom_pipe = None
    if mom_pipe is not None:
        out.append(Mode(
            mode="mom", group="pop", label="М/м",
            code=_code(base, "mom", overrides), pipeline=mom_pipe,
            unit=unit, frequency="monthly", forecastable=False,
        ))
    out.append(Mode(
        mode="qoq", group="pop", label="Кв/Кв",
        code=_code(base, "qoq", overrides),
        pipeline=((pop_op, {"granularity": "quarter", "method": method}),),
        unit=unit, frequency="quarterly", forecastable=False,
    ))
    return out


def _yoy_mode(base: str, freq: str, overrides: dict[str, str], *, forecastable: bool = False) -> Mode:
    """Лист «К соотв. периоду пред. года».

    Месячный ряд → yoy по месяцам. Недельный/дневной → сначала свести к
    месячным уровням (точные даты года-назад не совпадают), потом yoy.
    Квартальный → yoy по кварталам.
    """
    native = NATIVE_GRAN[freq]
    if native in ("week", "day"):
        pipeline: Pipeline = (("period_last", {"granularity": "month"}), ("yoy", {}))
        out_freq = "monthly"
    else:
        pipeline = (("yoy", {}),)
        out_freq = freq
    return Mode(
        mode="yoy", group="yoy", label="Г/г",
        code=_code(base, "yoy", overrides), pipeline=pipeline,
        unit="%", frequency=out_freq, forecastable=forecastable,
    )


# --- Группы-пресеты -----------------------------------------------------------

_G_EOP = Group("level", "На конец периода")
_G_AVG = Group("avg", "Средняя за период")
_G_POP = Group("pop", "К прошлому периоду")
_G_YOY = Group("yoy", "К соотв. периоду пред. года", leaf=True)
_G_FLOW = Group("flow", "За период")
_G_GDP_LEVEL = Group("level", "Уровень")
_G_POP_LEVEL = Group("pop", "К прошлому периоду")
_G_INDEX = Group("index", "Индекс", leaf=True)


def _build_rate_daily(f: "FamilyDef") -> Family:
    """T1 — дневные ставки/курсы/сырьё: 4 группы.

    На конец периода [default] + Средняя за период + К прошлому периоду
    (М/м, Кв/Кв) + Г/г. Для ставочных рядов (`abs_delta=True`: ключевая ставка,
    RUONIA) приросты в п.п.; для курсов/сырья — в процентах.
    """
    abs_delta = f.abs_delta
    yoy_unit = f.yoy_unit or "п.п."
    yoy_mode = (
        _yoy_abs_mode(f.base, "daily", yoy_unit, f.overrides)
        if abs_delta else _yoy_mode(f.base, "daily", f.overrides)
    )
    modes = (
        _level_modes(f.base, "daily", f.unit, f.overrides, group_id="level", forecastable=True)
        + _avg_modes(f.base, "daily", f.unit, f.overrides, forecastable=True)
        + _pop_modes_gen(f.base, "daily", f.overrides, abs_delta=abs_delta, abs_unit=yoy_unit)
        + [yoy_mode]
    )
    return Family(f.base, f.name, "T1", f.unit, f.category, "level",
                  [_G_EOP, _G_AVG, _G_POP, _G_YOY], modes)


def _build_rate_monthly(f: "FamilyDef") -> Family:
    """T2 — месячные ставки: На конец периода [default] + Средняя."""
    modes = (
        _level_modes(f.base, "monthly", f.unit, f.overrides, group_id="level", forecastable=True)
        + _avg_modes(f.base, "monthly", f.unit, f.overrides, forecastable=True)
    )
    return Family(f.base, f.name, "T2", f.unit, f.category, "level", [_G_EOP, _G_AVG], modes)


def _build_stock(f: "FamilyDef") -> Family:
    """T3/T4/T5 — запасы (monthly/quarterly/weekly): 4 группы."""
    freq = f.frequency
    fc = f.forecastable
    modes = (
        _level_modes(f.base, freq, f.unit, f.overrides, group_id="level", forecastable=fc)
        + _avg_modes(f.base, freq, f.unit, f.overrides, forecastable=fc)
        + _pop_modes(f.base, freq, f.overrides, flow=False)
        + [_yoy_mode(f.base, freq, f.overrides)]
    )
    tmpl = {"monthly": "T3", "quarterly": "T4", "weekly": "T5"}[freq]
    return Family(f.base, f.name, tmpl, f.unit, f.category, "level",
                  [_G_EOP, _G_AVG, _G_POP, _G_YOY], modes)


def _build_flow_sum(f: "FamilyDef") -> Family:
    """T6 — потоки бюджета (доходы/расходы): За период [default] + приросты."""
    modes = (
        _sum_modes(f.base, "monthly", f.unit, f.overrides, forecastable=f.forecastable)
        + _pop_modes(f.base, "monthly", f.overrides, flow=True)
        + [_yoy_mode(f.base, "monthly", f.overrides)]
    )
    return Family(f.base, f.name, "T6", f.unit, f.category, "level",
                  [_G_FLOW, _G_POP, _G_YOY], modes)


def _build_flow_balance(f: "FamilyDef") -> Family:
    """T7 — дефицит/профицит (поток со знаком): За период [default] + приросты (абс.).

    «За период» = сумма (нативный месяц → квартал/год). Приросты в АБСОЛЮТНОМ
    выражении (единица источника, млрд руб.): дефицит меняет знак, поэтому
    %-прирост бессмыслен. «К прошлому периоду» = М/м·Кв/Кв (abs на суммах),
    «Г/г» = yoy_abs — как у доходов/расходов (T6), но в рублях, а не процентах.
    """
    yoy_unit = f.yoy_unit or f.unit
    modes = (
        _sum_modes(f.base, "monthly", f.unit, f.overrides, forecastable=True)
        + _pop_modes_gen(f.base, "monthly", f.overrides, flow=True, abs_delta=True, abs_unit=yoy_unit)
        + [_yoy_abs_mode(f.base, "monthly", yoy_unit, f.overrides)]
    )
    return Family(f.base, f.name, "T7", f.unit, f.category, "level",
                  [_G_FLOW, _G_POP, _G_YOY], modes)


def _build_avg_level(f: "FamilyDef") -> Family:
    """T8 — среднемесячные показатели (зарплата, рабочая сила, занятость).

    Уровень такого ряда — это **среднее за период**, а НЕ баланс на конец
    периода (в отличие от денежной массы или резервов). Поэтому «На конец
    периода»/`period_last` здесь семантически неверен: квартальная зарплата —
    это средняя за три месяца, а не зарплата последнего месяца квартала.

    Группы: Средняя за период [default] (месяц = нативный уровень, далее
    среднее по кварталам/годам) · К прошлому периоду (М/м, Кв/Кв — на средних) ·
    Г/г.
    """
    base, unit, ov = f.base, f.unit, f.overrides
    modes: list[Mode] = [Mode(
        mode="level", group="avg", label=GRAN_LABEL["month"],
        code=base, pipeline=(), unit=unit, frequency="monthly", forecastable=True,
    )]
    for g in ("quarter", "year"):
        token = f"avg-{g}"
        modes.append(Mode(
            mode=token, group="avg", label=GRAN_LABEL[g],
            code=_code(base, token, ov),
            pipeline=(("period_avg", {"granularity": g}),),
            unit=unit, frequency=GRAN_FREQUENCY[g], forecastable=True,
        ))
    modes.append(Mode(
        mode="mom", group="pop", label="М/м",
        code=_code(base, "mom", ov), pipeline=(("mom", {}),),
        unit="%", frequency="monthly", forecastable=False,
    ))
    # Кв/Кв на квартальных СРЕДНИХ (method="avg"), не на последнем месяце.
    modes.append(Mode(
        mode="qoq", group="pop", label="Кв/Кв",
        code=_code(base, "qoq", ov),
        pipeline=(("period_over_period", {"granularity": "quarter", "method": "avg"}),),
        unit="%", frequency="quarterly", forecastable=False,
    ))
    modes.append(_yoy_mode(base, "monthly", ov))
    return Family(base, f.name, "T8", unit, f.category, "level",
                  [_G_AVG, _G_POP, _G_YOY], modes)


def _build_gdp(f: "FamilyDef") -> Family:
    """T9 — ВВП квартальный: Уровень [default] (кв + годовая сумма) + приросты."""
    base, unit = f.base, f.unit
    ov = f.overrides
    modes = [
        Mode("level", "level", GRAN_LABEL["quarter"], base, (), unit, "quarterly", True),
        Mode("sum-year", "level", GRAN_LABEL["year"], _code(base, "sum-year", ov),
             (("period_sum", {"granularity": "year"}),), unit, "annual", False),
        Mode("qoq", "pop", "Кв/Кв", _code(base, "qoq", ov), (("qoq", {}),), "%", "quarterly", False),
        _yoy_mode(base, "quarterly", ov),
    ]
    return Family(base, f.name, "T9", unit, f.category, "level",
                  [_G_GDP_LEVEL, _G_POP_LEVEL, _G_YOY], modes)


def _build_demography_annual(f: "FamilyDef") -> Family:
    """T10 — годовая демография/счётные ряды: Уровень [default] + Г/г + Индекс.

    У годового счётного ряда нет более мелкой гранулярности, поэтому
    «максимум информации» = уровень, темп Г/г и индекс относительно первого
    наблюдения (динамика накопленным итогом, удобно для сопоставления рядов
    разной размерности)."""
    base, unit = f.base, f.unit
    ov = f.overrides
    modes = [
        Mode("level", "level", GRAN_LABEL["year"], base, (), unit, "annual", True),
        _yoy_mode(base, "annual", ov),
        Mode("index", "index", "Индекс", _code(base, "index", ov),
             (("rebase_to_first", {}),), "индекс", "annual", False),
    ]
    return Family(base, f.name, "T10", unit, f.category, "level",
                  [_G_GDP_LEVEL, _G_YOY, _G_INDEX], modes)


def _yoy_abs_mode(base: str, freq: str, unit: str, overrides: dict[str, str]) -> Mode:
    """Лист «Г/г» в АБСОЛЮТНОМ выражении (yoy_abs).

    Для рядов, где процентный yoy бессмыслен: значения со знаком (баланс,
    сальдо, прирост) либо ставки/доли (изменение естественно мерить в пунктах,
    а не в «процентах от процента»). `unit` — «п.п.» / «‰» / единица источника.
    Код режима тот же (`-yoy`), что и у процентного, — карточка не смешивает оба.
    """
    native = NATIVE_GRAN[freq]
    if native in ("week", "day"):
        pipeline: Pipeline = (("period_last", {"granularity": "month"}), ("yoy_abs", {}))
        out_freq = "monthly"
    else:
        pipeline = (("yoy_abs", {}),)
        out_freq = freq
    return Mode(
        mode="yoy", group="yoy", label="Г/г",
        code=_code(base, "yoy", overrides), pipeline=pipeline,
        unit=unit, frequency=out_freq, forecastable=False,
    )


def _build_rate_monthly_yoy(f: "FamilyDef") -> Family:
    """T2y — месячные ставки/доли: На конец периода [default] + Средняя + Г/г (п.п.).

    Как T2, но добавлен лист «Г/г» в пунктах: ставка/доля выросла на X п.п. за
    год. Унифицирует ставочные карточки с запасами (у которых Г/г уже есть)."""
    yoy_unit = f.yoy_unit or "п.п."
    modes = (
        _level_modes(f.base, "monthly", f.unit, f.overrides, group_id="level", forecastable=True)
        + _avg_modes(f.base, "monthly", f.unit, f.overrides)
        + _pop_modes_gen(f.base, "monthly", f.overrides, abs_delta=True, abs_unit=yoy_unit)
        + [_yoy_abs_mode(f.base, "monthly", yoy_unit, f.overrides)]
    )
    return Family(f.base, f.name, "T2y", f.unit, f.category, "level",
                  [_G_EOP, _G_AVG, _G_POP, _G_YOY], modes)


def _build_signed_quarterly(f: "FamilyDef") -> Family:
    """T9s — квартальный ряд со знаком (сальдо/баланс): Уровень (кв + годовая
    сумма) + Г/г в единицах источника. Без Кв/Кв и %-Г/г: база меняет знак."""
    base, unit, ov = f.base, f.unit, f.overrides
    yoy_unit = f.yoy_unit or unit
    modes = [
        Mode("level", "level", GRAN_LABEL["quarter"], base, (), unit, "quarterly", True),
        Mode("sum-year", "level", GRAN_LABEL["year"], _code(base, "sum-year", ov),
             (("period_sum", {"granularity": "year"}),), unit, "annual", False),
        Mode("qoq", "pop", "Кв/Кв", _code(base, "qoq", ov), (("qoq_abs", {}),),
             unit, "quarterly", False),
        _yoy_abs_mode(base, "quarterly", yoy_unit, ov),
    ]
    return Family(base, f.name, "T9s", unit, f.category, "level",
                  [_G_GDP_LEVEL, _G_POP_LEVEL, _G_YOY], modes)


def _build_annual_abs(f: "FamilyDef") -> Family:
    """T10a — годовой ряд со знаком/долей: Уровень [default] + Г/г (абс.).

    Для коэффициентов (‰), долей (%) и приростов со знаком (тыс. чел.): yoy в
    процентах вводит в заблуждение, поэтому Г/г = абсолютное изменение к
    прошлому году в тех же единицах (или в пунктах для %/‰)."""
    base, unit, ov = f.base, f.unit, f.overrides
    yoy_unit = f.yoy_unit or unit
    modes = [
        Mode("level", "level", GRAN_LABEL["year"], base, (), unit, "annual", True),
        _yoy_abs_mode(base, "annual", yoy_unit, ov),
    ]
    return Family(base, f.name, "T10a", unit, f.category, "level",
                  [_G_GDP_LEVEL, _G_YOY], modes)


def _build_ratio_index(f: "FamilyDef") -> Family:
    """T12 — индекс-отношение (доступность жилья): помесячный безразмерный индекс,
    равный отношению двух индексов в общей базе.

    Уровень такого ряда — само значение месяца (не «на конец периода» и не
    сумма): по кварталам и годам берём СРЕДНЕЕ за период (решение владельца v7).
    Группы: Уровень (по месяцам / средняя за квартал / средняя за год) ·
    К прошлому периоду (М/м, Кв/Кв на средних) · Г/г.
    Прогноз: нативный уровень через monthly_auto на расчётном ряде отношения
    (если `f.forecastable`), агрегаты/приросты — derived-протяжкой. Флаг режима
    вычисляется централизованно `_mode_forecastable`.

    Режим «Скользящая 12 мес.» убран (созвон 2026-06-16): дублировал «средняя
    за год» и засорял переключатель — индекс отношения не нуждается в
    сглаживании на карточке.
    """
    base, unit, ov = f.base, f.unit, f.overrides
    modes: list[Mode] = [
        Mode("level", "level", GRAN_LABEL["month"], base, (), unit, "monthly", f.forecastable),
        Mode("avg-quarter", "level", "Средняя за квартал", _code(base, "avg-quarter", ov),
             (("period_avg", {"granularity": "quarter"}),), unit, "quarterly", False),
        Mode("avg-year", "level", "Средняя за год", _code(base, "avg-year", ov),
             (("period_avg", {"granularity": "year"}),), unit, "annual", False),
        Mode("mom", "pop", "М/м", _code(base, "mom", ov), (("mom", {}),),
             "%", "monthly", False),
        Mode("qoq", "pop", "Кв/Кв", _code(base, "qoq", ov),
             (("period_over_period", {"granularity": "quarter", "method": "avg"}),),
             "%", "quarterly", False),
        _yoy_mode(base, "monthly", ov),
    ]
    groups = [
        Group("level", "Уровень"),
        _G_POP,
        _G_YOY,
    ]
    return Family(base, f.name, "T12", unit, f.category, "level", groups, modes)


_BUILDERS = {
    "T1": _build_rate_daily,
    "T2": _build_rate_monthly,
    "T2y": _build_rate_monthly_yoy,
    "T3": _build_stock,
    "T4": _build_stock,
    "T5": _build_stock,
    "T6": _build_flow_sum,
    "T7": _build_flow_balance,
    "T8": _build_avg_level,
    "T9": _build_gdp,
    "T9s": _build_signed_quarterly,
    "T10": _build_demography_annual,
    "T10a": _build_annual_abs,
    "T12": _build_ratio_index,
}


@dataclass
class FamilyDef:
    base: str
    name: str
    template: str
    unit: str
    category: str
    frequency: str
    overrides: dict[str, str] = field(default_factory=dict)
    # Единица режима «Г/г» для абсолютного yoy (yoy_abs): «п.п.» для ставок/долей,
    # «‰» для коэффициентов, единица источника для рядов со знаком. None → unit.
    yoy_unit: str | None = None
    # Приросты (М/м, Кв/Кв, Г/г) в абсолютном выражении вместо процентов —
    # для ставочных дневных рядов (ключевая ставка, RUONIA): изменение в п.п.
    abs_delta: bool = False
    # Прогноз базового ряда и протяжка в sibling-режимы (monthly_auto + derived).
    forecastable: bool = True


# --- Каталог семейств --------------------------------------------------------
#
# Только семьи, унифицируемые через generic-движок. ИПЦ/ИЦП (T11) и housing
# живут отдельно (bespoke ops + тексты) — см. cpiViewMode*/housingViewMode*.

_FAMILY_DEFS: list[FamilyDef] = [
    # T1 — дневные ставки/курсы/сырьё (4 группы; ставки → приросты в п.п.)
    FamilyDef("key-rate", "Ключевая ставка ЦБ РФ", "T1", "%", "Финансы", "daily",
              abs_delta=True, yoy_unit="п.п."),
    FamilyDef("ruonia", "Ставка RUONIA", "T1", "%", "Финансы", "daily",
              abs_delta=True, yoy_unit="п.п."),
    FamilyDef("usd-rub", "Курс доллара США", "T1", "руб.", "Валюты", "daily"),
    FamilyDef("eur-rub", "Курс евро", "T1", "руб.", "Валюты", "daily"),
    FamilyDef("cny-rub", "Курс юаня", "T1", "руб.", "Валюты", "daily"),
    FamilyDef("brent", "Нефть Brent", "T1", "USD/баррель", "Сырьё", "daily"),
    FamilyDef("gold-price", "Цена золота (ЦБ)", "T1", "руб./г", "Сырьё", "daily"),
    FamilyDef("btc-usd", "Биткоин (BTC/USD)", "T1", "USD", "Сырьё", "daily"),
    # T2y — месячные ставки/доли: На конец периода + Средняя + Г/г (п.п.)
    FamilyDef("mortgage-rate", "Ставка по ипотеке", "T2y", "%", "Финансы", "monthly", yoy_unit="п.п."),
    FamilyDef("auto-loan-rate", "Ставка по автокредитам", "T2y", "%", "Финансы", "monthly", yoy_unit="п.п."),
    FamilyDef("deposit-rate", "Ставка по вкладам физических лиц", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    FamilyDef("credit-rate-corp-short", "Ставка по кредитам юридическим лицам", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    FamilyDef("credit-rate-ind-short", "Ставка по кредитам физическим лицам", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    # Срезы ставок по сроку — тот же T2y, что и `*-short`/`deposit-rate`: полный
    # набор режимов (на конец/средняя по кв./году, М/м·Кв/Кв, Г/г в п.п.), чтобы
    # внутри variant-группы «срок ставки» выбор режимов был одинаковым.
    FamilyDef("credit-rate-corp-1to3y", "Ставка по кредитам юридическим лицам от 1 до 3 лет", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    FamilyDef("credit-rate-corp-over3y", "Ставка по кредитам юридическим лицам свыше 3 лет", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    FamilyDef("credit-rate-ind-1to3y", "Ставка по кредитам физическим лицам от 1 до 3 лет", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    FamilyDef("credit-rate-ind-over3y", "Ставка по кредитам физическим лицам свыше 3 лет", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    FamilyDef("deposit-rate-medium", "Ставка по вкладам на 1-3 года", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    FamilyDef("deposit-rate-long", "Ставка по вкладам свыше 3 лет", "T2y", "%", "Ставки", "monthly", yoy_unit="п.п."),
    FamilyDef("unemployment", "Уровень безработицы", "T2y", "%", "Рынок труда", "monthly", yoy_unit="п.п."),
    # T3 — месячные запасы
    FamilyDef("m0", "Денежная масса М0", "T3", "млрд руб.", "Финансы", "monthly"),
    FamilyDef("m1", "Денежная масса М1", "T3", "млрд руб.", "Финансы", "monthly"),
    FamilyDef("m2", "Денежная масса М2", "T3", "млрд руб.", "Финансы", "monthly"),
    FamilyDef("business-credit", "Кредиты бизнесу", "T3", "трлн руб.", "Финансы", "monthly"),
    FamilyDef("consumer-credit", "Кредиты физическим лицам", "T3", "трлн руб.", "Финансы", "monthly"),
    FamilyDef("deposits-individual", "Вклады физических лиц", "T3", "млрд руб.", "Финансы", "monthly"),
    FamilyDef("deposits-business", "Депозиты организаций", "T3", "млрд руб.", "Финансы", "monthly"),
    # Рабочая сила и занятость — среднемесячные оценки обследования (среднее за
    # период), не балансы на конец месяца → шаблон T8 (avg-уровень), как зарплата.
    FamilyDef("labor-force", "Рабочая сила", "T8", "млн чел.", "Рынок труда", "monthly"),
    FamilyDef("employment", "Занятое население", "T8", "млн чел.", "Рынок труда", "monthly"),
    # T4 — квартальный запас
    FamilyDef("external-debt", "Внешний долг", "T4", "млн $", "Финансы", "quarterly"),
    # T5 — недельный запас
    FamilyDef("international-reserves", "Международные резервы", "T5", "млрд $", "Финансы", "weekly"),
    # T6 — потоки бюджета
    FamilyDef("budget-revenue", "Доходы бюджета", "T6", "млрд руб.", "Бюджет", "monthly"),
    FamilyDef("budget-expenditure", "Расходы бюджета", "T6", "млрд руб.", "Бюджет", "monthly"),
    # T6 — месячные потоки бизнеса (объём за период суммируется по кварталам/годам)
    FamilyDef("construction-work", "Объём строительных работ", "T6", "млрд руб.", "Бизнес", "monthly"),
    FamilyDef("housing-commissioned", "Ввод в действие жилых домов", "T6", "млн кв.м", "Бизнес", "monthly"),
    FamilyDef("retail-trade", "Оборот розничной торговли", "T6", "млрд руб.", "Бизнес", "monthly"),
    # T6 — месячные потоки внешней торговли (alternate frequency, is_listed=false)
    FamilyDef("exports-monthly", "Экспорт товаров (месячный ряд)", "T6", "млн $", "Торговля", "monthly"),
    FamilyDef("imports-monthly", "Импорт товаров (месячный ряд)", "T6", "млн $", "Торговля", "monthly"),
    FamilyDef("services-exports-monthly", "Экспорт услуг (месячный ряд)", "T6", "млн $", "Торговля", "monthly"),
    FamilyDef("services-imports-monthly", "Импорт услуг (месячный ряд)", "T6", "млн $", "Торговля", "monthly"),
    FamilyDef("trade-balance-monthly", "Торговый баланс (месячный ряд)", "T6", "млн $", "Торговля", "monthly"),
    # T7 — баланс бюджета
    FamilyDef("budget-deficit", "Дефицит/профицит бюджета", "T7", "млрд руб.", "Бюджет", "monthly"),
    # T8 — зарплата (real/index не режимы: остаются wages-real/wages-index)
    FamilyDef("wages-nominal", "Средняя заработная плата", "T8", "руб.", "Рынок труда", "monthly",
              overrides={"yoy": "wages-yoy"}),
    # T9 — ВВП (reuse легаси-кодов derived)
    FamilyDef("gdp-nominal", "Номинальный ВВП", "T9", "млрд руб.", "ВВП", "quarterly",
              overrides={"yoy": "gdp-yoy", "qoq": "gdp-qoq", "sum-year": "gdp-nominal-annual"}),
    FamilyDef("gdp-real", "Реальный ВВП", "T9", "млрд руб.", "ВВП", "quarterly",
              overrides={"yoy": "gdp-real-yoy", "qoq": "gdp-real-qoq", "sum-year": "gdp-real-annual"}),
    FamilyDef("gdp-consumption", "ВВП: расходы домохозяйств", "T9", "млрд руб.", "ВВП", "quarterly"),
    FamilyDef("gdp-government", "ВВП: госрасходы", "T9", "млрд руб.", "ВВП", "quarterly"),
    FamilyDef("gdp-investment", "ВВП: инвестиции", "T9", "млрд руб.", "ВВП", "quarterly"),
    # T9 — квартальные положительные потоки (уровень кв + годовая сумма + Кв/Кв + Г/г)
    FamilyDef("capital-investment", "Инвестиции в основной капитал", "T9", "млрд руб.", "Бизнес", "quarterly"),
    FamilyDef("exports", "Экспорт товаров", "T9", "млн $", "Торговля", "quarterly"),
    FamilyDef("imports", "Импорт товаров", "T9", "млн $", "Торговля", "quarterly"),
    FamilyDef("services-exports", "Экспорт услуг", "T9", "млн $", "Торговля", "quarterly"),
    FamilyDef("services-imports", "Импорт услуг", "T9", "млн $", "Торговля", "quarterly"),
    # T9s — квартальные ряды со знаком (сальдо/баланс/нетто): Уровень + Г/г (абс.)
    FamilyDef("trade-balance", "Торговый баланс", "T9s", "млн $", "Торговля", "quarterly"),
    FamilyDef("current-account", "Сальдо текущего счёта", "T9s", "млн $", "Торговля", "quarterly"),
    FamilyDef("fdi-net", "Прямые иностранные инвестиции (нетто)", "T9s", "млн $", "Бизнес", "quarterly"),
    # T10 — годовая демография/счётные годовые ряды (Уровень по годам + Г/г)
    FamilyDef("deaths", "Число смертей", "T10", "тыс. чел.", "Демография", "annual"),
    FamilyDef("births", "Число рождений", "T10", "тыс. чел.", "Население", "annual"),
    FamilyDef("population", "Численность населения", "T10", "млн чел.", "Население", "annual"),
    FamilyDef("working-age-population", "Население в трудоспособном возрасте", "T10", "млн чел.", "Население", "annual"),
    FamilyDef("pop-over-working-age", "Население старше трудоспособного возраста", "T10", "млн чел.", "Население", "annual"),
    FamilyDef("pop-under-working-age", "Население моложе трудоспособного возраста", "T10", "млн чел.", "Население", "annual"),
    FamilyDef("pensioners", "Численность пенсионеров", "T10", "тыс. чел.", "Население", "annual"),
    FamilyDef("doctoral-students", "Численность докторантов", "T10", "чел.", "Наука", "annual"),
    FamilyDef("grad-students", "Численность аспирантов", "T10", "чел.", "Наука", "annual"),
    FamilyDef("rd-organizations", "Число организаций НИР", "T10", "ед.", "Наука", "annual"),
    FamilyDef("rd-personnel", "Персонал НИР", "T10", "чел.", "Наука", "annual"),
    # T10a — годовые коэффициенты/доли/приросты со знаком: Уровень + Г/г (абс.)
    FamilyDef("birth-rate", "Коэффициент рождаемости", "T10a", "‰", "Население", "annual", yoy_unit="‰"),
    FamilyDef("death-rate", "Коэффициент смертности", "T10a", "‰", "Население", "annual", yoy_unit="‰"),
    FamilyDef("population-natural-growth", "Естественный прирост населения", "T10a", "тыс. чел.", "Население", "annual"),
    FamilyDef("population-migration", "Миграционный прирост", "T10a", "тыс. чел.", "Население", "annual"),
    FamilyDef("population-total-growth", "Общий прирост населения", "T10a", "тыс. чел.", "Население", "annual"),
    FamilyDef("depreciation-rate", "Степень износа основных фондов", "T10a", "%", "Бизнес", "annual", yoy_unit="п.п."),
    FamilyDef("innovation-activity", "Уровень инновационной активности", "T10a", "%", "Наука", "annual", yoy_unit="п.п."),
    FamilyDef("small-business-innovation", "Инновации малых предприятий", "T10a", "%", "Наука", "annual", yoy_unit="п.п."),
    FamilyDef("tech-innovation-share", "Доля организаций с технол. инновациями", "T10a", "%", "Наука", "annual", yoy_unit="п.п."),
    # Месячные/квартальные индексы — полный «запасный» шаблон (4 группы),
    # приросты в процентах (индекс уже относительный). ИПП переиспользует
    # существующий derived ipi-yoy как режим «Г/г» (отдельная карточка скрыта).
    FamilyDef("ipi", "Индекс промышленного производства", "T3", "индекс", "Бизнес", "monthly",
              overrides={"yoy": "ipi-yoy"}),
    # T12 — индекс доступности жилья (отношение индекса зарплаты к индексу цен на
    # жильё, общая база 2010). Помесячный; квартал/год = среднее. Два варианта
    # рынка (первичный/вторичный) — variant-группа, как у цен на жильё.
    FamilyDef("housing-affordability", "Индекс доступности жилья (вторичное жильё)",
              "T12", "индекс", "Цены", "monthly"),
    FamilyDef("housing-affordability-primary", "Индекс доступности жилья (первичное жильё)",
              "T12", "индекс", "Цены", "monthly"),
]


def _build_all() -> list[Family]:
    families: list[Family] = []
    for fdef in _FAMILY_DEFS:
        families.append(_BUILDERS[fdef.template](fdef))
    return families


FAMILIES: list[Family] = _build_all()
FAMILY_BY_BASE: dict[str, Family] = {f.base: f for f in FAMILIES}


# --- Итераторы для генераторов backend ---------------------------------------


def iter_derived_specs():
    """Yield `(dst_code, src_code, pipeline)` для каждого НЕ-нативного режима.

    Дедуплицирует по `dst_code` (несколько семей не пересекаются, но overrides
    легаси-кодов могут совпасть с уже существующими — caller решает, что делать
    с коллизией к hand-written `DERIVED_SPECS`).
    """
    seen: set[str] = set()
    for fam in FAMILIES:
        for m in fam.modes:
            if m.is_native or m.code in seen:
                continue
            seen.add(m.code)
            yield m.code, fam.base, m.pipeline


# Частоты, для которых прогноз базового ряда протягивается в агрегаты.
# Дневные/недельные базы исключены: агрегация день/неделя→месяц для прогноза
# шумна (полнота месяца по дневным точкам нечёткая), нативный уровень и так
# показывает прогнозный хвост.
_FORECAST_PROPAGATE_FREQ: frozenset[str] = frozenset({"monthly", "quarterly", "annual"})

# Сколько суб-периодов источника образует полный bucket (guard неполных
# будущих кварталов/годов в derived_from_source). Ключ: (нативная частота, гранулярность).
_BUCKET_MIN_PERIODS: dict[tuple[str, str], int] = {
    ("monthly", "quarter"): 3,
    ("monthly", "year"): 12,
    ("quarterly", "year"): 4,
}


def _mode_forecastable(m: "Mode", base_freq: str | None, base_forecastable: bool) -> bool:
    """Единый источник истины: показывает ли режим прогноз на карточке.

    Режим прогнозируем, если база прогнозируема И (это нативный уровень ИЛИ
    частота базы протягивает прогноз в агрегаты — `_FORECAST_PROPAGATE_FREQ`).
    Ровно при том же условии `_mode_forecast_meta` цепляет sibling'у
    derived-прогноз, поэтому фронт-флаг строго совпадает с наличием данных.

    Заменяет per-mode хардкод `forecastable=` в билдерах для НЕ-нативных
    режимов (он раньше всюду стоял False — из-за чего прогнозы yoy/mom/qoq не
    появлялись при переключении периода, хотя backend их считал).
    """
    if not base_forecastable:
        return False
    if m.is_native:
        return True
    return base_freq in _FORECAST_PROPAGATE_FREQ


def _mode_forecast_meta(fam: "Family", m: "Mode", base_freq: str) -> dict | None:
    """Конфиг `derived_forecast` для протяжки прогноза базы в режим-sibling.

    Возвращает None, если режим не прогнозируется (не та частота базы, либо
    база не forecastable). Иначе — generic-pipeline op + guard полноты bucket'а.
    """
    if base_freq not in _FORECAST_PROPAGATE_FREQ:
        return None
    # Гранулярность агрегации в пайплайне (если есть) — для guard'а полноты.
    agg_gran: str | None = None
    for _op, kwargs in m.pipeline:
        g = kwargs.get("granularity")
        if g in ("quarter", "year"):
            if agg_gran is None or GRAN_ORDER.index(g) > GRAN_ORDER.index(agg_gran):
                agg_gran = g
    cfg = {
        "source_code": fam.base,
        "operation": "pipeline",
        "pipeline": [[op, dict(kwargs)] for op, kwargs in m.pipeline],
        "model_name": f"{m.code}-derived",
    }
    # Квартал/год из месячного прогноза: последний месяц bucket'а → агрегат
    # (поток ×3/×12, уровень/ставка — как есть). Не ждём 12 полных месяцев.
    if agg_gran in ("quarter", "year"):
        cfg["monthly_tail_extrapolate"] = True
    else:
        min_periods = _BUCKET_MIN_PERIODS.get((base_freq, agg_gran)) if agg_gran else None
        if min_periods and min_periods > 1:
            cfg["complete_bucket"] = agg_gran
            cfg["min_periods"] = min_periods
    return cfg


def iter_sibling_indicators():
    """Yield метаданные seed-строки для каждого НЕ-нативного режима-sibling.

    Возвращает dict с публичными полями (без «внутренностей», см.
    methodology-language.mdc): code, name, unit, frequency, parent base,
    category, is_percent. Поле `forecast` (или None) — конфиг протяжки прогноза
    базового ряда в этот агрегат через generic-pipeline (см. derived_from_source).
    """
    seen: set[str] = set()
    for fam in FAMILIES:
        base_freq = next(
            (m.frequency for m in fam.modes if m.is_native), None
        )
        base_forecastable = any(m.is_native and m.forecastable for m in fam.modes)
        for m in fam.modes:
            if m.is_native or m.code in seen:
                continue
            seen.add(m.code)
            token = m.mode
            suffix = _SUFFIX_NAME.get(token, m.label)
            forecast = (
                _mode_forecast_meta(fam, m, base_freq)
                if (base_forecastable and base_freq) else None
            )
            yield {
                "code": m.code,
                "name": f"{fam.name} — {suffix}",
                "unit": m.unit,
                "frequency": m.frequency,
                "parent": fam.base,
                "category": fam.category,
                "is_percent": m.unit == "%",
                "forecastable": _mode_forecastable(m, base_freq, base_forecastable),
                "forecast": forecast,
            }


def resolve_view_mode(base: str, url_mode: str | None) -> Mode | None:
    """Разрешить (base, ?mode=) в режим generic-семьи (зеркало frontend resolveViewMode)."""
    fam = FAMILY_BY_BASE.get(base)
    if not fam:
        return None
    if url_mode and any(m.mode == url_mode for m in fam.modes):
        mode_token = url_mode
    else:
        mode_token = fam.default_mode
    return next((m for m in fam.modes if m.mode == mode_token), None)


def data_indicator_code(base: str, url_mode: str | None) -> str:
    """Backend-код ряда для SSR/API при выбранном режиме карточки."""
    resolved = resolve_view_mode(base, url_mode)
    return resolved.code if resolved else base


def mode_display_suffix(fam: Family, mode: Mode) -> str | None:
    """Человеческий суффикс режима для заголовка (как modeSuffix на frontend)."""
    if mode.mode == fam.default_mode:
        return None
    group = next((g for g in fam.groups if g.id == mode.group), None)
    if not group:
        return mode.label
    if group.leaf:
        return group.label
    return f"{group.label}, {mode.label.lower()}"


def to_frontend_families() -> dict:
    """JSON-сериализуемое зеркало конфига для frontend generic-движка."""
    out: dict = {}
    for fam in FAMILIES:
        base_freq = next((m.frequency for m in fam.modes if m.is_native), None)
        base_forecastable = any(m.is_native and m.forecastable for m in fam.modes)
        out[fam.base] = {
            "base": fam.base,
            "name": fam.name,
            "template": fam.template,
            "unit": fam.unit,
            "defaultMode": fam.default_mode,
            "variantAxis": fam.variant_axis,
            "groups": [{"id": g.id, "label": g.label, "leaf": g.leaf} for g in fam.groups],
            "modes": [
                {
                    "mode": m.mode,
                    "group": m.group,
                    "label": m.label,
                    "code": m.code,
                    "unit": m.unit,
                    "frequency": m.frequency,
                    "forecastable": _mode_forecastable(m, base_freq, base_forecastable),
                    "isNative": m.is_native,
                }
                for m in fam.modes
            ],
        }
    return out
