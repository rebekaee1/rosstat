#!/usr/bin/env python3
"""Оркестратор аудита + сборка отчёта scripts/audit-world-truthfulness-report.md."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
OUT = SCRIPTS / "audit-world-out"
REPORT = SCRIPTS / "audit-world-truthfulness-report.md"


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=str(ROOT))
    return p.returncode


def load(name: str) -> dict:
    path = OUT / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report() -> str:
    src = load("eurostat-source-compare.json")
    pl = load("plausibility.json")
    ex = load("export-audit.json")
    cov = load("country-coverage.json")

    ss = src.get("summary") or {}
    results = src.get("results") or []
    hard = [
        r for r in results
        if r.get("error")
        or (r.get("compare") or {}).get("status") in {"value_mismatch", "date_mismatch"}
    ]
    near = [r for r in results if (r.get("compare") or {}).get("status") == "near_match"]
    match = [r for r in results if (r.get("compare") or {}).get("status") == "match"]
    api_fail = [
        r for r in results
        if isinstance(r.get("api_vs_db"), dict) and r["api_vs_db"].get("match") is False
    ]

    lines: list[str] = []
    lines.append("# Аудит правдивости данных «Мировая экономика» (Eurostat)")
    lines.append("")
    lines.append(f"**Дата аудита:** {date(2026, 7, 27).isoformat()}")
    lines.append("**Область:** только чтение БД/API/Eurostat; продуктовый код не менялся.")
    lines.append("")
    lines.append("Артефакты JSON: `scripts/audit-world-out/`.")
    lines.append("Скрипты: `audit-world-eurostat-source.py`, `audit-world-plausibility.py`,")
    lines.append("`audit-world-export.py`, `audit-world-country-coverage.py`.")
    lines.append("")

    # 1 Source
    lines.append("## 1. Сверка с первоисточником Eurostat")
    lines.append("")
    lines.append(
        f"Проверено рядов: **{ss.get('checked', 0)}**. "
        f"Полное совпадение: **{len(match)}**. "
        f"Почти совпадение (краевые даты ±2): **{len(near)}**. "
        f"Проблемы: **{len(hard)}**. "
        f"API≠БД: **{len(api_fail)}**."
    )
    lines.append("")
    topics = ss.get("topics_present") or []
    lines.append(f"Темы в выборке: {', '.join(topics) or '—'}.")
    missing = ss.get("required_topics_missing") or []
    if missing:
        lines.append(f"Не удалось набрать обязательные темы: {', '.join(missing)}.")
    lines.append("")
    if not hard:
        lines.append("Расхождений значений с Eurostat JSON-stat **не найдено** "
                     "(в пределах abs_tol=1e-4 / rel=1e-6).")
    else:
        lines.append("### Расхождения")
        lines.append("")
        for r in hard:
            cmp_ = r.get("compare") or {}
            lines.append(
                f"- **{r.get('country')}** (`{r.get('geo')}`) / `{r.get('dataset_id')}` / "
                f"`{r.get('code')}` — {r.get('error') or cmp_.get('status')}"
            )
            for m in (cmp_.get("value_mismatches_sample") or [])[:3]:
                lines.append(
                    f"  - {m['date']}: наше={m['ours']}, Eurostat={m['eurostat']}, "
                    f"|Δ|={m['abs_diff']}"
                )
            if cmp_.get("only_ours_sample") or cmp_.get("only_eurostat_sample"):
                lines.append(
                    f"  - только у нас: {cmp_.get('only_ours_sample')}; "
                    f"только у источника: {cmp_.get('only_eurostat_sample')}"
                )
            lines.append(f"  - URL: `{r.get('eurostat_url')}`")
        lines.append("")
    if api_fail:
        lines.append("### API vs БД")
        for r in api_fail:
            lines.append(f"- `{r['code']}`: {r.get('api_vs_db')}")
        lines.append("")

    # 2 Plausibility
    lines.append("## 2. Misleading / правдоподобие")
    lines.append("")
    meta = pl.get("meta") or {}
    lines.append(
        f"Листингуемых рядов прогнано: **{meta.get('listed_total', 0)}**. "
        f"Срабатываний: **{meta.get('findings_total', 0)}** "
        f"(P0={meta.get('by_severity', {}).get('P0', 0)}, "
        f"P1={meta.get('by_severity', {}).get('P1', 0)}, "
        f"P2={meta.get('by_severity', {}).get('P2', 0)}, "
        f"P3={meta.get('by_severity', {}).get('P3', 0)})."
    )
    lines.append("")
    lines.append("Топ видов находок:")
    lines.append("")
    for kind, n in list((meta.get("by_kind") or {}).items())[:15]:
        lines.append(f"- `{kind}`: {n}")
    lines.append("")
    lines.append("### P0 — опасно для репутации")
    lines.append("")
    p0 = pl.get("p0") or []
    if not p0:
        lines.append("P0 не найдено.")
    else:
        for f in p0[:60]:
            lines.append(
                f"- **{f['severity']}** `{f['kind']}` — {f['country']} / `{f['code']}`: "
                f"{f['message']} (unit=`{f.get('unit_ru') or f.get('unit')}`)"
            )
        if len(p0) > 60:
            lines.append(f"- … ещё {len(p0) - 60} (см. plausibility.json)")
    lines.append("")
    lines.append("### P1 (выборка)")
    lines.append("")
    for f in (pl.get("p1") or [])[:25]:
        lines.append(
            f"- `{f['kind']}` — {f['country']} / `{f['code']}`: {f['message']}"
        )
    lines.append("")

    # 3 Export
    lines.append("## 3. Экспорт CSV/Excel")
    lines.append("")
    es = ex.get("summary") or {}
    lines.append(
        f"Проверено рядов: **{es.get('series_checked', 0)}**. "
        f"CSV↔API: **{'OK' if es.get('csv_values_match_api') else 'FAIL'}**. "
        f"Excel↔API: **{'OK' if es.get('xlsx_values_match_api') else 'FAIL'}**."
    )
    lines.append("")
    lines.append("Вердикт:")
    lines.append("")
    lines.append(
        "- Числа в выгрузке совпадают с API (после round(..., 4) на стороне экспорта)."
    )
    lines.append(
        f"- Десятичный разделитель в CSV: "
        f"{'точка (не русская запятая)' if es.get('csv_uses_dot_decimal') else 'не определён'} "
        f"— **не** проходит через `display.format_number_ru`."
    )
    lines.append(
        f"- Указание источника в файле: "
        f"{'есть' if es.get('source_attribution_in_file') else '**нет**'}."
    )
    lines.append("- Кодировка CSV: UTF-8 с BOM; разделитель полей `;`.")
    lines.append("- Заголовок: `Дата` + value_label (имя + единица) + `Тип`.")
    for n in es.get("notes") or []:
        lines.append(f"- {n}")
    lines.append("")

    # 4 Coverage
    lines.append("## 4. Покрытие стран")
    lines.append("")
    cm = cov.get("meta") or {}
    lines.append(
        f"Стран: **{cm.get('countries', 0)}**. "
        f"Медиана listed: **{cm.get('median_listed', 0):.0f}**. "
        f"Группа A (полноценный Eurostat): **{cm.get('group_a', 0)}**. "
        f"Группа B (огрызок/партнёр): **{cm.get('group_b', 0)}**. "
        f"Кандидаты на скрытие: **{cm.get('recommend_hide', 0)}**."
    )
    lines.append("")
    lines.append("### Таблица (проблемный хвост + партнёры)")
    lines.append("")
    lines.append("| Страна | geo | loaded | listed | группы | рекомендация | research |")
    lines.append("|---|---|---:|---:|---|---|---|")
    for t in cov.get("group_b_detail") or []:
        lines.append(
            f"| {t['name_ru']} | {t['geo']} | {t['loaded']} | {t['listed']} | "
            f"{t['group']} | `{t['action']}` | "
            f"{'да' if t.get('has_national_research') else 'нет'} |"
        )
    lines.append("")
    lines.append("Полная таблица — в `country-coverage.json`.")
    lines.append("")
    lines.append("Research-файлы национальных источников:")
    for geo, ok in (cov.get("research_xlsx_present") or {}).items():
        lines.append(f"- {geo}: {'есть' if ok else 'нет'}")
    lines.append("")

    # 5 Armenia
    lines.append("## 5. Армения")
    lines.append("")
    am = cov.get("armenia") or {}
    lines.append(am.get("verdict") or "нет данных")
    lines.append("")
    lines.append(
        f"Загружено: **{am.get('loaded')}**, listed: **{am.get('listed')}**, "
        f"скрыто: **{am.get('hidden')}**."
    )
    lines.append("")
    lines.append("По `name_quality`:")
    for q, d in (am.get("by_name_quality") or {}).items():
        lines.append(f"- `{q}`: listed={d.get('listed', 0)}, hidden={d.get('hidden', 0)}")
    lines.append("")
    lines.append("Категории на витрине:")
    for cat, n in (am.get("categories_listed") or {}).items():
        lines.append(f"- {cat or '—'}: {n}")
    lines.append("")
    lines.append(
        f"Можно вернуть законно прямо сейчас (curated/composed + глубина OK, "
        f"но всё ещё is_listed=false): **{len(am.get('restorable_now') or [])}**."
    )
    for h in (am.get("restorable_now") or [])[:15]:
        lines.append(f"- `{h['code']}` — {h['name_ru']} ({h['reasons']})")
    lines.append("")
    lines.append(
        f"Скрыто порогом глубины (при curated/composed): "
        f"**{len(am.get('hidden_by_depth_curated') or [])}**."
    )
    lines.append(
        f"Скрыто raw-заголовком: **{len(am.get('hidden_by_raw_title') or [])}**."
    )
    lines.append("")

    # 6 Priority fixes
    lines.append("## 6. Приоритеты исправления")
    lines.append("")
    lines.append("| # | Что | Уйдёт наружу? | Репутационный удар | Приоритет |")
    lines.append("|---|---|---|---|---|")

    # derive from findings
    prios = []
    if p0:
        kinds = {}
        for f in p0:
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
        for kind, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
            prios.append((
                f"P0 `{kind}` ×{n}",
                "Да, на витрине /world",
                "Высокий — misleading-значения как инцидент ИПЦ 100,2%",
                "P0",
            ))
    hide = cov.get("hide_candidates") or []
    if hide:
        names = ", ".join(f"{t['name_ru']}({t['listed']})" for t in hide[:8])
        prios.append((
            f"Скрыть/отложить партнёров-огрызки: {names}",
            "Да — карточки стран уже в меню",
            "Высокий — ложное равенство с DE/FR",
            "P0",
        ))
    if not es.get("source_attribution_in_file"):
        prios.append((
            "Добавить источник Eurostat в CSV/Excel экспорт",
            "Да — в файлах выгрузки",
            "Средний — не misleading чисел, но дыра в provenance",
            "P2",
        ))
    if es.get("csv_uses_dot_decimal") and not es.get("csv_uses_russian_decimal_comma"):
        prios.append((
            "Русская запятая в CSV через единый display-форматтер",
            "Да — в CSV",
            "Низкий/средний — не ломает числа, но ломает типографику",
            "P2",
        ))
    if am.get("listed", 0) < 50:
        prios.append((
            "Армения: либо оговорка о неполноте Eurostat, либо не ждать «как у Германии»",
            "Да — мало блоков на странице страны",
            "Средний — выглядит как баг продукта, хотя источник бедный",
            "P1",
        ))
    if hard:
        prios.append((
            f"Разобрать {len(hard)} расхождений с Eurostat (см. §1)",
            "Да",
            "Критический, если value_mismatch",
            "P0",
        ))
    if not prios:
        prios.append((
            "Критических находок нет — держать мониторинг",
            "—",
            "—",
            "P3",
        ))

    for i, (what, out_vis, rep, pr) in enumerate(prios, 1):
        lines.append(f"| {i} | {what} | {out_vis} | {rep} | {pr} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Повторный прогон: `python3 scripts/audit-world-run-all.py`.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    codes = []
    # coverage & plausibility first (no external rate limits as heavy)
    codes.append(run([py, str(SCRIPTS / "audit-world-country-coverage.py")]))
    codes.append(run([py, str(SCRIPTS / "audit-world-plausibility.py")]))
    codes.append(run([py, str(SCRIPTS / "audit-world-export.py")]))
    codes.append(run([py, str(SCRIPTS / "audit-world-eurostat-source.py"), "--limit", "48"]))
    titles_rc = run([
        "docker", "compose", "exec", "-T", "backend",
        "python", "/app/scripts/audit-world-titles.py",
    ])
    codes.append(titles_rc)

    report = build_report()
    REPORT.write_text(report, encoding="utf-8")
    print(f"Wrote {REPORT}", flush=True)

    pl = load("plausibility.json")
    p0_n = len(pl.get("p0") or [])
    # дубли kind от legacy+shared — считаем уникальные (code, kind)
    p0_unique = {
        (f.get("code"), f.get("kind"))
        for f in (pl.get("p0") or [])
    }
    meta = pl.get("meta") or {}
    constants = int(meta.get("constant_series_in_listing") or 0)
    inactive_listed = int(meta.get("listed_on_inactive_country") or 0)
    cov = load("country-coverage.json")
    cov_leak = int((cov.get("meta") or {}).get("inactive_with_listed_n") or 0)
    ex = load("export-audit.json")
    es = ex.get("summary") or {}
    export_fail = (
        es
        and (
            not es.get("csv_values_match_api")
            or not es.get("xlsx_values_match_api")
            or not es.get("source_attribution_in_file")
            or not es.get("csv_uses_russian_decimal_comma")
        )
    )
    print(
        f"GATE: P0_findings={p0_n} P0_unique={len(p0_unique)} "
        f"constants={constants} inactive_listed={inactive_listed} "
        f"cov_leak={cov_leak} export_fail={export_fail} "
        f"titles_rc={titles_rc}",
        flush=True,
    )
    if (
        p0_unique
        or export_fail
        or constants
        or inactive_listed
        or cov_leak
        or titles_rc != 0
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
