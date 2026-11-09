"""Googlebot на ru. не обходит годовые страницы мира и регионов мира (08.11.2026).

Хост ru. выпал из индекса Google 02.10.2026 целиком (разбор:
.artifacts/google-drop-2026-11-08/отчёт.md). Решение владельца 08.11.2026:
закрыть для Googlebot ~8,6 млн годовых страниц мира на ru., Россию, регионы РФ
и валюты оставить. Яндекс и apex (robots.en.txt, контрольная группа) не меняются.

Сопоставление — по правилам REP Google: побеждает самое длинное совпавшее
правило, при равной длине — Allow.
"""

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
RU = ROOT / "backend/app/data/seo_static/robots.txt"
EN = ROOT / "backend/app/data/seo_static/robots.en.txt"

YEAR_RULES = (
    "Disallow: /*/indicator/*/1\n",
    "Disallow: /*/indicator/*/2\n",
    "Disallow: /*/region/*/1\n",
    "Disallow: /*/region/*/2\n",
    "Allow: /russia/indicator/\n",
    "Allow: /russia/region/\n",
    "Allow: /currencies/indicator/\n",
)


def _group(text: str, agent: str) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    current = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        if field.lower() == "user-agent":
            current = value
        elif current == agent and field.lower() in {"allow", "disallow"} and value:
            rules.append((field.lower(), value))
    return rules


def _can_crawl(rules: list[tuple[str, str]], path: str) -> bool:
    best = (0, True)
    for field, value in rules:
        end = value.endswith("$")
        pattern = value[:-1] if end else value
        regex = "^" + re.escape(pattern).replace(r"\*", ".*") + ("$" if end else "")
        if re.match(regex, path):
            cand = (len(value), field == "allow")
            if cand > best:
                best = cand
    return best[1]


BLOCKED = (
    "/finland/indicator/fi-nrg_ind_pehnf-gep-total-total-ra110ror-gwh/1995",
    "/belgium/indicator/be-ei_bsbu_m_r2-bs-ceme-bal-sa/1989",
    "/united-states/indicator/us-bea-sainc5n-512/2008",
    "/cyprus/indicator/cy-ei_isppi_q-prc-prr-h-n-x-k-nsa-i2021/2021",
    "/united-states/region/alabama/unemployment-rate/1976",
    "/germany/region/bavaria/gdp/2020",
)

OPEN = (
    "/",
    "/russia/indicator/key-rate",
    "/russia/indicator/key-rate/2025",
    "/russia/indicator/cpi/2026",
    "/russia/region/altayskiy-kray/chislennost-naseleniya/2000",
    "/russia/region/moskva/chislennost-naseleniya/2018",
    "/currencies/indicator/eur-rub/2025",
    "/united-states/indicator/us-gdp-per-capita-real",
    "/united-states/region/alabama/unemployment-rate",
    "/united-states/region/map/unemployment-rate?year=2024",
    "/france-vs-united-states/government-debt-gdp",
    "/world/rating/gdp-per-capita-eu",
)


def test_ru_googlebot_group_has_year_rules():
    google = "".join(f"{f.capitalize()}: {v}\n" for f, v in _group(RU.read_text(encoding="utf-8"), "Googlebot"))
    for rule in YEAR_RULES:
        assert rule in google, f"ru Googlebot missing {rule!r}"


@pytest.mark.parametrize("path", BLOCKED)
def test_ru_googlebot_blocks_world_years(path):
    rules = _group(RU.read_text(encoding="utf-8"), "Googlebot")
    assert not _can_crawl(rules, path), path


@pytest.mark.parametrize("path", OPEN)
def test_ru_googlebot_keeps_russia_and_cards(path):
    rules = _group(RU.read_text(encoding="utf-8"), "Googlebot")
    assert _can_crawl(rules, path), path


@pytest.mark.parametrize("agent", ("*", "Yandex"))
def test_ru_other_agents_keep_world_years(agent):
    rules = _group(RU.read_text(encoding="utf-8"), agent)
    for path in BLOCKED:
        assert _can_crawl(rules, path), (agent, path)


def test_apex_control_group_unchanged():
    """apex (robots.en.txt) — контрольная группа: годовые страницы мира открыты."""
    text = EN.read_text(encoding="utf-8")
    rules = _group(text, "Googlebot")
    for path in BLOCKED:
        assert _can_crawl(rules, path), path
    assert "/*/indicator/*/1" not in text
