"""Per-dataset headline-member overrides for Eurostat slice selection.

Глобальный ``HEADLINE_PRIORITY`` в ``eurostat_parser`` одинаков для всех
наборов: для ``na_item`` первым идёт ``B1GQ`` (ВВП). В наборе про дефицит
бюджета это закрепляет ВВП, а имя карточки берётся из заголовка набора —
на витрине «дефицит = 100% ВВП».

Переопределения — конфиг, не ветки в парсере. Ключ = ``dataset_id`` (lower),
значение = dim → упорядоченный список кодов (первый присутствующий в
кодлисте побеждает). Пустой список = не пинить измерение.
"""

from __future__ import annotations

# dataset_id → dimension_id → priority member codes
HEADLINE_MEMBER_OVERRIDES: dict[str, dict[str, list[str]]] = {
    # Net lending (+)/net borrowing (−) of general government — не ВВП.
    "gov_10dd_edpt1": {
        "na_item": ["B9", "B9_T3", "B9F", "NLG_B9", "NET_LEND"],
        "sector": ["S13", "S1"],
        "unit": ["PC_GDP", "MIO_EUR", "MIO_NAC"],
    },
    "gov_10a_main": {
        "na_item": ["B9", "B9_T3", "TE", "TR"],
        "sector": ["S13", "S1"],
        "unit": ["PC_GDP", "MIO_EUR"],
    },
    "gov_10dd_slgd": {
        "na_item": ["GD", "F2", "F3", "F4"],
        "sector": ["S13", "S1"],
        "unit": ["PC_GDP", "MIO_EUR"],
    },
    # ВВП: объём / цепные цены, не тождество «ВВП как % ВВП».
    "nama_10_gdp": {
        "na_item": ["B1GQ", "B1G"],
        "unit": ["CLV15_MEUR", "CLV10_MEUR", "CP_MEUR", "MIO_EUR", "PC_GDP"],
    },
    "namq_10_gdp": {
        "na_item": ["B1GQ", "B1G"],
        "s_adj": ["SCA", "SA", "NSA"],
        "unit": ["CLV15_MEUR", "CLV10_MEUR", "CP_MEUR", "MIO_EUR", "PC_GDP"],
    },
    # Энергобалансы: inland / available, не пустая добыча/импорт-огрызок.
    "nrg_cb_sffm": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "IMP", "IPRD"],
        "siec": ["C0100", "C0200", "C0311"],
    },
    "nrg_cb_sff": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "IMP", "IPRD"],
    },
    "nrg_cb_em": {
        "nrg_bal": ["AIM", "IMP", "EXP", "DL"],
        "siec": ["E7000"],
    },
    "nrg_cb_h": {
        "nrg_bal": ["ID", "AIM", "FC_E", "IMP", "EXP"],
        "siec": ["H8000"],
    },
    "nrg_cb_oil": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "IMP", "IPRD"],
    },
    "nrg_cb_gas": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "IMP", "IPRD"],
    },
    "nrg_te_bio": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "IMP", "IPRD", "TOTAL"],
    },
    "nrg_te_gas": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "IMP", "IPRD"],
    },
    "nrg_te_gasm": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "IMP", "IPRD"],
    },
    "nrg_te_sff": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "IMP", "IPRD"],
    },
    "nrg_ti_bio": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "TI_EHG_MAP", "IMP"],
    },
    "nrg_ti_gas": {
        "nrg_bal": ["GID_OBS", "GID_CAL", "TI_EHG_MAP", "IMP"],
    },
    "nrg_inf_lbpc": {
        "nrg_bal": ["CAP_PRD", "CAP", "TOTAL"],
    },
}


def headline_priority_for(dataset_id: str | None, dim: str) -> list[str] | None:
    """Вернуть per-dataset приоритет для dim или None (→ глобальный)."""
    ds = (dataset_id or "").strip().lower()
    if not ds:
        return None
    by_dim = HEADLINE_MEMBER_OVERRIDES.get(ds)
    if not by_dim:
        return None
    if dim in by_dim:
        return by_dim[dim]
    return by_dim.get(dim.lower())
