"""Серверный HTML раздела «Исследования» (ADR-0003: тот же текст видят роботы и первый кадр человека).

Список отчётов — из `app/data/research_catalog.json` (тот же каталог отдаёт `/api/v1/research`). Каждый отчёт:
название, подзаголовок, аннотация, главное в цифрах, выводы и ссылка на PDF через счётчик скачиваний.
"""
from __future__ import annotations

from html import escape

from app.api.research import load_catalog
from app.services.locale import get_locale
from app.services.seo_i18n import get_page_seo
from app.services.seo_renderer import _breadcrumbs, _page_body, _page_trail, _site_json_ld, build_document, render_page_html, _absolute

_COPY = {
    "ru": {"release": "Выпуск: {r}", "download": "Скачать PDF", "pages": "{p} стр.", "figures": "Главное в цифрах",
           "conclusions": "Выводы", "authors": "Авторы: {a}", "n": "Исследование №{n}"},
    "en": {"release": "Release: {r}", "download": "Download PDF (in Russian)", "pages": "{p} pages",
           "figures": "Key figures", "conclusions": "Conclusions", "authors": "Authors: {a}", "n": "Study No. {n}"},
}


def _item_html(i: dict, c: dict, rel: str) -> str:
    figs = "".join(f"<li><strong>{escape(f['value'])}</strong> — {escape(f['label'])}</li>" for f in i.get("figures", []))
    concl = "".join(f"<li>{escape(x)}</li>" for x in i.get("conclusions", []))
    return (
        f'<article id="{escape(i["slug"])}">\n'
        f'<h2>{escape(c["n"].format(n=i["number"]))}. {escape(i["title"])}</h2>\n'
        f'<p>{escape(i["subtitle"])}</p>\n<p>{escape(i["annotation"])}</p>\n'
        f'<h3>{escape(c["figures"])}</h3>\n<ul>{figs}</ul>\n'
        f'<h3>{escape(c["conclusions"])}</h3>\n<ol>{concl}</ol>\n'
        f'<p>{escape(c["authors"].format(a=i.get("authors", "Forecast Economy")))}. {escape(c["release"].format(r=rel))}. '
        f'{escape(c["pages"].format(p=i.get("pages", "")))}, PDF {i.get("size_mb", "")} МБ. '
        f'<a href="/api/v1/research/{escape(i["slug"])}/download" rel="nofollow">{escape(c["download"])}</a></p>\n'
        "</article>"
    )


async def render_research_html() -> tuple[int, str]:
    locale = "en" if get_locale() == "en" else "ru"
    cat = load_catalog()
    items = cat.get("items") or []
    if not items:
        return await render_page_html("research")
    c = _COPY[locale]
    rel = cat.get("release_en" if locale == "en" else "release") or ""
    page = get_page_seo("research")
    trail = _page_trail("research", page)
    lead = f"<p>{escape(page.intro)}</p>"
    section = "\n".join(_item_html(i, c, rel) for i in items)
    body = _page_body(page, trail).replace(lead, f"{lead}\n{section}", 1)
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(trail),
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": page.h1,
            "description": page.description,
            "url": _absolute(page.path),
            "hasPart": [
                {"@type": "Report", "name": i["title"], "description": i["subtitle"], "inLanguage": "ru",
                 "author": {"@type": "Organization", "name": "Forecast Economy"},
                 "url": _absolute(f"{page.path}#{i['slug']}")}
                for i in items
            ],
        },
    ]
    return 200, await build_document(title=page.title, description=page.description, canonical_path=page.path,
                                     body=body, json_ld=json_ld, keywords=page.keywords)
