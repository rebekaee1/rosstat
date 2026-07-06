"""Кураторские единицы измерения для региональных показателей без unit (В-8).

79 показателей сборника «Регионы России» публикуются без единицы в шапке
таблицы (единица растворена в названии или примечании) — extract_unit()
отдавал пустую строку, и карточка показывала «Соотношение мужчин и женщин:
1200» без «на 1000 мужчин». Здесь единица восстановлена из примечаний
таблиц и методологии Росстата.

Потребители:
  - `parse_pril_2025.py` — подставляет при пересборке артефакта;
  - `python scripts/regional/unit_fallbacks.py --apply-artifact` — разово
    патчит уже закоммиченный `backend/app/data/regional/indicators.json`
    (сидер подхватит при следующем старте).
"""
from __future__ import annotations

_ZAB = "случаев на 1000 человек населения"
_PCT_ORG = "% организаций"
_PCT_HH = "% домашних хозяйств"
_PCT_POP = "% населения"
_UNITS_COUNT = "единиц"

UNIT_FALLBACK_BY_CODE: dict[str, str] = {
    "sootnoshenie-muzhchin-i-zhenschin": "женщин на 1000 мужчин",
    "koeffitsienty-demograficheskoy-nagruzki-vsego": "на 1000 человек трудоспособного возраста",
    "koeffitsienty-demograficheskoy-nagruzki-molozhe-trudosposobnogo-vozrasta": "на 1000 человек трудоспособного возраста",
    "koeffitsienty-demograficheskoy-nagruzki-starshe-trudosposobnogo-vozrasta": "на 1000 человек трудоспособного возраста",
    "obschie-koeffitsienty-rozhdaemosti": "родившихся на 1000 человек населения",
    "obschie-koeffitsienty-smertnosti": "умерших на 1000 человек населения",
    "koeffitsienty-mladencheskoy-smertnosti": "умерших до 1 года на 1000 родившихся живыми",
    "koeffitsienty-estestvennogo-prirosta-naseleniya-na-1000-chelovek": "на 1000 человек населения",
    "obschie-koeffitsienty-brachnosti-na-1000-chelovek-naseleniya": "браков на 1000 человек населения",
    "obschie-koeffitsienty-razvodimosti-na-1000-chelovek-naseleniya": "разводов на 1000 человек населения",
    "sootnoshenie-brakov-i-razvodov": "разводов на 1000 браков",
    "koeffitsienty-migratsionnogo-prirosta-na-10-000-chelovek": "на 10 000 человек населения",
    "chislennost-pensionerov-na-1000-chelovek-naseleniya": "на 1000 человек населения",
    "struktura-potrebitelskih-rashodov-domashnih-hozyaystv": "%",
    "udelnyy-ves-rashodov-domashnih-hozyaystv-na-oplatu": "%",
    "udelnyy-ves-rashodov-domashnih-hozyaystv-na-oplatu-3-27-2": "%",
    "obespechennost-detey-doshkolnogo-vozrasta-mestami-v-organizatsiyah": "мест на 1000 детей",
    "beremennosti-s-abortivnym-ishodom-na-1000-zhenschin": "на 1000 женщин 15–49 лет",
    "beremennosti-s-abortivnym-ishodom-na-100-rodov": "на 100 родов",
    "zabolevaemost-na-1000-chelovek-naseleniya": _ZAB,
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym": _ZAB,
    **{f"zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-{i}": _ZAB for i in range(2, 17)},
    "chislo-sportivnyh-sooruzheniy-stadiony-s-tribunami-na": _UNITS_COUNT,
    "chislo-sportivnyh-sooruzheniy-ploskostnye-sportivnye-sooruzheniya-ploschadki": _UNITS_COUNT,
    "chislo-sportivnyh-sooruzheniy-sportivnye-zaly": _UNITS_COUNT,
    "chislo-sportivnyh-sooruzheniy-plavatelnye-basseyny": _UNITS_COUNT,
    "detskie-ozdorovitelnye-lagerya-chislo-detskih-ozdorovitelnyh-lagerey": _UNITS_COUNT,
    "kollektivnye-sredstva-razmescheniya-chislo-kollektivnyh-sredstv-razmescheniya": _UNITS_COUNT,
    "turistskie-firmy-chislo-turistskih-firm": _UNITS_COUNT,
    "itogi-sploshnyh-nablyudeniy-chislo-malyh-predpriyatiy-na": "на 10 000 человек населения",
    "itogi-sploshnyh-nablyudeniy-chislo-individualnyh-predprinimateley-na": "на 10 000 человек населения",
    "lesnye-pozhary-na-zemlyah-lesnogo-fonda-i": _UNITS_COUNT,
    "vvod-v-deystvie-zdaniy-zhilogo-i-nezhilogo": _UNITS_COUNT,
    "vvod-v-deystvie-kvartir-vsego": "квартир",
    "vvod-v-deystvie-kvartir-na-1000-chelovek": "квартир на 1000 человек населения",
    "zhilye-doma-nahodyaschiesya-v-nezavershennom-stroitelstve": _UNITS_COUNT,
    "oborot-roznichnoy-torgovli-po-torgovym-setyam": "% от оборота розничной торговли",
    "struktura-oborota-roznichnoy-torgovli-pischevye-produkty-vklyuchaya": "% от оборота розничной торговли",
    "struktura-oborota-roznichnoy-torgovli-neprodovolstvennye-tovary": "% от оборота розничной торговли",
    "plotnost-zheleznodorozhnyh-putey-obschego-polzovaniya": "км на 10 000 км² территории",
    "plotnost-avtomobilnyh-dorog-obschego-polzovaniya-s-tverdym": "км на 1000 км² территории",
    "chislo-dorozhno-transportnyh-proisshestviy-na-100000-chelovek": "на 100 000 человек населения",
    "ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie": _PCT_ORG,
    **{f"ispolzovanie-tsifrovyh-tehnologiy-v-organizatsiyah-organizatsii-ispolzovavshie-17-1-{i}": _PCT_ORG for i in range(2, 10)},
    "organizatsii-imevshie-veb-sayt": _PCT_ORG,
    "ispolzovanie-elektronnogo-dokumentooborota-v-organizatsiyah-organizatsii-ispolzovavshie": _PCT_ORG,
    "ispolzovanie-elektronnogo-dokumentooborota-v-organizatsiyah-organizatsii-ispolzovavshie-17-5-2": _PCT_ORG,
    "ispolzovanie-kompyuterov-i-seti-internet-v-domashnih": _PCT_HH,
    "ispolzovanie-kompyuterov-i-seti-internet-v-domashnih-17-6-2": _PCT_HH,
    "ispolzovanie-kompyuterov-i-seti-internet-v-domashnih-17-6-3": _PCT_HH,
    "ispolzovanie-seti-internet-naseleniem-naselenie-ispolzovavshee-set": _PCT_POP,
    "ispolzovanie-seti-internet-naseleniem-naselenie-ispolzovavshee-set-17-7-2": _PCT_POP,
    "ispolzovanie-seti-internet-naseleniem-naselenie-ispolzovavshee-set-17-7-3": _PCT_POP,
    "organizatsii-vypolnyavshie-nauchnye-issledovaniya-i-razrabotki": _UNITS_COUNT,
    "razrabotannye-peredovye-proizvodstvennye-tehnologii": _UNITS_COUNT,
    "ispolzuemye-peredovye-proizvodstvennye-tehnologii": _UNITS_COUNT,
    "sredstva-vklady-fizicheskih-lits-na-valyutnyh-schetah": "млн руб.",
    "chislennost-gosudarstvennyh-grazhdanskih-sluzhaschih-territorialnyh-organov-federalnyh": "человек",
}


def fill_unit(code: str, unit: str) -> str:
    """Единица из парсера, либо кураторский фолбэк, либо как было."""
    if (unit or "").strip():
        return unit
    return UNIT_FALLBACK_BY_CODE.get(code, unit)


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    if "--apply-artifact" not in sys.argv:
        print("usage: python scripts/regional/unit_fallbacks.py --apply-artifact")
        raise SystemExit(2)

    artifact = Path(__file__).resolve().parents[2] / "backend/app/data/regional/indicators.json"
    indicators = json.loads(artifact.read_text(encoding="utf-8"))
    patched = 0
    for ind in indicators:
        new_unit = fill_unit(ind["code"], ind.get("unit") or "")
        if new_unit != (ind.get("unit") or ""):
            ind["unit"] = new_unit
            patched += 1
    artifact.write_text(
        json.dumps(indicators, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    empty = [i["code"] for i in indicators if not (i.get("unit") or "").strip()]
    print(f"patched: {patched}; осталось пустых unit: {len(empty)}")
    for c in empty:
        print(" -", c)
