#!/usr/bin/env python3
"""
Аудит публичного языка: ищет «внутренности» и устаревшие product-claims
в полях/файлах, которые видит пользователь сайта.

Сканирует:
  - backend/seed_data.py — поля description / methodology / seo_title / seo_description / name
  - backend/app/services/seo_content.py — CATEGORY_META, любые user-visible тексты
  - frontend/src/lib/categories.js — UI карточки категорий
  - frontend/src/lib/cpiViewModeContent.jsx — режимные тексты ИПЦ (состав × режим)
  - product-surfaces (About/Privacy/Terms/Footer/RegisterNudge/index.html/llms.txt)
    + banlist устаревших product-claims (80+/9/девяти, ложный guest-quota, overclaim мира)

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

# «Внутренности» реализации — нельзя в user-visible текстах.
INTERNAL_PATTERNS = [
    r'\.(pdf|xlsx?|csv|xml|json)\b',
    r'\{(MM|YYYY|YY)\}',
    r'\b(парсер|парсера|парсеру|cumulative|chain[\s\']?ит|chain to|chains|splice|overlap-год|bulk_upsert|регекс)\b',
    r'\b(SDDS|ADR-?\d+|publicationId|datasetId|element_id|measureId)\b',
    r'\b(path P|compat|legacy|fallback)\b',
    r'(лист\s+\d|строка\s+\d|колонк[аи]\s*[A-Z])',
    r'osn-', r'ind_baza', r'VVP_kvartal', r'GDP-quarters-of-use', r'bal_of_payments',
    r'/folder/\d+',
]
INTERNAL_RE = re.compile('|'.join(INTERNAL_PATTERNS), re.IGNORECASE)

# Устаревшие / вводящие в заблуждение product-claims на маркетинговых поверхностях.
PRODUCT_CLAIM_PATTERNS = [
    r'\b80\s*\+',
    r'\bв\s+9\s+категори',
    r'\b9\s+категори',
    r'\bдевяти\b',
    r'стран\s+мира',
    r'всей?\s+мир[ае]?\b',
    r'по\s+всем\s+странам',
    r'данных?\s+всего\s+мира',
    r'снимает\s+лимит',
    r'лимит\s+на\s+выгруз',
    r'лимит\s+бесплатных\s+выгрузок',
    r'выгрузк\w*\s+без\s+регистрац',
    r'скачиван\w*\s+без\s+регистрац',
    r'весь\s+аналитический\s+контент\s+Сайта\s+доступен\s+без\s+регистрац',
    r'доступ\s+к\s+Сайту\s+предоставляется\s+без\s+регистрац',
]
PRODUCT_CLAIM_RE = re.compile('|'.join(PRODUCT_CLAIM_PATTERNS), re.IGNORECASE)

PUBLIC_FIELDS = ('name', 'description', 'methodology', 'seo_title', 'seo_description')

INTERNAL_SURFACES = (
    'backend/app/services/seo_content.py',
    'frontend/src/lib/categories.js',
    'frontend/src/lib/cpiViewModeContent.jsx',
)

PRODUCT_SURFACES = (
    'frontend/src/pages/About.jsx',
    'frontend/src/pages/Privacy.jsx',
    'frontend/src/pages/Terms.jsx',
    'frontend/src/components/Footer.jsx',
    'frontend/src/components/RegisterNudge.jsx',
    'frontend/index.html',
    'frontend/public/llms.txt',
)

PRODUCT_CLAIM_ONLY_SURFACES = (
    'backend/app/services/seo_content.py',
    'backend/app/services/seo_renderer.py',
    # Публичные тексты SPA живут в словарях, а не в компонентах: после i18n
    # именно здесь появляются product-claims про охват и лимиты выгрузок.
    'frontend/src/i18n/messages.ru.js',
    'frontend/src/i18n/messages.en.js',
    'frontend/src/pages/Dashboard.jsx',
    'frontend/src/components/home/HomeHero.jsx',
    'frontend/src/components/home/HomeCountryList.jsx',
    'frontend/src/components/home/HomeWorkbench.jsx',
)

# EN-поверхности, где кириллица = утечка. Словарь messages.en.js содержит
# «Русский» у переключателя языка — это имя целевого языка, не утечка.
EN_NO_CYRILLIC = (
    'frontend/src/lib/compareCompatibility.js',
    'frontend/src/i18n/messages.en.js',
    'backend/app/data/i18n/indicator_copy_en.py',
)
EN_CYRILLIC_ALLOW = {
    'frontend/src/i18n/messages.en.js': ('Русский',),
}
CYRILLIC_RE = re.compile(r'[А-Яа-яЁё]')


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
            if INTERNAL_RE.search(text):
                issues.append((code, field, text[:240].replace('\n', ' ')))
    return issues


_URL_EXT = re.compile(r'^\.(pdf|xlsx?|csv|xml|json)$', re.IGNORECASE)
_COMMENT_RE = re.compile(
    r'//.*?$|/\*.*?\*/|<!--.*?-->',
    re.MULTILINE | re.DOTALL,
)


def _is_url_path_extension(text: str, start: int, matched: str) -> bool:
    """Не считать утечкой суффикс URL вроде /sitemap.xml или https://…/feed.xml."""
    if not _URL_EXT.match(matched):
        return False
    before = text[max(0, start - 12):start]
    return '/' in before or '://' in before


