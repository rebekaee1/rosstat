# IndexNow: медленная подача каталога из sitemap → очередь

**Статус:** черновик для SEO GO / NO-GO · **код на прод НЕ включаем** · **потолок 30k/UTC-день НЕ поднимаем**  
**Дата черновика:** 2026-09-25 (MSK)  
**Репозиторий:** `ForecastEconomy` (`backend/app/services/indexnow.py`, `backend/scripts/indexnow-ping-all.py`)

---

## 0. Пять жёстких ограничений SEO (встроены в дизайн)

| # | Ограничение | Как соблюдаем |
|---|-------------|----------------|
| 1 | **ETL важнее backfill** | Свежие URL после ETL (`ping_updated_indicators`) всегда имеют право попасть в очередь. Backfill **паузится**, пока backlog высокий или суточный остаток квоты ниже резерва ETL. Очередь Redis — `SET` без приоритетов → единственная защита ETL = **не раздувать очередь** backfill’ом. |
| 2 | **≤30k URL / UTC-день GLOBAL** | Счётчик `in:daily-send:global:YYYYMMDD`, потолок кода `_DAILY_SEND_CAP_MAX = 30_000`. Shared EN+RU. Не поднимаем `indexnow_daily_send_cap`, не обходим `reserve_daily_send_quota`. |
| 3 | **Per-host + dedupe** | Очереди `in:queue:{host}`; debounce `in:sent:{host}:{path}` (TTL 24ч). Enqueue только path; отдельно для `forecasteconomy.com` и `ru.forecasteconomy.com`. Перед `SADD` — skip если уже в очереди или в `in:sent:*`. |
| 4 | **Sitemap = primary discovery** | Источник каталога = тот же реестр, что публикует sitemap (`site_urls` / шарды `/sitemap-*.xml`). IndexNow = только «обновление/уведомление», не замена sitemap для discovery миллионов URL. |
| 5 | **Метрики без обещаний индексации** | Логи/админка: `queued`, `skipped_dedupe`, `sent_200/202`, `429`, `daily_used/remaining`, `cursor`, `backed_up`. **Запрещено** формулировать как «проиндексировано N». IndexNow ≠ гарантия попадания в выдачу. |

---

## 1. Факты прода (as-of запрос CEO, redis-state)

- Очереди (SET): `in:queue:forecasteconomy.com` ≈ **35 759**, `in:queue:ru.forecasteconomy.com` ≈ **35 757**
- Сегодня UTC daily already **30 000**; вчера **19 200**
- Drain: cron `*/10` мин × до **800** URL (`_QUEUE_BATCH`), fair-share между хостами, стоп при исчерпании global cap
- Живой sitemap index (EN и RU): **~1002** шарда каждый
- Оценка каталога: **~1,64M URL / хост** (`docs/site-inventory.json` → `sitemap_urls`; крупные шарды `*-years-*` по 10k URL)
- Dual-host полный проход ≈ **3,28M** «send-единиц» (один path × 2 хоста)

**Сейчас:** суточная квота уже выбрана → drain ждёт следующего UTC-дня. При ~71k в очередях и 30k/день без нового enqueue: **~2,4 UTC-дня** до слива текущего хвоста.

---

## 2. Что уже есть в коде (не изобретать заново)

| Компонент | Роль | Файл |
|-----------|------|------|
| `enqueue_paths` / `drain_indexnow_queue` | очередь + debounce + global cap | `backend/app/services/indexnow.py` |
| `indexnow_drain_job` | `*/10` мин MSK | `backend/app/main.py` |
| `indexnow_warm_job` | вт 06:40 MSK — хабы + demand | то же |
| `indexnow_history_job` | ежедневно 04:30 MSK — **длинный хвост** через `site_urls` + cursor v3 | то же |
| `ping_updated_indicators` | ETL → очередь (приоритет продукта) | scheduler + indexnow |
| `indexnow-ping-all.py` | ручной/разовый POST (не для миллионов) | `backend/scripts/` |
| Settings | `indexnow_daily_send_cap=30000` (hard max), `indexnow_history_daily_cap=30000`, `indexnow_history_year_min=2018` | `backend/app/config.py` |

**Важно для GO:** history-джоба **уже зарегистрирована** при `indexnow_enabled`. Порогом `backed_up` она **не досыпает чанки**, пока `SCARD(queue) ≥ history_daily_cap` (сейчас очереди ~35k ≥ 30k → history должна быть на паузе). После слива ниже порога history снова может класть до 30k path/день **на каждый хост** → риск снова забить очередь и съесть квоту у ETL.

Поэтому SEO-GO = не «включить миллионы прямо сейчас», а **отдельный kill-switch + более жёсткий slow-feed** поверх существующей схемы.

