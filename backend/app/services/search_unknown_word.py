"""Пустая выдача из-за слова, которого нет ни в одном названии ряда (14.11.2026).

На боевом за 30 дней 32 % поисков ничего не находили; частый случай — лишнее слово рядом с существующим рядом:
«воронежская область структура посевных площадей», «активных пользователей сети интернет». По ADR-0016 неизвестное
уточнение обязательно, поэтому основная выдача остаётся пустой. Здесь — только подсказка в существующем блоке
«Ближайшее» (`nearest`, как у R8-A): если слово с его формами не встречается ни в одном названии рядов той же
плоскости (регион — региональные ряды, иначе все), поиск повторяется без таких слов, и до трёх найденных рядов
показываются с пояснением, каких слов у нас нет.

Обычные слова — группы из одного слова, не понятия словаря и не служебные (`search-*`). Если неизвестны все слова
или ни одного — подсказки нет. Проверка — `EXISTS … ILIKE` по названиям (у мировых рядов — триграммный индекс),
не больше пяти слов, только после пустой выдачи.
"""
from __future__ import annotations

from dataclasses import replace

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Indicator, RegionIndicator, SubnationalIndicator, WorldIndicator
from app.services.search_intent import CONCEPTS_ALTERNATIVES, SearchIntent, nominal_variants

MAX_CHECKED_WORDS = 5
MIN_WORD_LEN = 4


def literal_groups(intent: SearchIntent) -> list[tuple[str, ...]]:
    """Обычные слова запроса (не понятия и не служебные группы)."""
    out = []
    for group in intent.terms:
        if len(group) != 1 or group in CONCEPTS_ALTERNATIVES:
            continue
        word = group[0]
        if word.startswith("search-") or not word.isalpha() or len(word) < MIN_WORD_LEN:
            continue
        out.append(group)
    return out


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _name_columns(intent: SearchIntent):
    if intent.regions:
        return (RegionIndicator.name, SubnationalIndicator.name_ru, SubnationalIndicator.name_en)
    return (Indicator.name, Indicator.name_en, RegionIndicator.name, SubnationalIndicator.name_ru,
            WorldIndicator.name_ru, WorldIndicator.name_en)


async def word_in_names(db: AsyncSession, word: str, intent: SearchIntent) -> bool:
    forms = nominal_variants(word)
    for column in _name_columns(intent):
        condition = or_(*(column.ilike(f"%{_escape(form)}%", escape="\\") for form in forms))
        if await db.scalar(select(exists().where(condition))):
            return True
    return False


async def unknown_words(db: AsyncSession, intent: SearchIntent) -> list[tuple[str, ...]]:
    groups = literal_groups(intent)[:MAX_CHECKED_WORDS]
    unknown = [group for group in groups if not await word_in_names(db, group[0], intent)]
    return unknown


MAX_TRIES = 3


def _enough_left(intent: SearchIntent, rest: tuple[tuple[str, ...], ...]) -> bool:
    """Остаток должен держать смысл: два и больше содержательных слова/понятия или регион и хотя бы одно.
    Одно общее слово («коэффициент» из «коэффициент напряженности») дало бы случайные ряды — не подсказываем."""
    content = [group for group in rest if not group[0].startswith("search-")]
    return len(content) >= 2 or (bool(intent.regions) and len(content) >= 1)


async def readings_without_words(db: AsyncSession, intent: SearchIntent) -> list[tuple[SearchIntent, list[str]]]:
    """До MAX_TRIES чтений без части обычных слов, по порядку: сначала без всех слов, которых нет ни в одном
    названии, затем без одного обычного слова слева направо. Каждое — с остатком, который держит смысл."""
    groups = literal_groups(intent)
    if len(intent.terms) < 2 or not groups:
        return []
    candidates: list[list[tuple[str, ...]]] = []
    unknown = await unknown_words(db, intent)
    if unknown:
        candidates.append(unknown)
    candidates.extend([group] for group in groups if [group] != unknown)
    out = []
    for dropped in candidates:
        rest = tuple(group for group in intent.terms if group not in dropped)
        if rest and _enough_left(intent, rest):
            out.append((replace(intent, terms=rest, literal=None), [group[0] for group in dropped]))
        if len(out) >= MAX_TRIES:
            break
    return out
