"""Валидация точек по model_config_json (диапазоны и т.д.)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.parser import DataPoint

logger = logging.getLogger(__name__)


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
    dropped = 0
    for p in points:
        v = float(p.value)
        if vmin is not None and v < vmin:
            dropped += 1
            continue
        if vmax is not None and v > vmax:
            dropped += 1
            continue
        out.append(p)

    if dropped:
        logger.warning(
            "Validation: dropped %d of %d points (range: min=%s, max=%s)",
            dropped, len(points), vmin, vmax,
        )
    return out
