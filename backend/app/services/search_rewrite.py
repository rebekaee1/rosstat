"""Запрос своими словами → словами каталога (18.11.2026). Только после пустой выдачи.

Разбор Пульса за 17.11.2026: из 832 поисков за 30 дней 224 ничего не нашли. Часть — пробелы каталога, часть —
промахи при существующих рядах: человек пишет ту же вещь другими словами («регистрируемая безработица» при ряде
«уровень зарегистрированной безработицы»), с опечаткой в слове каталога («посевные пложади»), вставляет строку
таблицы с числами («… Самарская область 2014 43,6») или спрашивает про два показателя сразу («рождаемость и
смертность псковская область»). Нейросеть по смыслу на сервере здесь не ставится: она выдала бы похожий, но
другой ряд, а ADR-0016 запрещает выдумывать выдачу. Вместо этого — проверяемые правила:

1. ``REWRITES`` — словарь «как говорят → как называется ряд». Каждая строка проверена на каталоге: замена находит
   настоящий ряд с тем же смыслом (не соседний). Пополняется разбором пустых запросов
   (`scripts/search-empty-review.py`: прогон, классы причин, предложения языковой модели с проверкой каталогом),
   но в код попадает только руками, после проверки.
2. Опечатка в слове каталога: слово, которого нет ни в одном названии ряда и ни в одном названии территории,
   заменяется единственным словом каталога на расстоянии одной правки («пложади» → «площади», «облатсь» →
   «область»). Если подходящих слов два и больше — не исправляется.
3. Числа из таблицы («43,6», «в том 17 числе», «дагеста6») — не уточнение, а значение ячейки: убираются.
   Год (1000–2999), «2015=100», «на 1000», «аи-92» остаются.

Переписанный запрос ищется обычным поиском. Запрос, который находил своё в первом чтении, сюда не попадает.
"""
from __future__ import annotations

import logging
import re
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, RegionIndicator, SubnationalIndicator
from app.services.search_intent import (CONCEPTS, STOP_WORDS, SearchIntent, edit_distance_one, geo_aliases, normalize,
                                        tokens)
from app.services.search_unknown_word import word_in_names

logger = logging.getLogger(__name__)

_W = r"(?<![a-zа-я0-9])"   # начало слова
_E = r"(?![a-zа-я0-9])"    # конец слова

# (выражение по нормализованному запросу, замена, чем подтверждено на каталоге).
# Замена — слова из названия настоящего ряда. Не добавлять замену на «похожий» ряд: только тот же смысл.
REWRITES: tuple[tuple[str, str, str], ...] = (
    (r"регистрируем\w*\s+безработиц\w*|безработиц\w*\s+регистрируем\w*", "уровень зарегистрированной безработицы",
     "регион: «Уровень безработицы — уровень зарегистрированной безработицы»"),
    (r"площад(?:ь|и|ей|ям|ях)\s+посева|посевн(?:ая|ой|ую)\s+площад(?:ь|и)", "посевные площади",
     "регион: «Посевные площади сельскохозяйственных культур», «… зерновых и зернобобовых культур»"),
    (r"(?:доля|удельный\s+вес)\s+инновационных\s+товаров(?:\s+работ)?(?:\s+услуг)?(?:\s+в\s+общем\s+объ\w*)?"
     r"(?:\s+отгруженных(?:\s+товаров)?)?",
     "объем инновационных товаров работ услуг в процентах от общего объема отгруженных товаров",
     "регион: «Объем инновационных товаров, работ, услуг — в процентах от общего объема отгруженных товаров…»"),
    (r"коэффициент\w*\s+напряженност\w*(?:\s+на\s+рынке\s+труда)?",
     "нагрузка незанятого населения на одну заявленную вакансию",
     "регион: «Нагрузка незанятого населения, состоящего на регистрационном учете…, на одну заявленную вакансию» — "
     "так Росстат считает коэффициент напряжённости"),
    (r"(?:сведения\s+о\s+)?задолженност\w*\s+по\s+кредитам\s+предоставленным\s+кредитными\s+организациями\s+"
     r"физическим\s+лицам(?:\s*-?\s*резидентам)?",
     "кредиты физическим лицам", "Россия: «Кредиты физическим лицам» — задолженность по кредитам населению, ЦБ"),
    (r"кредитн\w*\s+задолженност\w*\s+(?:физ\w*(?:\s+лиц\w*)?|населени\w*)|задолженност\w*\s+"
     r"(?:домохозяйств\w*|домашних(?:\s+хозяйств\w*)?|населени\w*\s+по\s+кредитам)",
     "кредиты физическим лицам", "Россия: «Кредиты физическим лицам»"),
    (r"кредитн\w*\s+задолженност\w*", "задолженность по кредитам",
     "регион: «Задолженность по кредитам в рублях, предоставленным кредитными организациями…»"),
    (r"ставк\w*\s+кредитовани\w*", "ставка по кредитам", "Россия: «Ставка по кредитам физическим лицам / юридическим лицам»"),
    (r"производственн\w*\s+травматизм\w*", "травматизм на производстве",
     "мир: «Смертельный травматизм на производстве на 100 тысяч занятых» (Евростат)"),
    (r"\s*по\s+кофп", "", "регион: «Структура потребительских расходов домашних хозяйств» — это и есть разбивка по КОФП"),
    (r"коэф{1,2}ици?ент(\w*)", r"коэффициент\1", "частое написание «коэфицент», «коэффицент»"),
    # 19.11.2026 (гипотезы Пульса 285, 166).
    (r"валов\w*\s+(продукци\w*\s+сельск\w*\s+хозяйств\w*)", r"\1",
     "регион: «Продукция сельского хозяйства» — так Росстат называет валовую продукцию сельского хозяйства"),
    (r"сельхозпродукци\w*", "продукция сельского хозяйства", "регион: «Продукция сельского хозяйства»"),
)
_COMPILED = tuple((re.compile(_W + "(?:" + pattern + ")" + _E), replacement) for pattern, replacement, _why in REWRITES)

