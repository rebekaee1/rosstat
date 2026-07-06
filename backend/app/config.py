from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "Forecast Economy API"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://rustats:rustats@localhost:5432/rustats"
    database_echo: bool = False
    # О-15: пул соединений per-process; бюджет см. комментарий в database.py.
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    # Долгоживущее состояние (сессии/lockout/гостевые квоты) — отдельный DB,
    # чтобы деплойный FLUSHDB кэша не разлогинивал пользователей.
    # Пусто = redis_url c номером DB + 1.
    state_redis_url: str = ""
    cache_ttl_data: int = 3600      # 1 hour for historical data
    cache_ttl_meta: int = 300       # 5 min for metadata/indicators list

    # ЦБ РФ / Минфин (Фаза 2+)
    cbr_base_url: str = "https://www.cbr.ru"
    cbr_request_timeout: int = 90  # KeyRate HTML может быть большим
    minfin_base_url: str = "https://minfin.gov.ru"

    # Rosstat
    rosstat_base_url: str = "https://rosstat.gov.ru/storage/mediabank"
    rosstat_cpi_template: str = "ipc_mes_{mm}-{yyyy}.xlsx"
    rosstat_ca_cert: str = str(Path(__file__).parent.parent / "certs" / "russiantrustedca2024.pem")
    rosstat_max_months_back: int = 6
    rosstat_request_timeout: int = 30

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_cron_hour: int = 6
    scheduler_cron_minute: int = 0
    # Второй полный прогон ETL вечером: многие источники (Росстат, ЦБ, биржи)
    # публикуют данные в течение дня — утренний прогон их не застаёт.
    scheduler_evening_hour: int = 20
    scheduler_evening_minute: int = 0
    ticker_pull_interval_seconds: int = 8

    # Alerting
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Forecast defaults
    forecast_steps: int = 12

    # SEO HTML rendering
    seo_app_shell_url: str = "http://frontend/__spa-index.html"

    # IndexNow — мгновенное уведомление поисковиков (Яндекс/Bing) об
    # обновлённых URL после ETL. Key-файл: frontend/public/{key}.txt.
    indexnow_enabled: bool = True
    indexnow_key: str = "a7c41d92e85f4b06b3d8f17c29e6a504"
    indexnow_endpoint: str = "https://yandex.com/indexnow"

    # Автоподача переобхода Яндекс.Вебмастера: ежедневный дренаж квоты
    # (~150 URL/день) приоритетными страницами из site_urls-реестра.
    webmaster_recrawl_enabled: bool = True

    # Internal endpoints protection
    metrics_token: str = ""

    # First-party приём событий фронта (/analytics/events → frontend_events).
    # РАЗВЯЗАН с analytics_enabled (та — про интеграцию с API Метрики). Наша
    # собственная телеметрия, питающая «Пульс», должна писаться всегда, даже
    # если внешняя Метрика-интеграция выключена. Иначе на проде «ничего не
    # собирается» при analytics_enabled=false.
    frontend_events_enabled: bool = True

    # Поведенческий поток (behavior.js): pageview/click/move/dwell/copy батчами
    # на /analytics/behavior. Стратегия владельца (2026-07-03): сырьё НЕ удаляем,
    # копим накопительно под Big Data/ML (0 = хранить вечно). Ненулевое значение —
    # аварийный клапан, если диск начнёт заканчиваться.
    behavior_events_enabled: bool = True
    behavior_batch_max_events: int = 500
    behavior_raw_retention_days: int = 0

    # Гео по IP (DB-IP City Lite, CC-BY). Файл лежит в docker-томе geoip_data;
    # при отсутствии backend скачивает свежую месячную сборку в фоне при старте
    # (сайт стартует и без гео — колонки просто NULL до появления файла).
    geoip_db_path: str = "/app/geoip/dbip-city-lite.mmdb"
    geoip_download_url_template: str = (
        "https://download.db-ip.com/free/dbip-city-lite-{yyyy}-{mm}.mmdb.gz"
    )
    geoip_auto_download: bool = True

    # OLAP-слой ClickHouse: производная копия Postgres, синк каждые 15 минут.
    # Выключен по умолчанию (локальная разработка без CH-контейнера).
    clickhouse_enabled: bool = False
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_db: str = "analytics"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    # Яндекс.Директ: расходы кампаний (коннектор включается после токена).
    direct_api_token: str = ""

    # Forecast Analytics OS
    analytics_enabled: bool = False
    analytics_scheduler_enabled: bool = False
    analytics_scheduler_cron_hour: int = 7
    analytics_scheduler_cron_minute: int = 20
    analytics_api_token: str = ""
    analytics_base_url: str = "https://forecasteconomy.com"
    analytics_allowed_counter_ids: str = "107136069"
    analytics_allowed_hosts: str = "forecasteconomy.com"
    analytics_default_retention_days: int = 180
    analytics_raw_log_retention_days: int = 90
    analytics_backfill_days: int = 30
    analytics_request_timeout: int = 30
    analytics_live_writes_enabled: bool = False

    yandex_metrika_read_token: str = ""
    yandex_metrika_write_token: str = ""
    yandex_webmaster_token: str = ""

    # Identity / личный кабинет (Phase 1)
    auth_session_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 дней sliding
    auth_cookie_secure: bool = False  # на проде → true (HTTPS)
    auth_cookie_domain: str = ""      # пусто = host-only cookie
    auth_oauth_state_ttl_seconds: int = 600  # 10 мин на завершение OAuth
    auth_login_max_fails: int = 8     # порог lockout по (email,ip)
    auth_login_lockout_seconds: int = 900  # 15 мин блокировки
    # Fake-провайдер только для dev/test (на проде ОБЯЗАН быть false — assert на старте)
    auth_fake_provider_enabled: bool = False
    # Базовый внешний URL для построения OAuth redirect_uri (callback).
    auth_public_base_url: str = "http://localhost:5173"

    # OAuth — Яндекс ID
    oauth_yandex_client_id: str = ""
    oauth_yandex_client_secret: str = ""
    oauth_yandex_scope: str = ""  # пусто = дефолт провайдера (login:email login:info login:avatar)
    # OAuth — VK ID (public client + PKCE, секрет в обмене не участвует)
    oauth_vk_client_id: str = ""
    oauth_vk_client_secret: str = ""   # классический VK; для VK ID PKCE не требуется
    oauth_vk_service_key: str = ""      # сервисный ключ VK (server-to-server), опц.
    oauth_vk_scope: str = ""            # пусто = дефолт провайдера (email)
    # Полный override redirect_uri (если в кабинете провайдера зарегистрирован
    # нестандартный путь/порт). Пусто = строим из auth_public_base_url.
    oauth_yandex_redirect_uri: str = ""
    oauth_vk_redirect_uri: str = ""

    # Лимит скачиваний для гостей (без сессии). Авторизованные — безлимит.
    download_anon_limit: int = 0
    download_anon_window_seconds: int = 60 * 60 * 24  # окно сессии скачиваний
    # Глубина истории в гостевой выгрузке (лет от последней точки). Полный период
    # истории — бонус за регистрацию. 0 = без ограничения глубины. Авторизованные
    # всегда получают весь ряд.
    download_anon_history_years: int = 3

    # Telegram-дайджест (ежедневная агрегированная статистика Метрики + регистрации)
    telegram_digest_enabled: bool = False
    telegram_digest_cron_hour: int = 9
    telegram_digest_cron_minute: int = 0
    # Доп. получатели сверх primary (comma-separated chat_id, напр. skrakan).
    # Получают дайджест 9:00, пульс, регистрации и обратную связь (указание
    # владельца 2026-07-06). Технические алерты (ETL/5xx) — только primary.
    telegram_digest_chat_ids: str = ""
    # Мгновенные уведомления (регистрации + обратная связь). false = тишина,
    # всё уходит только в ежедневный дайджест. ETL-алерты не затрагивает.
    telegram_realtime_alerts_enabled: bool = True

    # «Пульс» — дневные снапшоты активности + LLM-отчёт (П9б).
    # Получатели: pulse_chat_id + все digest_recipients (с 2026-07-06).
    pulse_enabled: bool = False
    pulse_chat_id: str = ""
    pulse_report_cron_hour: int = 9
    pulse_report_cron_minute: int = 5
    # LLM-фильтр отчёта через OpenRouter; пустой ключ = детерминированный fallback.
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-5"
    # Интерактивные кнопки бота (getUpdates-поллер каждые 30 с)
    telegram_poller_enabled: bool = False

    # Админ-BI (/admin/bi): comma-separated email'ы с доступом к дашборду.
    # Вход обычной сессией; email сверяется по способам входа пользователя.
    admin_emails: str = "admin_forecasteconomy@forecasteconomy.com"

    model_config = {"env_prefix": "RUSTATS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
