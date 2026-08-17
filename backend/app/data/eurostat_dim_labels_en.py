"""English Eurostat dimension member labels for locale=en world UI.

Official NACE / STS wording (Eurostat). Used for:
- EN title overlay when ``name_en`` is dataset-level (``append_en_slice_to_title``);
- EN variant-pill labels on the indicator card (``label_for_dim_member``).
"""

from __future__ import annotations

import re

# NACE Rev. 2 sections + frequent STS / industry aggregates (EN, Eurostat).
NACE_EN: dict[str, str] = {
    "A": "agriculture, forestry and fishing",
    "B": "mining and quarrying",
    "C": "manufacturing",
    "D": "electricity, gas, steam and air conditioning supply",
    "E": "water supply; sewerage, waste management",
    "F": "construction",
    "G": "wholesale and retail trade",
    "G47": "retail trade",
    "G47_FOOD": "retail sale of food",
    "G47_NFOOD": "retail sale of non-food products",
    "G47_NFOOD_X_G473": "retail sale of non-food products except fuel",
    "G47_X_G473": "retail trade except fuel",
    "G473": "retail sale of automotive fuel",
    "M_STS": "other services (STS)",
    "H-N_X_K": "services except financial and insurance (H–N except K)",
    "F_CC11_X_CC113": "construction of buildings except civil engineering",
    "H": "transportation and storage",
    "I": "accommodation and food service activities",
    "J": "information and communication",
    "K": "financial and insurance activities",
    "L": "real estate activities",
    "M": "professional, scientific and technical activities",
    "N": "administrative and support service activities",
    "O": "public administration and defence",
    "P": "education",
    "Q": "human health and social work activities",
    "R": "arts, entertainment and recreation",
    "S": "other service activities",
    "T": "activities of households as employers",
    "U": "activities of extraterritorial organisations",
    "B-D": "industry except construction (B–D)",
    "B-E": "industry including water supply (B–E)",
    "B-E36": "industry (sections B–E)",
    "B-S_X_O": "business economy except public administration",
    "B-S_X_O_S94": "business economy except public administration and membership organisations",
    "B-N": "business economy (B–N)",
    "B-S": "business economy (B–S)",
    "G-J": "trade, transport, accommodation, information and communication",
    "G-N": "trade and market services (G–N)",
    "K-N": "finance, real estate, professional and admin services",
    "O-S": "public administration, education, health and other services",
    "P-S_X_S94": "education, health, culture and other services",
    "C10": "manufacture of food products",
    "C10-C12": "food products, beverages and tobacco",
    "C13-C15": "textiles, wearing apparel and leather",
    "C16-C18": "wood, paper and printing",
    "C19": "coke and refined petroleum products",
    "C20": "chemicals and chemical products",
    "C21": "basic pharmaceutical products",
    "C22-C23": "rubber, plastics and non-metallic mineral products",
    "C24-C25": "basic metals and fabricated metal products",
    "C26": "computer, electronic and optical products",
    "C27": "electrical equipment",
    "C28": "machinery and equipment",
    "C29-C30": "transport equipment",
    "C31-C33": "other manufacturing and repair",
    "D35": "electricity, gas, steam and air conditioning",
    "E36": "water collection, treatment and supply",
    "F41": "construction of buildings",
    "F42": "civil engineering",
    "F43": "specialised construction activities",
    "G45": "wholesale and retail trade and repair of motor vehicles",
    "G46": "wholesale trade",
    "H49": "land transport and pipelines",
    "H50": "water transport",
    "H51": "air transport",
    "H52": "warehousing and support for transportation",
    "H53": "postal and courier activities",
    "I55": "accommodation",
    "I56": "food and beverage service activities",
    "J58": "publishing activities",
    "J59-J60": "motion picture, TV and broadcasting",
    "J61": "telecommunications",
    "J62-J63": "IT and other information services",
    "K64": "financial services except insurance",
    "K65": "insurance",
    "K66": "activities auxiliary to financial services",
    "M69-M71": "legal, accounting and engineering services",
    "M72": "scientific research and development",
    "M73-M75": "advertising, market research and other professional services",
    "N77": "rental and leasing",
    "N78": "employment activities",
    "N79": "travel agency activities",
    "N80-N82": "security, building services and other admin support",
}

