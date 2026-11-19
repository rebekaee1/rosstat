"""Парсер топлива читает сохранённые образцы реальных файлов Росстата.

12.10.2026 проверено вручную: живой `nedel_sred_cen.xlsx` и бюллетень
«О потребительских ценах на нефтепродукты» (156_07-10-2026) разбираются
текущим парсером; нулевой результат 09.10 был сетевым сбоем, не сменой вёрстки.
Образцы сжаты до нужных строк, структура листа и таблицы сохранена.
"""
from datetime import date
from pathlib import Path

from app.services.rosstat_weekly_price_parser import (
    _BULLETIN_HREF_RE,
    _FUEL_BULLETIN_TITLE_RE,
    _parse_fuel_bulletin_html,
    parse_weekly_price_xlsx,
)

FIX = Path(__file__).parent / "fixtures" / "rosstat_fuel"


def test_real_xlsx_sample_gives_weekly_prices_for_all_three_fuels():
    content = (FIX / "nedel_sred_cen_2026_fuel_trimmed.xlsx").read_bytes()
    for label in (
        "Бензин автомобильный марки АИ-92, л",
        "Бензин автомобильный марки АИ-95, л",
        "Дизельное топливо, л",
    ):
        points = parse_weekly_price_xlsx(content, label)
        assert len(points) >= 38, label  # с 12 января по конец сентября
        assert points[0].date == date(2026, 1, 12)
        assert all(40 < p.value < 120 for p in points)
        assert [p.date for p in points] == sorted({p.date for p in points})
    ai92 = {p.date: p.value for p in parse_weekly_price_xlsx(content, "Бензин автомобильный марки АИ-92, л")}
    assert ai92[date(2026, 9, 28)] == 74.51


def test_real_bulletin_sample_gives_last_two_registration_dates():
    html = (FIX / "bulletin_156_2026-10-07_trimmed.html").read_text(encoding="utf-8")
    assert _parse_fuel_bulletin_html(html, "аи-92")[-1].date == date(2026, 10, 5)
    out = {p.date: p.value for p in _parse_fuel_bulletin_html(html, "аи-92")}
    assert out == {date(2026, 9, 28): 74.51, date(2026, 10, 5): 74.72}
    diesel = {p.date: p.value for p in _parse_fuel_bulletin_html(html, "дизельное топливо")}
    assert diesel == {date(2026, 9, 28): 86.77, date(2026, 10, 5): 86.72}


def test_central_news_link_pattern_matches_real_markup():
    html = (
        '<a class="x" href="/storage/mediabank/156_07-10-2026.html" title="">'
        "О потребительских ценах на нефтепродукты с 29 сентября по 5 октября 2026 года</a>"
    )
    found = [(h, t) for h, t in _BULLETIN_HREF_RE.findall(html) if _FUEL_BULLETIN_TITLE_RE.search(t)]
    assert found and found[0][0].endswith("156_07-10-2026.html")


# --- PDF-бюллетени (с октября 2026). 19.11.2026: точка 16.11 стояла в 175_18-11-2026.pdf,
# а парсер искал только …_DD-MM-YYYY.html и ждал xlsx — на сайте оставалась цена на 9.11.

def test_real_pdf_bulletin_page_gives_two_registration_dates():
    from app.services.rosstat_weekly_price_parser import _parse_fuel_bulletin_content

    pdf = (FIX / "bulletin_169n-ben28_2026-10-28_page1.pdf").read_bytes()
    href = "/storage/mediabank/169n-ben28.pdf"
    assert {p.date: p.value for p in _parse_fuel_bulletin_content(pdf, href, "аи-92")} == {
        date(2026, 10, 19): 74.02, date(2026, 10, 26): 72.55,
    }
    assert {p.date: p.value for p in _parse_fuel_bulletin_content(pdf, href, "аи-95")} == {
        date(2026, 10, 19): 80.30, date(2026, 10, 26): 78.90,
    }
    assert {p.date: p.value for p in _parse_fuel_bulletin_content(pdf, href, "дизельное топливо")} == {
        date(2026, 10, 19): 86.58, date(2026, 10, 26): 86.52,
    }


