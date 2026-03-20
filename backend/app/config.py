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

    # ЦБ РФ / Минфин (зарезервировано для парсеров Фазы 2+)
    cbr_base_url: str = "https://www.cbr.ru"
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

    # OLS forecast defaults
    forecast_steps: int = 12

    model_config = {"env_prefix": "RUSTATS_", "env_file": ".env"}


settings = Settings()
