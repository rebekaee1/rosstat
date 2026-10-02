"""REP wildcard/longest-rule checks for the finite year-document mode exception.

The matcher covers ASCII fixture URLs with the Google/Yandex documented REP
rules. An independent REP parser is also used for the release smoke; this test
does not substitute for live robots/SSR acceptance.
"""

from functools import lru_cache
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
ROBOTS = (
    ROOT / "backend/app/data/seo_static/robots.txt",
    ROOT / "backend/app/data/seo_static/robots.en.txt",
    ROOT / "frontend/public/robots.txt",
)


@lru_cache(maxsize=None)
def _rules(text: str, agent: str) -> tuple[tuple[re.Pattern, int, bool], ...]:
    """Select the explicit agent group, then wildcard or longest-path rules."""
    groups: dict[str, list[tuple[re.Pattern, int, bool]]] = {}
    current = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        if field.lower() == "user-agent":
            current = value.lower()
            groups.setdefault(current, [])
        elif field.lower() in {"allow", "disallow"} and current and value:
            end = value.endswith("$")
            pattern = value[:-1] if end else value
            regex = "^" + re.escape(pattern).replace(r"\*", ".*") + ("$" if end else "")
            groups[current].append((re.compile(regex), len(value.encode()), field.lower() == "allow"))
    return tuple(groups.get(agent.lower(), groups.get("*", ())))


def _can_crawl(text: str, agent: str, path: str) -> bool:
    matches = [(length, allowed) for pattern, length, allowed in _rules(text, agent) if pattern.match(path)]
    return max(matches, default=(0, True))[1]


@lru_cache(maxsize=1)
def _registered_year_paths() -> frozenset[str]:
    from app.data.legacy_redirects import _BESPOKE_UNLISTED_CANONICAL
    from app.data.view_model_families import FAMILIES
    from app.services.search_paths import russia_year_mode_paths

    codes = {mode.code for family in FAMILIES for mode in family.modes} | set(_BESPOKE_UNLISTED_CANONICAL)
    return frozenset(path for code in codes for _, path in russia_year_mode_paths(code, 2024))


def test_ru_en_frontend_templates_have_identical_directives():
    directives = []
    for template in ROBOTS:
        directives.append(tuple(line for raw in template.read_text(encoding="utf-8").splitlines()
            if (line := raw.split("#", 1)[0].strip())))
    assert directives[0] == directives[1] == directives[2]


@pytest.mark.parametrize("template", ROBOTS, ids=lambda path: str(path.relative_to(ROOT)))
def test_year_mode_allowlist_matches_registered_resolver(template):
    """A new registered token cannot be silently blocked by shipped templates."""
    text = template.read_text(encoding="utf-8")
    assert len(text.encode()) < 500 * 1024
    paths = _registered_year_paths()
    assert {urlsplit(path).path.split("/")[1] for path in paths} == {"russia", "currencies"}
    modes = {parse_qs(urlsplit(path).query)["mode"][0] for path in paths}
    expected = {f"/{plane}/indicator/*/*?mode={mode}$" for plane in ("russia", "currencies") for mode in modes}
    for agent in ("*", "Googlebot"):
        start = text.index(f"User-agent: {agent}\n")
        group = text[start:].split("\nUser-agent:", 1)[0]
        actual = {line.removeprefix("Allow: ") for line in group.splitlines() if line.startswith("Allow: ")}
        assert actual == expected | {"/"}
        for path in paths:
            assert _can_crawl(text, agent, path), (template, agent, path)
            assert not _can_crawl(text, agent, path.replace("/2024?", "/2024-01?")), path
            assert not _can_crawl(text, agent, path.replace("/2024?", "/2024/01?")), path


@pytest.mark.parametrize("template", ROBOTS, ids=lambda path: str(path.relative_to(ROOT)))
@pytest.mark.parametrize("agent", ("OtherBot", "Googlebot"))
@pytest.mark.parametrize(("path", "allowed"), (
    ("/russia/indicator/gdp-nominal/2024?mode=yoy", True),
    ("/russia/indicator/wages-nominal/2024?mode=avg-year", True),
    ("/currencies/indicator/eur-usd/2024?mode=avg-year", True),
    ("/russia/indicator/wages-nominal/2024", True),
    ("/russia/indicator/gdp-nominal?mode=yoy", False),
    ("/currencies/indicator/eur-usd?mode=avg-year", False),
    ("/russia/indicator/gdp-nominal/2024?mode=not-registered", False),
    ("/russia/indicator/gdp-nominal/2024?mode=yoy&mode=qoq", False),
    ("/russia/indicator/gdp-nominal/2024?mode=yoy&utm_source=test", False),
    ("/russia/indicator/gdp-nominal/2024?utm_source=test&mode=yoy", False),
    ("/russia/indicator/gdp-nominal/2024?foo=test&mode=yoy", False),
    ("/russia/indicator/gdp-nominal/2024?mode=yoy&foo=test", False),
    ("/russia/indicator/gdp-nominal/2024-01?mode=yoy", False),
    ("/russia/indicator/gdp-nominal/2024/01?mode=yoy", False),
    ("/russia/indicator/gdp-nominal/2024/01/extra?mode=yoy", False),
    ("/russia/indicator/gdp-nominal/2024/?mode=yoy", False),
    ("/currencies/indicator/eur-usd/2024-01?mode=avg-year", False),
    ("/currencies/indicator/eur-usd/2024/01?mode=avg-year", False),
    ("/germany/indicator/gdp/2024?mode=yoy", False),
    ("/russia/region/moscow/gdp/2024?mode=yoy", False),
    ("/russia/regions?year=2024", True),
    ("/assets/index.js", True),
    ("/login", True),
    ("/embed/indicator/gdp-nominal", False),
))
def test_year_mode_rep_decisions(template, agent, path, allowed):
    assert _can_crawl(template.read_text(encoding="utf-8"), agent, path) is allowed


@pytest.mark.parametrize("template", ROBOTS, ids=lambda path: str(path.relative_to(ROOT)))
def test_yandex_reads_card_canonical_and_preserves_year_mode(template):
    text = template.read_text(encoding="utf-8")
    for path in (
        "/russia/indicator/gdp-nominal?mode=yoy",
        "/russia/indicator/gdp-nominal/2024?mode=yoy",
        "/currencies/indicator/eur-usd/2024?mode=avg-year",
    ):
        assert _can_crawl(text, "Yandex", path)
    names = {name for line in text.splitlines() if line.startswith("Clean-param:")
        for name in line.split(":", 1)[1].strip().split(" ", 1)[0].split("&")}
    assert "mode" not in names
