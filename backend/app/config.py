from pydantic_settings import BaseSettings
from pathlib import Path
from urllib.parse import urlparse


class Settings(BaseSettings):
    app_name: str = "Forecast Economy API"
    debug: bool = False

    # Публичный origin сайта (canonical, SSR, sitemap, robots Host, IndexNow, CORS).
    # Единая точка истины для домена; дефолт = текущий прод.
    public_base_url: str = "https://forecasteconomy.com"
    # Языковой сплит (ADR-0013 §F): apex = EN, ru. = RU.
    apex_locale_en: bool = False
    # Людей с IP RU/СНГ с английского apex уводим на ru. Ботов не редиректим.
    geo_locale_redirect_enabled: bool = False
    # Кто географически считается русской аудиторией для geo-редиректа.
    geo_ru_country_codes: str = (
        "RU,BY,KZ,UA,AM,AZ,GE,KG,TJ,TM,UZ,MD"
    )
    # Accept-Language не источник редиректа (VPN/браузер путали язык).
    browser_lang_redirect_enabled: bool = False
    browser_lang_min_quality: float = 0.6
    locale_preference_cookie: str = "fe_locale_pref"

    # Database
    database_url: str = "postgresql+asyncpg://rustats:rustats@localhost:5432/rustats"
    database_echo: bool = False
    # О-15: пул соединений per-process; бюджет см. комментарий в database.py.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 10
    db_statement_timeout_ms: int = 30_000
    db_idle_in_transaction_timeout_ms: int = 120_000
    # Отдельный пул аналитики (rollups / Pulse / BI / ClickHouse sync) —
    # не может забрать соединения у витрины (инцидент 2026-09-03).
    analytics_db_pool_size: int = 2
    analytics_db_max_overflow: int = 2
    analytics_db_pool_timeout: int = 15
    analytics_db_statement_timeout_ms: int = 60_000
    analytics_db_idle_in_transaction_timeout_ms: int = 120_000
    # Каталог статических sitemap (ночной job → nginx try_files).
    sitemap_dir: str = "/var/www/sitemaps"
    # Google Search Console: meta google-site-verification (пусто = не эмитить).
    google_site_verification: str = ""
    # Bing Webmaster meta msvalidate.01.
    bing_site_verification: str = ""
    # Bearer-токен Search Analytics API. Пусто = джоб не синхронизирует.
    gsc_access_token: str = ""
    # Аварийный гео-блок скрейпа (ISO через запятую). Пусто = выкл.
    # Основная защита — bind-cookie (scrape_bind_enabled): ферма крутит
    # страны, гео ловит только перечисленные.
    scrape_block_countries: str = ""
    # HMAC(IP-префикс, день) в cookie fe_bind. HTML и API с кукой чужого /24 → 403.
    scrape_bind_enabled: bool = True
    scrape_bind_secret: str = ""
    # Бан хостинговых ASN (не стран). Пустая ASN-база = fail-open.
    scrape_block_hosting: bool = True
    # JS-ворота: HTML без fe_bind — заглушка, кука после проверки ядер/WebGL.
    # Гидра 1 IP = 1 хит иначе забирает SSR с первого запроса.
    scrape_challenge_enabled: bool = True
    scrape_challenge_min_cores: int = 48

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
    # Late FRED pass: US market close ~16:00 ET ≈ 23:00 MSK (EDT). Evening
    # full ETL at 20:00 MSK is too early for same-day Treasury / EIA / Fed
    # points that land on FRED after the US afternoon. This pass is insurance
    # so the home market pulse shows the latest trading day overnight.
    scheduler_late_fred_hour: int = 23
    scheduler_late_fred_minute: int = 30
    ticker_pull_interval_seconds: int = 8
    # Eurostat world block — отдельный opt-in job. Eurostat-часть до двух
    # успешных shadow прогонов не меняет world_*; национальные паспорта
    # (world_national_core) пишут данные сразу и идут до длинной Eurostat-
    # очереди. Не смешивается с daily_update_job России.
    world_eurostat_ingest_enabled: bool = False
    world_eurostat_ingest_shadow: bool = True
    world_eurostat_ingest_hour: int = 2
    world_eurostat_ingest_minute: int = 20
    # Прогнозы world_* изолированы от российского pipeline и выключены до
    # локального backfill + проверки quality-gate отчёта.
    world_forecast_enabled: bool = False
    world_forecast_hour: int = 4
    world_forecast_minute: int = 20

    # Официальный график публикаций Росстата («План выпуска публикаций»,
    # Grafik_srochn_YYYY.docx): события date_confidence='official_explicit'
    # с полным provenance. Выключен до выката — включается одной переменной
    # CALENDAR_ROSSTAT_PLAN_ENABLED=true в .env.
    calendar_rosstat_plan_enabled: bool = False

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
    geoip_asn_db_path: str = "/app/geoip/dbip-asn-lite.mmdb"
    geoip_asn_download_url_template: str = (
        "https://download.db-ip.com/free/dbip-asn-lite-{yyyy}-{mm}.mmdb.gz"
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

    # Яндекс.Директ: расход кампаний (spend). Токен — только в prod .env.
    direct_api_token: str = ""
    # Яндекс.Партнёр (РСЯ): доход площадки (Partner Statistics). Не путать с Директом.
    yandex_partner_client_id: str = ""
    yandex_partner_client_secret: str = ""
    yandex_partner_token: str = ""

    # Forecast Analytics OS
    analytics_enabled: bool = False
    analytics_scheduler_enabled: bool = False
    analytics_scheduler_cron_hour: int = 7
    analytics_scheduler_cron_minute: int = 20
    analytics_api_token: str = ""
    # По умолчанию совпадает с public_base_url; отдельный override — если
    # аналитический crawl ходит на другой origin (стейджинг и т.п.).
    analytics_base_url: str = "https://forecasteconomy.com"
    analytics_allowed_counter_ids: str = "107136069"
    analytics_allowed_hosts: str = "forecasteconomy.com,ru.forecasteconomy.com"
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
    auth_cookie_domain: str = ""      # пусто = auto `.forecasteconomy.com` на проде, host-only на localhost
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
    # 2026-07-08: прод-IP российский, OpenRouter/Anthropic режут его на границе
    # Cloudflare (гео/санкционный комплаенс, не репутация конкретного IP —
    # подтверждено: тот же блок на api.openai.com/api.anthropic.com напрямую,
    # а Mistral/DeepSeek/Together с того же IP отвечают штатным 401). Пустая
    # строка = без прокси (для dev/других сред, где блока нет).
    openrouter_proxy_url: str = ""
    # Исходящий HTTP-прокси для ETL-парсеров (http_client ProxyFallbackSession).
    # Пусто = тот же URL, что openrouter_proxy_url. Отдельное поле — если для
    # Минфина/Росстата нужен другой egress (residential), чем для LLM.
    etl_http_proxy_url: str = ""
    # SOCKS (например host Tor): после direct и HTTP-прокси. Prod Docker →
    # socks5h://172.18.0.1:9050 (Tor SocksPort на gateway rosstat_default). Нужен PySocks.
    etl_socks_proxy_url: str = ""
    # Интерактивные кнопки бота (getUpdates-поллер каждые 30 с)
    telegram_poller_enabled: bool = False

    # Админ-BI (/admin/bi): comma-separated email'ы с доступом к дашборду.
    # Вход обычной сессией; email сверяется по способам входа пользователя.
    admin_emails: str = "admin_forecasteconomy@forecasteconomy.com"

    model_config = {"env_prefix": "RUSTATS_", "env_file": ".env", "extra": "ignore"}

    @property
    def public_origin(self) -> str:
        """Origin без завершающего слэша: https://forecasteconomy.com."""
        return self.public_base_url.rstrip("/")

    @property
    def public_host(self) -> str:
        """Hostname без схемы: forecasteconomy.com."""
        return urlparse(self.public_base_url).hostname or ""

    @property
    def webmaster_host_id(self) -> str:
        """host_id Яндекс.Вебмастера: схема через одно двоеточие + :443."""
        return self.webmaster_host_id_for(self.public_host)

    def webmaster_host_id_for(self, host: str) -> str:
        """host_id Вебмастера для произвольного хоста (apex или ``ru.``)."""
        h = (host or "").split(":", 1)[0].strip().lower().removeprefix("www.")
        return f"https:{h}:443"


settings = Settings()
