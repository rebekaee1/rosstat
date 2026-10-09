"""Telegram alerting for ETL failures and critical events."""

import logging
from html import escape
from typing import Optional

import httpx

from app.config import settings
from app.services.telegram_retry import request_with_retry
from app.services.telegram_text import split_telegram_text

logger = logging.getLogger(__name__)
# httpx logs the full request URL at INFO; Telegram's URL embeds the bot token.
# Keep transport URLs out of application logs while retaining warnings/errors.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Антиспам повторяющихся технических алертов (state-Redis DB 1).
# Daily ETL + evening + late-Minfin иначе шлют один и тот же budget-*/coal
# по 2–3 раза в сутки; zero-parse — на каждый прогон.
_ETL_FAILURE_MUTE_TTL = 12 * 3600
_ZERO_PARSE_MUTE_TTL = 24 * 3600
STALENESS_MUTE_TTL = 6 * 24 * 3600  # хронический список — раз в неделю


async def alert_muted(alert_key: str, ttl_seconds: int) -> bool:
    """True = уже слали недавно, пропустить. False = можно слать (ключ поставлен).

    При недоступности Redis — fail-open (шлём): лучше шум, чем слепота.
    """
    try:
        from app.core.cache import get_state_redis

        r = await get_state_redis()
        key = f"fe:alerts:mute:{alert_key}"
        if await r.get(key):
            return True
        await r.set(key, "1", ex=ttl_seconds)
        return False
    except Exception:  # noqa: BLE001
        logger.warning("alert mute check failed for %s — sending anyway", alert_key)
        return False


async def send_telegram(
    message: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[dict] = None,
    kind: str = "alert",
) -> bool:
    """Send alert to Telegram (async, non-blocking). Returns True on success.

    `chat_id` переопределяет получателя; без него — primary `settings.telegram_chat_id`.
    `reply_markup` — inline-клавиатура (напр. меню бота под дайджестом).
    `kind` — семантика отправки для архива telegram_outbox (etl_alert / digest / …).
    Каждая отправка полностью архивируется в БД (`telegram_outbox`) — это
    «глаза» агента следующей сессии; архивация не влияет на доставку.
    """
    token = settings.telegram_bot_token
    cid = chat_id or settings.telegram_chat_id
    if not token or not cid:
        return False

    # E3 (круг 11): длинный текст режется на части под лимит Bot API; клавиатура
    # вешается на последнюю часть, в архиве — по строке на каждую часть (как у
    # telegram_bot.send_message), поэтому досылка работает по частям.
    chunks = split_telegram_text(message)
    all_ok = True
    for index, chunk in enumerate(chunks):
        payload: dict = {"chat_id": cid, "text": chunk, "parse_mode": "HTML"}
        if reply_markup and index == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        if not await _send_one(token, payload, kind):
            all_ok = False
    return all_ok


async def _send_one(token: str, payload: dict, kind: str) -> bool:
    """Одна отправка `sendMessage` с архивом (pending до, итог после)."""
    from app.services.telegram_outbox import archive_begin, archive_finish  # против цикла

    ok = False
    tg_message_id: Optional[int] = None
    error: Optional[str] = None

    # Н-16: pending-запись ДО отправки — креш между send и архивом не оставляет дыру.
    row_id = await archive_begin(
        chat_id=str(payload["chat_id"]), method="sendMessage", kind=kind,
        text=payload["text"], payload=payload,
    )
    try:
        url = _TELEGRAM_API.format(token=token)
        async with httpx.AsyncClient(timeout=10) as client:
            # Временные сбои (сеть/таймаут/429/5xx) повторяются с паузой в
            # пределах общего потолка; 400/403/404 — нет. Одна архивная строка
            # на всю отправку: итог (и число попыток при ошибке) пишет finish.
            resp, error, _attempts = await request_with_retry(
                lambda: client.post(url, json=payload)
            )
        if error is None and resp is not None:
            ok = True
            try:
                tg_message_id = resp.json().get("result", {}).get("message_id")
            except Exception:
                pass
        else:
            logger.warning("Telegram alert failed: %s", error)
    except Exception as exc:
        # str(httpx.ConnectTimeout()) пустая — без имени класса архив молчит.
        error = f"{type(exc).__name__}: {exc}"[:250]
        logger.warning("Telegram alert failed", exc_info=True)

    await archive_finish(row_id, ok=ok, telegram_message_id=tg_message_id, error=error)
    return ok


def site_version_label(locale: str | None) -> str:
    """Человеческая подпись версии сайта в Telegram: русская / английская."""
    code = (locale or "").strip().lower()
    if code == "ru":
        return "русская"
    if code == "en":
        return "английская"
    return "—"


