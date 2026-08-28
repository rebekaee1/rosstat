"""Фетчер ЕМИСС (fedstat.ru): топливные показатели по субъектам РФ в артефакт regional.

Закрывает пробел «потребление автомобильного топлива по регионам»: прямого
показателя потребления в открытой статистике нет, поэтому собираем фактуру
смежными витринами ЕМИСС:

1. 31448 — средние потребительские цены на бензин/дизель (руб./л), помесячно,
   живая витрина (обновляется ежемесячно), с 2000 года.
2. 57699 — розничные продажи дизельного топлива (тыс. руб.), годовые
   (кумулятив «январь–декабрь»). Бензина в витрине нет; топливный срез
   публикуется по 2021 год.
3. 59002 — оптовые продажи нефтепродуктов (тыс. тонн), годовые, только 2017.

Механика dataGrid.do (проверена живьём 2026-08-26/27): все обязательные
измерения должны иметь хотя бы одно выбранное значение, иначе пустой ответ.
Территории (ОКАТО 57831) перечисляются явно — «все территории» не отдаётся.
РФ берётся значением «РФ без учёта новых субъектов» (1849012): каноническое
значение 1688487 с 2023 года пусто по большинству периодов. Месяцы не
смешиваются в одном запросе: ключ ячейки не содержит период, значения
схлопываются в последнюю выбранную ячейку — фетч идёт запросами
«год × месяц», каждый такой запрос отдаёт все территории сразу (~0.8 с).

Выход: backend/app/data/regional/fuel_points.csv
(indicator_code;region_slug;period;value). Период цен — YYYYMM, годовых
витрин — YYYY. В data.csv.gz артефакта точки досеиваются отдельным шагом
(scripts/regional/append_fuel_to_artifact.py), сидер остаётся без изменений.

Запуск: python3 scripts/regional/fetch_emiss_fuel.py [--years 2000-2026]
         [--skip-prices] [--skip-annual]
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "backend", "app", "data", "regional", "fuel_points.csv",
)

DATA_GRID_URL = "https://www.fedstat.ru/indicator/dataGrid.do"
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
}

RUSSIA_ID = "1849012"

OKATO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emiss_okato_31448.json")
DIMNAMES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emiss_dimnames.json")

# 58273 «Виды товаров и услуг» витрины 31448 (проверено живьём 2026-08-27).
PRICE_FUELS = {
    "1709730": "ceni-ai92",
    "1709750": "ceni-ai95",
    "1755196": "ceni-dt",
}

# 33560 «Период» витрины 31448.
MONTHS = [
    ("1540283", 1), ("1540282", 2), ("1540236", 3), ("1540229", 4),
    ("1540235", 5), ("1540234", 6), ("1540233", 7), ("1540228", 8),
    ("1540276", 9), ("1540273", 10), ("1540272", 11), ("1540230", 12),
]

# 57939 «ОКПД2» витрины 57699 (розничные продажи, тыс. руб. — единица 950352).
# Бензина в витрине нет, только дизельное топливо (проверено 2026-08-27: слово
# «бензин» в конфиге витрины отсутствует).
RETAIL_FUELS_57699 = {
    "1700657": "roznica-dt",
}

# 57939 витрины 59002 (оптовые продажи, тыс. тонн), 2017.
WHOLESALE_FUELS_59002 = {
    "1704128": "opt-benzin",
    "1692982": "opt-dt",
}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def post_grid(indicator: int, params: list[tuple[str, str]]) -> dict:
    body = urllib.parse.urlencode(params).encode()
    headers = dict(HEADERS)
    headers["Referer"] = f"https://www.fedstat.ru/indicator/{indicator}"
    req = urllib.request.Request(
        f"{DATA_GRID_URL}?id={indicator}", data=body, headers=headers
    )
    last_err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read())
        except Exception as e:  # noqa: BLE001 — ретрай транзиентных сетевых сбоев
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"dataGrid.do?id={indicator}: {last_err}")


def parse_ru_float(raw):
    if raw in (None, "", "-"):
        return None
    try:
        return float(str(raw).replace("\xa0", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def territory_ids(okato: dict) -> list[str]:
    return sorted(set(okato.values()) | {RUSSIA_ID})


def dim_slug(row: dict, dimnames: dict):
    return dimnames.get(row.get("dim57831"))


def key_fuel_oid(key: str, fuels: dict) -> str | None:
    """Код товара из dim-ключа ячейки.

    Форматы различаются по витринам: 31448/59002 — `dim<товар>_d…_i…`;
    57699 — `dim<год>_<ед>_<товар>_<период>_d…_i…`. Ищем первый сегмент,
    известный в словаре топливных кодов.
    """
    for part in key[3:].split("_"):
        if part in fuels:
            return part
        if part.startswith("d") and part[1:].isdigit():
            break
    return None


def fetch_prices(years, okato, dimnames):
    """31448: запрос «год × месяц» → все территории × 3 топлива."""
    points = []
    ids = territory_ids(okato)
    # Каноническая РФ (ОКАТО 1688487) — единственная территория со сквозным
    # рядом с 2003; «РФ без новых субъектов» (1849012) появляется в витрине
    # только с 2023-01. Догружаем обе и склеиваем в slug `russia`: до 2022
    # значение канонической, с 2023 — новой единицы (на стыке методологически
    # однородны — средние цены, состав субъектов на уровень не влияет заметно).
    RUSSIA_LEGACY = "1688487"
    for year in years:
        for month_oid, month in MONTHS:
            params = [
                ("lineObjectIds", "57831"),
                ("columnObjectIds", "58273"),
                ("selectedFilterIds", "0_31448"),
                ("selectedFilterIds", f"3_{year}"),
                ("selectedFilterIds", "30611_950351"),
                ("selectedFilterIds", f"33560_{month_oid}"),
            ]
            params += [("selectedFilterIds", f"58273_{f}") for f in PRICE_FUELS]
            params += [("selectedFilterIds", f"57831_{oid}") for oid in ids]
            if year <= 2022:
                params.append(("selectedFilterIds", f"57831_{RUSSIA_LEGACY}"))

            d = post_grid(31448, params)
            rows = d.get("results", [])
            n_new = 0
            for row in rows:
                slug = dim_slug(row, dimnames)
                if row.get("dim57831") == RUSSIA_LEGACY:
                    slug = "russia"  # каноническая РФ до 2023 → тот же slug
                if not slug:
                    continue
                for key, raw in row.items():
                    if "_d" not in key or raw in (None, "", "-"):
                        continue
                    fuel_oid = key_fuel_oid(key, PRICE_FUELS)
                    if not fuel_oid:
                        continue
                    code = PRICE_FUELS.get(fuel_oid)
                    if not code:
                        continue
                    value = parse_ru_float(raw)
                    if value is None:
                        continue
                    points.append((code, slug, year * 100 + month, value))
                    n_new += 1
            print(f"  31448 {year}-{month:02d}: {n_new} значений", flush=True)
            time.sleep(0.4)
    return points


def fetch_annual(indicator, fuels, years, extra_filters, okato, dimnames):
    """Годовые витрины 57699/59002: один запрос на год."""
    points = []
    ids = territory_ids(okato)
    for year in years:
        params = [
            ("lineObjectIds", "57831"),
            ("columnObjectIds", "3"),
            ("columnObjectIds", "30611"),
            ("columnObjectIds", "57939"),
            ("columnObjectIds", "33560"),
            ("selectedFilterIds", f"0_{indicator}"),
            ("selectedFilterIds", f"3_{year}"),
        ]
        params += extra_filters
        params += [("selectedFilterIds", f"57939_{f}") for f in fuels]
        params += [("selectedFilterIds", f"57831_{oid}") for oid in ids]

        d = post_grid(indicator, params)
        rows = d.get("results", [])
        for row in rows:
            slug = dim_slug(row, dimnames)
            if not slug:
                continue
            for key, raw in row.items():
                if "_d" not in key or raw in (None, "", "-"):
                    continue
                fuel_oid = key_fuel_oid(key, fuels)
                if not fuel_oid:
                    continue
                code = fuels.get(fuel_oid)
                if not code:
                    continue
                value = parse_ru_float(raw)
                if value is None:
                    continue
                points.append((code, slug, year, value))
        print(f"  {indicator} {year}: {len(points)} точек накопленно, строк {len(rows)}")
    return points


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2000-2026", help="диапазон лет цен 31448")
    ap.add_argument("--skip-prices", action="store_true")
    ap.add_argument("--skip-annual", action="store_true")
    args = ap.parse_args()

    y0, y1 = (int(x) for x in args.years.split("-"))
    okato = load_json(OKATO_PATH)
    dimnames = load_json(DIMNAMES_PATH)
    points: list[tuple[str, str, int, float]] = []

    if not args.skip_prices:
        print("31448: средние потребительские цены (помесячно)…")
        points += fetch_prices(range(y0, y1 + 1), okato, dimnames)

    if not args.skip_annual:
        print("57699: розничные продажи дизтоплива (годовые, 2017–2021)…")
        points += fetch_annual(
            57699, RETAIL_FUELS_57699, range(2017, 2022),
            [("selectedFilterIds", "30611_950352"),
             ("selectedFilterIds", "33560_1540286")],
            okato, dimnames,
        )
        print("59002: оптовые продажи нефтепродуктов (2017)…")
        points += fetch_annual(
            59002, WHOLESALE_FUELS_59002, [2017],
            [("selectedFilterIds", "30611_1341910"),
             ("selectedFilterIds", "33560_1558883"),
             ("selectedFilterIds", "57956_1694829")],
            okato, dimnames,
        )

    with open(OUT_PATH, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["indicator_code", "region_slug", "period", "value"])
        for p in points:
            w.writerow(p)
    print(f"итого: {len(points)} точек → {OUT_PATH}")


if __name__ == "__main__":
    main()
