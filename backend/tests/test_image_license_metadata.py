"""Google Images «Метаданные изображений»: полный набор полей лицензии.

Отчёт Search Console предупреждает, если у ImageObject есть хотя бы одно из
creator / creditText / copyrightNotice / license, а остальные (и
acquireLicensePage) пустые. На карточке индикатора таким триггером был
creditText без остальных полей; author Google за creator не считает.
"""

from pathlib import Path

from app.services.locale import reset_request_origin, set_request_origin
from app.services.seo_renderer import _chart_image_rights

_SERVICES = Path(__file__).resolve().parents[1] / "app" / "services"
_REQUIRED = (
    "creator",
    "creditText",
    "copyrightNotice",
    "license",
    "acquireLicensePage",
)


def test_chart_image_rights_match_site_terms():
    rights = _chart_image_rights()
    assert set(_REQUIRED) <= set(rights)
    assert rights["creator"]["@type"] == "Organization"
    assert rights["creator"]["name"] == "Forecast Economy"
    assert rights["creditText"] == "Forecast Economy"
    assert rights["copyrightNotice"] == "Forecast Economy"
    assert rights["license"] == "https://forecasteconomy.com/terms"
    assert rights["acquireLicensePage"] == rights["license"]
    assert "creativecommons.org" not in rights["license"]


def test_chart_image_rights_follow_request_host():
    token = set_request_origin("https://ru.forecasteconomy.com")
    try:
        rights = _chart_image_rights()
    finally:
        reset_request_origin(token)
    assert rights["license"] == "https://ru.forecasteconomy.com/terms"
    assert rights["creator"]["url"] == "https://ru.forecasteconomy.com"
    assert rights["creator"]["@id"] == "https://ru.forecasteconomy.com/#organization"


def test_indicator_imageobject_uses_complete_rights():
    """Единственный creditText живёт в хелпере и подмешивается в ImageObject карточки."""
    src = (_SERVICES / "seo_renderer.py").read_text(encoding="utf-8")
    assert src.count('"creditText"') == 1
    assert "**_chart_image_rights()" in src
    others = [
        path.name
        for path in _SERVICES.glob("seo_*.py")
        if path.name != "seo_renderer.py" and "creditText" in path.read_text(encoding="utf-8")
    ]
    assert others == []
