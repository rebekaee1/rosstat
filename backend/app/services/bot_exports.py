"""Выгрузки файлами в служебном боте (14.11.2026, слова владельца: «в информационном боте всё что
угодно выгрузить, посмотреть, когда душе угодно»).

Три набора кроме прежнего «CSV пользователей» (`telegram_bot._users_csv`):
- «Скачивания и лимит» — книга Excel из `download_content.build_xlsx`;
- «Все действия на сайте» — каждое бизнес-событие посетителя (`frontend_events`) за период, CSV;
- «Регистрации» — как пришёл каждый зарегистрированный (`user_signups`), CSV.

Границы: роботы и своя активность исключены (правило витрин, ADR-0010); имён, почт,
телефонов и `user_id` нет — человек обозначен коротким хэшем посетителя; свободный текст
параметров (поисковые запросы) проходит `scrub_text`. Окно «всех действий» не длиннее 30 дней и
не больше `EVENTS_ROW_CAP` строк: задача идёт в scheduler, чья память на боевом бывает на пределе.
CSV — с BOM и «;», чтобы Excel открыл кириллицу сразу.
"""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FrontendEvent, UserSignup
from app.services.analytics_period import MSK_OFFSET, Period
from app.services.goal_taxonomy import GROUP_LABELS_RU, group_of_event, tier_for_event

EVENTS_MAX_DAYS = 30
EVENTS_ROW_CAP = 100_000

TIER_LABELS_RU = {
    "macro": "главная цель", "micro": "ценное действие", "intent": "намерение",
    "engagement": "вовлечение", "technical": "служебное",
}
TRIGGER_LABELS_RU = {
    "gate_download": "упёрся в лимит скачиваний", "gate_chart_image": "картинка графика",
    "gate_compare": "сравнение", "gate_gif": "анимация карты", "nudge": "приглашение на странице",
    "header": "кнопка в шапке", "direct": "сам, без подсказки",
}


def _csv(header: list[str], rows: list[list[Any]]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def _msk(dt) -> str:
    return (dt + MSK_OFFSET).strftime("%d.%m.%Y %H:%M") if dt else ""


async def events_csv(db: AsyncSession, period: Period, *, anonymous: bool = False) -> tuple[bytes, int, bool]:
    """(файл, строк, обрезано ли). Все бизнес-события людей за период; `anonymous` — без хэша посетителя
    (роль «только отчёты», 14.11.2026)."""
    from app.services.analytics_marts import admin_identity
    from app.services.download_content import _excluded_visitors
    from app.services.pii_scrub import scrub_text

    raw = (await db.execute(
        select(FrontendEvent.occurred_at, FrontendEvent.event_name, FrontendEvent.visitor_id_hash,
               FrontendEvent.session_id_hash, FrontendEvent.user_id, FrontendEvent.authed,
               FrontendEvent.url, FrontendEvent.params_json)
        .where(FrontendEvent.occurred_at >= period.start, FrontendEvent.occurred_at < period.end)
        .order_by(FrontendEvent.occurred_at)
        .limit(EVENTS_ROW_CAP + 1)
    )).all()
    cut = len(raw) > EVENTS_ROW_CAP
    raw = raw[:EVENTS_ROW_CAP]
    visitors = {r.visitor_id_hash for r in raw if r.visitor_id_hash}
    excluded = await _excluded_visitors(db, visitors, period) if visitors else set()
    admin_users, _ = await admin_identity(db)

    from app.services.download_content import _path_parts

    rows = []
    for r in raw:
        if r.visitor_id_hash in excluded or (r.user_id and r.user_id in admin_users):
            continue
        params = dict(r.params_json) if isinstance(r.params_json, dict) else {}
        params.pop("authed", None)
        segs, query = _path_parts(r.url)
        page = "/" + "/".join(segs)
        if query:
            page += "?" + "&".join(f"{k}={v[0]}" for k, v in sorted(query.items()) if v)
        group = group_of_event(r.event_name)
        rows.append([
            _msk(r.occurred_at), r.event_name,
            GROUP_LABELS_RU.get(group, "") if group else "", TIER_LABELS_RU.get(tier_for_event(r.event_name), ""),
            scrub_text(page)[:300], "да" if r.authed else "гость", "" if anonymous else (r.visitor_id_hash or "")[:10],
            scrub_text(json.dumps(params, ensure_ascii=False))[:500] if params else "",
        ])
    data = _csv(["Время (МСК)", "Событие", "Группа", "Вид", "Страница", "Аккаунт", "Посетитель", "Параметры"], rows)
    return data, len(rows), cut


async def signups_csv(db: AsyncSession, period: Period) -> tuple[bytes, int]:
    """Регистрации за период: откуда и как пришёл человек, что подтолкнуло. Без ПДн."""
    from app.services.telegram_reports import CHANNEL_LABELS, DEVICE_LABELS, METHOD_LABELS

    rows_db = (await db.execute(
        select(UserSignup).where(UserSignup.created_at >= period.start, UserSignup.created_at < period.end)
        .order_by(UserSignup.created_at)
    )).scalars().all()
    rows = [[
        _msk(s.created_at), METHOD_LABELS.get(s.method or "", s.method or ""),
        {"ru": "русская", "en": "английская"}.get(s.site_locale or "", ""),
        s.country or "", s.geo_region or "",
        CHANNEL_LABELS.get(s.channel or "", s.channel or ""), s.referrer_host or "",
        " / ".join(x for x in (s.utm_source, s.utm_medium, s.utm_campaign) if x),
        DEVICE_LABELS.get(s.device_type or "", s.device_type or ""),
        s.landing_page or "", TRIGGER_LABELS_RU.get(s.trigger or "", s.trigger or ""),
        "" if s.days_to_signup is None else s.days_to_signup,
        "" if s.sessions_before is None else s.sessions_before,
        {True: "да", False: "нет", None: ""}[s.newsletter],
    ] for s in rows_db]
    data = _csv([
        "Дата (МСК)", "Способ", "Версия сайта", "Страна", "Регион", "Канал", "С какого сайта", "Метка кампании",
        "Устройство", "Первая страница", "Что подтолкнуло", "Дней до регистрации", "Визитов до регистрации",
        "Рассылка",
    ], rows)
    return data, len(rows)
