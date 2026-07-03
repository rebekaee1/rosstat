#!/usr/bin/env python3
"""Аудит целей Яндекс.Метрики против событий, которые реально шлёт фронтенд.

Зачем: first-party события (frontend_events) собираются ВСЕГДА и питают «Пульс».
Но чтобы событие стало «Целью» в интерфейсе Метрики (воронки, сегменты,
сравнение периодов), одноимённый goal (type=action, goal_id=имя события) должен
существовать в счётчике. Скрипт сверяет:

  - какие события объявлены в frontend/src/lib/track.js (events = {...});
  - какие цели уже заведены в счётчике (management API, read-token);
  - чего не хватает → печатает список для добавления (или создаёт с --create).

Запуск (внутри backend-контейнера, там есть settings и токены):
  docker compose exec backend python /app/scripts/metrika-goals-audit.py
  docker compose exec backend python /app/scripts/metrika-goals-audit.py --create

--create требует RUSTATS_YANDEX_METRIKA_WRITE_TOKEN и создаёт недостающие
JS-цели (type=action). Без него — только аудит (owner заводит руками).
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

# Путь к track.js: в контейнере фронт не смонтирован, поэтому имена событий
# дублируем здесь как fallback-словарь «событие → человеческое имя цели».
# Источник истины — track.js; при расхождении обновить оба места.
_TRACK_JS = Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "track.js"

# Человеческие имена для целей (для type=action goal). Ключ = имя события.
GOAL_NAMES: dict[str, str] = {
    "indicator_view": "Просмотр карточки индикатора",
    "region_indicator_view": "Просмотр карточки региона",
    "frequency_switch": "Переключение частоты",
    "chart_mode_change": "Смена режима графика",
    "chart_range_change": "Смена диапазона графика",
    "chart_zoom": "Зум графика",
    "forecast_toggle": "Включение прогноза",
    "forecast_view": "Просмотр прогноза",
    "methodology_click": "Клик на методологию",
    "table_search": "Поиск в таблице",
    "table_sort": "Сортировка таблицы",
    "table_page": "Листание таблицы",
    "compare_open": "Открытие сравнения",
    "compare_change": "Изменение сравнения",
    "compare_range": "Диапазон сравнения",
    "download_ical": "Скачивание календаря iCal",
    "calc_direction": "Калькулятор: смена направления",
    "calc_preset": "Калькулятор: пресет",
    "calc_share": "Калькулятор: поделиться",
    "calc_copy_result": "Калькулятор: копировать результат",
    "calc_chart_mode": "Калькулятор: режим графика",
    "calc_breakdown": "Калькулятор: детализация",
    "faq_toggle": "Раскрытие FAQ",
    "calendar_month_nav": "Календарь: смена месяца",
    "calendar_source_filter": "Календарь: фильтр источника",
    "calendar_day_select": "Календарь: выбор дня",
    "calendar_clear_day": "Календарь: сброс дня",
    "demographics_chart_type": "Демография: тип графика",
    "demographics_csv": "Демография: CSV",
    "embed_type_change": "Виджет: тип",
    "embed_indicator_select": "Виджет: выбор индикатора",
    "embed_period_change": "Виджет: период",
    "embed_theme_change": "Виджет: тема",
    "embed_size_change": "Виджет: размер",
    "embed_option_toggle": "Виджет: опция",
    "embed_code_tab": "Виджет: вкладка кода",
    "embed_code_copy": "Виджет: копировать код",
    "embed_runtime_view": "Виджет: показ на чужом сайте",
    "nav_category_open": "Навигация: открытие категорий",
    "nav_mobile_toggle": "Навигация: мобильное меню",
    "nav_link_click": "Навигация: клик по ссылке",
    "home_category_click": "Главная: клик по категории",
    "home_indicator_click": "Главная: клик по индикатору",
    "category_tile_click": "Категория: клик по плитке",
    "related_indicator_click": "Клик по связанному индикатору",
    "related_link_click": "Клик по связанной ссылке",
    "breadcrumb_click": "Клик по хлебным крошкам",
    "source_link_click": "Клик по источнику",
    "scroll_depth": "Глубина прокрутки",
    "outbound_link": "Внешняя ссылка",
    "contact_email": "Клик по email",
    "consent_update": "Обновление согласия cookie",
    "api_retry": "Повтор запроса при ошибке",
    "error_reload": "Перезагрузка после ошибки",
    "empty_state": "Пустой экран",
    "api_load_error": "Ошибка загрузки данных",
    "experiment_exposure": "A/B: показ варианта",
    "newsletter_opt_out": "Отписка от рассылки",
    "feedback_nudge_view": "Показ окна обратной связи",
    "register_nudge_view": "Показ окна регистрации",
    "regions_view_toggle": "Регионы: список/карта",
    "regions_map_metric": "Регионы: показатель на карте",
    "regions_map_select": "Регионы: выбор на карте",
    "region_compare_add": "Регионы: добавить в сравнение",
    "region_crosslink_click": "Регионы ↔ макро: переход",
}


def declared_events() -> dict[str, str]:
    """Парсит events = {...} из track.js: имя события → человеческое имя цели."""
    out: dict[str, str] = {}
    try:
        text = _TRACK_JS.read_text(encoding="utf-8")
    except OSError:
        # Фронт не смонтирован (контейнер) — используем только GOAL_NAMES.
        return dict(GOAL_NAMES)
    for m in re.finditer(r"^\s*[A-Z0-9_]+:\s*'([a-z0-9_]+)'", text, re.M):
        ev = m.group(1)
        out[ev] = GOAL_NAMES.get(ev, ev)
    # добить именами из GOAL_NAMES на случай отсутствия в файле
    for ev, name in GOAL_NAMES.items():
        out.setdefault(ev, name)
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true", help="создать недостающие JS-цели")
    ap.add_argument("--counter", default="107136069")
    args = ap.parse_args()

    from app.services.yandex_metrika_management import MetrikaManagementClient

    client = MetrikaManagementClient()
    resp = await client.goals(args.counter)
    goals = (resp.data or {}).get("goals") or []
    existing: set[str] = set()
    for g in goals:
        for cond in g.get("conditions") or []:
            gid = cond.get("value") or cond.get("goal_id") or cond.get("url")
            if gid:
                existing.add(str(gid))

    events = declared_events()
    missing = {ev: name for ev, name in sorted(events.items()) if ev not in existing}

    print(f"Счётчик {args.counter}: целей заведено {len(goals)}, "
          f"уникальных goal_id {len(existing)}")
    print(f"Событий у фронта: {len(events)}; без цели в Метрике: {len(missing)}\n")

    if not missing:
        print("Все события покрыты целями. Ничего добавлять не нужно.")
        return 0

    print("=== НЕТ ЦЕЛИ В МЕТРИКЕ (тип «JavaScript-событие», Идентификатор = слева) ===")
    for ev, name in missing.items():
        print(f"  {ev:32s} → {name}")

    if not args.create:
        print("\nЗапусти с --create, чтобы создать автоматически "
              "(нужен RUSTATS_YANDEX_METRIKA_WRITE_TOKEN).")
        return 0

    from app.config import settings
    if not settings.yandex_metrika_write_token:
        print("\nRUSTATS_YANDEX_METRIKA_WRITE_TOKEN не задан — создать нельзя.")
        return 1

    print("\nСоздаю цели…")
    created, failed = 0, 0
    for ev, name in missing.items():
        goal = {
            "name": name[:255],
            "type": "action",
            "is_retargeting": 0,
            "conditions": [{"type": "exact", "url": ev}],
        }
        try:
            r = await client.create_goal(args.counter, goal, approved=True)
            if r.data and (r.data.get("goal") or r.data.get("id")):
                created += 1
                print(f"  ✓ {ev}")
            else:
                failed += 1
                print(f"  ✗ {ev}: {str(r.data)[:120]}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {ev}: {exc}")
    print(f"\nГотово: создано {created}, ошибок {failed}.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
