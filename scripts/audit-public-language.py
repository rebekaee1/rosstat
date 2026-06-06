#!/usr/bin/env python3
"""
Аудит публичного языка: ищет «внутренности» в полях, которые видит пользователь сайта.

Сканирует:
  - backend/seed_data.py — поля description / methodology / seo_title / seo_description / name
  - backend/app/services/seo_content.py — CATEGORY_META, любые user-visible тексты
  - frontend/src/lib/categories.js — UI карточки категорий
  - frontend/src/lib/cpiViewModeContent.jsx — режимные тексты ИПЦ (состав × режим)

Правило закреплено в .cursor/rules/methodology-language.mdc.

Запуск: python3 scripts/audit-public-language.py
Exit code: 0 — чисто, 1 — найдены утечки.
"""
from __future__ import annotations
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BAD_PATTERNS = [
    r'\.(pdf|xlsx?|csv|xml|json)\b',
    r'\{(MM|YYYY|YY)\}',
    r'\b(парсер|парсера|парсеру|cumulative|chain[\s\']?ит|chain to|chains|splice|overlap-год|bulk_upsert|регекс)\b',
    r'\b(SDDS|ADR-?\d+|publicationId|datasetId|element_id|measureId)\b',
    r'\b(path P|compat|legacy|fallback)\b',
    r'(лист\s+\d|строка\s+\d|колонк[аи]\s*[A-Z])',
    r'osn-', r'ind_baza', r'VVP_kvartal', r'GDP-quarters-of-use', r'bal_of_payments',
    r'/folder/\d+',
]
master = re.compile('|'.join(BAD_PATTERNS), re.IGNORECASE)

PUBLIC_FIELDS = ('name', 'description', 'methodology', 'seo_title', 'seo_description')

def scan_seed() -> list[tuple[str, str, str]]:
    seed_path = ROOT / 'backend' / 'seed_data.py'
    tree = ast.parse(seed_path.read_text(encoding='utf-8'))
    indicators = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'INDICATORS' for t in node.targets
        ):
            indicators = node.value
            break
    if not isinstance(indicators, ast.List):
        return []
    issues = []
    for elem in indicators.elts:
        if not isinstance(elem, ast.Dict):
            continue
        rec = {}
        for k, v in zip(elem.keys, elem.values):
            if isinstance(k, ast.Constant):
                try:
                    rec[k.value] = ast.literal_eval(v)
                except Exception:
                    pass
        code = rec.get('code', '???')
        for field in PUBLIC_FIELDS:
            text = rec.get(field)
            if not text or not isinstance(text, str):
                continue
            if master.search(text):
                issues.append((code, field, text[:240].replace('\n', ' ')))
    return issues

def scan_file(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding='utf-8')
    lines = text.split('\n')
    out = []
    for m in master.finditer(text):
        line_no = text[:m.start()].count('\n') + 1
        out.append((line_no, lines[line_no - 1][:200]))
    return out

def main() -> int:
    leaks = 0
    seed_issues = scan_seed()
    if seed_issues:
        leaks += len(seed_issues)
        print(f'\n[seed_data.py] {len(seed_issues)} leaks:')
        for code, field, preview in seed_issues:
            print(f'  {code} | {field}')
            print(f'    {preview}')

    for rel in (
        'backend/app/services/seo_content.py',
        'frontend/src/lib/categories.js',
        'frontend/src/lib/cpiViewModeContent.jsx',
    ):
        p = ROOT / rel
        if not p.exists():
            continue
        hits = scan_file(p)
        if hits:
            leaks += len(hits)
            print(f'\n[{rel}] {len(hits)} leaks:')
            for line_no, line in hits:
                print(f'  line {line_no}: {line}')

    if leaks == 0:
        print('OK: no public-language leaks found.')
        return 0
    print(f'\nFAIL: {leaks} total leaks. See .cursor/rules/methodology-language.mdc.')
    return 1

if __name__ == '__main__':
    sys.exit(main())