# Short-term business statistics measures (indic_bt) — pill-facing.
INDIC_BT_EN: dict[str, str] = {
    "REG": "registrations",
    "BKRT": "bankruptcies",
    "BPRM_DW": "building permits, dwellings",
    "BPRM_SQM": "building permits, useful floor area",
    "EMP": "employment",
    "PRD": "production",
    "HW": "hours worked",
    "WAGE": "wages and salaries",
    "COST": "labour costs",
    "NETTUR": "turnover",
    "NETTUR_DOM": "domestic turnover",
    "NETTUR_NDOM": "non-domestic turnover",
    "NETTUR_NDOM_EU": "non-domestic turnover, EU",
    "PRC_PRR": "producer prices",
    "PRC_PRR_DOM": "producer prices, domestic market",
    "PRC_PRR_NDOM": "producer prices, non-domestic market",
    "PRC_PRR_B2B": "producer prices B2B",
    "PRC_IMP": "import prices",
    "VOL_SLS": "volume of sales",
}

SEX_EN: dict[str, str] = {
    "M": "males",
    "F": "females",
}

AGE_EN: dict[str, str] = {
    "Y15-24": "15–24 years",
    "Y15-74": "15–74 years",
    "Y25-74": "25–74 years",
    "Y15-64": "15–64 years",
    "Y20-64": "20–64 years",
    "Y_LT25": "under 25 years",
    "Y25-54": "25–54 years",
    "Y55-64": "55–64 years",
    "Y65-74": "65–74 years",
}

CPA2_1_EN: dict[str, str] = {
    "CPA_F41001": "residential buildings",
    "CPA_F41001_41002": "residential and non-residential buildings",
    "CPA_F41001_X_410014": "residential buildings except residences for communities",
    "CPA_F410011": "one-dwelling buildings",
    "CPA_F410012_410013": "two- and more dwelling buildings",
    "CPA_F410014": "residences for communities",
    "CPA_F41002": "non-residential buildings",
    "CPA_F41002_X_410023": "non-residential buildings except industrial",
    "CPA_F410023": "industrial buildings",
    "CPA_B-E36": "industry (B–E)",
}

LABELS_BY_DIM: dict[str, dict[str, str]] = {
    "nace_r2": NACE_EN,
    "nace_r1": NACE_EN,
    "indic_bt": INDIC_BT_EN,
    "sex": SEX_EN,
    "age": AGE_EN,
    "cpa2_1": CPA2_1_EN,
}

_TOTALISH = frozenset({"", "TOTAL", "T"})

_NACE_BY_ACTIVITY_TAIL = re.compile(
    r"\s+by\s+NACE\s+Rev\.?\s*2(?:\s+activity)?\s*$",
    re.I,
)

_AGE_RANGE = re.compile(r"^Y(\d+)-(\d+)$", re.I)
_AGE_GE = re.compile(r"^Y_GE(\d+)$", re.I)
_AGE_LT = re.compile(r"^Y_LT(\d+)$", re.I)
_AGE_YEAR = re.compile(r"^Y(\d+)$", re.I)


def nace_label_en(code: str | None) -> str | None:
    if not code:
        return None
    return NACE_EN.get(str(code).strip().upper())


def _age_label_fallback_en(code: str) -> str | None:
    m = _AGE_RANGE.match(code)
    if m:
        return f"{m.group(1)}–{m.group(2)} years"
    m = _AGE_GE.match(code)
    if m:
        return f"{m.group(1)} years and over"
    m = _AGE_LT.match(code)
    if m:
        return f"under {m.group(1)} years"
    m = _AGE_YEAR.match(code)
    if m:
        y = int(m.group(1))
        return f"{y} year" if y == 1 else f"{y} years"
    return None


def label_for_dim_member(dim: str, code: str | None) -> str | None:
    """EN label for a dimension member, or None if unknown."""
    if code is None:
        return None
    d = (dim or "").strip().lower()
    c = (code or "").strip().upper()
    if not d or not c:
        return None
    table = LABELS_BY_DIM.get(d)
    if table is not None:
        hit = table.get(c)
        if hit is not None:
            return hit
    if d == "age":
        return _age_label_fallback_en(c)
    return None


def append_en_slice_to_title(name_en: str, slice_json: dict | None) -> str:
    """Attach EN NACE slice when ``name_en`` is dataset-level (not slice-aware)."""
    base = (name_en or "").strip()
    if not base or not slice_json:
        return base
    nace = None
    for dim in ("nace_r2", "nace_r1"):
        raw = slice_json.get(dim)
        if raw is None:
            continue
        code = str(raw).strip().upper()
        if code in _TOTALISH:
            continue
        nace = nace_label_en(code)
        if nace:
            break
    if not nace:
        return base
    if nace.lower() in base.lower():
        return base
    cleaned = _NACE_BY_ACTIVITY_TAIL.sub("", base).strip(" ,;—–-")
    return f"{cleaned}: {nace}"
