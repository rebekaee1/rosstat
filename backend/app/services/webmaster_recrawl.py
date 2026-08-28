"""Ежедневная автоподача URL в переобход Яндекс.Вебмастера.

Квота переобхода (~150 URL/день) — самый сильный форсированный сигнал
Яндексу. Job каждое утро выбирает следующие по приоритету ещё не поданные
URL из единого реестра (`site_urls.collect_all_paths`, порядок секций =
приоритет) и подаёт их до исчерпания квоты.

Состояние «что уже подавали» — Redis-set в state-DB (переживает деплойный
FLUSHDB кэша). Когда весь реестр пройден, множество очищается и цикл
начинается заново — повторный обход раз в N месяцев полезен.

Языковой сплит: ``origin`` / ``host_id`` / ``submitted_key`` — для второго
свойства Вебмастера (`ru.`). Дефолт = текущий apex. Не подавать `ru.` пока
хост не добавлен в Вебмастер и DNS/TLS не живы.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.core.cache import get_state_redis
from app.database import async_session
from app.services.seo_content import DOMAIN
from app.services.yandex_webmaster_client import YandexWebmasterClient

logger = logging.getLogger(__name__)

_SUBMITTED_KEY = "wm:recrawl:submitted"


async def _alert_recrawl(text: str) -> None:
    try:
        from app.services.alerting import send_telegram
        await send_telegram(f"🟡 <b>Webmaster recrawl</b>\n{text}", kind="recrawl_alert")
    except Exception:
        logger.warning("Recrawl alert failed", exc_info=True)


async def recrawl_daily_job(
    *,
    origin: str | None = None,
    host_id: str | None = None,
    submitted_key: str | None = None,
) -> dict[str, int]:
    """Подать в переобход следующую порцию приоритетных URL (до квоты).

    Для второго хоста после cutover:
      await recrawl_daily_job(
          origin="https://ru.forecasteconomy.com",
          host_id=settings.webmaster_host_id_for("ru.forecasteconomy.com"),
          submitted_key="wm:recrawl:submitted:ru.forecasteconomy.com",
      )
    """
    if not settings.yandex_webmaster_token:
        logger.info("Recrawl job skipped: no webmaster token")
        return {"submitted": 0, "quota": 0}

    # submit_recrawl идёт через action_policy: без live writes POST не уходит,
    # квота 150 сгорает впустую (инцидент 2026-07-11/12: submitted 0 при quota 150).
    if not settings.analytics_live_writes_enabled:
        logger.error(
            "Recrawl job blocked: analytics_live_writes_enabled=false "
            "(нужен RUSTATS_ANALYTICS_LIVE_WRITES_ENABLED=true на проде)"
        )
        await _alert_recrawl(
            "Заблокирован: <code>analytics_live_writes_enabled=false</code>. "
            "Квота переобхода не тратится — включите live writes на проде."
        )
        return {"submitted": 0, "quota": 0, "blocked": "live_writes_disabled"}

    base = (origin or DOMAIN).rstrip("/")
    wm_host_id = host_id or settings.webmaster_host_id
    cursor_key = submitted_key or _SUBMITTED_KEY

    client = YandexWebmasterClient()
    try:
        user = await client.user()
        user_id = user.data["user_id"]
        quota_resp = await client.recrawl_quota(user_id, wm_host_id)
        remaining = int(quota_resp.data.get("quota_remainder", 0))
    except Exception as exc:
        # Н-24: живой токен + недоступный API = дневная квота переобхода
        # потеряна; молчаливый лог откладывал обнаружение на недели.
        logger.exception("Recrawl job: quota/user fetch failed")
        await _alert_recrawl(f"Квота/пользователь недоступны: {str(exc)[:200]}")
        return {"submitted": 0, "quota": 0}

    if remaining <= 0:
        logger.info("Recrawl job: daily quota exhausted, nothing to do")
        return {"submitted": 0, "quota": 0}

    from app.services.site_urls import collect_all_paths, filter_recrawl_paths

    async with async_session() as db:
        paths = await collect_all_paths(db)
        # Приоритет спроса (2026-08-23): страницы, на которые больше всего
        # «потерянных показов» из поиска Яндекса, идут первыми — переобход
        # по спросу, а не только по порядку реестра.
        try:
            from app.services.demand_router import priority_recrawl_paths

            demand = await priority_recrawl_paths(db, days=30, limit=remaining * 3)
        except Exception:
            logger.exception("Recrawl job: demand priority failed, fallback to registry")
            demand = []

    # Защитный слой: даже если junk снова попадёт в реестр (или останется в
    # старом курсоре), помечаем skip без POST — квота не горит, курсор идёт дальше.
    eligible, skipped = filter_recrawl_paths(paths)
    eligible_set = set(eligible)
    # Спрос-страницы, которых нет в реестре (например, битый матчинг), не подаём.
    demand_first = [p for p, _lost in demand if p in eligible_set]

    from app.services.yandex_client import YandexApiError

    redis = await get_state_redis()
    if skipped:
        # Batch SADD — junk из прошлых циклов / query-варианты не блокируют прогресс.
        await redis.sadd(cursor_key, *skipped)

    submitted = 0
    demand_submitted = 0

    demand_first_set = set(demand_first)

    async def _submit(path: str) -> bool:
        url = f"{base}{path}"
        try:
            await client.submit_recrawl(user_id, wm_host_id, url, approved=True)
            await redis.sadd(cursor_key, path)
            return True
        except YandexApiError as exc:
            err = str(exc.payload)[:200].upper()
            if "QUOTA" in err:
                logger.info("Recrawl job: quota hit mid-run after %d", submitted)
                return False
            # URL_ALREADY_ADDED и прочие мягкие отказы — помечаем и идём дальше.
            await redis.sadd(cursor_key, path)
            logger.warning("Recrawl submit %s rejected: %s", url, err)
            return True
        except Exception:
            logger.exception("Recrawl submit failed for %s", url)
            return False

    for path in demand_first:
        if submitted >= remaining:
            break
        if await redis.sismember(cursor_key, path):
            continue
        if not await _submit(path):
            break
        submitted += 1
        demand_submitted += 1
    for path in eligible:
        if submitted >= remaining:
            break
        if path in demand_first_set:
            continue
        if await redis.sismember(cursor_key, path):
            continue
        if not await _submit(path):
            break
        submitted += 1
    else:
        # Прошли весь eligible-реестр — все URL уже подавались. Начинаем новый цикл.
        if submitted < remaining:
            await redis.delete(cursor_key)

    total_submitted = int(await redis.scard(cursor_key))
    logger.info(
        "Recrawl job: submitted %d URL(s) (quota %d), demand-priority %d, "
        "skipped_noncanonical %d, cursor at %d/%d host_id=%s",
        submitted,
        remaining,
        demand_submitted,
        len(skipped),
        total_submitted,
        len(eligible),
        wm_host_id,
    )
    return {
        "submitted": submitted,
        "demand_priority": demand_submitted,
        "quota": remaining,
        "cursor": total_submitted,
        "skipped_noncanonical": len(skipped),
        "eligible": len(eligible),
        "origin": base,
    }
