"""Авто-расширение Eurostat-срезов: headline + независимые разрезы по одному dim.

Ручной ``DEEP_DATASET_SLICES`` важнее авто. Декартово произведение измерений
не строится (иначе взрыв каталога).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

NEVER_EXPAND_DIMS = frozenset({
    "geo", "time", "time_period", "freq", "unit", "s_adj", "currency",
})

# Предметные измерения, которые имеем смысл раскрывать в UI (variant-срезы).
EXPANDABLE_DIMS = frozenset({
    "age", "sex", "hhcomp", "nace_r2", "nace_r1", "coicop", "coicop18",
    "isced11", "isced11f", "sizeclas", "citizen", "wstatus", "siec",
    "cpa2_1", "deg_urb", "duration", "partner", "na_item", "statinfo",
    "worktime", "ord_brth", "month", "weight", "marsta", "stk_flow",
    "bop_item", "fdi_item", "nrg_bal", "c_birth", "rskpovth",
})

MAX_NON_TOTAL_MEMBERS = 40

TOTALISH_BASE = frozenset({"TOTAL", "TOT", "T", "ALL", "NSP"})


def is_expandable_dim(dim: str) -> bool:
    d = (dim or "").strip().lower()
    if not d or d in NEVER_EXPAND_DIMS:
        return False
    if d in EXPANDABLE_DIMS:
        return True
    if d.startswith("indic"):
        return True
    return False


def is_totalish(dim: str, member: str | None) -> bool:
    if not member:
        return True
    u = str(member).strip().upper()
    d = (dim or "").strip().lower()
    if u in TOTALISH_BASE:
        return True
    if d == "age" and u in {"Y15-74"}:
        return True
    if d in {"coicop", "coicop18"} and u in {"CP00", "TOTAL"}:
        return True
    return False


def non_totalish_members(dim: str, members: list[str]) -> list[str]:
    return [m for m in members if not is_totalish(dim, m)]


@dataclass(frozen=True)
class ExpandSkip:
    dataset_id: str
    dim: str
    non_total_count: int
    reason: str


@dataclass
class SlicePlan:
    dataset_id: str
    source: Literal["manual_deep", "independent_expand", "headline_only"]
    specs: list[dict[str, str]] = field(default_factory=list)
    skips: list[ExpandSkip] = field(default_factory=list)


def _canon_spec(spec: dict[str, str]) -> str:
    import json
    return json.dumps({k: spec[k] for k in sorted(spec)}, ensure_ascii=True)


def expand_independent_slices(
    headline: dict[str, str],
    dims: dict[str, list[str]],
    *,
    dataset_id: str,
) -> tuple[list[dict[str, str]], list[ExpandSkip]]:
    """headline ∪ (headline с заменой одного expandable dim на non-total member)."""
    specs: list[dict[str, str]] = [dict(headline)]
    seen = {_canon_spec(headline)}
    skips: list[ExpandSkip] = []

    for dim, members in dims.items():
        if not is_expandable_dim(dim):
            continue
        non_tot = non_totalish_members(dim, members)
        if not non_tot:
            continue
        if len(non_tot) > MAX_NON_TOTAL_MEMBERS:
            skips.append(ExpandSkip(
                dataset_id=dataset_id,
                dim=dim,
                non_total_count=len(non_tot),
                reason="over_cap",
            ))
            continue
        head_val = headline.get(dim)
        for m in non_tot:
            if head_val is not None and str(head_val) == str(m):
                continue
            spec = dict(headline)
            spec[dim] = m
            key = _canon_spec(spec)
            if key in seen:
                continue
            seen.add(key)
            specs.append(spec)

    return specs, skips


def resolve_slice_specs(
    dataset_id: str,
    dims: dict[str, list[str]],
) -> SlicePlan:
    """Manual DEEP wins; иначе independent expand от headline."""
    from app.data.eurostat_listing import DEEP_DATASET_SLICES
    from app.services.eurostat_parser import choose_headline_slice

    ds = (dataset_id or "").strip().lower()
    manual = DEEP_DATASET_SLICES.get(ds)
    if manual:
        return SlicePlan(
            dataset_id=ds,
            source="manual_deep",
            specs=[dict(s) for s in manual],
            skips=[],
        )

    headline = choose_headline_slice(dims, dataset_id=ds)
    specs, skips = expand_independent_slices(headline, dims, dataset_id=ds)
    source: Literal["independent_expand", "headline_only"] = (
        "independent_expand" if len(specs) > 1 else "headline_only"
    )
    return SlicePlan(dataset_id=ds, source=source, specs=specs, skips=skips)


def plan_dataset_slices(dataset_id: str, *, session: Any = None) -> SlicePlan:
    from app.services.eurostat_parser import fetch_dataset_structure

    dims = fetch_dataset_structure(dataset_id, session=session)
    return resolve_slice_specs(dataset_id, dims)