_DEVICE_RU = {"mobile": "телефон", "tablet": "планшет", "desktop": "компьютер", "bot": "робот"}


def visitor_country_line(ip: str | None) -> str:
    """«Германия, Берлин» по геобазе; «—», если страна неизвестна. Сам IP не показываем."""
    if not ip:
        return "—"
    try:
        from app.services.geoip import lookup

        geo = lookup(ip)
    except Exception:  # noqa: BLE001 — гео опционально
        return "—"
    parts = [p for p in (geo.get("country"), geo.get("city")) if p]
    return ", ".join(parts) if parts else "—"


def visitor_device_line(user_agent: str | None) -> str:
    """«Chrome 126 · Windows 10/11 · компьютер» вместо полной строки User-Agent."""
    if not user_agent:
        return "—"
    try:
        from app.services.ua_parser import parse_user_agent

        parsed = parse_user_agent(user_agent)
    except Exception:  # noqa: BLE001
        return "—"
    browser = " ".join(p for p in (parsed.get("browser"), parsed.get("browser_version")) if p)
    os_name = " ".join(p for p in (parsed.get("os"), parsed.get("os_version")) if p)
    kind = _DEVICE_RU.get(parsed.get("device_type") or "", "")
    return " · ".join(p for p in (browser, os_name, kind) if p) or "—"