---

## 3. Целевой дизайн (после слива текущей очереди)

### 3.1. Kill-switch (OFF by default)

Новый флаг (имя рабочее):

```text
indexnow_sitemap_backfill_enabled: bool = False
```

- **Не** трогаем `indexnow_enabled` (ETL + drain остаются).
- Backfill/history-хвост из каталога крутится **только** если флаг true **и** SEO дал GO **и** текущий backlog ниже порога.
- До GO: флаг false в env/проде; при необходимости временно снизить `indexnow_history_daily_cap` (enqueue), **не** send-cap.

### 3.2. Обход каталога без миллионов в RAM

**Рекомендуемый primary (совпадает с sitemap):**  
итерация секций `site_urls.section_names(db)` + `resolve_section` **по одному чанку**, cursor уже есть (`in:history:cursor`, version 3, families × phase × skip).

Алгоритм дня:

1. Lock `in:history:lock` (как сейчас).
2. Если `not indexnow_sitemap_backfill_enabled` → exit.
3. Если любой `SCARD(in:queue:{host}) ≥ BACKLOG_PAUSE` (предложение: **8 000–10 000**, не 30k) → `backed_up`, exit (ETL дышит).
4. Если `daily_send_remaining() < ETL_RESERVE` (предложение: **3 000–5 000**) → exit (квота на свежие пинги).
5. Бюджет enqueue на день:  
   `min(backfill_daily_enqueue_cap, room_to_pause_threshold, rough_remaining_after_reserve)`  
   Предложение стартового enqueue-cap: **5 000–10 000 path/UTC-день** (не 30k), ×2 хоста осторожно считать как нагрузку на drain.
6. Для каждого path перед `SADD`:  
   - skip if `SISMEMBER in:queue:{host} path`  
   - skip if `EXISTS in:sent:{host}:{path}`  
   - (опционально позже) отдельный long-term `in:catalog-pinged:{host}` с длинным TTL — **не в v1**.
7. Dual-host: те же path в обе очереди (как сейчас при `apex_locale_en`), fair drain уже делит send-бюджет.

**Альтернатива / верификация:** стрим XML `sitemap.xml` → шарды через `iterparse`, без DOM. Нужен только если сверка «live XML ≠ site_urls». Для прода предпочтителен `site_urls` (тот же билдер, что ночная публикация sitemap) — меньше self-crawl и расхождений.

**Не делать:** `collect_all_paths` / загрузка всех секций в память; прямой `indexnow-ping-all.py --apply` по years-чанкам; обход cap.

### 3.3. Расписание

| Job | Когда | Поведение |
|-----|-------|-----------|
| Drain | `*/10` (как сейчас) | единственный отправитель в IndexNow endpoint |
| ETL enqueue | после daily ETL | всегда (если indexnow_enabled) |
| Warm | вт 06:40 | хабы + demand; оставить, объём мал |
| Sitemap backfill | ежедневно (reuse 04:30 MSK history или 05:00) | только при флаге ON + backlog low + reserve OK |

Пауза intra-day: каждый backfill tick проверяет backlog/remaining; при росте очереди — стоп до следующего запуска / UTC-дня.

Resume next UTC day: автоматически — ключ `in:daily-send:global:YYYYMMDD` меняется в полночь UTC; cursor в Redis сохраняется.

### 3.4. Приоритет ETL (операционно)

1. Backfill **не** шлёт HTTP сам — только enqueue.
2. Порог backlog низкий → ETL URL уходит за часы, не за дни.
3. Резерв квоты в v1 = **не enqueue’ить**, когда `daily_send_remaining` мал (отдельный Redis-reserve не обязателен).
4. Future (после GO, отдельный тикет): `in:queue:prio:` / `in:queue:bulk:` — **не блокирует текущий GO**.

---

## 4. ETA (порядок величины)

Исходные:

- ~**1,64M** URL / хост × **2** хоста ≈ **3,28M** send-единиц полного каталога  
- Cap **30 000**/UTC-день shared  
- Текущий хвост очередей ≈ **2,4** UTC-дня до «пустого» (если не enqueue’ить)

| Режим backfill (после GO) | Эффективный send на каталог | Полный dual-host каталог |
|---------------------------|-----------------------------|---------------------------|
| 100% квоты на backfill (плохо для ETL) | 30k/день | ~**109 дней (~3,6 мес)** |
| ~20k/день backfill + ~10k запас ETL | 20k/день | ~**164 дня (~5,5 мес)** |
| ~15k/день (консервативно) | 15k/день | ~**219 дней (~7 мес)** |
| Старт 5–10k enqueue/день | ещё медленнее | **8–12+ мес** — ок для «slow», безопаснее для 429/ETL |