# Число из ячейки таблицы: дробное («43,6», «20 053,4»), разряды («17 383 024») и короткое число посреди слов.
_DECIMAL = re.compile(_W + r"\d{1,3}(?:[  ]\d{3})*,\d+" + _E)
_DIGIT_GROUPS = re.compile(_W + r"\d{1,3}(?:[  ]\d{3})+" + _E)
_SHORT_NUMBER = re.compile(r"(?<![a-zа-я0-9=\-])(?<!на )(?<!per )(?<!аи )(?<!ai )\d{1,3}(?![a-zа-я0-9=%\-])")
_GLUED_DIGITS = re.compile(r"(?<=[а-я]{4})\d+" + _E)


_PUNCTUATION = re.compile(r"[,;:«»\"“”„()!?]")


def plain(raw: str) -> str:
    """Нормализованный запрос без знаков препинания между словами (запятые и кавычки скопированного названия)."""
    return " ".join(_PUNCTUATION.sub(" ", normalize(raw)).split())


def rewrite_words(raw: str) -> str:
    """Словарь и числа из таблицы. Без базы: чистая функция нормализованной строки."""
    # Дробь и разряды — до снятия запятых: «43,6» и «20 053,4» уходят целиком.
    text = _DIGIT_GROUPS.sub(" ", _DECIMAL.sub(" ", normalize(raw)))
    text = plain(text)
    for pattern, replacement in _COMPILED:
        text = pattern.sub(replacement, text)
    text = _GLUED_DIGITS.sub("", text)
    if re.search(r"[a-zа-я]{3}", text):
        text = _SHORT_NUMBER.sub(" ", text)
    return " ".join(text.split())


_VOCABULARY_TTL = 6 * 3600
_vocabulary: tuple[float, frozenset[str], dict[int, tuple[str, ...]]] | None = None
MIN_TYPO_WORD = 5
MAX_TYPO_WORDS = 5


async def catalogue_vocabulary(db: AsyncSession, geometry: list[dict]) -> tuple[frozenset[str], dict[int, tuple[str, ...]]]:
    """Слова названий рядов России, регионов и субнациональных контуров, территорий и словаря понятий.

    Около 5 000 коротких названий; читаются раз в шесть часов на процесс. Мировые названия (360 тыс. рядов) сюда не
    входят: слово из них распознаётся отдельной проверкой ``word_in_names`` и не исправляется.
    """
    global _vocabulary
    now = time.monotonic()
    if _vocabulary is not None and now - _vocabulary[0] < _VOCABULARY_TTL:
        return _vocabulary[1], _vocabulary[2]
    words: set[str] = set()
    for statement in (select(Indicator.name, Indicator.name_en), select(RegionIndicator.name),
                      select(SubnationalIndicator.name_ru, SubnationalIndicator.name_en)):
        for row in (await db.execute(statement)).all():
            for value in row:
                words.update(tokens(value))
    for item in geometry:
        for value in (item.get("name_ru"), item.get("name_en"), *geo_aliases(item)):
            words.update(tokens(value))
    for aliases, _alternatives in CONCEPTS:
        for alias in aliases:
            words.update(tokens(alias))
    words = {word for word in words if word.isalpha()}
    by_length: dict[int, list[str]] = {}
    for word in words:
        by_length.setdefault(len(word), []).append(word)
    vocabulary = frozenset(words)
    index = {length: tuple(sorted(items)) for length, items in by_length.items()}
    _vocabulary = (now, vocabulary, index)
    return vocabulary, index


