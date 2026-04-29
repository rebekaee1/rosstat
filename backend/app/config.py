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

    # Alerting
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Forecast defaults
    forecast_steps: int = 12

    # SEO HTML rendering
    seo_app_shell_url: str = "http://frontend/__spa-index.html"

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

    model_config = {"env_prefix": "RUSTATS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
