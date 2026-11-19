"""Цены производителей на сталь в России из ЕМИСС 57606 (19.11.2026).

Ряд `steel` (мировая цена горячекатаного проката в долларах) снят 16.08.2026: свободного официального источника не
было. Люди сталь ищут (поиск «сталь», «steel», «стальной прокат» с нулём результатов, гипотезы Пульса с 16.09),
поэтому заведены официальные помесячные цены Росстата — «Средние цены производителей промышленных товаров», рубли за тонну, с января 2017 года, Россия целиком, канал
«Внутренний рынок» (цены для покупателей в России; в канале «Всего» есть экспорт):

- прокат листовой горячекатаный стальной, без дополнительной обработки — та же продукция, что и прежний `steel`;
- прокат сортовой и катанка из нелегированных сталей — арматура, круг, катанка (строительный прокат);
- трубы стальные электросварные — самые массовые стальные трубы.

Не взяты (живой запрос 19.11.2026): «Прокат сортовой и катанка горячекатаные стальные» (1693266) и «Трубы, профили
пустотелые и их фитинги стальные» (1700490) — агрегаты без опубликованных значений; «Трубы круглого сечения прочие»
(1795425) — значения 0,4–1,2 млн ₽/т скачут в разы от месяца к месяцу; «Сталь нелегированная в слитках» (1693561) на
внутреннем рынке — тонкий рынок: 13–75 тыс. ₽/т с перепадами в полтора раза за месяц.
"""

from dataclasses import dataclass

DATASET = 57606
PRODUCT_DIM = "57939"       # ОКПД2
RUBLE = "950351"
TONNE = "1694829"           # ОКЕИ «Тонна»
DOMESTIC = "1744136"        # канал реализации «Внутренний рынок»
FIRST_YEAR = 2017
SOURCE_URL = f"https://www.fedstat.ru/indicator/{DATASET}"
UNIT, UNIT_EN = "руб./т", "RUB/t"


# Название ряда держит слово «стали» и не держит «стальн…»/«из … стали»: так поиск отличает цену стали от посуды
# из стали (search_language.MEASURE_RULES["steel"]).
@dataclass(frozen=True)
class SteelSeries:
    product: str        # oid позиции ОКПД2
    label: str          # название позиции у Росстата (так приходит в ответе)
    name: str
    name_en: str
    explanation: str
    explanation_en: str


SERIES: dict[str, SteelSeries] = {
    "steel-hot-rolled": SteelSeries(
        "1694672", "Прокат листовой горячекатаный стальной, без дополнительной обработки",
        "Цена стали: горячекатаный лист", "Steel price: hot-rolled sheet",
        "Средняя цена производителей горячекатаного стального листа и рулона в России, рублей за тонну. Это базовый "
        "вид проката: из него делают холоднокатаный лист, трубы, металлоконструкции и детали машин.",
        "Average producer price of hot-rolled steel sheet and coil in Russia, roubles per tonne. It is the basic flat "
        "product used for cold-rolled sheet, pipes, structural steelwork and machine parts.",
    ),
    "steel-rebar": SteelSeries(
        "1694665",
        "Прокат сортовой и катанка стальные прочие, кованые, горячекатаные, горячетянутые или экструдированные, без "
        "дополнительной обработки, включая смотанные после прокатки, из нелегированных сталей",
        "Цена стали: арматура и сортовой прокат", "Steel price: rebar and bars",
        "Средняя цена производителей сортового проката и катанки из углеродистой стали в России, рублей за тонну. "
        "Сюда входят арматура, круг, квадрат и катанка — основной стальной прокат для стройки.",
        "Average producer price of carbon steel bars and wire rod in Russia, roubles per tonne. It covers rebar, "
        "round and square bars and wire rod, the main steel products used in construction.",
    ),
    "steel-pipes": SteelSeries(
        "1694350", "Трубы стальные электросварные",
        "Цена стали: электросварные трубы", "Steel price: welded pipes",
        "Средняя цена производителей стальных электросварных труб в России, рублей за тонну. Это самые массовые "
        "стальные трубы: для водопровода и отопления, строительных конструкций и трубопроводов.",
        "Average producer price of electric-welded steel pipes in Russia, roubles per tonne. These are the most "
        "common steel pipes, used for water and heating systems, structures and pipelines.",
    ),
}

METHODOLOGY = (
    "Цена производителей — цена, по которой заводы продают продукцию покупателям в России, без НДС, акциза и других "
    "налогов. Росстат считает среднюю по всем производителям с весами по объёму выпуска. Значение за месяц выходит "
    "примерно через три недели после его окончания. С 2023 года данные приведены без учёта новых субъектов "
    "Российской Федерации."
)
METHODOLOGY_EN = (
    "The producer price is the price at which manufacturers sell to buyers in Russia, excluding VAT, excise and "
    "other taxes. Rosstat averages prices across producers, weighted by output. Monthly figures are released about "
    "three weeks after the month ends. From 2023, the data exclude the territories identified by Rosstat as new "
    "constituent entities."
)

KEYWORDS = (
    "цена стали, сталь, стоимость стали, цена тонны стали, цены на металл, металлопрокат, прокат, "
    "цены производителей, Росстат"
)
KEYWORDS_BY_CODE = {
    "steel-hot-rolled": "горячекатаный прокат, горячекатаный лист, листовой прокат, рулонная сталь, лист стальной",
    "steel-rebar": "арматура, цена арматуры, стоимость арматуры, сортовой прокат, катанка, круг стальной",
    "steel-pipes": "трубы стальные, цена труб, стальные трубы, электросварные трубы, трубы водогазопроводные",
}


def seed_indicators():
    for code, series in SERIES.items():
        yield {
            "code": code,
            "name": series.name,
            "name_en": series.name_en,
            "unit": UNIT,
            "frequency": "monthly",
            "source": "Росстат",
            "source_url": SOURCE_URL,
            "description": series.explanation,
            "methodology": METHODOLOGY,
            "parser_type": "rosstat_emiss_steel",
            "model_config_json": {"forecast_steps": 0},
            "is_active": True,
            "category": "Товарные рынки",
        }


def seo_keywords() -> dict[str, str]:
    return {code: f"{series.name}, {KEYWORDS_BY_CODE[code]}, {KEYWORDS}" for code, series in SERIES.items()}


def seo_meta() -> dict[str, dict[str, str]]:
    return {
        code: {
            "seo_title": f"{series.name} — цены производителей в России, руб./т",
            "seo_description": (
                f"{series.name} в России: средние цены производителей Росстата помесячно с 2017 года, "
                "рублей за тонну, без НДС."
            ),
        }
        for code, series in SERIES.items()
    }