def _neighbours(word: str, index: dict[int, tuple[str, ...]]) -> set[str]:
    out = set()
    for length in (len(word) - 1, len(word), len(word) + 1):
        out.update(candidate for candidate in index.get(length, ()) if edit_distance_one(word, candidate))
    return out


def _correction(word: str, candidates: set[str]) -> str | None:
    """Единственный сосед, либо формы одного слова («хозяйста» → «хозяйства», а не «хозяйств»).

    Формы одного слова — общее начало не короче всех букв, кроме двух последних. Среди них сначала пропущенная
    буква (самая частая опечатка), затем замена, затем лишняя буква."""
    if len(candidates) == 1:
        return next(iter(candidates))
    stem = len(word) - 2
    if not candidates or any(candidate[:stem] != word[:stem] for candidate in candidates):
        return None
    order = {len(word) + 1: 0, len(word): 1, len(word) - 1: 2}
    ranked = sorted(candidates, key=lambda candidate: (order[len(candidate)], candidate))
    if len(ranked) > 1 and order[len(ranked[0])] == order[len(ranked[1])]:
        return None
    return ranked[0]


async def correct_catalogue_typos(db: AsyncSession, text: str, geometry: list[dict]) -> str:
    """Исправить слова, которых нет ни в каталоге, ни в названиях территорий, единственным соседом по одной правке."""
    try:
        vocabulary, index = await catalogue_vocabulary(db, geometry)
    except Exception:  # noqa: BLE001 - без словаря запрос остаётся как есть
        logger.warning("search rewrite: catalogue vocabulary unavailable", exc_info=True)
        return text
    checked = 0
    for word in dict.fromkeys(tokens(text)):
        if (len(word) < MIN_TYPO_WORD or not word.isalpha() or word in vocabulary or word in STOP_WORDS):
            continue
        checked += 1
        if checked > MAX_TYPO_WORDS:
            break
        correction = _correction(word, _neighbours(word, index))
        if correction is None:
            continue
        # Слово может быть настоящим словом мировых названий, которых нет в словаре: тогда не трогаем.
        probe = SearchIntent(word, word, ((word,),), frozenset(), frozenset(), None, None, None, None, None)
        if await word_in_names(db, word, probe):
            continue
        text = re.sub(_W + re.escape(word) + _E, correction, text)
    return text


async def rewritten_query(db: AsyncSession, raw: str, geometry: list[dict]) -> str | None:
    """Запрос словами каталога или None, если переписывать нечего."""
    text = rewrite_words(raw)
    text = await correct_catalogue_typos(db, text, geometry)
    return text if text and text != plain(raw) else None


# Слова о странице территории целиком: «псковская область в экономике», «место псковской области в экономике России».
PROFILE_WORDS = frozenset((
    "экономика", "экономики", "экономике", "экономику", "экономикой", "место", "месте", "роль",
    "показатели", "показателей", "показателям", "основные", "социально", "экономические", "экономических",
    "социальноэкономические", "статистика", "статистики", "статистику", "данные", "данных", "обзор", "профиль",
    "положение", "развитие", "развития", "скачать", "регионы", "регионов", "регионам", "регион", "региона",
    "economy", "economic", "profile", "overview", "statistics", "data", "indicators",
))


def profile_only(terms: tuple[tuple[str, ...], ...]) -> bool:
    """Все слова запроса, кроме географии, — общие слова о территории, а не название показателя."""
    return bool(terms) and all(len(term) == 1 and term[0] in PROFILE_WORDS for term in terms)


# «Рождаемость и смертность псковская область», «инфляция и доходы населения России»: два показателя в одном запросе.
# Только союзы: запятая в скопированном названии таблицы («Дефицит федерального бюджета, в том числе …») — не союз.
_CONJUNCTION = re.compile(r"\s+(?:и|а также|vs|versus|против|and)\s+")


def conjunction_parts(raw: str) -> list[str]:
    """Части запроса из двух-трёх показателей. Пусто, если союза нет или частей больше трёх.

    Вызывающая сторона отвечает частями, только если каждая часть нашла свои ряды: слово не выпадает молча."""
    text = normalize(raw)
    parts = [part.strip() for part in _CONJUNCTION.split(text) if part and part.strip()]
    if not 2 <= len(parts) <= 3:
        return []
    return parts
