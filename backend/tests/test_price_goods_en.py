"""R3-C: every average-price item has a human English name and unit."""
import re

from app.data.emiss_price_goods import ALL_PRICE_GOODS, price_meta
from app.data.i18n.price_goods_en import PRICE_GOODS_EN
from app.data.i18n.region_indicators_en import REGION_INDICATORS_EN

CYR = re.compile(r"[А-Яа-яЁё]")


def test_every_good_has_english_copy():
    for g in ALL_PRICE_GOODS:
        assert g.label_en, g.code
        en = REGION_INDICATORS_EN[g.code]
        assert not CYR.search(en["name"]) and not CYR.search(en["unit"]), g.code
        assert en["name"].startswith("Average consumer price: ")


def test_auto_goods_covered_exactly():
    auto = {g.code for g in ALL_PRICE_GOODS if g.code in PRICE_GOODS_EN}
    assert len(auto) == len(PRICE_GOODS_EN) == 801


def test_names_are_clean():
    for code, (name, per) in PRICE_GOODS_EN.items():
        assert name and name[0].isupper() or name[0].isdigit(), code
        assert "  " not in name and not name.endswith((",", ".")), code
        assert "·" not in name and "·" not in per, code
        assert not CYR.search(name) and not CYR.search(per), code


def test_short_name_en_is_plain():
    assert price_meta("ceni-yaytsa")["short_name_en"] == "Chicken eggs, 10 eggs"
    for code in PRICE_GOODS_EN:
        short = price_meta(code)["short_name_en"]
        assert short and not CYR.search(short)