def test_pdf_text_of_bulletin_175_gives_price_on_16_november():
    from app.services.rosstat_weekly_price_parser import _parse_fuel_bulletin_text

    text = (FIX / "bulletin_175_2026-11-18_pypdf.txt").read_text(encoding="utf-8")
    diesel = {p.date: p.value for p in _parse_fuel_bulletin_text(text, "дизельное топливо")}
    assert diesel == {date(2026, 11, 9): 86.63, date(2026, 11, 16): 87.09}
    ai92 = {p.date: p.value for p in _parse_fuel_bulletin_text(text, "аи-92")}
    assert ai92 == {date(2026, 11, 9): 70.01, date(2026, 11, 16): 70.04}
    # Таблица субъектов («Российская Федерация* 74,15 70,04 …») не подменяет таблицу по России.
    ai95 = {p.date: p.value for p in _parse_fuel_bulletin_text(text, "аи-95")}
    assert ai95 == {date(2026, 11, 9): 76.29, date(2026, 11, 16): 76.33}


def test_pdf_text_with_words_broken_by_pypdf_still_parses():
    from app.services.rosstat_weekly_price_parser import _parse_fuel_bulletin_text

    text = (
        "Средние потребительские цены на бензин автомобильный и дизельное топливо по Российской Федерации "
        "рублей за литр\n На дату регистрации\n9 но ября\n2026 г.\n16 нояб ря\n2026 г.\n"
        "марки АИ-92  70,01 70,04\nмарки АИ-98 и выше 103,97 104,15\nДизельное топливо 86,63 87,09\n"
    )
    assert [p.value for p in _parse_fuel_bulletin_text(text, "дизельное топливо")] == [86.63, 87.09]
    assert [p.date for p in _parse_fuel_bulletin_text(text, "аи-92")] == [date(2026, 11, 9), date(2026, 11, 16)]


def test_central_news_link_pattern_matches_pdf_and_absolute_links():
    html = (
        '<a href="/storage/mediabank/175_18-11-2026.pdf">'
        "О потребительских ценах на нефтепродукты с 10 по 16 ноября 2026 года</a>"
        '<a href="https://rosstat.gov.ru/storage/mediabank/169n-ben28.pdf">'
        "О потребительских ценах на нефтепродукты с 20 по 26 октября 2026 года</a>"
        '<a href="/storage/mediabank/174_18-11-2026.pdf">'
        "Об оценке индекса потребительских цен с 10 по 16 ноября 2026 года</a>"
    )
    found = [h for h, t in _BULLETIN_HREF_RE.findall(html) if _FUEL_BULLETIN_TITLE_RE.search(t)]
    assert found == ["/storage/mediabank/175_18-11-2026.pdf", "/storage/mediabank/169n-ben28.pdf"]


class _Resp:
    def __init__(self, status: int, content: bytes = b"", text: str = ""):
        self.status_code, self.content, self.text = status, content, text

    def raise_for_status(self):
        import requests

        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error")


class _Session:
    def __init__(self, routes):
        self.routes, self.verify = routes, True

    def get(self, url, params=None, timeout=None):
        key = url + (f"?page={params['page']}" if params else "")
        return self.routes.get(key, _Resp(404))

    def close(self):
        pass


def test_xlsx_404_does_not_cancel_pdf_bulletin(monkeypatch):
    import app.services.rosstat_weekly_price_parser as mod

    pdf = (FIX / "bulletin_169n-ben28_2026-10-28_page1.pdf").read_bytes()
    news = (
        '<a href="https://rosstat.gov.ru/storage/mediabank/169n-ben28.pdf">'
        "О потребительских ценах на нефтепродукты с 20 по 26 октября 2026 года</a>"
    )
    routes = {
        mod.CENTRAL_NEWS_URL + "?page=1": _Resp(200, text=news),
        "https://rosstat.gov.ru/storage/mediabank/169n-ben28.pdf": _Resp(200, content=pdf),
    }
    monkeypatch.setattr(mod, "create_session", lambda: _Session(routes))
    points, _ = mod.fetch_weekly_price("Дизельное топливо, л")
    assert [(p.date, p.value) for p in points] == [(date(2026, 10, 19), 86.58), (date(2026, 10, 26), 86.52)]


def test_xlsx_404_and_no_bulletin_still_raises(monkeypatch):
    import pytest
    import requests

    import app.services.rosstat_weekly_price_parser as mod

    monkeypatch.setattr(mod, "create_session", lambda: _Session({}))
    with pytest.raises(requests.HTTPError):
        mod.fetch_weekly_price("Дизельное топливо, л")
