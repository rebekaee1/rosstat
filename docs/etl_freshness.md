# ETL Freshness — диагностика устаревших данных

**Источник:** правка `v3/edit_006` (видео НА правки 3). Высокий приоритет.

## Заявленная проблема

Пользователь замечает, что на проде некоторые индикаторы (`unemployment`, `usd-rub`) показывают данные на `15.04` (или другую старую дату), что неактуально на дату просмотра.

## Диагностика

### Архитектура ETL

```
APScheduler (06:00 МСК ежедневно)
  └─ daily_update_job
       ├─ for source in [cbr, rosstat, minfin, ...]:
       │    ├─ parser.fetch_and_save()
       │    ├─ bulk_upsert(db, indicator_id, points) → (added, updated)
       │    └─ telegram_alert on Exception
       ├─ calculation_engine.recompute_all_derived()
       └─ cache_invalidate
```

**Где:** `backend/app/services/scheduler.py`.

### Точки сбоя

1. **Cron не запускается.** Проверить `docker compose logs backend | grep "daily_update"`. Если нет логов в 06:00 за последние дни — APScheduler упал.
2. **Парсер падает на одном источнике, ловится try/except, остальные не страдают.** Может проявиться как «один индикатор устарел, остальные свежие». Проверить `telegram_alerts` в чате на предмет ERROR-сообщений.
3. **Источник изменил формат.** ЦБ может поменять URL XLSX, добавить колонки. Парсер падает на assert. Проверить логи parser-specific.
4. **bulk_upsert игнорирует точки с прошлой датой.** Уже починено (см. history 2026-04-17 — `_split_point` принимает оба формата).
5. **derived series не пересчитан.** Мнимая «устарелость», т.к. факт обновился, но `wages-real`/`gdp-yoy` остались на старых значениях. Уже починено (см. 2026-04-17 — `result.fetchone() is not None`).

## Action items

### Проверка кода (текущая итерация)

- [ ] Прочитать `backend/app/services/scheduler.py` — убедиться, что:
  - `daily_update_job` вызывается через `scheduler.add_job(..., 'cron', hour=6, timezone='Europe/Moscow')`.
  - Каждый парсер обернут в try/except с telegram_alert.
  - После всех парсеров — `recompute_all_derived(db)`.
  - В конце — `cache_invalidate_all()`.
- [ ] Прочитать каждый парсер на предмет последнего URL источника — сравнить с реальным URL (cbr.ru/rosstat).
- [ ] Локально запустить `python -m backend.app.services.scheduler` или `pytest backend/tests/test_scheduler.py` — убедиться, что задача успешно отрабатывает и обновляет хотя бы одну точку в `IndicatorData`.

### На проде (требует доступа)

- [ ] `ssh forecast@5.129.204.194` → `docker compose logs backend | tail -200 | grep -E "daily_update|ERROR"` — последние логи.
- [ ] `psql -U fcst -d forecast` → `SELECT code, MAX(date) FROM indicators i JOIN indicator_data d ON d.indicator_id = i.id GROUP BY code ORDER BY MAX(date) DESC;` — увидеть, что устарело.
- [ ] Проверить chat алерты в Telegram за последние 7 дней.

## Hypothesis: основная причина — операционная

Не баг в коде, а одно из:
- APScheduler упал после deploy (нужно пересмотреть deploy.sh: останавливает ли он scheduler корректно?).
- Источник заблокировал IP сервера (cbr.ru может фильтровать).
- Disk full → задача создаётся, но данные не пишутся → silently fails.

Это **операционная проблема**, не правится кодом. Решение:
1. Health-check эндпоинт `/api/v1/system/freshness` уже есть — возвращает freshness каждого индикатора. Нужно настроить **alert при freshness > 24h** (Telegram).
2. UptimeRobot / cronjob.org dejavu monitoring HTTP `/api/v1/system/freshness?max_lag_hours=24`.

## Текущее состояние

- ⚠ **Не воспроизведено локально** — в этой итерации диагностика только на уровне кода.
- 🔵 **Документ создан** для последующего расследования.
- 🟡 **Действия на проде** — ждут разрешения пользователя зайти на сервер.

---

## История правок документа

- 2026-04-27 — создан как ответ на правку `v3/edit_006` НА правки 3.
