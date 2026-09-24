"""Native phone images for every data family, with separate cache variants."""
import asyncio
import io
from datetime import date

from bs4 import BeautifulSoup
from PIL import Image
import pytest

from app.services import og_image
from app.services.seo_renderer import _responsive_chart_images


CASES = [
    (og_image.render_rating_og, dict(name="Wages", year=2024, unit="RUB", rows=[("Region A", -3), ("Region B", 5)], total=2)),
    (og_image.render_world_rating_og, dict(name="Population", year=2024, unit="people", rows=[("Country A", 12), ("Country B", 5)], total=2, order_label="descending")),
    (og_image.render_today_hub_og, dict(date_text="2026-09-24", items=[("Rate", "12 % (2026-09-20)")])),
    (og_image.render_region_vs_og, dict(name_a="Region A", name_b="Region B", rows=[("Wages · 2024", "120 000 RUB", "80 000 RUB")])),
    (og_image.render_world_country_og, dict(country_name="Country A", indicators_count=2, items=[("GDP", "20 bn USD (2024)")])),
]


@pytest.mark.parametrize("renderer,kwargs", CASES)
@pytest.mark.parametrize("portrait,size", [(False,(1200,630)), (True,(1080,1350))])
def test_every_hub_has_native_composition(renderer,kwargs,portrait,size):
    png=renderer(**kwargs,portrait=portrait)
    with Image.open(io.BytesIO(png)) as im:
        assert im.size==size


@pytest.mark.parametrize("path", [
    "/api/v1/og-image/region-rating/wages.png?year=2020",
    "/api/v1/og-image/today.png",
    "/api/v1/og-image/region-vs/tula-vs-moscow.png",
    "/api/v1/og-image/world-vs/france-vs-germany/population.png",
    "/api/v1/og-image/world/germany.png",
    "/api/v1/og-image/world-rating/population.png",
    "/api/v1/og-image/world-rating/population/2024.png",
    "/api/v1/og-image/world-region/united-states/california.png",
    "/api/v1/og-image/world-regions/united-states.png",
])
def test_endpoint_cache_keys_separate_portrait_from_landscape(auth_env,monkeypatch,path):
    from fastapi.testclient import TestClient
    keys=[]
    monkeypatch.setattr(og_image,"cached_og",lambda key: keys.append(key) or b"png")
    with TestClient(auth_env["app"]) as client:
        assert client.get(path).status_code==200
        assert client.get(path+("&" if "?" in path else "?")+"portrait=1").status_code==200
    assert keys[0].endswith(":landscape")
    assert keys[1].endswith(":portrait")
    assert keys[0]!=keys[1]


def test_legacy_figure_upgrade_preserves_period_cta_fallback_and_is_idempotent():
    html='<figure class="seo-chart"><a href="/world/rating/population?year=2020#chart"><img src="/og/world/rating/population/2020.png" width="1200" height="630" alt="Population 2020"></a><figcaption>Official data</figcaption></figure>'
    first=_responsive_chart_images(html)
    soup=BeautifulSoup(_responsive_chart_images(first),"html.parser")
    assert len(soup.select("picture"))==1
    assert soup.source["srcset"]=="/og/world/rating/population/2020.png?portrait=1"
    assert soup.img["src"]=="/og/world/rating/population/2020.png"
    assert soup.img["alt"]=="Population 2020"
    assert soup.a["href"].endswith("?year=2020#chart")
    assert soup.figure["data-portrait"]=="true"
    assert soup.img["fetchpriority"]=="high"