Порядок обхода (уже в history v3): сначала «свежие» годы (`year >= indexnow_history_year_min`, default 2018), потом legacy; семьи чанков пропорционально объёму (`chunk_item_counts`).

**Повторный цикл:** history после полного прохода отдыхает `_HISTORY_RESTART_DAYS = 14`. После первого полного круга backfill — **оставить отдых** или увеличить; не крутить каталог непрерывно.

---

## 5. Риски и контрмеры

| Риск | Почему | Контрмера |
|------|--------|-----------|
| **429** | Слишком крупные/частые POST | Не поднимать cap; batch drain 800; уважать Retry-After (уже есть); backfill не POST’ит напрямую |
| **Дубли пингов** | SET + 24h debounce; history может снова положить path | Skip `in:sent` + `SISMEMBER` на enqueue; не завышать enqueue-cap |
| **Starve ETL** | Очередь SET без приоритета, 70k backlog | `BACKLOG_PAUSE` ~8–10k; флаг OFF до слива; резерв remaining |
| **Раздвоение EN/RU квоты** | 1 path × 2 host = 2 send | ETA и капы считать в send-единицах; fair drain уже есть |
| **Self-DDoS sitemap HTTP** | Миллионы fetch XML с собственных хостов | Primary = `site_urls`, не live crawl |
| **Ложные SEO-обещания** | «Проиндексировали каталог» | Только метрики отправки/очереди; индекс — Вебмастер/GSC отдельно |
| **Ручной ping-all** | Обходит очередь, жжёт квоту | Запрет на years-чанки без SEO; dry-run default |

---

## 6. Метрики для отчёта SEO (без indexing promises)

Минимум в логах / redis ops snapshot:

- `in:daily-send:global:YYYYMMDD` used / cap / remaining  
- `SCARD in:queue:{host}` по хостам  
- backfill: `queued`, `skipped_queued`, `skipped_sent`, `backed_up`, `cursor phase/families`  
- drain: `sent`, `requeued_on_fail`, count `429`  
- ETL: число path от `ping_updated_indicators` за сутки (если легко)  

Формулировки OK: «отправлено в IndexNow N URL», «в очереди M», «квота исчерпана».  
Формулировки NO: «проиндексировано», «Яндекс принял в поиск», «охват каталога в выдаче».

---

## 7. План внедрения (после SEO GO) — поэтапно

**Сейчас (до GO):**  
- ❌ не enable, не force, не enqueue миллионов  
- ❌ не трогать prod IndexNow / не поднимать ceiling  
- ✅ дождаться слива текущих ~71k (или пока SCARD стабильно < BACKLOG_PAUSE)  
- ✅ этот документ = база для финального GO/NO-GO  

**Если SEO GO:**  
1. Ветка: флаг `indexnow_sitemap_backfill_enabled=False` + снижение эффективного enqueue (history cap или отдельный `indexnow_backfill_enqueue_cap`) + skip dedupe на enqueue + более низкий `BACKLOG_PAUSE`.  
2. Тесты: cap 30k hard; dual-host share; backed_up; flag off ⇒ zero enqueue from backfill; ETL enqueue всё ещё работает.  
3. Deploy с флагом **false**.  
4. SEO/CEO ручной ON на одно UTC-утро, наблюдение 48ч (429, backlog, ETL freshness).  
5. Только потом поднять enqueue-cap осторожно (5k→10k→…).  

**Если SEO NO-GO:**  
- Оставить только ETL + warm + drain; history держать выключенной отдельным флагом или `history_daily_cap=0`.

---

## 8. Чеклист SEO GO / NO-GO

**GO только если все да:**

- [ ] Текущие очереди слиты / стабильно ниже порога паузы  
- [ ] Согласован резерв ETL (3–5k remaining или эквивалент backlog policy)  
- [ ] Согласован стартовый enqueue ≤10k path/день (не 30k)  
- [ ] Kill-switch default false, включение только руками после deploy  
- [ ] Потолок send 30k/UTC global без изменений  
- [ ] Отчётность = send/queue метрики, без обещаний индексации  
- [ ] Понимание ETA: полный dual-host каталог = **месяцы**, не дни  

**NO-GO если:** нужны «проиндексировать всё за недели», желание поднять cap, включение до слива очереди, прямой HTTP ping миллионов.

---

## 9. Рекомендация исполнителя

1. **Сейчас:** план готов; **код на main/prod не включали**; ждать SEO final GO.  
2. После слива очереди + GO — минимальный dormant PR (флаг false): ужесточить history/backfill, dedupe на enqueue, низкий backlog pause.  
3. Cloud Agent не использовать (usage-blocked); правки на Mac по GO.

**Next step = wait SEO GO.**
