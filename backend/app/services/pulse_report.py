"""LLM-отчёт «пульса» в Telegram (П9б, 2026-07-02).

Пайплайн: снапшот дня (`pulse.py`) + память прошлых дней → OpenRouter
(model = settings.openrouter_model) → человеческая сводка на русском →
Telegram-сообщение владельцу (`settings.pulse_chat_id`) с новым оформлением
Bot API: expandable blockquote для сырых цифр + inline-кнопки, которые
обрабатывает `telegram_bot.py` (getUpdates-поллер).

Контроль контекста: модели передаём полный снапшот ТОЛЬКО за отчётный день;
прошлые дни — компактная память (числовое ядро + однострочная сводка),
поэтому окно не растёт с историей. После отчёта сводка дня записывается
в память (TTL 30 дней) — так у системы есть «вчера» и тренд недели.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from html import escape

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import async_session
from app.models import Hypothesis
from app.services import pulse
from app.services.telegram_bot import main_menu_keyboard, send_message

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_PROMPT = """Ты — аналитик forecasteconomy.com (экономическая статистика России). Раз в
день тебе присылают JSON с активностью сайта за сутки и краткую память по
прошлым дням.

Прочитай и напиши владельцу короткую записку — как понимающий человек, а не
как отчёт по шаблону. Что реально стоит внимания: рост/спад, аномалия,
проблема (ошибки фронта, упавший ETL, запросы в поиске без результатов — это
пробелы каталога, их стоит явно назвать). Разрез authed/guest в данных — это
зарегистрированные и гости сайта; упомяни, если там есть что-то интересное, не
ради галочки. Если день обычный — так и скажи в паре строк, не придумывай
значимость там, где её нет. Длину и структуру выбирай сам по ситуации.

Блок behavior — сырой поведенческий поток (наша «видеокамера»): просмотры
страниц, каждый клик по элементам интерфейса, время и глубина скролла по
страницам, что копируют. dead-клики — человек кликнул в некликабельное (ждал
реакции — её нет), rage-клики — злая серия кликов в одну точку; и то и другое —
прямые сигналы UX-проблем, называй конкретный элемент и страницу.

Блок acquisition — привлечение из Яндекс.Метрики: источники трафика
(реклама/органика/прямые/переходы с сайтов), поисковики, поисковые фразы,
рекламные кампании. Фразы — самое ценное: по ним видно, что люди ищут и чего
сайту не хватает. Если по фразам виден спрос, который мы не закрываем, —
скажи об этом прямо, это кандидат на новый раздел или текст.

Блок hypotheses в конце входа — булев слой знаний: открытые гипотезы о
пользователях и сайте. Твоя обязанность — вести его: пересматривай открытые
гипотезы по свежим данным (подтверждай/опровергай, если оснований достаточно)
и добавляй новые проверяемые гипотезы, когда данные их подсказывают. Гипотеза —
конкретное проверяемое утверждение («фразы про X дают визиты, но раздела X
нет — трафик уходит»), не банальность.

Цифры — только из данных, ничего не выдумывай и не округляй заметно.

Формат — Telegram HTML: <b>, <i>, <code>, <blockquote>. Markdown и списки через
"-"/"*" не рендерятся Telegram, не используй их.