def test_country_endpoint_keeps_observation_date_and_actual_source(auth_env,monkeypatch):
    from app.models import WorldCountry, WorldIndicator, WorldDataPoint
    from fastapi.testclient import TestClient

    async def seed():
        async with auth_env["session_maker"]() as db:
            country=WorldCountry(code="US",slug="united-states",name_ru="США",name_en="United States",region_ru="Америка")
            db.add(country);await db.flush()
            ind=WorldIndicator(country_id=country.id,provider="bea",code="us-gdp-test",dataset_id="test",slice_hash="test",name_ru="ВВП",name_en="GDP",unit="USD",unit_ru="долл.",frequency="annual",source="BEA",is_listed=True,points_count=1)
            db.add(ind);await db.flush()
            db.add(WorldDataPoint(indicator_id=ind.id,date=date(2023,1,1),value=123))
            await db.commit()
    asyncio.run(seed())
    captured=[]
    monkeypatch.setattr(og_image,"cached_og",lambda key:None)
    monkeypatch.setattr(og_image,"store_og",lambda *args:None)
    monkeypatch.setattr(og_image,"render_world_country_og",lambda **kw:captured.append(kw) or b"png")
    with TestClient(auth_env["app"]) as client:
        response=client.get("/api/v1/og-image/world/united-states.png?portrait=1",headers={"X-FE-Locale":"en"})
        assert response.status_code==200
    got=captured[0]
    assert got["portrait"] is True
    assert "2023" in got["items"][0][1]
    assert "BEA" in got["footer_note"]
    assert "Eurostat" not in got["footer_note"]


def test_portrait_six_long_rows_keep_text_inside_card(monkeypatch):
    # Capture actual draw positions: dimensions alone would miss clipped values.
    draws=[]
    original=og_image.ImageDraw.ImageDraw.text
    def capture(draw, xy, text, *args, **kwargs):
        draws.append((xy,text,kwargs.get("font")))
        return original(draw,xy,text,*args,**kwargs)
    monkeypatch.setattr(og_image.ImageDraw.ImageDraw,"text",capture)
    og_image.render_world_country_og(country_name="Соединённых Штатов Америки",indicators_count=80,
        items=[("Среднемесячная заработная плата",f"{i+1} 071 156,53 млн долл. 2017 (2024)") for i in range(6)],
        portrait=True,footer_note="Fixture provenance")
    values=[(xy,text,font) for xy,text,font in draws if "долл. 2017" in text]
    assert len(values)==6
    assert all(xy[1]+font.size<1180 for xy,text,font in values)
    assert all(font.size>=36 for xy,text,font in values)


@pytest.mark.parametrize("portrait", [False, True])
def test_rating_values_use_observation_precision_not_rounded_axis_labels(monkeypatch,portrait):
    texts=[]
    original=og_image.ImageDraw.ImageDraw.text
    def capture(draw, xy, text, *args, **kwargs):
        texts.append(text)
        return original(draw,xy,text,*args,**kwargs)
    monkeypatch.setattr(og_image.ImageDraw.ImageDraw,"text",capture)
    og_image.render_world_rating_og(name="Rate",year=2024,unit="%",rows=[("A",12.45),("B",12.4)],total=2,order_label="descending",locale="en",portrait=portrait)
    assert "12.45" in texts and "12.4" in texts


@pytest.mark.parametrize("same_period", [True, False])
def test_world_comparison_preserves_dates_and_canonical_column_order(auth_env,monkeypatch,same_period):
    from app import database
    from app.models import WorldCountry, WorldIndicator, WorldDataPoint
    from fastapi.testclient import TestClient

    async def seed():
        async with auth_env["session_maker"]() as db:
            for code,slug,label,last in (("FR","france","France",2024),("DE","germany","Germany",2024 if same_period else 2023)):
                country=WorldCountry(code=code,slug=slug,name_ru=label,name_en=label,region_ru="Европа")
                db.add(country);await db.flush()
                ind=WorldIndicator(country_id=country.id,code=f"{code.lower()}-population",dataset_id="demo_pjan",slice_hash=slug,slice_json={"unit":"NR","age":"TOTAL","sex":"T"},name_ru="Население",name_en="Population",unit="NR",unit_ru="человек",frequency="annual",source="Eurostat",is_listed=True,points_count=2)
                db.add(ind);await db.flush()
                for year in (last-1,last):
                    db.add(WorldDataPoint(indicator_id=ind.id,date=date(year,1,1),value=100+year+(10 if code=="DE" else 0)))
            await db.commit()
    asyncio.run(seed())
    captured=[]
    monkeypatch.setattr(database,"async_session",auth_env["session_maker"])
    monkeypatch.setattr(og_image,"cached_og",lambda key:None)
    monkeypatch.setattr(og_image,"store_og",lambda *args:None)
    monkeypatch.setattr(og_image,"render_region_vs_og",lambda **kw:captured.append(kw) or b"png")
    with TestClient(auth_env["app"]) as client:
        r=client.get("/api/v1/og-image/world-vs/germany-vs-france/population.png?portrait=1",headers={"X-FE-Locale":"en"})
        assert r.status_code==200
    got=captured[0]
    assert got["portrait"] is True
    assert (got["name_a"],got["name_b"])==("France","Germany")
    assert got["rows"][1]==("Period","2024","2024" if same_period else "2023")
    assert any(row[0]=="Difference" for row in got["rows"]) is same_period
    assert "Eurostat" in got["footer_note"]


