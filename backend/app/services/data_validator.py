"""Валидация точек по model_config_json (диапазоны и т.д.)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.parser import DataPoint


def validate_points(points: list, model_config: dict | None) -> list:
    """Отфильтровать выбросы по optional validation { min, max } в model_config."""
    if not model_config:
        return points
    val = model_config.get("validation") or {}
    vmin = val.get("min")
    vmax = val.get("max")
    if vmin is None and vmax is None:
        return points

    out = []
    for p in points:
        v = float(p.value)
        if vmin is not None and v < vmin:
            continue
        if vmax is not None and v > vmax:
            continue
        out.append(p)
    return out
