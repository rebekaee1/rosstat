"""Классификация скачанных наборов ЕМИСС: название, ведомство, уровень, частота, периоды, ряды, значения, свежесть, дубли.
Только чтение: читает catalog.json, pages/, grid/ сборщика; пишет classified.csv и classified.md рядом с ними.
В базы ничего не пишет.

    python3 -I scripts/emiss/classify_collected.py [--data DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grid_to_series import (REGIONAL, TERRITORY_DIMS, UNIT_DIM, iter_cells, load_grid, parse_period,  # noqa: E402
                            parse_ru_float, period_layer)

DATA = Path("/Users/iprofi/tradingeconomics/rosstat/.artifacts/emiss-opendata-2026-11-08")
TODAY = date(2026, 11, 9)
STALE_BEFORE = (TODAY.year - 2, TODAY.month)          # последний период раньше этого месяца → устарел

# ИНН ведомства из идентификатора набора. Названия — по составу наборов; в самом каталоге их нет.
AGENCIES = {
    "7708234640": "Росстат",
    "7702235133": "Банк России",
    "7710539135": "Минобрнауки",
    "7707418081": "Образование (Рособрнадзор/Минпросвещения)",
    "7706016118": "Социальный фонд",
    "7708525167": "Транспорт (ВСМ, РЖД)",
    "7706562710": "ФСИН",
    "7708257207": "Минрегион (идентичность)",
}

# ЕМИСС-наборы, которые сайт уже подключил (кодом): цены 31448, труд 43913/591xx/593xx/62298, зарплаты 33414/43062.
SITE_EMISS_IDS = {"31448", "33414", "43062", "43913", "59191", "59194", "59197", "59301", "59302", "59303", "62298"}

# Тема → (человеческое название, раздел регионального каталога, категория карточек России, вес пользы)
TOPICS = [
    ("natacc", r"снс|конечное потребление|конечный спрос|валовое накопление|валовой национальный|паритет покупательной способности|статистическое расхождение|запасов материальных", "Национальные счета (СНС)", "8 Валовой региональный продукт", "gdp", 6),
    ("prices", r"\bцен|тариф|инфляц|стоимость (набора|услуг|одного)", "Цены и тарифы", "20 Цены и тарифы", "prices", 10),
    ("wages", r"заработн|оплат[аы] труда|зарплат", "Зарплаты", "3 Уровень жизни населения", "labor", 10),
    ("agri", r"сельск|урожа|скот|зерн|молок|посев|животн|растениевод|птиц|яйценос|настриг|рыб|тракторов|ферм", "Сельское хозяйство", "13 Сельское хозяйство", "business", 6),
    ("income", r"доход|прожиточн|бедност|малоимущ|пенси|потребительские расходы|расходы домашних|домохозяйств|трансферт|коэффициент фондов", "Доходы и уровень жизни", "3 Уровень жизни населения", "population", 9),
    ("housing", r"жиль|жилищ|жилых|квартир|ипотек|многоквартир|аварийн|коммунальн|теплоснабж|водопровод|водоснабж|сточн|канализац|газификац|благоустро|расход воды|утечек", "Жильё и ЖКХ", "14 Строительство + новый «Жильё и ЖКХ»", "prices", 9),
    ("labor", r"безработ|занят|рабочей силы|рабочая сила|вакан|трудов|охран[аы] труда|производственн.*травм|производительност. труда", "Рынок труда", "2 Труд", "labor", 9),
    ("population", r"рожд|смерт|умерш|миграц|выбыло|прибыло|численност[ьи] (постоянного )?населения|население в разбивке|браков|развод|демограф|ожидаемая продолжительность|возрастн|доля городского|беременн", "Население и демография", "1 Население", "population", 8),
    ("health", r"здравоох|заболева|врач|медицин|больнич|поликлин|коек|пациент|вакцин|инвалид|лекарств|нетрудоспособност|утрат. профессиональн", "Здоровье", "5 Здравоохранение", "population", 8),
    ("education", r"образован|школ|студент|вуз|дошкольн|учител|педагог|егэ|выпускник|обучающ|колледж", "Образование", "4 Образование", "science", 8),
    ("culture", r"культурн.*наслед|музе|театр|библиотек|туризм|турист|гостиниц|санатор|отдых", "Культура, туризм", "6 Культура, отдых и туризм", "population", 6),
    ("ecology", r"окружающ|выброс|отход|лесн|лес[аов] |водопотреблен|охран[аы] (природ|воздух|вод)|земел|особо охраняем|красного списка", "Природа и экология", "7 Земельные ресурсы и охрана среды", "business", 5),
    ("grp", r"валов.*(региональн|внутренн)|ввп|врп", "ВРП и ВВП", "8 Валовой региональный продукт", "gdp", 7),
    ("invest", r"инвестиц|основн.*(фонд|капитал)", "Инвестиции и основные фонды", "10 Инвестиции / 9 Основные фонды", "business", 6),
    ("industry", r"промышлен|добыч|обрабатывающ|производство|производил|отгружен|выпуск продукц|электроэнерг|тепловой энерги", "Промышленность", "12 Промышленное производство", "business", 6),
    ("construction", r"строительств|строительн|ввод", "Строительство", "14 Строительство", "business", 6),
    ("trade", r"торгов|розничн|общественного питания|услуг.*населени|платных услуг|ярмарк", "Торговля и услуги", "15 Торговля и услуги населению", "business", 6),
    ("transport", r"транспорт|дорог|дтп|железнодорож|авиа|перевозк|пассажир|автомобил|судов|порт", "Транспорт и безопасность дорог", "16 Транспорт", "business", 5),
    ("ict", r"интернет|связь|связи|цифров|информационн|телефон|широкополос|информатизац", "Связь и цифровизация", "17 ИКТ", "science", 5),
    ("science", r"наук|исследован|инновац|патент|технолог|стартап|изобретен|кубит|квант", "Наука и инновации", "18 Наука и инновации", "science", 5),
    ("finance", r"кредит|банк|бюджет|налог|денежн|вклад|депозит|долг|ставк|финанс|страхов|ликвидност|счет|курс", "Финансы", "19 Финансы", "finance", 5),
    ("trade_ext", r"внешн.*торгов|экспорт|импорт", "Внешняя торговля", "21 Внешняя торговля", "trade", 5),
    ("crime", r"преступ|правонаруш|осужд|суд[аеыо]|адвокат|следствен|заключенн|исправительн|мвд|полици|несовершеннолетн|нарушител", "Правонарушения и юстиция", "22 Правонарушения", "population", 4),
    ("business", r"организаци|предприят|малого|малое|индивидуальн.*предприним|банкрот", "Бизнес и организации", "11 Организации", "business", 5),
    ("social", r"молод|семь[яи]|дет[ейи]|социальн|ветеран|волонтер|идентичност", "Социальная политика, семья, молодёжь", "3 Уровень жизни населения", "population", 5),
]
TOPIC_RE = [(k, re.compile(rx), label, sec, cat, w) for k, rx, label, sec, cat, w in TOPICS]

FIELDS = ["indicator_id", "ident", "title", "agency", "agency_name", "level", "frequency", "first_period", "last_period",
          "territories", "rows", "series", "values", "units", "data_date", "collected", "flags", "topic", "site_section",
          "russia_category", "action", "score"]


def norm_tokens(text: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[а-яёa-z0-9]{4,}", text.lower())}


def match_topic(title: str):
    t = title.lower() + " "
    for k, rx, label, sec, cat, w in TOPIC_RE:
        if rx.search(t):
            return k, label, sec, cat, w
    return "other", "Прочее", "", "", 1


def month_end(kind: str, num: int, year: int) -> tuple[int, int]:
    if kind == "M" or kind in ("C", "S", "D"):
        return year, num
    if kind in ("Q", "QE"):
        return year, num * 3
    if kind == "H":
        return year, num * 6
    if kind == "AS":
        return year, 1
    return year, 12


def label(layer: str, ym: tuple[int, int]) -> str:
    y, m = ym
    return f"{y}" if layer == "annual" else f"{y}-{m:02d}"


def scan_grid(grid_path: Path, page_path: Path):
    grid = load_grid(grid_path)
    page = json.load(open(page_path)) if page_path.exists() else {"dims": {}}
    periods = page.get("dims", {}).get("33560", {}).get("values", {})
    terr_dim = next((d for d in grid.get("lines", []) if d in TERRITORY_DIMS), None)
    ocsm = "30613" in grid.get("lines", [])
    rows = set(); series = set(); terr = set(); units = collections.Counter(); values = 0
    layer_counts = collections.Counter(); first = last = None; kinds = set()
    skip = {"0", "3", "33560", UNIT_DIM}
    qual = [d for d in grid.get("lines", []) if d not in skip and d != terr_dim]
    seen_rows = set()
    for pl in grid.get("payloads", []):
        for row in pl.get("results", []):
            rk = tuple(str(row.get(f"dim{d}") or "") for d in grid.get("lines", []))
            seen_rows.add(rk)
            series.add((tuple(str(row.get(f"dim{d}") or "") for d in qual), str(row.get(f"dim{UNIT_DIM}") or "")))
            if terr_dim:
                terr.add(str(row.get(f"dim{terr_dim}") or ""))
            units[str(row.get(f"dim{UNIT_DIM}") or "")] += 1
    for row, year, oid, raw in iter_cells(grid.get("payloads", [])):
        if parse_ru_float(raw) is None:
            continue
        kind, num = parse_period(periods.get(oid, "значение показателя за год")) if oid else ("A", 0)
        layer = period_layer(kind) if kind != "?" else "other"
        values += 1
        layer_counts[layer] += 1
        kinds.add(kind)
        ym = month_end(kind, num, year)
        if first is None or ym < first: first = ym
        if last is None or ym > last: last = ym
    dom = layer_counts.most_common(1)[0][0] if layer_counts else ""
    return {
        "terr_dim": terr_dim, "ocsm": ocsm, "territories": len(terr), "rows": len(seen_rows), "series": len(series),
        "values": values, "units": [u for u, _ in units.most_common(3) if u], "layer": dom, "layers": layer_counts,
        "first": first, "last": last, "kinds": kinds,
        "page_terr_values": len(page.get("dims", {}).get(terr_dim, {}).get("values", {})) if terr_dim else 0,
    }


def level_of(info, title: str) -> str:
    if info is None:
        t = title.lower()
        if "муниципал" in t: return "муниципалитеты?"
        if "по странам" in t or "стран" in t: return "страны?"
        if "субъект" in t or "регион" in t: return "регионы?"
        return "не собран"
    if info["ocsm"]:
        return "страны"
    if info["terr_dim"] == "36175" and info["page_terr_values"] > 300:
        return "муниципалитеты"
    if info["terr_dim"]:
        return "регионы"
    return "Россия"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DATA)); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    data = Path(a.data); out = Path(a.out or a.data)
    cat = json.load(open(data / "catalog.json"))
    regional = json.load(open(REGIONAL / "indicators.json"))
    reg_tokens = [(r["code"], r["section_num"], norm_tokens(r["name"])) for r in regional if r.get("frequency") is None]
    out_rows = []
    for r in cat:
        iid = r["indicator_id"]; gp = data / "grid" / f"{iid}.json.gz"
        info = scan_grid(gp, data / "pages" / f"{iid}.json") if gp.exists() else None
        title = " ".join(r["title"].split())
        flags = []
        topic, tlabel, sec, rcat, w = match_topic(title)
        lvl = level_of(info, title)
        if info:
            if info["values"] == 0: flags.append("пустой")
            if info["last"] and info["last"] < STALE_BEFORE: flags.append("устарел")
            if info["kinds"] & {"C"}: flags.append("нарастающим итогом")
            if info["kinds"] & {"S", "D", "QE", "AS", "H", "?"} and not (info["kinds"] & {"M", "Q", "A", "AE"}): flags.append("только срезы/полугодия")
            if info["layers"].get("quarterly"): flags.append("есть кварталы")
        else:
            dd = r["data_date"] or ""
            if dd and dd < f"{STALE_BEFORE[0]}-{STALE_BEFORE[1]:02d}": flags.append("каталог: обновлён давно")
        if info and info["last"] and info["last"] > (TODAY.year, TODAY.month): flags.append("период в будущем (план/прогноз?)")
        if iid in SITE_EMISS_IDS: flags.append("дубль: уже на сайте")
        else:
            tk = norm_tokens(title)
            best = max(((len(tk & t) / max(1, len(tk | t)), c, s) for c, s, t in reg_tokens), default=(0, "", 0))
            if best[0] >= 0.6 and (info is None or info["values"]): flags.append(f"похож на региональный {best[1]}")
        agency_name = AGENCIES.get(r["agency"], r["agency"])
        score = 0.0
        action = "не собран"
        if info:
            fresh = 0 if "устарел" in flags else 1
            reach = {"регионы": 1.0, "Россия": 0.6, "муниципалитеты": 0.8, "страны": 0.3}.get(lvl, 0.3)
            terr_bonus = 1.3 if info["territories"] >= 80 else 1.0
            score = round(w * reach * fresh * terr_bonus * math.log10(info["values"] + 10), 2) if info["values"] else 0.0
            if "пустой" in flags: action = "не брать: пусто"
            elif "дубль: уже на сайте" in flags: action = "не брать: уже есть"
            elif "устарел" in flags: action = "не брать: устарел"
            elif topic == "other" or w <= 1: action = "скрыть/позже: тема неясна"
            elif info["values"] < 20: action = "скрыть: мало значений"
            elif score >= 25: action = "первым"
            elif any(f.startswith("похож") for f in flags): action = "проверить дубль"
            else: action = "взять"
        out_rows.append({
            "indicator_id": iid, "ident": r["ident"], "title": title, "agency": r["agency"], "agency_name": agency_name,
            "level": lvl, "frequency": {"annual": "год", "monthly": "месяц", "quarterly": "квартал", "other": "срезы", "": ""}[info["layer"]] if info else "",
            "first_period": label(info["layer"], info["first"]) if info and info["first"] else "",
            "last_period": label(info["layer"], info["last"]) if info and info["last"] else "",
            "territories": info["territories"] if info else "", "rows": info["rows"] if info else "",
            "series": info["series"] if info else "", "values": info["values"] if info else "",
            "units": "; ".join(info["units"]) if info else "", "data_date": r["data_date"] or "",
            "collected": "да" if info else "нет", "flags": "; ".join(flags), "topic": tlabel,
            "site_section": sec, "russia_category": rcat, "action": action, "score": score,
        })
    out_rows.sort(key=lambda x: (x["collected"] != "да", -float(x["score"] or 0), x["title"]))
    with open(out / "classified.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=FIELDS); wr.writeheader(); wr.writerows(out_rows)
    write_md(out / "classified.md", out_rows)
    n = sum(1 for x in out_rows if x["collected"] == "да")
    print(f"каталог {len(out_rows)}, собрано {n}, значений {sum(int(x['values']) for x in out_rows if x['values'] != '')}")


def write_md(path: Path, rows):
    got = [r for r in rows if r["collected"] == "да"]
    L = [f"# Классификация наборов ЕМИСС ({TODAY.isoformat()})", "",
         f"Каталог открытых данных: {len(rows)} наборов; скачано и разобрано: {len(got)}. "
         "Свежесть: «устарел» — последний период раньше "
         f"{STALE_BEFORE[1]:02d}.{STALE_BEFORE[0]}. Подробности по каждому набору — `classified.csv`.", ""]

    def table(title, keyf, rows_):
        agg = collections.defaultdict(lambda: [0, 0, 0, 0])
        for r in rows_:
            a = agg[keyf(r)]
            a[0] += 1; a[1] += int(r["series"] or 0); a[2] += int(r["values"] or 0)
            a[3] += 1 if r["action"] in ("первым", "взять", "проверить дубль") else 0
        L.append(f"## {title}"); L.append("")
        L.append("| Группа | Наборов | Рядов | Значений | Годны к показу |"); L.append("|---|---:|---:|---:|---:|")
        for k, (n, s, v, g) in sorted(agg.items(), key=lambda kv: -kv[1][2]):
            L.append(f"| {k} | {n} | {s:,} | {v:,} | {g} |".replace(",", "\u202f") if False else "| " + k + " | " + str(n) + " | " + f"{s:,}".replace(",", " ") + " | " + f"{v:,}".replace(",", " ") + f" | {g} |")
        L.append("")

    table("По темам (скачанные)", lambda r: r["topic"], got)
    table("По разделам сайта (скачанные)", lambda r: r["site_section"] or "— без раздела", got)
    table("По уровню (скачанные)", lambda r: r["level"], got)
    table("По ведомству (скачанные)", lambda r: r["agency_name"], got)
    table("По решению (скачанные)", lambda r: r["action"], got)
    ctab = collections.Counter(r["topic"] for r in rows if r["collected"] != "да")
    L.append("## Чего ещё нет на ноутбуке (по каталогу, по темам)"); L.append("")
    L.append("| Тема | Наборов в каталоге |"); L.append("|---|---:|")
    for k, v in ctab.most_common(): L.append(f"| {k} | {v} |")
    L.append(""); L.append("## 30 самых полезных (оценка: вес темы × охват × свежесть × лог значений)"); L.append("")
    L.append("| № | Набор | Уровень | Частота | Последний | Терр. | Значений | Куда |"); L.append("|---:|---|---|---|---|---:|---:|---|")
    top = [r for r in got if r["action"] in ("первым", "взять", "проверить дубль")][:30]
    for i, r in enumerate(top, 1):
        L.append(f"| {i} | [{r['indicator_id']}] {r['title'][:90]} | {r['level']} | {r['frequency']} | {r['last_period']} | {r['territories']} | {r['values']} | {r['site_section'] or r['russia_category']} |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
