# ADR-0007 — Identity и личный кабинет (Phase 1)

- **Status:** Accepted
- **Date:** 2026-06-19
- **Last verified:** 2026-09-02 (прод: Яндекс ID живой; VK ID кабинет принимает только `/api/auth/vk/callback` без `/v1`).
- **Part of:** [`AGENTS.md`](../../AGENTS.md), [`CONTEXT.md`](../../CONTEXT.md), [`ADR-0003`](0003-seo-single-source-server-rendered.md).
- **Контекст:** звонок-стратегия + грилл 2026-06-19. Личный кабинет как фундамент идентичности (lead-gen), от которого позже зависят монетизация, рассылки, download-gate.

---

## Контекст

Сайт `forecasteconomy.com` до сих пор полностью анонимный (ADR-0003: весь публичный контент — для `Visitor`, без wall'ов, ради SEO). Бизнес-задача: ввести **личный кабинет** как фундамент для будущей монетизации/ретеншна. Phase 1 — только идентичность (регистрация, вход, кабинет, управление способами входа, 152-ФЗ-минимум), локально, всё E2E. Почты на Phase 1 нет (нет подтверждения email, сброса пароля, рассылок) — это Phase 2.

Требования, формирующие решение:
1. SEO нельзя ломать: публичные эндпоинты и SSR остаются анонимными; auth-кука не должна варьировать публичный кэш.
2. Несколько способов входа (Яндекс ID, VK ID, email+пароль) должны резолвиться в одного `User` без pre-hijack.
3. 152-ФЗ: явное согласие, право на удаление и экспорт ПДн.

---

## Решение

### Доменная модель

- **`User`** — UUID PK (не enumerable), без колонки email. Сущность появляется только после первого входа.
- **`OAuthIdentity`** — `(provider, provider_user_id)` UNIQUE; email — атрибут привязки, `email_verified=true` (провайдер подтвердил).
- **`EmailCredential`** — `email` UNIQUE (нормализованный lower+trim), `password_hash` (argon2id), `email_verified=false` на Phase 1.
- **`Consent`** — event-log согласий на обработку ПДн, версионируется датой редакции политики.
- **`AuthAudit`** — события (register/login/link/unlink/delete/logout_all) с ip/ua.

Все FK `user_id → users.id` с `ondelete=CASCADE`. Тип id — SQLAlchemy `Uuid` с Python-side `default=uuid.uuid4` (portable, без pgcrypto/`gen_random_uuid()`). Времена — наивный UTC (конвенция всей схемы). Alembic-ревизия `20260619_identity` (down_revision `20260510_calendar_official`).

### Резолв идентичности (инвариант против pre-hijack)

Ключ OAuth — `(provider, provider_user_id)` (sub), **никогда не email**. Автосвязывание разных способов в один `User` — только когда **оба email верифицированы и равны**. Неверифицированный парольный аккаунт никогда не мерджится автоматически. Кросс-способ связывание — вручную из кабинета под активной сессией. Это закрывает атаку «занять email жертвы паролем без подтверждения, чтобы перехватить её будущий OAuth-вход».

### Сессии

Opaque 256-bit id в httpOnly+Secure+SameSite=Lax cookie `fe_sess`; значение сессии (user_id, csrf_token) — в Redis `fe:sess:{id}` (TTL sliding 30д); индекс-Set `fe:user_sessions:{uid}` для logout-all и purge при удалении. На каждый успешный вход минтим новый id (анти-fixation). Сессии не в Postgres.

### OAuth — без Authlib

OAuth2 authorization-code + PKCE (S256) реализован вручную на `httpx`. Authlib не используется: его high-level starlette-клиент держит state/PKCE в session-cookie или framework-cache, чистого Redis-свапа нет (authlib#866) — конфликт с «state в Redis». Провайдеры — реестр в стиле `PARSER_REGISTRY` (`fake`/`yandex`/`vk`). Транзит OAuth (state→{code_verifier, intent, provider, next}) в Redis (TTL 10 мин) + короткоживущая cookie `fe_oauth` (SameSite=Lax) для привязки к браузеру (login-CSRF). Callback — чистый backend-эндпоинт (302), без HTML/JS (требование VK ID: встроенный контент утекает код через Referer).

### CSRF

Double-submit: cookie `XSRF-TOKEN` (не httpOnly, читается JS) + заголовок `X-XSRF-TOKEN` на всех мутациях. Same-origin (Vite-proxy локально, nginx на проде) + SameSite=Lax — основная линия; double-submit — defense-in-depth.

---

## Инварианты

- **Нет глобальной уникальности `User.email`** — email живёт на способе входа.
- **Публичный кэш не варьировать по auth-куке** — публичные эндпоинты/SSR сессию не читают, иначе общий Redis-кэш дробится по юзерам и убивает SEO (ADR-0003).
- **Fake-провайдер выключен в проде** — `auth_fake_provider_enabled=false`; на старте backend assert.
- **Lockout login → 423 Locked** (не 429): фронтовый axios-интерсептор ретраит 429/503, что повторно зашлёт креды.
- **152-ФЗ:** явное (не пред-отмеченное) согласие при регистрации; `DELETE /account` чистит Postgres каскадом + Redis (`fe:user_sessions:{uid}`, `fe:login_fail:*`); `GET /account/export` отдаёт ПДн в JSON.

---

## Скоуп прода (pre-prod чеклист)

- Реальные Яндекс/VK-приложения с прод-redirect, креды в env (`RUSTATS_OAUTH_*`).
- `RUSTATS_AUTH_FAKE_PROVIDER_ENABLED=false`, `RUSTATS_AUTH_COOKIE_SECURE=true`.
- `alembic upgrade head` на проде.
- Финал текстов Privacy/Terms; согласие 152-ФЗ обязательно до запуска.
- Деплой — отдельной командой пользователя (регламент `docs/workflow.md`).

---

## Отложено в Phase 2+

Почтовый провайдер (за `NotificationChannel`), double-opt-in + сброс пароля + подтверждение email, download-gate (домен Export), подписки/рассылки (домен Notifications), монетизация/entitlements.

## Subsequent additions (after acceptance)

### 2026-06-19 — Phase 2 (UX, гейт скачиваний, телефоны, аналитика-бот)

- **Download-gate (домен Export).** Генерация Excel/CSV перенесена с клиента на backend (`app/api/export.py`, `POST /export/table`): убирает ~430 КБ `xlsx` из бандла и даёт жёсткий конверсионный гейт. Гость — `download_anon_limit` (по умолчанию 2) выгрузок на «сессию скачиваний» (opaque cookie `fe_dl` + счётчик `fe:dl:{id}` в Redis, TTL `download_anon_window_seconds`); авторизованный (валидная сессия) — безлимит, счётчик не трогаем. Это не security-граница (данные публичны через API), а UX-гейт. При превышении — 403 `{code: "download_limit"}`, фронт ловит и показывает модалку регистрации.
- **Телефон в `OAuthIdentity.phone`** (миграция `20260619_oauth_phone`). Канал рассылки наряду с email. Яндекс — `default_phone.number` (только при scope `login:default_phone`), VK — `phone` (только при scope `phone`); scope конфигурируем (`oauth_*_scope`), по умолчанию без телефона, чтобы не падал authorize у приложений без разрешения. Email-регистрация телефон не собирает.
- **Согласия.** Кроме `kind="pd"` (ПДн) при регистрации пишем опциональный `kind="newsletter"` (информационная рассылка email/телефон). Чекбокс рассылки в `Register.jsx` (предотмечен, добровольный, не блокирует регистрацию).
- **`GET /api/v1/auth/oauth/providers`** — список включённых публичных провайдеров; фронт (`OAuthButtons.jsx`) скрывает несконфигурированные кнопки. Брендовые кнопки в цветах Яндекс (#FC3F1D) и VK (#0077FF).
- **Redirect override.** `oauth_{yandex,vk}_redirect_uri` — полный override `redirect_uri`, если в кабинете провайдера зарегистрирован нестандартный путь/порт. Плюс compat-роутер `app-level /api/auth/{provider}/{start,callback}` (без `/v1`) для совпадения с такими кабинетами.
- **Telegram-бот (домен Notifications, частично).** Переиспользует `alerting.send_telegram`. `notify_new_user` — мгновенное уведомление о регистрации (способ входа, email/телефон, имя, рассылка, IP, UA, id), вызывается в `register` и oauth-callback (только при `created=True`; `resolve_oauth` теперь возвращает `(user, created)`). Ежедневный дайджест `telegram_daily_digest_job` (cron `telegram_digest_*`, флаг `telegram_digest_enabled`): статистика пользователей из БД + визиты/посетители + достижения всех целей счётчика Метрики (каждый CTA — цель). Цели-CTA заданы в `frontend/src/lib/track.js` (`signup`, `login_success`, `oauth_start`, `download_limit`, `register_nudge_*`, `header_*_click`, `newsletter_opt_in`) — чтобы попасть в дайджест, одноимённая цель должна существовать в счётчике Метрики.
- **Персистентность/бэкап.** Тома `postgres_data`/`redis_data` уже в compose. `scripts/pg-backup.sh` расширен: помимо полного custom-dump делает отдельный data-only SQL identity-таблиц (`users/email_credentials/oauth_identities/consents/auth_audit`, gzip) — подстраховка «пользователи не теряются». Восстановление документировано в шапке скрипта и `docs/workflow.md`.
- **UI.** Хедер: отдельный блок Войти/Регистрация (гость) / Кабинет (авторизован) с разделителем. Инлайн-поиск (`IndicatorSearch variant="inline"`) на Dashboard и CategoryPage (не на IndicatorDetail). Плавающее окно `RegisterNudge` (свёрнутая пилюля → раскрытие с бенефитами; «не показывать больше» в `localStorage`, скрыто для авторизованных и на /login,/register,/account). `Account.jsx` очищен от техжаргона.

### 2026-06-20 — Phase 2.2 (звонок с руководителем «на правки 11»)

- **OAuth-согласие до редиректа.** `OAuthButtons.jsx` больше не редиректит сразу: клик по Яндекс/VK открывает всплывающее окно с двумя чекбоксами — «ознакомлен с пользовательским соглашением + политикой» (обязателен, иначе «Продолжить» disabled) и «согласен на рассылку» (по умолчанию **включён**). Согласие пробрасывается параметром `newsletter=1` в `oauth_start`, хранится в state Redis; на callback при `created=True && intent=login` пишем `Consent(pd)` + опц. `Consent(newsletter)`. Закрывает требование явного согласия для OAuth-входа (раньше фиксировался только для email).
- **Подписка/отписка из кабинета.** `POST /auth/account/newsletter {subscribe}` (CSRF). Журнал согласий append-only: подписка пишет `Consent("newsletter")`, отписка — `Consent("newsletter_revoked")`; `serialize_user.newsletter` = «побеждает последняя запись по `granted_at`». Тоггл в `Account.jsx` рядом с обратной связью, мелким шрифтом.
- **Кабинет упрощён.** Убраны технические блоки «Вход в аккаунт» (привязки/отвязки) и «Пароль для входа по почте». Текст обратной связи переписан в позитивном ключе (просьба добавить данные вместо «не хватает данных»).
- **«Скачать мои данные» убрана из UI.** 152-ФЗ (ст. 14) даёт право на **доступ по запросу** (10 рабочих дней по email), не на self-service экспорт/переносимость (это GDPR ст. 20, неприменимо). Эндпоинт `GET /auth/account/export` сохранён для обработки запроса, но кнопки в кабинете нет; политика конфиденциальности уточнена. «Удалить аккаунт» (право на отзыв согласия/удаление) оставлена.
- **Хедер.** Убрана статус-плашка «Онлайн»; десктоп-поиск — pill «🔍 Поиск» (`IndicatorSearch variant="pill"`), мобильный поиск без изменений.
- **Гостевой лимит выгрузок 2 → 5** (`download_anon_limit`, compose default `:-5`).
- **Маркировка рекламы.** Маркировку «Реклама» (+ домен/erid рекламодателя) несёт сам креатив РСЯ — это зона ответственности рекламной системы в RTB. Свой оверлей-ярлык в `YandexRSY` **убран** (2026-06-24): floorAd имеет переменную высоту, и фиксированный элемент с захардкоженным `bottom` попадал в середину объявления; дубль был избыточен и ломал вёрстку.

### 2026-07-02 — Изоляция сессий от кэша + sliding cookie + «Пульс»

- **Trap «FLUSHDB разлогинивал всех» закрыт.** Сессии, lockout, гостевые квоты
  и OAuth-state переехали в отдельный Redis logical DB (`get_state_redis`,
  compose: `RUSTATS_STATE_REDIS_URL=…/1`; дефолт — DB кэша + 1). Деплойный
  `redis-cli -n 0 FLUSHDB` теперь чистит только кэш. `load_session` делает
  one-shot миграцию сессий, оставшихся в кэш-DB со времён до разделения, —
  живые пользователи не разлогинились и при самом переезде.
- **Sliding cookie.** Redis-TTL сессии продлевался на каждом запросе, а
  `max_age` куки был заморожен датой логина — активный пользователь «слетал»
  ровно через 30 дней. Теперь `GET /auth/me` (каждая загрузка SPA)
  переустанавливает `fe_sess`/`XSRF-TOKEN` с новым `max_age`.
- **Фронт.** `AuthProvider` ретраит транзиентные сбои `/me` (не-401, до 2 раз):
  секундная недоступность бэка при деплое больше не выглядит как разлогин.
- **«Пульс» (мониторинг).** `services/pulse.py` — дневной снапшот всего
  (пользователи, auth-аудит, события фронта, поиск/нулевые запросы, скачивания,
  ошибки, ETL, приток точек) в state-Redis с TTL 8 дней (самоочистка недельного
  окна); компактная память дня (ядро чисел + однострочная сводка, TTL 30 дней).
  `services/pulse_report.py` — ежедневный отчёт через OpenRouter
  (`openrouter_model`, деградация в детерминированный fallback без ключа) →
  Telegram владельцу (`pulse_chat_id`), оформление Bot API 7.10+
  (`<blockquote expandable>`); контекст LLM не растёт: полный снапшот только за
  отчётный день, прошлое — память. `services/telegram_bot.py` — getUpdates-поллер
  (30 с, offset в state-Redis) с inline-кнопками: таблица пользователей
  (+карточка-аналитика по каждому: identity, согласия, история входов),
  CSV-выгрузка sendDocument, пульс текущего дня. Отвечает только чату владельца.

### 2026-07-02 (вечер) — Атрибуция аудитории в first-party аналитике

- **Проблема.** События фронта (`frontend_events`) писали только хэш сессии —
  ни `user_id`, ни признака авторизации. Разрез «гость vs зарегистрированный»
  был невозможен ни в «Пульсе», ни в Метрике. Плюс приём событий висел за
  `analytics_enabled` (Метрика-OS); при `false` на проде first-party телеметрия
  не собиралась вообще — отсюда «метрика где-то сломалась».
- **Атрибуция на приёме.** `POST /analytics/events` резолвит сессионную куку
  `fe_sess` (эндпоинт не кэшируется — инвариант «не варьировать кэш по куке» не
  нарушается) и проставляет `frontend_events.user_id` + `authed`. Миграция
  `20260702_fe_audience` (аддитивная). Гость → `authed=false, user_id=NULL`.
- **Развязка от Метрика-OS.** Сбор гейтится собственным флагом
  `frontend_events_enabled` (по умолчанию **on**, compose
  `RUSTATS_FRONTEND_EVENTS_ENABLED=true`), а не `analytics_enabled`. Наша
  телеметрия пишется всегда, даже если внешняя интеграция с API Метрики off.
- **Метрика-сегментация.** `track.js` шлёт `authed` В КАЖДОЕ событие (goal-params)
  и вызывает `ym setUserID` + `ym userParams {authed, audience}` при резолве
  `/me` (`AuthProvider`). В интерфейсе Метрики сегмент «зарегистрированные» =
  визиты с `authed=1`.
- **Пульс.** Снапшот получил `events.by_audience`, `events.downloads_by_audience`,
  `audience.{authed_active, guest_sessions}`; отчёт/бот/карточка юзера показывают
  разрез. Карточка пользователя в боте дополнена first-party активностью
  (события, скачивания, топ индикаторов, последняя активность по `user_id`).
- **Цели Метрики.** `scripts/metrika-goals-audit.py` сверяет события фронта с
  целями счётчика (read-token) и создаёт недостающие JS-цели (`--create`,
  нужен write-token). 64 события без цели — список для владельца.

### 2026-09-02 — прод: VK ID `redirect_uri` байт-в-байт с кабинетом

Живой экран `id.vk.ru` для `client_id=54644188`: `error=invalid_request`,
`redirect_uri is missing or invalid`, в payload приложения `name: DELETED`.
Канонический путь `/api/v1/auth/oauth/vk/callback` кабинет **не** принимает.
Тот же authorize с `https://forecasteconomy.com/api/auth/vk/callback` открывает
форму «Вход в «forecasteconomy»». Compat-роутер это уже умеет; на проде нужен
override `RUSTATS_OAUTH_VK_REDIRECT_URI` (пустое значение снова шлёт `/v1`).
Яндекс ID: анонимная форма входа на `/v1` **не** значит, что Callback URL
совпал. После аккаунта кабинет отдаёт `400 redirect_uri не совпадает с
Callback URL`. Живой зарегистрированный URI — тот же compat-путь
`https://forecasteconomy.com/api/auth/yandex/callback`; override
`RUSTATS_OAUTH_YANDEX_REDIRECT_URI`. Cookie `fe_oauth` / сессия —
`Domain=.forecasteconomy.com`. Кабинеты Яндекс/VK не трогать без явной команды.

### 2026-09-06 — `fe_bind` не режет вход

`/login` и `/register` отдаёт nginx как SPA (`try_files /index.html`), без
FastAPI — `fe_bind` на этих URL не ставится. Старт OAuth, callback
(`/api/auth/{vk,yandex}/callback`), `/auth/me` и POST `/register` шли как
«API без куки» → 403 `Forbidden`. На форме это выглядело как «Аккаунт
недоступен»; после VK на мобильном callback часто приходил с другого /24
и снова 403. Живые кабинеты принимали `redirect_uri` (apex `/api/auth/…`).
`bind_decision` пропускает `/api/v1/auth/` и `/api/auth/` так же, как
телеметрию; ряды `/api/v1/indicators*` по-прежнему требуют куку.

### 2026-09-06 — VK ID базовый домен vs `ru.`

Живой экран `id.vk.ru` с телефона: «Error loading» / «The platform's
settings don't show this base domain». `redirect_uri` кабинета
(`https://forecasteconomy.com/api/auth/vk/callback`) совпал; authorize
с Referer `https://ru.forecasteconomy.com/register` остаётся на ошибке,
с Referer apex открывает форму. Документация VK ID: базовый домен без
ведущей точки не покрывает поддомены (для всех — `.forecasteconomy.com`).
Кабинет не трогаем. Старт VK с `ru.`/`www.` сначала 302 на тот же path
на хосте callback, затем на `id.vk.ru` — Referer уже apex. Гео `/api/`
не редиректит.
