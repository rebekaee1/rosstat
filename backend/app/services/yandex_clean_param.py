"""Public Yandex Clean-param rules, mirrored in both robots.txt templates.

Only parameters that cannot change the canonical document belong here. The
``codes`` filter is scoped to /compare; ``view`` and ``mode`` select client
views whose canonical URL is the unparameterized page. ``preview_locale`` is
excluded because it changes the language before cutover and redirects after.
Yandex limits each rule to 500 characters and treats names as case-sensitive.
Reference: https://yandex.ru/support/webmaster/ru/robot-workings/clean-param
"""

from __future__ import annotations


CLEAN_PARAM_RULES: tuple[str, ...] = (
    "utm_source&utm_medium&utm_campaign&utm_term&utm_content&utm_referrer"
    "&utm_media&utm_group&utm_expid&utm_id",
    "ysclid&yrclid&yclid&yadclid&yadordid&gclid&gbraid&wbraid&fbclid"
    "&msclkid&ttclid&twclid&srsltid",
    "etext&ybaip&_openstat&openstat&clid&yandex_referrer&erid&from&ref"
    "&ref_src&source&mc_cid&mc_eid&igshid&_ga&mode",
    "codes /compare",
    "view",
)

CONTENT_PARAMS = frozenset({
    "preview_locale", "year", "amount", "to", "country", "y", "m",
    "period", "size", "portrait",
})


def clean_param_lines() -> list[str]:
    lines = [f"Clean-param: {rule}" for rule in CLEAN_PARAM_RULES]
    if any(len(line) > 500 for line in lines):
        raise ValueError("Clean-param rule exceeds Yandex's 500-character limit")
    return lines


def clean_param_names() -> frozenset[str]:
    names = frozenset(
        name for rule in CLEAN_PARAM_RULES
        for name in rule.split(" ", 1)[0].split("&")
    )
    forbidden = names & CONTENT_PARAMS
    if forbidden:
        raise ValueError(f"content-changing Clean-param names: {sorted(forbidden)}")
    return names