def _strip_comments(text: str) -> str:
    """Убрать JS/JSX/HTML-комментарии, сохранив длины строк (замена пробелами)."""
    def repl(m: re.Match[str]) -> str:
        return re.sub(r'[^\n]', ' ', m.group(0))

    return _COMMENT_RE.sub(repl, text)


def scan_file(
    path: Path,
    pattern: re.Pattern[str],
    *,
    strip_comments: bool = False,
) -> list[tuple[int, str]]:
    raw = path.read_text(encoding='utf-8')
    text = _strip_comments(raw) if strip_comments else raw
    lines = raw.split('\n')
    out = []
    for m in pattern.finditer(text):
        if _is_url_path_extension(text, m.start(), m.group(0)):
            continue
        line_no = text[:m.start()].count('\n') + 1
        out.append((line_no, lines[line_no - 1][:200]))
    return out


def collect_issues() -> list[tuple[str, str]]:
    """Возвращает список (location, preview) для печати и тестов."""
    found: list[tuple[str, str]] = []

    for code, field, preview in scan_seed():
        found.append((f'seed_data.py:{code}:{field}', preview))

    # Квантифицированные строки витрины главной (число + подпись в соседних
    # ключах i18n, например «48» + «стран мира») — официальный факт, а не
    # overclaim; синхронно с QUANTIFIED_LINE в publicProductClaims.test.js.
    quantified = re.compile(r"'home\.scope\.stat\.")

    for rel in INTERNAL_SURFACES:
        p = ROOT / rel
        if not p.exists():
            found.append((rel, 'MISSING FILE'))
            continue
        for line_no, line in scan_file(p, INTERNAL_RE):
            found.append((f'{rel}:{line_no}', line))

    for rel in PRODUCT_SURFACES:
        p = ROOT / rel
        if not p.exists():
            found.append((rel, 'MISSING FILE'))
            continue
        # В JSX/HTML комментарии — для разработчиков; user-visible — строки/разметка.
        for line_no, line in scan_file(p, INTERNAL_RE, strip_comments=True):
            found.append((f'{rel}:{line_no}:internal', line))
        for line_no, line in scan_file(p, PRODUCT_CLAIM_RE, strip_comments=True):
            found.append((f'{rel}:{line_no}:product-claim', line))

    for rel in PRODUCT_CLAIM_ONLY_SURFACES:
        p = ROOT / rel
        if not p.exists():
            found.append((rel, 'MISSING FILE'))
            continue
        for line_no, line in scan_file(p, PRODUCT_CLAIM_RE, strip_comments=True):
            if rel.startswith('frontend/src/i18n/') and quantified.search(line):
                continue
            found.append((f'{rel}:{line_no}:product-claim', line))

    for rel in EN_NO_CYRILLIC:
        p = ROOT / rel
        if not p.exists():
            found.append((rel, 'MISSING FILE'))
            continue
        for line_no, line in scan_file(p, CYRILLIC_RE, strip_comments=True):
            allowed = EN_CYRILLIC_ALLOW.get(rel, ())
            if any(token in line for token in allowed):
                continue
            found.append((f'{rel}:{line_no}:cyrillic-on-en', line))

    return found


def main() -> int:
    issues = collect_issues()
    if not issues:
        print('OK: no public-language leaks found.')
        return 0

    by_file: dict[str, list[tuple[str, str]]] = {}
    for loc, preview in issues:
        key = loc.split(':')[0]
        by_file.setdefault(key, []).append((loc, preview))

    for key, rows in by_file.items():
        print(f'\n[{key}] {len(rows)} leaks:')
        for loc, preview in rows:
            print(f'  {loc}')
            print(f'    {preview}')

    print(f'\nFAIL: {len(issues)} total leaks. See .cursor/rules/methodology-language.mdc.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
