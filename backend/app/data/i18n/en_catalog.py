"""EN catalog: which public paths have a real English twin (hreflang-safe).

Until a path is listed here, SSR must NOT emit ``hreflang="en"`` for it.
Content agents expand prefixes/exact paths as EN pages ship.
Do NOT treat arbitrary first segments as countries — that would advertise
hreflang to 404s.
"""

from __future__ import annotations

# Exact paths with curated EN SEO + UI.
EN_EXACT_PATHS: frozenset[str] = frozenset({
    "/",
    "/about",
    "/methodology",
    "/privacy",
    "/terms",
    "/compare",
    "/calculator",
    "/calculator/mortgage",
    "/calculator/compound",
    "/russia",
    "/russia/category",
    "/russia/today",
    "/russia/calendar",
    "/russia/demographics",
    "/russia/region",
    "/russia/region-rating",
    "/widgets",
})

# Prefixes: path == prefix.rstrip("/") or path.startswith(prefix).
EN_PATH_PREFIXES: tuple[str, ...] = (
    "/world/rating",
    "/russia/category/",
    "/russia/indicator/",
    "/russia/today/",
    "/russia/calendar/",
    "/russia/region/",
    "/russia/region-rating/",
    "/russia/region-vs/",
)


def has_en_path(path: str) -> bool:
    """True if this path may advertise an English alternate."""
    if not path:
        return False
    if not path.startswith("/"):
        path = f"/{path}"
    path = path.split("?", 1)[0]
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    if path in EN_EXACT_PATHS:
        return True
    for prefix in EN_PATH_PREFIXES:
        if path == prefix.rstrip("/") or path.startswith(prefix):
            return True
    return False
