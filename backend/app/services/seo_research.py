"""Серверный HTML раздела «Исследования» (ADR-0003: тот же текст видят роботы и первый кадр человека).

Список отчётов — из `app/data/research_catalog.json` и `app/data/research_articles/*.json` (тот же каталог отдаёт
`/api/v1/research`). Каждый отчёт: название, подзаголовок, аннотация, главное в цифрах, выводы и ссылка на PDF через
счётчик скачиваний. У исследований со статьёй (20.11.2026, туризм) — ссылка на страницу `/research/{slug}`; её SSR —
`render_research_article_html` (тот же HTML отдаёт `/api/v1/research/{slug}` для SPA).
"""
from __future__ import annotations

from html import escape

from app.api.research import article_page, load_catalog, localize_item
from app.services import breadcrumbs as crumbs
from app.services.locale import get_locale, in_language
from app.services.seo_i18n import get_page_seo
from app.services.seo_renderer import _breadcrumbs, _breadcrumbs_nav, _page_body, _page_trail, _site_json_ld, build_document, render_page_html, _absolute

_COPY = {
    "ru": {"release": "Выпуск: {r}", "download": "Скачать PDF", "pages": "{p} стр.", "figures": "Главное в цифрах",
           "conclusions": "Выводы", "authors": "Авторы: {a}", "n": "Исследование №{n}", "read": "Читать исследование",
           "pdf_note": "PDF-версия: {p} стр., {s} МБ.", "back": "Все исследования", "size": "МБ"},
    "en": {"release": "Release: {r}", "download": "Download PDF (in Russian)", "pages": "{p} pages",
           "figures": "Key figures", "conclusions": "Conclusions", "authors": "Authors: {a}", "n": "Study No. {n}",
           "read": "Read the study", "pdf_note": "PDF version in Russian: {p} pages, {s} MB.", "back": "All studies",
           "size": "MB"},
}


def _locale() -> str:
    return "en" if get_locale() == "en" else "ru"


def _item_html(i: dict, c: dict, rel: str) -> str:
    figs = "".join(f"<li><strong>{escape(f['value'])}</strong> — {escape(f['label'])}</li>" for f in i.get("figures", []))
    concl = "".join(f"<li>{escape(x)}</li>" for x in i.get("conclusions", []))
    title = escape(i["title"])
    if i.get("has_article"):
        title = f'<a href="/research/{escape(i["slug"])}">{title}</a>'
    read = f' <a href="/research/{escape(i["slug"])}">{escape(c["read"])}</a>.' if i.get("has_article") else ""
    return (
        f'<article id="{escape(i["slug"])}">\n'
        f'<h2>{escape(c["n"].format(n=i["number"]))}. {title}</h2>\n'
        f'<p>{escape(i["subtitle"])}</p>\n<p>{escape(i["annotation"])}</p>\n'
        f'<h3>{escape(c["figures"])}</h3>\n<ul>{figs}</ul>\n'
        f'<h3>{escape(c["conclusions"])}</h3>\n<ol>{concl}</ol>\n'
        f'<p>{escape(c["authors"].format(a=i.get("authors", "Forecast Economy")))}. {escape(c["release"].format(r=rel))}. '
        f'{escape(c["pages"].format(p=i.get("pages", "")))}, PDF {i.get("size_mb", "")} {c["size"]}.{read} '
        f'<a href="/api/v1/research/{escape(i["slug"])}/download" rel="nofollow">{escape(c["download"])}</a></p>\n'
        "</article>"
    )


async def render_research_html() -> tuple[int, str]:
    locale = _locale()
    cat = load_catalog()
    items = [localize_item(i, locale) for i in cat.get("items") or []]
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
                {"@type": "Report", "name": i["title"], "description": i["subtitle"], "inLanguage": i.get("lang", "ru"),
                 "author": {"@type": "Organization", "name": "Forecast Economy"},
                 "url": _absolute(f"/research/{i['slug']}" if i.get("has_article") else f"{page.path}#{i['slug']}")}
                for i in items
            ],
        },
    ]
    return 200, await build_document(title=page.title, description=page.description, canonical_path=page.path,
                                     body=body, json_ld=json_ld, keywords=page.keywords)


def research_article_trail(title: str, slug: str) -> list[tuple[str, str]]:
    page = get_page_seo("research")
    return crumbs.trail(crumbs.home(), (page.path, page.h1), (f"/research/{slug}", title))


async def render_research_article_html(slug: str) -> tuple[int, str] | None:
    """SSR статьи исследования. None — у исследования нет страницы (маршрут отдаёт 404)."""
    locale = _locale()
    a = article_page(slug, locale)
    if not a:
        return None
    c = _COPY[locale]
    rel = a["release_en"] if locale == "en" else a["release"]
    trail = research_article_trail(a["title"], slug)
    figs = "".join(f"<li><strong>{escape(f['value'])}</strong> — {escape(f['label'])}</li>" for f in a.get("figures", []))
    body = f"""<main class="seo-page seo-research-article">
{_breadcrumbs_nav(trail)}
<article>
<p>{escape(c["n"].format(n=a["number"]))} · {escape(c["release"].format(r=rel))}</p>
<h1>{escape(a["title"])}</h1>
<p>{escape(a["subtitle"])}</p>
<ul>{figs}</ul>
{a["html"]}
<p>{escape(c["pdf_note"].format(p=a["pages"], s=a["size_mb"]))} <a href="/api/v1/research/{escape(slug)}/download" rel="nofollow">{escape(c["download"])}</a></p>
<p><a href="/research">{escape(c["back"])}</a></p>
</article>
</main>"""
    url = _absolute(a["path"])
    json_ld = [
        _site_json_ld(),
        _breadcrumbs(trail),
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": a["title"][:110],
            "description": a["description"],
            "inLanguage": in_language(),
            "datePublished": a["published"],
            "dateModified": a["published"],
            "author": {"@type": "Organization", "name": "Forecast Economy"},
            "publisher": {"@type": "Organization", "name": "Forecast Economy"},
            "image": _absolute(a["cover"]),
            "keywords": a["keywords"],
            "mainEntityOfPage": url,
            "url": url,
            "isPartOf": {"@type": "CollectionPage", "url": _absolute("/research")},
        },
    ]
    return 200, await build_document(title=a["seo_title"], description=a["description"], canonical_path=a["path"],
                                     body=body, json_ld=json_ld, keywords=a["keywords"], og_image=_absolute(a["cover"]))
