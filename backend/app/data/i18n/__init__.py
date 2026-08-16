"""i18n data package: glossary + EN catalogs (content filled by other agents)."""

from app.data.i18n.en_catalog import has_en_path
from app.data.i18n.glossary_en import GLOSSARY_EN, term
from app.data.i18n.indicator_copy_en import INDICATOR_COPY_EN, get_indicator_copy_en

__all__ = [
    "GLOSSARY_EN",
    "term",
    "has_en_path",
    "INDICATOR_COPY_EN",
    "get_indicator_copy_en",
]
