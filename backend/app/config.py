from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "Forecast Economy API"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://rustats:rustats@localhost:5432/rustats"
    database_echo: bool = False

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

    # Internal endpoints protection
    metrics_token: str = ""

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
    # Доп. получатели дайджеста сверх primary (comma-separated chat_id). Realtime
    # сюда НЕ дублируется — только ежедневный дайджест в 9:00.
    telegram_digest_chat_ids: str = ""
    # Мгновенные уведомления (регистрации + обратная связь). false = тишина,
    # всё уходит только в ежедневный дайджест. ETL-алерты не затрагивает.
    telegram_realtime_alerts_enabled: bool = True

    # «Пульс» — дневные снапшоты активности + LLM-отчёт владельцу (П9б).
    # Получатель ТОЛЬКО владелец (pulse_chat_id), не digest-рассылка.
    pulse_enabled: bool = False
    pulse_chat_id: str = ""
    pulse_report_cron_hour: int = 9
    pulse_report_cron_minute: int = 5
    # LLM-фильтр отчёта через OpenRouter; пустой ключ = детерминированный fallback.
    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-sonnet-5"
    # Интерактивные кнопки бота (getUpdates-поллер каждые 30 с)
    telegram_poller_enabled: bool = False

    model_config = {"env_prefix": "RUSTATS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
