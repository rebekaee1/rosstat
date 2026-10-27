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

import asyncio
import logging

from app.config import settings
from app.core.cache import get_state_redis
from app.database import async_session
from app.services.alerting import exception_reason
from app.services.seo_content import DOMAIN
from app.services.yandex_webmaster_client import YandexWebmasterClient

logger = logging.getLogger(__name__)

_SUBMITTED_KEY = "wm:recrawl:submitted"
_MAX_UNKNOWN_REJECTS = 3  # подряд отказов без понятной причины, после чего подача прекращается
_MAX_SOFT_REJECTS_PER_RUN = 300  # потолок «уже в очереди» за запуск: не крутить реестр впустую


def is_soft_recrawl_reject(exc: Exception) -> bool:
    """Отказ по конкретному адресу (уже в очереди, неверный адрес): 400/409/422 и непустая причина.

    Всё остальное (пустое тело, 401/403, 5xx) говорит о канале или правах, не об адресе.
    """
    status = getattr(exc, "status_code", None)
    payload = getattr(exc, "payload", None)
    if status not in (400, 409, 422):
        return False
    if isinstance(payload, dict):
        return bool(payload.get("error_code") or payload.get("error_message") or payload.get("message"))
    return bool(str(payload or "").strip())


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
        await _alert_recrawl(f"Квота/пользователь недоступны: {exception_reason(exc, 200)}")
        return {"submitted": 0, "quota": 0}

    if remaining <= 0:
        logger.info("Recrawl job: daily quota exhausted, nothing to do")
        return {"submitted": 0, "quota": 0}

    from app.services.site_urls import collect_all_paths, filter_recrawl_paths
    from app.services.sitemap_static import has_published_generation

    async with async_session() as db:
        # Приоритет спроса (2026-08-23): страницы, на которые больше всего
        # «потерянных показов» из поиска Яндекса, идут первыми — переобход
        # по спросу, а не только по порядку реестра.
        try:
            from app.services.demand_router import priority_recrawl_paths

            demand = await priority_recrawl_paths(
                db, days=30, limit=remaining * 3, host=wm_host_id,
            )
        except Exception:
            logger.exception("Recrawl job: demand priority failed, fallback to registry")
            demand = []
        # Commit/release before the long registry pass: no pool slot held idle.
        await db.commit()

    redis = await get_state_redis()

    if has_published_generation(base):
        # Реестр = опубликованная ночная генерация sitemap этого хоста (те же
        # URL и порядок секций, что видит робот). Разбор файлов в потоке:
        # ~5 млн <loc> не блокируют event loop, БД не трогается. Прежний путь
        # (collect_all_paths) падал 2026-09-26 по statement_timeout на
        # count(*) мировых лет по 16 млн world_data_points.
        already = set(await redis.smembers(cursor_key))
        scan = await asyncio.to_thread(
            _scan_published_registry, base, {p for p, _lost in demand}, already, remaining + _MAX_SOFT_REJECTS_PER_RUN,
        )
        eligible = scan["regular"]
        eligible_total = scan["eligible_total"]
        skipped = scan["skipped"]
        demand_first = [p for p, _lost in demand if p in scan["demand_found"]]
    else:
        async with async_session() as db:
            paths = await collect_all_paths(db)
        # Защитный слой: даже если junk снова попадёт в реестр (или останется в
        # старом курсоре), помечаем skip без POST — квота не горит, курсор идёт дальше.
        eligible, skipped = filter_recrawl_paths(paths)
        eligible_total = len(eligible)
        eligible_set = set(eligible)
        # Спрос-страницы, которых нет в реестре (например, битый матчинг), не подаём.
        demand_first = [p for p, _lost in demand if p in eligible_set]

    from app.services.yandex_client import YandexApiError
    if skipped:
        # Batch SADD — junk из прошлых циклов / query-варианты не блокируют прогресс.
        await redis.sadd(cursor_key, *skipped)

    submitted = 0
    demand_submitted = 0
    soft_rejected = 0
    unknown_rejects = 0  # подряд, сбрасывается успешной подачей
    abort_reason: str | None = None
    attempts = 0
    max_attempts = remaining + _MAX_SOFT_REJECTS_PER_RUN

    demand_first_set = set(demand_first)

    async def _submit(path: str) -> str:
        """ok | soft | unknown | quota | error. В курсор попадает только ok и soft."""
        nonlocal unknown_rejects, abort_reason
        url = f"{base}{path}"
        try:
            await client.submit_recrawl(user_id, wm_host_id, url, approved=True)
            await redis.sadd(cursor_key, path)
            unknown_rejects = 0
            return "ok"
        except YandexApiError as exc:
            err = str(exc.payload)[:200].upper()
            if "QUOTA" in err:
                logger.info("Recrawl job: quota hit mid-run after %d", submitted)
                return "quota"
            if is_soft_recrawl_reject(exc):
                # URL_ALREADY_ADDED и другие отказы по конкретному адресу: адрес считаем обработанным.
                await redis.sadd(cursor_key, path)
                logger.info("Recrawl submit %s skipped: status=%s payload=%s", url, exc.status_code, err)
                return "soft"
            # Пустое тело, 401/403, 5xx и т.п. — это отказ всего канала, а не адреса. Курсор НЕ двигаем:
            # 07–27.10.2026 каждый POST получал отказ без тела, 940 адресов в сутки уходили в «обработанные».
            unknown_rejects += 1
            logger.warning(
                "Recrawl submit %s rejected: status=%s payload=%s error=%s",
                url, exc.status_code, err, str(exc)[:200],
            )
            if unknown_rejects >= _MAX_UNKNOWN_REJECTS:
                abort_reason = f"HTTP {exc.status_code}, тело ответа: {err or 'пусто'}"
                return "error"
            return "unknown"
        except Exception:
            logger.exception("Recrawl submit failed for %s", url)
            return "error"

    ordered = [*demand_first, *(path for path in eligible if path not in demand_first_set)]
    for path in ordered:
        if submitted >= remaining or attempts >= max_attempts or abort_reason:
            break
        if await redis.sismember(cursor_key, path):
            continue
        attempts += 1
        result = await _submit(path)
        if result in ("quota", "error"):
            break
        if result == "soft":
            soft_rejected += 1
        elif result == "ok":
            submitted += 1
            if path in demand_first_set:
                demand_submitted += 1
    else:
        # Прошли весь eligible-реестр — все URL уже подавались. Начинаем новый цикл.
        if submitted < remaining and attempts < max_attempts and not abort_reason:
            await redis.delete(cursor_key)

    if abort_reason:
        await _alert_recrawl(
            f"Яндекс отклоняет подачу в переобход подряд {_MAX_UNKNOWN_REJECTS} раза ({abort_reason}). "
            "Подача остановлена, курсор не сдвинут: адреса не считаются поданными. "
            "Проверьте права на хост и его статус в Вебмастере."
        )

    total_submitted = int(await redis.scard(cursor_key))
    logger.info(
        "Recrawl job: submitted %d URL(s) (quota %d), demand-priority %d, "
        "soft_rejected %d, aborted=%s, skipped_noncanonical %d, cursor at %d/%d host_id=%s",
        submitted,
        remaining,
        demand_submitted,
        soft_rejected,
        abort_reason,
        len(skipped),
        total_submitted,
        eligible_total,
        wm_host_id,
    )
    return {
        "submitted": submitted,
        "demand_priority": demand_submitted,
        "soft_rejected": soft_rejected,
        "aborted": abort_reason,
        "quota": remaining,
        "cursor": total_submitted,
        "skipped_noncanonical": len(skipped),
        "eligible": eligible_total,
        "origin": base,
    }


def _scan_published_registry(
    origin: str, demand: set[str], already: set[str], need: int,
) -> dict:
    """Один проход по опубликованным файлам хоста (синхронно, для to_thread).

    regular — первые ``need`` подаваемых путей реестра, ещё не бывших в
    курсоре и не из спроса (спрос подаётся первым отдельно); demand_found —
    спрос-пути, реально присутствующие в реестре; eligible_total — размер
    подаваемого реестра (для лога курсора); skipped — неканонические пути.
    """
    from app.services.site_urls import is_recrawl_eligible
    from app.services.sitemap_static import iter_published_paths

    regular: list[str] = []
    skipped: list[str] = []
    demand_found: set[str] = set()
    eligible_total = 0
    for path in iter_published_paths(origin):
        if not is_recrawl_eligible(path):
            if path not in already:
                skipped.append(path)
            continue
        eligible_total += 1
        if path in demand:
            demand_found.add(path)
            continue
        if len(regular) < need and path not in already:
            regular.append(path)
    return {
        "regular": regular,
        "skipped": skipped,
        "demand_found": demand_found,
        "eligible_total": eligible_total,
    }
