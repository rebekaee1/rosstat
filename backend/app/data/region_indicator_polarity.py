"""Полярность региональных показателей: где меньшее значение лучше.

Единая точка истины для рейтингов `/region-rating/{code}`, блока «место
в России» на карточке региона и SSR-текстов. Справочник curated: только то,
в чём уверены глазами по каталогу. Нет автоматического угадывания по словам
имени — ошибка в полярности выдаст пользователю ложного «лидера».

Значения полярности:
  ``lower_better`` — меньшее значение предпочтительнее (безработица, смертность…).
  ``None`` — полярность неизвестна: нейтральная подача, сортировка по убыванию
  величины, без языка достижений («первое место», «лидеры»).
"""

from __future__ import annotations

from typing import Literal

Polarity = Literal["lower_better"]
SortDir = Literal["asc", "desc"]

# Коды показателей, где меньшее значение однозначно лучше.
# Абсолютные численности безработных / долгов без пересчёта на душу сюда не
# входят: межрегиональное сравнение размеров субъектов вводит в заблуждение.
LOWER_BETTER_CODES: frozenset[str] = frozenset({
    # Занятость
    "uroven-bezrabotitsy",
    "uroven-bezrabotitsy-uroven-bezrabotitsy-v-trudosposobnom-vozraste",
    "uroven-bezrabotitsy-uroven-zaregistrirovannoy-bezrabotitsy",
    # Бедность (доля населения, %)
    "chislennost-naseleniya-s-denezhnymi-dohodami-nizhe-granitsy",
    # Смертность
    "obschie-koeffitsienty-smertnosti",
    "koeffitsienty-mladencheskoy-smertnosti",
    "smertnost-naseleniya-bez-pokazatelya-smertnosti-ot-vneshnih",
    "smertnost-naseleniya-v-trudosposobnom-vozraste",
    # Заболеваемость (общий ряд + классы болезней)
    "zabolevaemost-na-1000-chelovek-naseleniya",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-2",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-3",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-4",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-5",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-6",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-7",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-8",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-9",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-10",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-11",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-12",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-13",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-14",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-15",
    "zabolevaemost-na-1000-chelovek-naseleniya-po-osnovnym-5-9-16",
    # Преступность (на 100 тыс. / удельные)
    "chislo-zaregistrirovannyh-prestupleniy-na-100000",
    "chislo-zaregistrirovannyh-ubiystv-i-pokusheniy-na-ubiystvo",
    "chislo-prestupleniy-nesovershennoletnih",
    # Износ фондов
    "stepen-iznosa-osnovnyh-fondov",
    "udelnyy-ves-polnostyu-iznoshennyh-osnovnyh-fondov-v",
    # Экология (вредные потоки)
    "vybrosy-zagryaznyayuschih-veschestv-v-atmosfernyy-vozduh-othodyaschih",
    "sbros-zagryaznennyh-stochnyh-vod-v-poverhnostnye-vodnye",
    # Задолженность по зарплате (в т.ч. на одного должника)
    "prosrochennaya-zadolzhennost-po-zarabotnoy-plate-rabotnikam-organizatsiy",
    "prosrochennaya-zadolzhennost-po-zarabotnoy-plate-v-raschete",
    "chislennost-rabotnikov-pered-kotorymi-organizatsiya-imeet-prosrochennuyu",
    # Аварийность на дорогах (на 100 тыс.)
    "chislo-dorozhno-transportnyh-proisshestviy-na-100000-chelovek",
    "chislo-lits-pogibshih-v-dorozhno-transportnyh-proisshestviyah",
    # Дополнительно: однозначные «хуже, если больше»
    "udelnyy-ves-ubytochnyh-organizatsiy",
    "beremennosti-s-abortivnym-ishodom-na-100-rodov",
    "beremennosti-s-abortivnym-ishodom-na-1000-zhenschin",
})

# table_code как запасной ключ (если код ряда сменится, а таблица сборника та же).
LOWER_BETTER_TABLE_CODES: frozenset[str] = frozenset({
    "2.10.1",  # уровень безработицы
    "3.12",    # доля населения ниже границы бедности
    "1.10",    # общие коэффициенты смертности
    "1.11",    # смертность в трудоспособном возрасте
    "1.13",    # младенческая смертность
    "9.3",     # степень износа основных фондов
    "22.1",    # преступления на 100 000
})


def region_indicator_polarity(
    code: str | None,
    table_code: str | None = None,
) -> Polarity | None:
    """Вернуть ``lower_better`` или ``None`` (нейтральная подача)."""
    if code and code in LOWER_BETTER_CODES:
        return "lower_better"
    if table_code and table_code in LOWER_BETTER_TABLE_CODES:
        return "lower_better"
    return None


def region_rating_default_sort(
    code: str | None,
    table_code: str | None = None,
) -> SortDir:
    """Направление сортировки рейтинга по умолчанию."""
    return "asc" if region_indicator_polarity(code, table_code) == "lower_better" else "desc"


def region_rating_is_achievement(
    code: str | None,
    table_code: str | None = None,
) -> bool:
    """Можно ли говорить о «месте» как о достижении (лучшее значение первым)."""
    return region_indicator_polarity(code, table_code) is not None


def region_rating_order_by(value_column, code: str | None, table_code: str | None = None):
    """SQLAlchemy order_by для рейтинга регионов."""
    if region_rating_default_sort(code, table_code) == "asc":
        return value_column.asc()
    return value_column.desc()


def region_rating_meta(code: str | None, table_code: str | None = None) -> dict:
    """Поля полярности для API/SSR (единый контракт)."""
    polarity = region_indicator_polarity(code, table_code)
    return {
        "polarity": polarity,
        "default_sort": region_rating_default_sort(code, table_code),
        "rank_as_achievement": polarity is not None,
    }
