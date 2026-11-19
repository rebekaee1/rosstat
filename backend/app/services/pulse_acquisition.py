"""Недельная строка привлечения в Пульсе (совет 19.11.2026, `.artifacts/council-2026-11-19/общая-стратегия.md`).

Совет решил: до 30.12 весь сайт работает на одно действие — человек из Яндекса получает «пришлём новую цифру»
(Telegram-бот или почта). Каждый круг агентов называет число, которое он двигает. Эти числа — здесь, одной строкой
за 7 дней, которые кончаются отчётным днём (скользящее окно; в понедельник это ровно прошлая неделя).

Определения (одинаковые у всех шести членов совета после пересчёта 19.11):

* **Люди из Яндекса** — визиты Метрики с поисковиком «yandex» за 7 дней. Прямые заходы Метрики почти целиком
  фермы, поэтому базой служит поиск.
* **Возврат** считается по когорте: первый вход человека (`client_id_hash`) из Яндекса был 31–60 дней назад, за 30
  дней после него человек пришёл ещё раз. «В другой день» — любым путём; **«сам, не из поиска»** — следующий визит
  без поисковика (закладка, бот, письмо, канал). Главное число — второе: его двигает строка «присылать», а возврат
  через поиск — заслуга Яндекса. Метрика не видит человека на другом устройстве: возврат занижен, но одинаково
  каждую неделю. База на 19.11: 5,3 % и 1,4 %.
* **Строка «присылать»** — события сайта `subscribe_line_view` / `subscribe_line_click` (свойства `topic`,
  `channel` = telegram | email). Нажатия считаем на 1 000 показов: решение совета по кнопке — по объёму показов.
* **Нажал → открыл бота** — чаты публичного бота с первым кодом `site_<тема>` (10 тем бота; `site_welcome`,
  `site_research` и другие коды сайта не считаются), впервые пришедшие за окно.
* **Подписки** — новые подписки публичного бота у чатов со строки (`first_code` = `site_<тема>`) и все новые; почтовые —
  новые слежения (`user_watches`) и согласия `watch_mail`.
* **Регистрации** — по поводу (`user_signups.trigger`).
* **ИИ** — визиты Метрики с ChatGPT, Алисы, Perplexity и других помощников (`traffic_channel.assistant_name`).
* **Google-Россия** — визиты Метрики из Google со страной «Russia». Это не клики Search Console: у
  `gsc_page_daily` нет страны.

Только суммы, без идентификаторов. Сбой раздела не роняет Пульс (`pulse_extra.build_extra`).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

WINDOW_DAYS = 7
COHORT_FROM_DAYS = 60   # когорта возврата: первый вход 31–60 дней назад…
COHORT_TO_DAYS = 31
RETURN_DAYS = 30        # …и следующие 30 дней после него
FIRST_VISIT_LOOKBACK_DAYS = 150  # «первый» — первый за столько дней истории Метрики
SAME_VISIT_GAP = timedelta(minutes=30)
LINE_VIEW = "subscribe_line_view"
LINE_CLICK = "subscribe_line_click"
SITE_CODE_PREFIX = "site_"


def site_topic_codes() -> tuple[str, ...]:
    """Коды строки «присылать»: `site_<тема>` для тем публичного бота (10 тем).

    Сайт шлёт в бота и другие коды (`site_welcome`, `site_research` — приветственный экран и исследования):
    это не нажатие строки, поэтому «нажал → открыл бота» и «подписки с сайта» считаются только по темам.
    """
    from app.services.public_bot import TOPICS

    return tuple(f"{SITE_CODE_PREFIX}{key}" for key in TOPICS)
_IN_CHUNK = 900  # SQLite ограничивает число параметров запроса


def _is_yandex(engine: str | None) -> bool:
    return (engine or "").lower().startswith("yandex")


def _no_search(engine: str | None) -> bool:
    return not (engine or "").strip()


async def _yandex_people(db, d: date) -> dict[str, Any]:
    from app.models import RawMetrikaVisit

    week_from = d - timedelta(days=WINDOW_DAYS - 1)
    rows = (await db.execute(
        select(RawMetrikaVisit.search_engine, RawMetrikaVisit.referer,
               RawMetrikaVisit.raw_json, RawMetrikaVisit.client_id_hash)
        .where(RawMetrikaVisit.visit_date >= week_from, RawMetrikaVisit.visit_date <= d,
               RawMetrikaVisit.traffic_source.in_(("organic", "referral")))
    )).all()
    from app.services.traffic_channel import assistant_name

    yandex = google_ru = 0
    ai: Counter[str] = Counter()
    for engine, referer, raw, _client in rows:
        eng = (engine or "").lower()
        if _is_yandex(eng):
            yandex += 1
        elif eng.startswith("google"):
            country = (raw or {}).get("ym:s:regionCountry") if isinstance(raw, dict) else None
            if country == "Russia":
                google_ru += 1
        elif not eng:
            name = assistant_name(referrer=referer)
            if name:
                ai[name] += 1
    return {"yandex_visits": yandex, "google_ru_visits": google_ru,
            "ai_visits": sum(ai.values()), "ai_by_name": dict(ai.most_common(5))}


async def return_cohort(db, d: date) -> dict[str, Any]:
    """Возврат людей из Яндекса: когорта первого входа 31–60 дней назад, следующие 30 дней после входа."""
    from app.models import RawMetrikaVisit

    cohort_from = datetime.combine(d - timedelta(days=COHORT_FROM_DAYS - 1), datetime.min.time())
    cohort_to = datetime.combine(d - timedelta(days=COHORT_TO_DAYS - 1), datetime.min.time())
    first = func.min(RawMetrikaVisit.start_time)
    firsts = (await db.execute(
        select(RawMetrikaVisit.client_id_hash, first)
        .where(RawMetrikaVisit.visit_date >= d - timedelta(days=FIRST_VISIT_LOOKBACK_DAYS),
               RawMetrikaVisit.visit_date <= d,
               RawMetrikaVisit.client_id_hash.is_not(None),
               func.lower(RawMetrikaVisit.search_engine).like("yandex%"))
        .group_by(RawMetrikaVisit.client_id_hash)
        .having(first >= cohort_from, first < cohort_to)
    )).all()
    cohort = {c: f for c, f in firsts if c and f}
    other_day: set[str] = set()
    by_self: set[str] = set()
    clients = list(cohort)
    for i in range(0, len(clients), _IN_CHUNK):
        chunk = clients[i:i + _IN_CHUNK]
        visits = (await db.execute(
            select(RawMetrikaVisit.client_id_hash, RawMetrikaVisit.start_time, RawMetrikaVisit.search_engine)
            .where(RawMetrikaVisit.client_id_hash.in_(chunk), RawMetrikaVisit.start_time >= cohort_from)
        )).all()
        for client, started, engine in visits:
            f = cohort.get(client)
            if f is None or started is None or started <= f + SAME_VISIT_GAP:
                continue
            if started >= f + timedelta(days=RETURN_DAYS) or started.date() <= f.date():
                continue
            other_day.add(client)
            if _no_search(engine):
                by_self.add(client)
    n = len(cohort)
    return {
        "cohort": n,
        "cohort_first_from": cohort_from.date().isoformat(),
        "cohort_first_to": (cohort_to - timedelta(days=1)).date().isoformat(),
        "other_day": len(other_day),
        "by_self": len(by_self),
        "other_day_pct": round(100 * len(other_day) / n, 1) if n else None,
        "by_self_pct": round(100 * len(by_self) / n, 1) if n else None,
    }


async def _people_week(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.models import ServerSession

    humans = await db.scalar(
        select(func.count(func.distinct(ServerSession.visitor_id_hash)))
        .where(ServerSession.day >= (start - timedelta(days=1)).date(),
               ServerSession.started_at >= start, ServerSession.started_at < end,
               ServerSession.is_human.is_(True), ServerSession.is_bot.is_(False),
               ServerSession.is_internal.is_(False)))
    return {"human_visitors": int(humans or 0)}


async def _subscribe_line(db, start: datetime, end: datetime) -> dict[str, Any]:
    """Показы и нажатия строки «присылать»: события, разные посетители, по теме и способу."""
    from app.models import FrontendEvent

    rows = (await db.execute(
        select(FrontendEvent.event_name, FrontendEvent.visitor_id_hash, FrontendEvent.session_id_hash,
               FrontendEvent.params_json)
        .where(FrontendEvent.occurred_at >= start, FrontendEvent.occurred_at < end,
               FrontendEvent.event_name.in_((LINE_VIEW, LINE_CLICK)))
    )).all()
    views = clicks = 0
    viewers: set[str] = set()
    clickers: set[str] = set()
    by_channel: Counter[str] = Counter()
    by_topic: Counter[str] = Counter()
    for name, visitor, session, params in rows:
        who = visitor or session or ""
        p = params if isinstance(params, dict) else {}
        if name == LINE_VIEW:
            views += 1
            viewers.add(who)
        else:
            clicks += 1
            clickers.add(who)
            by_channel[str(p.get("channel") or "—")] += 1
            by_topic[str(p.get("topic") or "—")] += 1
    return {
        "views": views, "viewers": len(viewers), "clicks": clicks, "clickers": len(clickers),
        "clicks_per_1000_views": round(1000 * clicks / views, 1) if views else None,
        "clicks_by_channel": dict(by_channel.most_common()), "clicks_by_topic": dict(by_topic.most_common(10)),
    }


async def _subscriptions(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.models import Consent, PublicBotChat, PublicBotSubscription, UserWatch

    codes = site_topic_codes()
    site_chats_new = int(await db.scalar(select(func.count()).select_from(PublicBotChat).where(
        PublicBotChat.first_seen_at >= start, PublicBotChat.first_seen_at < end,
        PublicBotChat.first_code.in_(codes))) or 0)
    bot_new = int(await db.scalar(select(func.count()).select_from(PublicBotSubscription).where(
        PublicBotSubscription.created_at >= start, PublicBotSubscription.created_at < end)) or 0)
    bot_new_site = int(await db.scalar(
        select(func.count()).select_from(PublicBotSubscription)
        .join(PublicBotChat, PublicBotChat.chat_id == PublicBotSubscription.chat_id)
        .where(PublicBotSubscription.created_at >= start, PublicBotSubscription.created_at < end,
               PublicBotChat.first_code.in_(codes))) or 0)
    bot_total = int(await db.scalar(select(func.count()).select_from(PublicBotSubscription)) or 0)
    watches_new = int(await db.scalar(select(func.count()).select_from(UserWatch).where(
        UserWatch.created_at >= start, UserWatch.created_at < end)) or 0)
    watch_mail_new = int(await db.scalar(select(func.count()).select_from(Consent).where(
        Consent.kind == "watch_mail", Consent.granted_at >= start, Consent.granted_at < end)) or 0)
    return {"site_bot_chats_new": site_chats_new, "bot_subscriptions_new": bot_new,
            "bot_subscriptions_new_from_site": bot_new_site, "bot_subscriptions_total": bot_total,
            "mail_watches_new": watches_new, "watch_mail_consents_new": watch_mail_new}


async def _signups(db, start: datetime, end: datetime) -> dict[str, Any]:
    from app.models import UserSignup

    rows = (await db.execute(
        select(UserSignup.trigger, func.count())
        .where(UserSignup.created_at >= start, UserSignup.created_at < end)
        .group_by(UserSignup.trigger))).all()
    by = {str(t or "—"): int(n) for t, n in rows}
    return {"total": sum(by.values()), "by_trigger": dict(sorted(by.items(), key=lambda kv: -kv[1]))}


async def build_week(db, d: date, end: datetime) -> dict[str, Any]:
    """Раздел `acquisition_week` снимка: 7 дней, которые кончаются отчётным днём (`end` — конец дня, UTC)."""
    start = end - timedelta(days=WINDOW_DAYS)
    return {
        "window": {"from": (d - timedelta(days=WINDOW_DAYS - 1)).isoformat(), "to": d.isoformat()},
        "metrika": await _yandex_people(db, d),
        "people": await _people_week(db, start, end),
        "return": await return_cohort(db, d),
        "line": await _subscribe_line(db, start, end),
        "subscriptions": await _subscriptions(db, start, end),
        "signups": await _signups(db, start, end),
    }


def _pct(v: Any) -> str:
    return "нет данных" if v is None else f"{v:.1f}".replace(".", ",") + " %"


def week_lines(section: dict | None) -> list[str]:
    """Строки недельного блока для отчёта Пульса. Пусто — у снимка нет раздела или раздел со сбоем."""
    if not isinstance(section, dict) or section.get("error") or "metrika" not in section:
        return []
    w = section.get("window") or {}
    m = section.get("metrika") or {}
    ppl = section.get("people") or {}
    r = section.get("return") or {}
    ln = section.get("line") or {}
    s = section.get("subscriptions") or {}
    su = section.get("signups") or {}
    per_k = ln.get("clicks_per_1000_views")
    triggers = ", ".join(f"{k} {v}" for k, v in (su.get("by_trigger") or {}).items()) or "—"
    return [
        f"Неделя {w.get('from', '?')} — {w.get('to', '?')}: люди из Яндекса {m.get('yandex_visits', 0)}, "
        f"живых посетителей сайта {ppl.get('human_visitors', 0)}",
        f"Возврат за 30 дней (первый вход {r.get('cohort_first_from', '?')} — {r.get('cohort_first_to', '?')}, "
        f"{r.get('cohort', 0)} чел.): сами, не из поиска {_pct(r.get('by_self_pct'))}; "
        f"в другой день {_pct(r.get('other_day_pct'))}",
        f"Строка «присылать»: показов {ln.get('views', 0)} ({ln.get('viewers', 0)} чел.), нажатий "
        f"{ln.get('clicks', 0)} ({ln.get('clickers', 0)} чел.)"
        + (f", {str(per_k).replace('.', ',')} на 1 000 показов" if per_k is not None else ""),
        f"Нажал → открыл бота: {s.get('site_bot_chats_new', 0)}; подписки бота новых {s.get('bot_subscriptions_new', 0)} "
        f"(с сайта {s.get('bot_subscriptions_new_from_site', 0)}, всего {s.get('bot_subscriptions_total', 0)}); "
        f"почта: слежений {s.get('mail_watches_new', 0)}, согласий на письма {s.get('watch_mail_consents_new', 0)}",
        f"Регистрации {su.get('total', 0)} ({triggers}); ИИ {m.get('ai_visits', 0)}; "
        f"Google-Россия {m.get('google_ru_visits', 0)} визитов",
    ]


def memory_core(section: dict | None) -> dict[str, Any]:
    if not isinstance(section, dict) or section.get("error") or "metrika" not in section:
        return {}
    r = section.get("return") or {}
    ln = section.get("line") or {}
    s = section.get("subscriptions") or {}
    return {
        "week_yandex": (section.get("metrika") or {}).get("yandex_visits"),
        "week_return_self_pct": r.get("by_self_pct"),
        "week_return_other_day_pct": r.get("other_day_pct"),
        "week_line_views": ln.get("views"), "week_line_clicks": ln.get("clicks"),
        "week_bot_subs_from_site": s.get("bot_subscriptions_new_from_site"),
        "week_signups": (section.get("signups") or {}).get("total"),
    }