LONG_TITLES = [
    "Выпуск обучающихся организациями, осуществляющих образовательную деятельность по образовательным программам начального, основного и среднего общего образования — выпуск обучающихся с аттестатом о среднем общем образовании — Московская область",
    "Graduates of educational organisations implementing programmes of primary, basic and secondary general education — students graduating with a certificate of secondary general education — Moscow Region",
    "Выбросы загрязняющих веществ в атмосферный воздух, отходящих от стационарных источников загрязнения, по видам экономической деятельности — производство и распределение электрической энергии — Московская область",
]


@pytest.mark.parametrize("name", LONG_TITLES)
@pytest.mark.parametrize("portrait", [True,False])
def test_long_official_title_keeps_every_word_and_reserves_real_chart(monkeypatch,name,portrait):
    boxes=[];texts=[]
    original_chart=og_image._draw_editorial_chart
    original_text=og_image.ImageDraw.ImageDraw.text
    def chart(draw,values,box,**kw):
        boxes.append(box)
        return original_chart(draw,values,box,**kw)
    def text(draw,xy,value,*args,**kwargs):
        texts.append((xy,str(value),kwargs.get("font")))
        return original_text(draw,xy,value,*args,**kwargs)
    monkeypatch.setattr(og_image,"_draw_editorial_chart",chart)
    monkeypatch.setattr(og_image.ImageDraw.ImageDraw,"text",text)
    og_image.render_indicator_og(code="education",name=name,value_text="57 310,4",unit_suffix="тысяч человек",
        date_text="Годовое значение",context_pill="2023 → 2024: +2,5 %",values=[33,40,47,57.31],
        point_dates=[date(y,1,1) for y in range(2021,2025)],frequency="annual",period_text="2024",
        x_labels=("2021","2024"),source_label="Росстат",portrait=portrait)
    combined=" ".join(value for _,value,_ in texts)
    assert name in combined
    assert "57 310,4" in [value for _,value,_ in texts]
    assert boxes[0][3]-boxes[0][1]>=(200 if portrait else 150)
    title_words=set(name.split())
    title_bottom=max(xy[1]+font.size for xy,value,font in texts if set(value.split()) & title_words)
    number_y=next(xy[1] for xy,value,_ in texts if value=="57 310,4")
    assert title_bottom<number_y


@pytest.mark.parametrize("separator", ["\u00a0", "\u202f", "\u2007", "\u2009"])
def test_raster_unicode_spaces_match_plain_space_in_measurement_and_pixels(separator):
    plain="4 684,18"; spaced=plain.replace(" ",separator)
    assert og_image._raster_text(spaced)==plain
    assert og_image._raster_text("−1\u202f234,5\n% / $ — человек")=="−1 234,5\n% / $ — человек"
    images=[]
    for value in (plain,spaced):
        im=Image.new("RGB",(550,160),"white")
        draw=og_image._raster_draw(im)
        font=og_image.FG(72,600)
        assert draw.textlength(value,font=font)==draw.textlength(plain,font=font)
        assert draw.textbbox((0,0),value,font=font)==draw.textbbox((0,0),plain,font=font)
        draw.text((10,10),value,font=font,fill="black")
        images.append(im.tobytes())
    assert images[0]==images[1]


@pytest.mark.parametrize("portrait", [False,True])
def test_formatted_number_unicode_separator_is_identical_in_complete_image(portrait):
    common=dict(code="gdp",name="ВВП Германии",unit_suffix="млрд $",date_text="2024",values=[4500,4684.18],portrait=portrait)
    assert og_image.render_indicator_og(value_text="4\u202f684,18",**common)==og_image.render_indicator_og(value_text="4 684,18",**common)
