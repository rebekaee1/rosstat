"""Редизайн целей Метрики под таксономию goal_taxonomy (этап 0 BI 2.1).

Приводит счётчик к состоянию «цель = конверсия»:
- держим только macro/micro события таксономии как action-цели с ТОЧНЫМ
  (exact) совпадением имени события, единым неймингом «[Macro]/[Micro] …»
  и default_price из весов таксономии;
- удаляем всё остальное (60+ событий engagement/technical/intent, битую
  scroll_depth-цель, файловую и email-автоцели, дубли);
- добавляем 2 составные step-воронки: «Регистрация» (показ нуджа → клик →
  signup) и «Выгрузка данных» (просмотр индикатора → скачивание).

Строки metrika_goals в нашей БД НЕ удаляются — исторические goals_json в
raw_metrika_visits продолжают резолвиться; sync_metrika_goals пометит
исчезнувшие цели как deleted=true (soft-delete в словаре).

Запуск (внутри backend-контейнера или локально с env):
    python scripts/metrika-goals-redesign.py           # dry-run: печатает план
    python scripts/metrika-goals-redesign.py --apply   # выполняет
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.services.goal_taxonomy import (  # noqa: E402
    TIER_MACRO,
    _MACRO,
    _MICRO,
    weight_for_event,
    tier_for_event,
)
from app.services.yandex_metrika_management import MetrikaManagementClient  # noqa: E402

# Русские имена целей (публичный кабинет Метрики — без кода событий в имени).
_GOAL_NAMES = {
    "signup": "Регистрация",
    "newsletter_opt_in": "Подписка на рассылку",
    "feedback_submit": "Обратная связь",
    "login_success": "Вход в аккаунт",
    "download_csv": "Выгрузка CSV",
    "download_excel": "Выгрузка Excel",
    "download_ical": "Календарь iCal",
    "demographics_csv": "Выгрузка демографии",
    "chart_image_download": "Скачивание графика",
    "compare_image_download": "Скачивание сравнения",
    "compare_add": "Добавление в сравнение",
    "compare_change": "Изменение сравнения",
    "region_compare_add": "Сравнение регионов",
    "calc_share": "Шеринг калькулятора",
    "calc_copy_result": "Копирование расчёта",
    "calc_mortgage": "Ипотечный калькулятор",
    "calc_compound": "Калькулятор сложного процента",
    "embed_code_copy": "Копирование embed-кода",
    "contact_email": "Клик по e-mail",
}

_FUNNELS = [
    {
        "name": "[Воронка] Регистрация",
        "type": "step",
        "is_retargeting": 0,
        "steps": [
            {"name": "Показ приглашения", "type": "action",
             "conditions": [{"type": "exact", "url": "register_nudge_view"}]},
            {"name": "Клик по приглашению", "type": "action",
             "conditions": [{"type": "exact", "url": "register_nudge_cta"},
                            {"type": "exact", "url": "header_register_click"}]},
            {"name": "Регистрация", "type": "action",
             "conditions": [{"type": "exact", "url": "signup"}]},
        ],
    },
    {
        "name": "[Воронка] Выгрузка данных",
        "type": "step",
        "is_retargeting": 0,
        "steps": [
            {"name": "Просмотр индикатора", "type": "action",
             "conditions": [{"type": "exact", "url": "indicator_view"}]},
            {"name": "Скачивание", "type": "action",
             "conditions": [{"type": "exact", "url": "download_csv"},
                            {"type": "exact", "url": "download_excel"}]},
        ],
    },
]


def _desired_goals() -> dict[str, dict]:
    """event_name → payload действия-цели."""
    out = {}
    for ev in sorted(_MACRO | _MICRO):
        prefix = "[Macro]" if tier_for_event(ev) == TIER_MACRO else "[Micro]"
        out[ev] = {
            "name": f"{prefix} {_GOAL_NAMES.get(ev, ev)}",
            "type": "action",
            "is_retargeting": 0,
            "default_price": weight_for_event(ev),
            "conditions": [{"type": "exact", "url": ev}],
        }
    return out


def _goal_event(goal: dict) -> str | None:
    """event_name action-цели (условие url при type=action — имя события)."""
    if goal.get("type") != "action":
        return None
    conds = goal.get("conditions") or []
    if len(conds) == 1:
        return conds[0].get("url")
    return None


async def main(apply: bool) -> None:
    counter_id = (settings.analytics_allowed_counter_ids or "").split(",")[0].strip()
    client = MetrikaManagementClient(
        write_token=settings.yandex_metrika_write_token or settings.yandex_metrika_read_token,
    )
    resp = await client.goals(counter_id)
    goals = (resp.data or {}).get("goals") or []
    print(f"Целей в счётчике {counter_id}: {len(goals)}")

    desired = _desired_goals()
    seen_events: set[str] = set()
    to_update: list[tuple[dict, dict]] = []
    to_delete: list[dict] = []

    for g in goals:
        ev = _goal_event(g)
        if ev in desired and ev not in seen_events:
            seen_events.add(ev)
            want = desired[ev]
            if (g.get("name") != want["name"]
                    or (g.get("conditions") or [{}])[0].get("type") != "exact"
                    or g.get("default_price") != want["default_price"]):
                to_update.append((g, want))
        elif g.get("name", "").startswith("[Воронка]"):
            seen_events.add(f"__funnel__{g['name']}")
        else:
            to_delete.append(g)

    to_create = [payload for ev, payload in desired.items() if ev not in seen_events]
    to_create += [f for f in _FUNNELS if f"__funnel__{f['name']}" not in seen_events]

    print(f"Оставляем и выравниваем: {len(seen_events)}; обновить: {len(to_update)}; "
          f"создать: {len(to_create)}; удалить: {len(to_delete)}")
    for g, want in to_update:
        print(f"  UPDATE {g['id']}: «{g.get('name')}» → «{want['name']}» price={want['default_price']}")
    for payload in to_create:
        print(f"  CREATE «{payload['name']}»")
    for g in to_delete:
        print(f"  DELETE {g['id']}: «{g.get('name')}» ({g.get('type')})")

    if not apply:
        print("\nDry-run. Запустить с --apply для выполнения.")
        return

    from app.services.yandex_client import YandexApiError

    ok = fail = 0
    ops = (
        [("update", str(g["id"]), lambda g=g, w=want: client.update_goal(counter_id, str(g["id"]), w, approved=True))
         for g, want in to_update]
        + [("create", p["name"], lambda p=p: client.create_goal(counter_id, p, approved=True))
           for p in to_create]
        + [("delete", str(g["id"]), lambda g=g: client.delete_goal(counter_id, str(g["id"]), approved=True))
           for g in to_delete]
    )
    for op, label, call in ops:
        try:
            await call()
            ok += 1
        except YandexApiError as exc:
            fail += 1
            print(f"  ! {op} {label} → {exc} {getattr(exc, 'payload', '')}")
    print(f"\nГотово: {ok} операций успешно, {fail} с ошибкой.")


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