def digest_recipients() -> list[str]:
    """Получатели ежедневного дайджеста: primary + extra (config-driven, dedup).

    primary — `telegram_chat_id`; extra — comma-separated `telegram_digest_chat_ids`.
    Realtime-алерты (новый юзер/обратная связь) шлём только primary; дайджест —
    всем (звонок 2026-06-21: skrakan получает дайджест в 9:00 наравне с rebekaee1).
    """
    primary = settings.telegram_chat_id
    extra = [c.strip() for c in (settings.telegram_digest_chat_ids or "").split(",") if c.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for cid in [primary, *extra]:
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


async def send_telegram_digest(message: str, reply_markup: Optional[dict] = None) -> dict[str, bool]:
    """Рассылка дайджеста всем получателям. Возвращает {chat_id: ok}.

    `reply_markup` — общее меню бота под отчётом, чтобы получатели (владелец +
    skrakan) могли сразу выгрузить CSV/раскрыть пользователей той же кнопкой.
    """
    return {
        cid: await send_telegram(message, chat_id=cid, reply_markup=reply_markup, kind="digest")
        for cid in digest_recipients()
    }


def interactive_authorized_ids() -> set[str]:
    """Кто вправе жать кнопки бота (меню, карточки, выгрузка CSV пользователей).

    Владелец (`telegram_chat_id`) + получатели отчёта (`telegram_digest_chat_ids`,
    напр. skrakan) + `pulse_chat_id`. Регистрации/обратная связь/пульс с 2026-07-06
    тоже уходят всем получателям дайджеста (указание владельца); технические
    realtime-алерты (ETL/5xx/аномалии) остаются только у владельца.
    """
    ids = set(digest_recipients())
    if settings.pulse_chat_id:
        ids.add(str(settings.pulse_chat_id))
    return {str(i) for i in ids if i}


async def notify_new_user(info: dict) -> None:
    """Мгновенное уведомление администратора о новой регистрации (ADR-0007 Phase 2).

    Никогда не роняет регистрацию: вызывать через try/except или fire-and-forget.
    Молчит, если realtime-алерты выключены (`telegram_realtime_alerts_enabled`) —
    данные всё равно есть в ежедневном дайджесте.
    """
    if not settings.telegram_realtime_alerts_enabled:
        return
    def esc(v) -> str:
        return escape(str(v)) if v not in (None, "") else "—"

    lines = [
        "🆕 <b>Новый пользователь</b>",
        f"Версия сайта: {site_version_label(info.get('locale'))}",
        f"Способ входа: {esc(info.get('method'))}",
        f"Email: {esc(info.get('email'))}",
        f"Телефон: {esc(info.get('phone'))}",
        f"Имя: {esc(info.get('display_name'))}",
        f"Рассылка: {'да' if info.get('newsletter') else 'нет'}",
        # 152-ФЗ (круг 11): вместо IP и полного User-Agent — страна и «браузер, ОС, тип»;
        # сообщение хранится в telegram_outbox без срока. Старые строки архива не трогаем.
        f"Страна: {esc(visitor_country_line(info.get('ip')))}",
        f"Устройство: {esc(visitor_device_line(info.get('user_agent')))}",
        f"ID: <code>{esc(info.get('user_id'))}</code>",
    ]
    # Всем получателям дайджеста (владелец + skrakan) — указание владельца 2026-07-06.
    for cid in digest_recipients():
        await send_telegram("\n".join(lines), chat_id=cid, kind="new_user")


async def notify_login(info: dict) -> None:
    """Мгновенное уведомление о входе существующего пользователя.

    Регистрация — `notify_new_user`. Повторный OAuth/почта раньше молчали:
    сегодняшние Яндекс/VK (аккаунты с июня) в outbox не попали. Владелец
    просил видеть входы тоже, не только первую регистрацию.
    """
    if not settings.telegram_realtime_alerts_enabled:
        return

    def esc(v) -> str:
        return escape(str(v)) if v not in (None, "") else "—"

    lines = [
        "🔑 <b>Вход</b>",
        f"Способ входа: {esc(info.get('method'))}",
        f"Email: {esc(info.get('email'))}",
        f"Телефон: {esc(info.get('phone'))}",
        f"Имя: {esc(info.get('display_name'))}",
        f"Страна: {esc(visitor_country_line(info.get('ip')))}",
        f"Устройство: {esc(visitor_device_line(info.get('user_agent')))}",
        f"ID: <code>{esc(info.get('user_id'))}</code>",
    ]
    for cid in digest_recipients():
        await send_telegram("\n".join(lines), chat_id=cid, kind="login")


async def notify_feedback(info: dict) -> None:
    """Мгновенная отправка обратной связи от авторизованного пользователя (ADR-0007 Phase 2)."""
    if not settings.telegram_realtime_alerts_enabled:
        return
    def esc(v) -> str:
        return escape(str(v)) if v not in (None, "") else "—"

    lines = [
        "💬 <b>Обратная связь</b>",
        f"Email: {esc(info.get('email'))}",
        f"Имя: {esc(info.get('display_name'))}",
        f"ID: <code>{esc(info.get('user_id'))}</code>",
        "",
        esc(info.get("message")),
    ]
    contact = info.get("contact")
    if contact:
        lines.insert(4, f"Контакт для ответа: {esc(contact)}")
    for cid in digest_recipients():
        await send_telegram("\n".join(lines), chat_id=cid, kind="feedback")


# Сегменты «Для чего нужны данные» заявки на API (ключевая сегментация замера
# спроса). Ключи — контракт с фронтом (ApiInterestModal), подписи — для владельца.
API_INTEREST_USE_CASES = {
    "analytics_treasury": "аналитика / казначейство",
    "planning_contracts": "бизнес-планирование и договоры",
    "consulting": "консалтинг",
    "research": "исследование / наука",
    "study": "учёба",
    "journalism": "журналистика",
    "other": "другое",
}
_API_INTEREST_SOURCES = {"indicator": "страница показателя", "limit_modal": "окно лимита скачиваний"}


def format_api_interest_message(info: dict) -> str:
    """Текст Telegram-сообщения «заявка на API». Чистая функция (тестируется).

    Почта и комментарий — введённый гостем текст: экранируем под parse_mode=HTML.
    Это единственное место, где почта попадает в хранилище (telegram_outbox,
    как и у обратной связи); в логи и в frontend_events она не пишется.
    """
    def esc(v) -> str:
        return escape(str(v)) if v not in (None, "") else "—"

    use_case = info.get("use_case")
    lines = [
        "🧪 <b>Заявка на API</b> (замер спроса)",
        f"Email: {esc(info.get('email'))}",
        f"Для чего: {esc(API_INTEREST_USE_CASES.get(use_case, use_case))}",
        f"Откуда: {esc(_API_INTEREST_SOURCES.get(info.get('source'), info.get('source')))}",
        f"Показатель: {esc(info.get('indicator_code'))}",
        f"Версия сайта: {site_version_label(info.get('locale'))}",
    ]
    comment = info.get("comment")
    if comment:
        lines += ["", esc(comment)]
    return "\n".join(lines)


async def notify_api_interest(info: dict) -> bool:
    """Заявка на платный API → всем получателям дайджеста (владелец + skrakan).

    Не зависит от `telegram_realtime_alerts_enabled`: заявка — это данные
    замера, а не алерт, молча терять её нельзя. Возвращает True, если хотя бы
    одно сообщение доставлено. Недоставленное остаётся в telegram_outbox и
    досылается job'ом (kind in RESEND_KINDS).
    """
    text = format_api_interest_message(info)
    delivered = False
    for cid in digest_recipients():
        if await send_telegram(text, chat_id=cid, kind="api_interest"):
            delivered = True
    return delivered


async def alert_forecast_issue(indicator_code: str, detail: str) -> None:
    """Прогнозный контур (Н-7/Н-8): нерезолвнутая стратегия, провал каскада."""
    msg = (
        f"🟡 <b>Forecast issue</b>\n"
        f"Indicator: <code>{escape(indicator_code)}</code>\n"
        f"{escape(detail[:300])}"
    )
    await send_telegram(msg, kind="forecast_issue")


async def alert_etl_failure(indicator_code: str, error: str) -> None:
    """Per-indicator ETL fail. Mute 12h на код — иначе late-Minfin/evening
    дублируют утренний fail тем же 503. В daily_update_job per-indicator
    не зовём: там достаточно summary со списком failed.
    """
    if await alert_muted(f"etl_failure:{indicator_code}", _ETL_FAILURE_MUTE_TTL):
        logger.info("ETL failure muted for %s", indicator_code)
        return
    msg = (
        f"🔴 <b>ETL Failed</b>\n"
        f"Indicator: <code>{escape(indicator_code)}</code>\n"
        f"Error: {escape(error[:200])}"
    )
    await send_telegram(msg, kind="etl_failure")


async def alert_zero_parse(indicator_code: str, existing_points: int) -> None:
    """Zero-parse regression (история есть, парсер вернул 0). Mute 24h на код."""
    if await alert_muted(f"zero_parse:{indicator_code}", _ZERO_PARSE_MUTE_TTL):
        logger.info("Zero-parse muted for %s", indicator_code)
        return
    await send_telegram(
        "🟡 <b>Zero-parse regression</b>\n"
        f"Indicator: <code>{escape(indicator_code)}</code>\n"
        f"Парсер вернул 0 точек при {existing_points} точках истории — "
        "вероятна смена layout источника.",
        kind="zero_parse",
    )


_DEGRADED_LABELS = {
    "parsed_zero": "Parsed zero (layout?)",
    "fallback_used": "Fallback source",
}


async def alert_etl_summary(
    total: int,
    updated: int,
    failed: list[str],
    duration_sec: Optional[float] = None,
    *,
    degraded: Optional[dict[str, list[str]]] = None,
) -> None:
    """Итог daily ETL. `degraded` — {status: [codes]} для parsed_zero /
    fallback_used: прогон «прошёл», но данные могут не обновляться — это
    проблема (🟡), а не зелёный no_new_data."""
    degraded = {k: v for k, v in (degraded or {}).items() if v}
    n_problems = sum(len(v) for v in degraded.values())
    status = "🔴" if failed else ("🟡" if n_problems else "🟢")
    parts = [
        f"{status} <b>Daily ETL Complete</b>",
        f"Total: {total} | Updated: {updated} | Failed: {len(failed)}"
        f" | Problems: {n_problems}",
    ]
    if duration_sec is not None:
        parts.append(f"Duration: {duration_sec:.0f}s")
    if failed:
        parts.append(f"Failed: {escape(', '.join(failed))}")
    for key, codes in degraded.items():
        label = _DEGRADED_LABELS.get(key, key)
        parts.append(f"{escape(label)} ({len(codes)}): {escape(', '.join(codes))}")
    await send_telegram("\n".join(parts), kind="etl_summary")


# Поимённые списки наборов/рядов длиннее 1000 символов; лимит Telegram — 4096.
_WORLD_SUMMARY_DETAILS_LIMIT = 2000


async def alert_world_ingest_summary(
    source: str,
    *,
    status: str,
    checked: int,
    changed: int,
    failed: int,
    details: str = "",
    checked_label: str = "Проверено",
    changed_label: str = "Изменено",
) -> None:
    """Report a *completed* world source run to the primary technical chat.

    ``shadow`` means that source changes were inspected without publishing
    observations. It must never be shown as a successful data refresh.
    Empty successful polls are reduced to one heartbeat per source per day.
    """
    if status not in {"ok", "partial", "failed", "shadow"}:
        raise ValueError(f"unsupported world ingest status: {status}")
    if status == "ok" and changed == 0 and failed == 0:
        if await alert_muted(f"world_ingest_noop:{source}", 20 * 3600):
            return
    symbol = {"ok": "🟢", "partial": "🟡", "failed": "🔴", "shadow": "🟡"}[status]
    label = {
        "ok": "завершено", "partial": "частично", "failed": "ошибка",
        "shadow": "теневая проверка — данные не обновлены",
    }[status]
    parts = [
        f"{symbol} <b>Обновление: {escape(source[:100])}</b>",
        f"Итог: {label}",
        f"{escape(checked_label)}: {checked} · {escape(changed_label)}: {changed} · Ошибок: {failed}",
    ]
    if details:
        parts.append(escape(details[:_WORLD_SUMMARY_DETAILS_LIMIT]))
    await send_telegram("\n".join(parts), kind="world_ingest_summary")
