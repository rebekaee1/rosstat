"""R5-D: слова охвата («по регионам», «по областям») не становятся обязательным термином запроса."""
import pytest

from app.services.search_intent import parse_intent


@pytest.mark.parametrize("query,expected", [
    ("цены по регионам", (("цены",),)),
    ("яйца по регионам", (("яйца",),)),
    # 13.11.2026: «врп» стало понятием (раньше оставалось буквальным словом и ничего не находило).
    ("ВРП по регионам", (("valovoy-regionalnyy-produkt", "валовой региональный продукт",
                          "валового регионального продукта", "gross regional product"),)),
    ("безработица в регионах", None),
])
def test_scope_words_dropped(query, expected):
    terms = parse_intent(query, []).terms
    assert all(not any(w.startswith("регион") for w in group) for group in terms)
    if expected:
        assert terms == expected
