#!/usr/bin/env python3
"""Детерминированная «карта индикаторов» → docs/indicator-index.json (+ .md).

Единая машинная карта «код индикатора → источник / UI-стек / прогноз / файлы»,
чтобы агент (и человек) не угадывали, где править индикатор.

ИСТОЧНИКИ ИСТИНЫ (только парсинг существующих файлов, без догадок):
  - backend/seed_data.py            — импорт; финальный список INDICATORS
                                       (включая сгенерированные siblings,
                                       monthly_auto-стратегию, hidden-флаги).
  - app/data/view_model_families.py — FAMILY_BY_BASE (generic config-стек).
  - app/services/calculation_engine — DERIVED_SPECS (derived → src).
  - app/data/indicator_seo.py       — seo_title (для title).
  - frontend/src/lib/*ViewModeResolve.js — легаси-стеки (cpi/housing/ppi/
                                       cbr-term/unemployment) и их состав.
  - frontend/src/lib/viewModeFamilies.js — легаси VIEW_MODE_FAMILIES (trade).
  - frontend/src/lib/indicatorVariants.js — VARIANT_GROUPS.

UI-СТЕК определяется ТОЧНО как каскад в IndicatorDetail.jsx: generic
(getViewModeFamily early-return) проверяется ПЕРВЫМ, поэтому коды, попавшие в
config-driven движок, рендерятся generic, даже если у них есть легаси-ветка
(её standalone-рендер недостижим → флаг shadowed_legacy). ВНИМАНИЕ: флаг НЕ
значит «легаси-файл мёртв» — content/resolve часто переиспользуются общими
секциями (chart/table) и держат canonical-редиректы старых URL. Детали и
почему это НЕ delete-list — в docs/dead-code-report.md.

Запуск:
    python scripts/build-indicator-index.py           # пишет docs/indicator-index.{json,md}
    python scripts/build-indicator-index.py --check    # падает, если карта расходится с кодом
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONT_LIB = ROOT / "frontend" / "src" / "lib"
OUT_JSON = ROOT / "docs" / "indicator-index.json"
OUT_MD = ROOT / "docs" / "indicator-index.md"
OUT_DEAD = ROOT / "docs" / "dead-code-report.md"

# Файлы легаси view-mode механики (где живут «мёртвые» ветки).
_LEGACY_FILE_MARKERS = (
    "frontend/src/lib/viewModeFamilies.js",          # легаси trade-реестр
    "cbrTermSliceRate", "unemploymentViewMode",       # bespoke-стеки, перекрытые generic
)

sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # для import completeness

import completeness  # noqa: E402  (паспорт полноты семейств — отдельный модуль)


# ---------------------------------------------------------------------------
#  Источники истины (Python import — детерминированно)
# ---------------------------------------------------------------------------

def load_python_sources():
    import seed_data
    from app.data.view_model_families import FAMILY_BY_BASE
    from app.services.calculation_engine import DERIVED_SPECS
    from app.data import indicator_seo as iseo
    from app.services.rosstat_cpi_parser import PARSER_REGISTRY
    return {
        "indicators": seed_data.INDICATORS,
        "hidden": set(seed_data.INDICATOR_HIDDEN_FROM_LISTING),
        "monthly_auto": set(seed_data.MONTHLY_AUTO_FORECAST_CODES),
        "family_by_base": set(FAMILY_BY_BASE),
        "derived_specs": [
            (s.dst_code, tuple(s.src_codes)) for s in DERIVED_SPECS
        ],
        "seo_titles": {c: v.get("seo_title") for c, v in iseo.INDICATOR_SEO.items()},
        "parser_types": set(PARSER_REGISTRY),
    }


# ---------------------------------------------------------------------------
#  Парсинг легаси-конфигов на JS (детерминированно — regex по литералам)
# ---------------------------------------------------------------------------

def _js_string_array(path: Path, varname: str) -> list[str]:
    """Извлечь `export const NAME = ['a', 'b', ...];` (плоский массив строк)."""
    text = path.read_text(encoding="utf-8")
    m = re.search(
        rf"const\s+{re.escape(varname)}\s*=\s*\[(.*?)\]", text, re.DOTALL
    )
    if not m:
        return []
    return re.findall(r"'([a-z0-9-]+)'", m.group(1))


def parse_legacy_js():
    cpi = _js_string_array(FRONT_LIB / "useIndicatorViewModeData.js", "CPI_CODES")
    housing = _js_string_array(FRONT_LIB / "housingViewModeResolve.js", "HOUSING_CODES")
    ppi = _js_string_array(FRONT_LIB / "ppiViewModeResolve.js", "PPI_CODES")
    cbr = (
        _js_string_array(FRONT_LIB / "cbrTermSliceRateResolve.js", "CORPORATE_LOAN_CODES")
        + _js_string_array(FRONT_LIB / "cbrTermSliceRateResolve.js", "INDIVIDUAL_LOAN_CODES")
        + _js_string_array(FRONT_LIB / "cbrTermSliceRateResolve.js", "DEPOSIT_RATE_CODES")
    )
    unemp_text = (FRONT_LIB / "unemploymentViewModeResolve.js").read_text(encoding="utf-8")
    m = re.search(r"UNEMPLOYMENT_ROOT\s*=\s*'([a-z0-9-]+)'", unemp_text)
    unemployment_root = m.group(1) if m else "unemployment"

    # Легаси VIEW_MODE_FAMILIES (frontend/src/lib/viewModeFamilies.js):
    # ключи семей + все code:'...' внутри.
    vmf_text = (FRONT_LIB / "viewModeFamilies.js").read_text(encoding="utf-8")
    block = re.search(
        r"VIEW_MODE_FAMILIES\s*=\s*\{(.*?)\n\};", vmf_text, re.DOTALL
    )
    legacy_js_codes: set[str] = set()
    if block:
        body = block.group(1)
        # ключи верхнего уровня: `  exports: {` или `  'trade-balance': {`
        for km in re.finditer(r"^\s{2}'?([a-z][a-z0-9-]*)'?:\s*\{", body, re.MULTILINE):
            legacy_js_codes.add(km.group(1))
        # члены: `code: 'xxx'`
        for cm in re.finditer(r"code:\s*'([a-z0-9-]+)'", body):
            legacy_js_codes.add(cm.group(1))

    # VARIANT_GROUPS (frontend/src/lib/indicatorVariants.js) → code → group label
    iv_text = (FRONT_LIB / "indicatorVariants.js").read_text(encoding="utf-8")
    variant_group_of: dict[str, str] = {}
    for gm in re.finditer(
        r"\{\s*label:\s*'([^']+)',\s*codes:\s*\[(.*?)\]\s*,?\s*\}",
        iv_text, re.DOTALL,
    ):
        glabel = gm.group(1)
        for cm in re.finditer(r"code:\s*'([a-z0-9-]+)'", gm.group(2)):
            variant_group_of[cm.group(1)] = glabel

    return {
        "cpi": set(cpi),
        "housing": set(housing),
        "ppi": set(ppi),
        "cbr_term": set(cbr),
        "unemployment_root": unemployment_root,
        "legacy_js_codes": legacy_js_codes,
        "variant_group_of": variant_group_of,
    }


# ---------------------------------------------------------------------------
#  Индекс ссылок на код по файлам (один regex-проход по дереву)
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "dist", "build", ".idea", ".vscode", ".cursor",
}
SKIP_SUFFIXES = {
    ".lock", ".ttf", ".woff", ".woff2", ".eot", ".png", ".ico", ".svg",
    ".pdf", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".zip", ".gz",
    ".xlsx", ".xls", ".pyc", ".so", ".bin", ".db", ".sqlite", ".sqlite3",
    ".pem", ".crt",
}
SKIP_NAMES = {"package-lock.json"}
# Карту-индекс не сканируем саму на себя (иначе self-reference шум).
SKIP_RELPATHS = {
    "docs/indicator-index.json", "docs/indicator-index.md",
    "docs/repo-inventory.md", "docs/dead-code-report.md",
}


STAMP_PREFIX = "**Сгенерировано:**"


def head_stamp() -> str:
    """Дата последней генерации. Строка исключается из --check-сравнения
    (см. _strip_stamp), поэтому wall-clock не ломает guard."""
    return f"{STAMP_PREFIX} {_dt.date.today().isoformat()}"


def _strip_stamp(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.startswith(STAMP_PREFIX)
    )


def _git_tracked() -> list[Path] | None:
    """git-tracked + untracked-not-ignored — детерминированно, без gitignored
    скрэтча/build, стабильно до и после коммита новых файлов."""
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        )
        others = subprocess.run(
            ["git", "ls-files", "-z", "--others", "--exclude-standard"], cwd=ROOT,
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    rels = set(tracked.stdout.split("\0")) | set(others.stdout.split("\0"))
    return [ROOT / r for r in sorted(rels) if r]


def _text_files() -> list[Path]:
    tracked = _git_tracked()
    candidates = tracked if tracked is not None else [
        p for p in ROOT.rglob("*") if p.is_file()
    ]
    out: list[Path] = []
    for p in candidates:
        if not p.is_file():
            continue
        rel = str(p.relative_to(ROOT))
        if set(p.relative_to(ROOT).parts) & SKIP_DIRS:
            continue
        if p.suffix.lower() in SKIP_SUFFIXES or p.name in SKIP_NAMES:
            continue
        if rel in SKIP_RELPATHS:
            continue
        out.append(p)
    return out


def _classify(rel: str) -> str:
    # Тесты — первыми: иначе test_calculation_engine.py / test_cbr_keyrate.py
    # ошибочно попали бы в derived/parser по совпадению имени.
    if rel.endswith(".test.js") or "/tests/" in rel or rel.startswith("backend/tests"):
        return "tests"
    if rel == "backend/seed_data.py":
        return "seed"
    if rel.endswith("_parser.py") or rel.endswith("/parser.py") or "cbr_keyrate.py" in rel:
        return "parser"
    if "calculation_engine" in rel or "derived_ops" in rel or "view_model_families" in rel:
        return "derived"
    if "indicator_seo" in rel or "seo_content" in rel or "seo_renderer" in rel:
        return "seo"
    if "indicatorVariants" in rel:
        return "variants"
    if "ViewMode" in rel or "viewModeFamilies" in rel or "viewModeEngine" in rel or "GenericIndicatorView" in rel:
        return "family"
    return "other"


def build_file_refs(codes: list[str]) -> dict[str, list[dict]]:
    # Один комбинированный regex со всеми кодами (длинные — первыми), чтобы
    # 'cpi-food' матчился раньше 'cpi'. Границы: символ-код = [a-z0-9-];
    # слева/справа не должно быть [A-Za-z0-9_-].
    ordered = sorted(set(codes), key=lambda c: (-len(c), c))
    alternation = "|".join(re.escape(c) for c in ordered)
    pattern = re.compile(rf"(?<![A-Za-z0-9_-])({alternation})(?![A-Za-z0-9_-])")
    refs: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for p in _text_files():
        rel = str(p.relative_to(ROOT))
        try:
            lines = p.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(lines, 1):
            seen_in_line: set[str] = set()
            for m in pattern.finditer(line):
                code = m.group(1)
                if code in seen_in_line:
                    continue
                seen_in_line.add(code)
                refs[code].append((rel, i))
    out: dict[str, list[dict]] = {}
    for code, occ in refs.items():
        occ_sorted = sorted(set(occ))
        out[code] = [
            {"file": rel, "line": ln, "kind": _classify(rel)}
            for rel, ln in occ_sorted
        ]
    return out


# ---------------------------------------------------------------------------
#  Forecast strategy (резолв как в forecast_pipeline._legacy_resolve_name)
# ---------------------------------------------------------------------------

CPI_BASE = {"cpi", "cpi-food", "cpi-nonfood", "cpi-services"}


def resolve_forecast_strategy(code: str, mc: dict) -> tuple[str | None, str]:
    """Вернуть (strategy, source): explicit | legacy | none."""
    explicit = mc.get("forecast_strategy")
    if explicit:
        return explicit, "explicit"
    steps = int(mc.get("forecast_steps", 0) or 0)
    if steps <= 0:
        return None, "none"
    # legacy_resolve_name из forecast_pipeline
    if mc.get("approved_forecast_values"):
        return "approved", "legacy"
    if code in CPI_BASE:
        return "cpi_combined", "legacy"
    if mc.get("forecast_model") == "housing_quarterly":
        return "housing_quarterly", "legacy"
    return "generic_ols", "legacy"


# ---------------------------------------------------------------------------
#  Сборка карты
# ---------------------------------------------------------------------------

def build_index() -> dict:
    py = load_python_sources()
    js = parse_legacy_js()

    indicators = {i["code"]: i for i in py["indicators"]}
    codes = sorted(indicators)

    # derived: dst → src-список; src → {dst}
    derived_parent: dict[str, str] = {}
    siblings_of: dict[str, set[str]] = defaultdict(set)
    derived_dsts: set[str] = set()
    for dst, srcs in py["derived_specs"]:
        derived_dsts.add(dst)
        if srcs:
            derived_parent[dst] = srcs[0]
        for s in srcs:
            siblings_of[s].add(dst)

    # derived_from_source: model_config.derived_forecast.source_code → code
    for code, ind in indicators.items():
        mc = ind.get("model_config_json") or {}
        df = (mc.get("derived_forecast") or {})
        src = df.get("source_code")
        if src:
            siblings_of[src].add(code)

    family_by_base = py["family_by_base"]
    cpi_set, housing_set, ppi_set = js["cpi"], js["housing"], js["ppi"]
    cbr_set = js["cbr_term"]
    unemp_root = js["unemployment_root"]
    variant_group_of = js["variant_group_of"]
    variant_members = set(variant_group_of)

    def base_stack(code: str) -> str | None:
        # ПОРЯДОК = каскад IndicatorDetail.jsx: generic (early-return) первым.
        if code in family_by_base:
            return "generic"
        if code in cpi_set:
            return "cpi"
        if code in housing_set:
            return "housing"
        if code in ppi_set:
            return "ppi"
        if code in cbr_set:
            return "cbr-term"
        if code == unemp_root:
            return "unemployment"
        if code in variant_members:
            return "variant"
        return None

    def resolve_stack(code: str, _seen: set[str] | None = None) -> tuple[str | None, str | None]:
        """Вернуть (ui_stack, redirect_parent). Для siblings — стек родителя."""
        _seen = _seen or set()
        if code in _seen:
            return None, None
        _seen.add(code)
        s = base_stack(code)
        if s:
            return s, None
        parent = derived_parent.get(code)
        if parent is None and code.startswith("inflation-weekly"):
            parent = "cpi"  # недельный ИПЦ — source, рендерится как режим cpi
        if parent is None:
            return None, None
        ps, _ = resolve_stack(parent, _seen)
        return ps, parent

    # generic-коды (для флагов): generic-базы + siblings, чей стек резолвится в generic
    def is_generic(code: str) -> bool:
        st, _ = resolve_stack(code)
        return st == "generic"

    legacy_js = js["legacy_js_codes"]
    legacy_bespoke_base = cpi_set | housing_set | ppi_set | cbr_set | {unemp_root}

    records: list[dict] = []
    unresolved: list[str] = []
    counts = defaultdict(int)

    all_file_codes = list(codes)
    file_refs = build_file_refs(all_file_codes)

    for code in codes:
        ind = indicators[code]
        mc = ind.get("model_config_json") or {}
        ui_stack, redirect_parent = resolve_stack(code)
        strategy, strat_source = resolve_forecast_strategy(code, mc)
        is_listed = code not in py["hidden"]

        in_both = (code in legacy_js) and is_generic(code)
        shadowed = bool(
            ((code in legacy_js) and is_generic(code))
            or (code in legacy_bespoke_base and code in family_by_base)
        )
        no_stack = ui_stack is None

        if no_stack:
            unresolved.append(code)
        counts[ui_stack or "null"] += 1

        title = py["seo_titles"].get(code) or ind.get("name")
        sibs = sorted(siblings_of.get(code, set()))

        records.append({
            "code": code,
            "title": title,
            "name": ind.get("name"),
            "category": ind.get("category"),
            "frequency": ind.get("frequency"),
            "source": ind.get("source"),
            "parser_type": ind.get("parser_type"),
            "is_listed": is_listed,
            "is_derived": ind.get("parser_type") == "derived",
            "monthly_auto": code in py["monthly_auto"],
            "forecast_strategy": strategy,
            "forecast_strategy_source": strat_source,
            "forecast_steps": int(mc.get("forecast_steps", 0) or 0),
            "ui_stack": ui_stack,
            "redirect_parent": redirect_parent,
            "variant_group": variant_group_of.get(code),
            "derived_siblings": sibs,
            "flags": {
                "in_both_viewmode_systems": in_both,
                "shadowed_legacy": shadowed,
                "in_seed_no_ui_stack": no_stack,
            },
            "files": file_refs.get(code, []),
        })

    # derived dst, отсутствующие в seed (orphan-кандидаты)
    derived_not_seeded = sorted(d for d in derived_dsts if d not in indicators)

    index = {
        "generated_by": "scripts/build-indicator-index.py",
        "do_not_edit": True,
        "summary": {
            "total_codes": len(records),
            "by_ui_stack": dict(sorted(counts.items())),
            "in_both_viewmode_systems": sum(
                1 for r in records if r["flags"]["in_both_viewmode_systems"]
            ),
            "shadowed_legacy": sum(
                1 for r in records if r["flags"]["shadowed_legacy"]
            ),
            "unresolved": len(unresolved),
            "derived_not_seeded": len(derived_not_seeded),
        },
        "unresolved": sorted(unresolved),
        "derived_not_seeded": derived_not_seeded,
        "indicators": sorted(records, key=lambda r: r["code"]),
    }
    return index


def render_md(index: dict) -> str:
    s = index["summary"]
    out: list[str] = []
    out.append("# Indicator index — карта индикаторов")
    out.append("")
    out.append(
        "> Генерируется `scripts/build-indicator-index.py`. НЕ редактировать руками. "
        "Полная машинная версия — `docs/indicator-index.json`. "
        "Подробности по каждому коду (files/derived_siblings) — в JSON."
    )
    out.append("")
    out.append(head_stamp())
    out.append("")
    out.append("## Как пользоваться (для агента)")
    out.append("")
    out.append("1. `python scripts/locate-indicator.py <code>` — где код вообще встречается.")
    out.append("2. Найди запись `<code>` в `docs/indicator-index.json`.")
    out.append("3. Правь стек из `ui_stack`. `flags.shadowed_legacy=true` — standalone-ветка "
               "рендера в `IndicatorDetail.jsx` перекрыта generic, НО bespoke content/resolve "
               "часто переиспользуются общими секциями + держат старые URL-редиректы → НЕ "
               "удалять вслепую (см. `dead-code-report.md`).")
    out.append("")
    out.append("**ui_stack** определяется как реальный каскад `IndicatorDetail.jsx` "
               "(generic early-return проверяется первым):")
    out.append("")
    out.append("| Стек | Где правится UI |")
    out.append("|------|-----------------|")
    out.append("| `generic` | `backend/app/data/view_model_families.py` → `viewModelFamilies.generated.json` → `GenericIndicatorView` |")
    out.append("| `cpi` | `frontend/src/lib/cpiViewMode*` + `CpiIndicatorControls` |")
    out.append("| `housing` | `frontend/src/lib/housingViewMode*` + `HousingIndicatorControls` |")
    out.append("| `ppi` | `frontend/src/lib/ppiViewMode*` + `PpiIndicatorControls` |")
    out.append("| `cbr-term` | `cbrTermSliceRate*` — рендер через generic + общие секции; content/resolve ЖИВЫЕ (chart/table title, picker) |")
    out.append("| `unemployment` | `unemploymentViewMode*` — рендер через generic + общие секции; canonical-редирект старых URL ЖИВОЙ |")
    out.append("| `variant` | `frontend/src/lib/indicatorVariants.js` + `VariantGroupPicker` |")
    out.append("")
    out.append("## Сводка")
    out.append("")
    out.append(f"- Всего кодов: **{s['total_codes']}**")
    out.append(f"- in_both_viewmode_systems (дубль легаси+generic): **{s['in_both_viewmode_systems']}**")
    out.append(f"- shadowed_legacy (мёртвая легаси-ветка): **{s['shadowed_legacy']}**")
    out.append(f"- unresolved (нет ui_stack): **{s['unresolved']}**")
    out.append(f"- derived_not_seeded: **{s['derived_not_seeded']}**")
    out.append("")
    out.append("По стекам: " + ", ".join(f"`{k}`={v}" for k, v in s["by_ui_stack"].items()))
    out.append("")
    if index["unresolved"]:
        out.append("### Unresolved (ui_stack=null)")
        out.append("")
        out.append(", ".join(f"`{c}`" for c in index["unresolved"]))
        out.append("")
    out.append("## Все индикаторы")
    out.append("")
    out.append("| Код | Категория | Частота | Стек | Стратегия | Listed | Флаги |")
    out.append("|-----|-----------|---------|------|-----------|:------:|-------|")
    for r in index["indicators"]:
        fl = []
        if r["flags"]["in_both_viewmode_systems"]:
            fl.append("both")
        if r["flags"]["shadowed_legacy"]:
            fl.append("shadowed")
        if r["flags"]["in_seed_no_ui_stack"]:
            fl.append("no-stack")
        flags = ", ".join(fl) or "—"
        listed = "✓" if r["is_listed"] else "—"
        out.append(
            f"| `{r['code']}` | {r['category'] or '—'} | {r['frequency'] or '—'} | "
            f"`{r['ui_stack'] or 'null'}` | {r['forecast_strategy'] or '—'} | {listed} | {flags} |"
        )
    out.append("")
    return "\n".join(out)


def _legacy_files(record: dict) -> list[dict]:
    out = []
    for f in record["files"]:
        if any(marker in f["file"] for marker in _LEGACY_FILE_MARKERS):
            out.append(f)
    return out


def render_dead_code(index: dict) -> str:
    s = index["summary"]
    both = [r for r in index["indicators"] if r["flags"]["in_both_viewmode_systems"]]
    shadowed = [r for r in index["indicators"] if r["flags"]["shadowed_legacy"]]
    out: list[str] = []
    out.append("# Dead / duplicate view-mode code report")
    out.append("")
    out.append(
        "> Генерируется `scripts/build-indicator-index.py` из флагов карты. "
        "НЕ редактировать руками. Это **список на расследование, НЕ слепой "
        "delete-list**. Флаги ловят shadowing standalone-ветки рендера в "
        "`IndicatorDetail.jsx`, но НЕ доказывают, что легаси-код мёртв: см. "
        "раздел «Почему это НЕ delete-list» ниже. Источник флагов — "
        "`docs/indicator-index.json`."
    )
    out.append("")
    out.append(head_stamp())
    out.append("")
    out.append("## Почему это НЕ delete-list (расследование 2026-06-24)")
    out.append("")
    out.append("Попытка чистки view-mode показала, что помеченное флагами легаси "
               "**живое** по двум независимым причинам — удалять нельзя без эскалации:")
    out.append("")
    out.append("1. **Живые canonical-редиректы старых URL.** `IndicatorDetail.jsx` "
               "редиректит старые derived-URL на родительскую карточку через легаси "
               "`viewModeCanonicalTarget` / `unemploymentCanonicalTarget`. Коды "
               "`trade-balance-yoy-abs`, `current-account-yoy-abs`, "
               "`unemployment-quarterly`, `unemployment-annual` **отсутствуют** в "
               "generated-конфиге → их редирект держится ТОЛЬКО на легаси. Эти URL "
               "в sitemap (индексируются) — удаление тихо ломает SEO, тесты не ловят. "
               "ЭСКАЛАЦИЯ.")
    out.append("2. **bespoke content переиспользуется живыми секциями.** "
               "`cbrTermSliceRate*` / `unemploymentViewMode*` импортируются в "
               "`IndicatorChartSection.jsx`, `IndicatorDataTableSection.jsx`, "
               "`cpiViewModeContent.jsx`, `useIndicatorViewModeData.js`, picker-groups — "
               "т.е. заголовки графика/таблицы и резолв режимов живут через общие "
               "секции, а не только через standalone-ветку. Файлы НЕ мёртвые.")
    out.append("")
    out.append("Вывод: `shadowed_legacy`/`in_both` = «standalone-ветка рендера "
               "перекрыта», НЕ «файл можно удалить». Перед любым удалением — проверить "
               "(а) покрывает ли generated-движок старый URL, (б) импорты экспортов.")
    out.append("")
    out.append("## Что значат флаги")
    out.append("")
    out.append("- **in_both_viewmode_systems** — код объявлен И в легаси "
               "`frontend/src/lib/viewModeFamilies.js`, И в config-driven движке "
               "(`view_model_families.py` → `viewModelFamilies.generated.json`).")
    out.append("- **shadowed_legacy** — standalone-ветка рендера в `IndicatorDetail.jsx` "
               "недостижима (generic early-return ПЕРВЫМ). НЕ значит, что легаси-файл "
               "мёртв — см. раздел выше (живые редиректы + переиспользование секциями).")
    out.append("")
    out.append(f"Итог: in_both={s['in_both_viewmode_systems']}, shadowed_legacy={s['shadowed_legacy']}.")
    out.append("")
    out.append("## in_both_viewmode_systems — легаси-trade vs generated")
    out.append("")
    out.append("Коды есть и в `viewModeFamilies.js`, и в generated-конфиге. Для "
               "`*-yoy`/`*-qoq`/`*-mom`, покрытых движком, легаси-запись мёртвая. Но "
               "`*-yoy-abs` движок НЕ покрывает → их легаси canonical-редирект живой "
               "(см. раздел выше). Удаление — только после эскалации по старым URL.")
    out.append("")
    if both:
        out.append("| Код | ui_stack | Легаси-запись (файл:строка) | Перекрыто (generated) |")
        out.append("|-----|----------|------------------------------|------------------------|")
        for r in both:
            legacy = _legacy_files(r)
            legacy_str = "; ".join(f"`{f['file']}:{f['line']}`" for f in legacy) or "— (см. files в JSON)"
            override = "`view_model_families.py` (generic base "
            override += f"`{r['redirect_parent'] or r['code']}`)"
            out.append(f"| `{r['code']}` | `{r['ui_stack']}` | {legacy_str} | {override} |")
    else:
        out.append("_нет_")
    out.append("")
    out.append("## shadowed_legacy — standalone-ветка перекрыта (НЕ значит «удалить»)")
    out.append("")
    out.append("Bespoke-стеки `cbr-term` (ставки по сроку) и `unemployment`: их "
               "standalone-ветка рендера в `IndicatorDetail.jsx` перекрыта generic-движком "
               "(`view_model_families.py` содержит эти базы как T2y-семьи). НО файлы "
               "`cbrTermSliceRate*` / `unemploymentViewMode*` **живые** — их content/resolve "
               "переиспользуются общими секциями (chart/table title, режимы, picker), а "
               "canonical-редиректы держат старые URL `unemployment-quarterly/-annual`. "
               "Удалять нельзя (см. раздел «Почему это НЕ delete-list»).")
    out.append("")
    out.append("| Код | ui_stack | Легаси-файлы (file:line) |")
    out.append("|-----|----------|--------------------------|")
    for r in shadowed:
        legacy = _legacy_files(r)
        legacy_str = "; ".join(f"`{f['file']}:{f['line']}`" for f in legacy) or "— (см. files в JSON)"
        out.append(f"| `{r['code']}` | `{r['ui_stack']}` | {legacy_str} |")
    out.append("")
    out.append("## Рекомендации (требуют продуктового решения — ЭСКАЛАЦИЯ)")
    out.append("")
    out.append("Чистка этого слоя НЕ автономна: упирается в старые индексируемые URL. "
               "Прежде чем резать — решить с владельцем:")
    out.append("")
    out.append("1. **Старые derived-URL** `trade-balance-yoy-abs`, `current-account-yoy-abs`, "
               "`unemployment-quarterly`, `unemployment-annual` (в sitemap, движком НЕ "
               "покрыты): держим легаси-редирект как есть, или консолидируем ряды в движок "
               "(`*-yoy-abs` → `*-yoy`) с 301-картой? Второе — отдельная задача с правкой "
               "seed/derived/sitemap.")
    out.append("2. Только ПОСЛЕ решения по (1): живые редиректы вынести в явную redirect-карту, "
               "затем убрать мёртвую standalone-ветку рендера. content/resolve, "
               "переиспользуемые секциями, НЕ трогать.")
    out.append("3. После любой правки — `python scripts/build-indicator-index.py` и "
               "`./scripts/check-all.sh`.")
    out.append("")
    return "\n".join(out)


def main() -> int:
    index = build_index()
    index["completeness"] = completeness.build_completeness()
    md = render_md(index)
    comp_md = completeness.render_md(index["completeness"])
    dead = render_dead_code(index)
    json_text = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    md_text = md + "\n\n" + comp_md + "\n"
    dead_text = dead + "\n"

    targets = [(OUT_JSON, json_text), (OUT_MD, md_text), (OUT_DEAD, dead_text)]

    if "--check" in sys.argv:
        ok = True
        for path, text in targets:
            if not path.exists() or _strip_stamp(
                path.read_text(encoding="utf-8")
            ) != _strip_stamp(text):
                print(
                    f"indicator-index: {path.name} расходится с кодом — "
                    "запусти scripts/build-indicator-index.py",
                    file=sys.stderr,
                )
                ok = False
        if ok:
            print("indicator-index: --check OK (карта актуальна)")
            return 0
        return 1

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    for path, text in targets:
        path.write_text(text, encoding="utf-8")
    s = index["summary"]
    print(
        "indicator-index: wrote "
        f"{OUT_JSON.relative_to(ROOT)} + {OUT_MD.relative_to(ROOT)} + {OUT_DEAD.relative_to(ROOT)}"
    )
    print(
        f"  codes={s['total_codes']} unresolved={s['unresolved']} "
        f"in_both={s['in_both_viewmode_systems']} shadowed={s['shadowed_legacy']}"
    )
    cs = index["completeness"]["summary"]
    print(
        f"  completeness: roots={cs['roots_total']} "
        f"complete={cs['roots_complete_matrix']} gaps={cs['roots_with_gaps']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
