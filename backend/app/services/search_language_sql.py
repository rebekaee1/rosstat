"""SQL mirrors of typed economic measure guards, applied before candidate limits."""
from __future__ import annotations

import re

from sqlalchemy import and_, func, literal, not_, or_
from sqlalchemy.sql.elements import ColumnElement

from app.services.search_language import MEASURE_RULES, VALUATION_UNIT_RULES


def _pattern_clause(text: ColumnElement, pattern: str, *, postgres: bool) -> ColumnElement:
    """Match the controlled guard grammar on PostgreSQL or hermetic SQLite."""
    if postgres:
        return text.op("~")(pattern)
    # Current controlled rules use plain literal phrases, alternation and .*.
    # Escaping SQL wildcards keeps metadata punctuation literal. Do not turn a
    # future unsupported regex construct into a silently weaker semantic guard.
    branches = []
    for branch in pattern.split("|"):
        pieces = branch.split(".*")
        if any(re.search(r"[\\^$+?{}\[\]()]", piece) for piece in pieces):
            raise ValueError("unsupported SQLite search measure pattern")
        escaped = [piece.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") for piece in pieces]
        branches.append(text.like("%" + "%".join(escaped) + "%", escape="\\"))
    return or_(*branches)


def measure_constraints(terms: tuple[tuple[str, ...], ...], code_column: ColumnElement,
        name_columns: tuple[ColumnElement, ...], *, postgres: bool,
        unit_columns: tuple[ColumnElement, ...] = ()) -> list[ColumnElement]:
    """Require every typed subject/measure in code or titles before SQL LIMIT.

    The shared MEASURE_RULES is the only rule source; SEO/category metadata does
    not establish a measure. Coalescing prevents NULL names from bypassing an
    exclusion. Final Python guard remains an additional check on returned DTOs.
    """
    text = func.coalesce(code_column, "")
    for column in name_columns:
        text = text + literal(" ") + func.coalesce(column, "")
    text = func.replace(func.replace(func.lower(text), "-", " "), "ё", "е")
    clauses = []
    for alternatives in terms:
        rule = MEASURE_RULES.get(alternatives[0]) if alternatives else None
        if not rule:
            continue
        required, excluded = rule
        if alternatives[0] in VALUATION_UNIT_RULES:
            # Names/code and each native unit label form distinct evidence.
            # A title "Current transfers" plus currency-only unit "USD" is
            # never joined into an invented current-price valuation.
            def normalized(column):
                return func.replace(func.replace(func.lower(func.coalesce(column, "")), "-", " "), "ё", "е")
            title_labels = [normalized(column) for column in (code_column, *name_columns)]
            unit_labels = [normalized(column) for column in unit_columns]
            unit_required, unit_excluded = VALUATION_UNIT_RULES[alternatives[0]]
            positive = [and_(*(_pattern_clause(label, pattern, postgres=postgres) for pattern in required))
                for label in title_labels] + [and_(*(_pattern_clause(label, pattern, postgres=postgres) for pattern in unit_required))
                for label in unit_labels]
            negatives = [_pattern_clause(label, pattern, postgres=postgres)
                for label in (*title_labels, *unit_labels) for pattern in excluded]
            negatives += [_pattern_clause(label, pattern, postgres=postgres)
                for label in unit_labels for pattern in unit_excluded]
            clauses.append(and_(or_(*positive), not_(or_(*negatives))))
            continue
        if required:
            clauses.append(and_(*(_pattern_clause(text, pattern, postgres=postgres) for pattern in required)))
        if excluded:
            clauses.append(not_(or_(*(_pattern_clause(text, pattern, postgres=postgres) for pattern in excluded))))
    return clauses
