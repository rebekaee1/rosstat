from types import SimpleNamespace

from app.services.seo_i18n import public_indicator_fields, public_indicator_seo
from app.services.seo_renderer import _indicator_body


def test_key_rate_identifies_country_in_shared_api_ssr_overlay():
    fields = public_indicator_fields("key-rate", name_ru="Ключевая ставка", locale="en")
    seo = public_indicator_seo("key-rate", name_ru="Ключевая ставка", locale="en")
    assert fields["name"] == "Bank of Russia key rate"
    assert seo["name"] == fields["name"]
    assert seo["seo_title"] == "Bank of Russia key rate — data and chart"


def test_month_link_grammar_uses_localized_period():
    ind = SimpleNamespace(code="budget-deficit", name="Сальдо бюджета", unit="млрд руб.",
        frequency="monthly", source="Минфин", source_url="https://minfin.gov.ru/",
        description="Бюджет", methodology="Помесячное сальдо", seo_blocks=None, model_config_json={})
    ru = _indicator_body(ind, None, [], [], 0, None, None, data_month_pairs=[(2026,m) for m in range(1,13)], locale="ru")
    assert "Сальдо бюджета за июнь 2026" in ru
    assert "Сальдо бюджета за май 2026" in ru
    assert "Сальдо бюджета за декабрь 2026" in ru
    assert "в июнь" not in ru
    en = _indicator_body(ind, None, [], [], 0, None, None, display_name="Budget balance", data_month_pairs=[(2026,6)], locale="en")
    assert "Budget balance in June 2026" in en