В конце ответа, после строки ---HYPOTHESES---, выведи JSON-массив изменений
гипотез (может быть пустым []): [{"id": число или null для новой, "statement":
"утверждение", "verdict": true|false|null, "confidence": 0.0-1.0, "rationale":
"на чём основано"}]. Не более 5 изменений за день. Всё до разделителя — текст
сообщения владельцу, без преамбул."""


_HYP_SEPARATOR = "---HYPOTHESES---"


async def _open_hypotheses() -> list[dict]:
    """Открытые гипотезы для контекста модели (id нужен для пересмотра)."""
    async with async_session() as db:
        rows = (await db.execute(
            select(Hypothesis).where(Hypothesis.verdict.is_(None))
            .order_by(Hypothesis.created_at).limit(30)
        )).scalars().all()
    return [
        {"id": h.id, "statement": h.statement, "rationale": h.rationale}
        for h in rows
    ]


async def _apply_hypothesis_updates(updates: list[dict]) -> int:
    """Изменения гипотез от LLM → таблица hypotheses. Возвращает число применённых."""
    applied = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with async_session() as db:
        for upd in updates[:5]:
            if not isinstance(upd, dict) or not str(upd.get("statement") or "").strip():
                continue
            verdict = upd.get("verdict")
            if verdict is not None and not isinstance(verdict, bool):
                verdict = None
            confidence = upd.get("confidence")
            try:
                confidence = max(0.0, min(1.0, float(confidence))) if confidence is not None else None
            except (TypeError, ValueError):
                confidence = None
            h = None
            if upd.get("id") is not None:
                try:
                    h = await db.get(Hypothesis, int(upd["id"]))
                except (TypeError, ValueError):
                    h = None
            if h is None:
                h = Hypothesis(created_at=now)
                db.add(h)
            h.statement = str(upd["statement"])[:500]
            h.rationale = str(upd.get("rationale") or "")[:2000] or None
            h.verdict = verdict
            h.confidence = confidence
            h.updated_at = now
            applied += 1
        await db.commit()
    return applied


def _split_llm_output(content: str) -> tuple[str, list[dict]]:
    """Ответ модели → (текст владельцу, изменения гипотез)."""
    if _HYP_SEPARATOR not in content:
        return content.strip(), []
    text, _, tail = content.partition(_HYP_SEPARATOR)
    updates: list[dict] = []
    match = re.search(r"\[.*\]", tail, flags=re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                updates = [u for u in parsed if isinstance(u, dict)]
        except ValueError:
            logger.warning("Pulse hypotheses JSON parse failed: %s", tail[:200])
    return text.strip(), updates


async def _llm_summary(snapshot: dict, memory: list[dict]) -> str | None:
    """Сводка дня через OpenRouter (+ ведение гипотез). None при сбое —
    отчёт уйдёт без LLM."""
    if not settings.openrouter_api_key:
        return None
    hypotheses = await _open_hypotheses()
    payload = {
        "model": settings.openrouter_model,
        "max_tokens": 1400,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Память за прошлые дни (старые → новые):\n"
                    + json.dumps(memory, ensure_ascii=False)
                    + "\n\nСнапшот за отчётный день:\n"
                    + json.dumps(snapshot, ensure_ascii=False)
                    + "\n\nОткрытые гипотезы (hypotheses):\n"
                    + json.dumps(hypotheses, ensure_ascii=False)
                ),
            },
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                _OPENROUTER_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": "https://forecasteconomy.com",
                    "X-Title": "Forecast Economy Pulse",
                },
            )
        if resp.status_code != 200:
            logger.warning("OpenRouter HTTP %d: %s", resp.status_code, resp.text[:300])
            return None
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if not content:
            return None
        text, updates = _split_llm_output(content)
        if updates:
            try:
                n = await _apply_hypothesis_updates(updates)
                logger.info("Pulse hypotheses: %s updates applied", n)
            except Exception:
                logger.warning("Pulse hypotheses apply failed", exc_info=True)
        return text or None
    except Exception:
        logger.warning("OpenRouter call failed", exc_info=True)
        return None


def _fallback_summary(snapshot: dict) -> str:
    """Детерминированная сводка, если LLM недоступен."""
    u = snapshot.get("users", {})
    ev = snapshot.get("events", {})
    etl = snapshot.get("etl", {})
    aud = snapshot.get("audience", {})
    by_aud = ev.get("by_audience", {})
    dl_aud = ev.get("downloads_by_audience", {})
    lines = [
        f"👤 Пользователи: всего {u.get('total', 0)}, новых {u.get('new', 0)}",
        f"🫂 Активны за день: зарег. {aud.get('authed_active', 0)}, "
        f"гостей {aud.get('guest_sessions', 0)}",
        f"⚡ Событий: {ev.get('total', 0)} "
        f"(зарег. {by_aud.get('authed', 0)} / гости {by_aud.get('guest', 0)})",
        f"📥 Скачиваний: {sum(ev.get('downloads', {}).values())} "
        f"(зарег. {dl_aud.get('authed', 0)} / гости {dl_aud.get('guest', 0)})",
        f"🛑 Ошибок фронта: {sum(ev.get('errors', {}).values())}",
        f"🏭 Упавших ETL-индикаторов: {len(etl.get('failed_indicator_ids', []))}",
        f"➕ Новых точек данных: {snapshot.get('data', {}).get('new_points', 0)}",
    ]
    return "\n".join(lines)


def _raw_digits_block(snapshot: dict) -> str:
    """Сырые цифры дня в expandable blockquote (новое оформление Bot API 7.10)."""
    ev = snapshot.get("events", {})
    parts: list[str] = []
    aud = snapshot.get("audience", {})
    by_aud = ev.get("by_audience", {})
    dl_aud = ev.get("downloads_by_audience", {})
    parts.append(
        "Аудитория: зарег. активных "
        f"{aud.get('authed_active', 0)}, гостевых сессий {aud.get('guest_sessions', 0)}; "
        f"события зарег/гость {by_aud.get('authed', 0)}/{by_aud.get('guest', 0)}; "
        f"скачивания зарег/гость {dl_aud.get('authed', 0)}/{dl_aud.get('guest', 0)}"
    )
    if ev.get("by_name"):
        top = ", ".join(f"{k}: {v}" for k, v in list(ev["by_name"].items())[:15])
        parts.append(f"События: {escape(top)}")
    if ev.get("top_indicators"):
        top = ", ".join(f"{k} ×{v}" for k, v in ev["top_indicators"].items())
        parts.append(f"Индикаторы: {escape(top)}")
    if ev.get("top_regions"):
        top = ", ".join(f"{k} ×{v}" for k, v in ev["top_regions"].items())
        parts.append(f"Регионы: {escape(top)}")
    if ev.get("search_top"):
        top = ", ".join(f"«{k}» ×{v}" for k, v in ev["search_top"].items())
        parts.append(f"Поиск: {escape(top)}")
    if ev.get("search_zero_results"):
        top = ", ".join(f"«{k}»" for k in ev["search_zero_results"])
        parts.append(f"Поиск без результатов: {escape(top)}")
    auth = snapshot.get("auth", {})
    if auth:
        parts.append("Auth: " + escape(", ".join(f"{k}: {v}" for k, v in auth.items())))
    acq = snapshot.get("acquisition", {})
    if acq.get("traffic_sources"):
        top = ", ".join(
            f"{name}: {row.get('visits', 0)}"
            for name, row in sorted(acq["traffic_sources"].items(),
                                    key=lambda kv: -kv[1].get("visits", 0))
        )
        parts.append(f"Источники (Метрика): {escape(top)}")
    if acq.get("search_phrases_top"):
        top = ", ".join(
            f"«{p['phrase'][:40]}» ×{p['visits']}" for p in acq["search_phrases_top"][:10]
        )
        parts.append(f"Фразы из поиска: {escape(top)}")
    if not parts:
        return ""
    return "<blockquote expandable>" + "\n".join(parts) + "</blockquote>"


async def send_pulse_report(report_date: date | None = None) -> bool:
    """Собрать (или взять готовый) снапшот дня, прогнать через LLM, отправить в ТГ."""
    if not (settings.telegram_bot_token and settings.pulse_chat_id):
        logger.info("Pulse report skipped: telegram not configured")
        return False

    d = report_date or (date.today() - timedelta(days=1))
    snapshot = await pulse.get_or_build_snapshot(d)
    # Привлечение обновляем на момент отчёта: снапшот фиксируется в 23:57,
    # а синк Метрики за этот день отрабатывает только утром (08:20).
    try:
        acquisition = await pulse.build_acquisition(d)
        if acquisition:
            snapshot["acquisition"] = acquisition
            await pulse.store_snapshot(snapshot)
    except Exception:
        logger.warning("Pulse acquisition refresh failed", exc_info=True)
    memory = await pulse.load_memory(days=7, before=d)

    summary = await _llm_summary(snapshot, memory)
    body = summary or _fallback_summary(snapshot)

    msg_parts = [f"🛰 <b>Пульс платформы — {d.isoformat()}</b>", "", body]
    raw = _raw_digits_block(snapshot)
    if raw:
        msg_parts += ["", raw]
    text = "\n".join(msg_parts)

    ok = await send_message(
        settings.pulse_chat_id, text, reply_markup=main_menu_keyboard()
    )
    # память дня пишем даже при сбое отправки — снапшот уже посчитан
    await pulse.store_memory(d, pulse.memory_core(snapshot), summary or _fallback_summary(snapshot))
    return ok


async def pulse_snapshot_job() -> None:
    """Ежедневная фиксация снапшота (23:57 МСК) — чтобы день не потерялся."""
    try:
        snap = await pulse.build_snapshot(date.today())
        await pulse.store_snapshot(snap)
        logger.info("Pulse snapshot stored for %s", snap["date"])
    except Exception:
        logger.exception("Pulse snapshot job failed")


async def pulse_report_job() -> None:
    """Ежедневный LLM-отчёт за вчера (09:05 МСК)."""
    try:
        await send_pulse_report()
    except Exception:
        logger.exception("Pulse report job failed")
