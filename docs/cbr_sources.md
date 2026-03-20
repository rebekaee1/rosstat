# Источники Банка России (Фаза 2)

Все ряды подтягиваются **только** с официальных страниц и API ЦБ РФ (`cbr.ru`).

## Ключевая ставка (`key-rate`)

| Поле | Значение |
|------|----------|
| Страница | [Ключевая ставка Банка России](https://www.cbr.ru/hd_base/KeyRate/) |
| Метод | HTTP GET, форма `UniDbQuery` (диапазон дат) |
| Парсер | `cbr_keyrate_html` |
| Код | `app/services/cbr_keyrate.py`, `cbr_keyrate_parser.py` |

Первичное заполнение: с **2013-09-13** (полный ряд из базы). Повторные запуски ETL: окно **~150 дней** (новые даты добавляются через `ON CONFLICT DO NOTHING`).

Запуск вручную (из каталога `backend`, БД и Redis доступны):

```bash
PYTHONPATH=. python -c "import asyncio; from app.tasks.scheduler import run_etl_for_indicator; asyncio.run(run_etl_for_indicator('key-rate'))"
```

Или: `./scripts/etl-key-rate.sh` из корня репозитория.

### Миграция со старых БД

Если индикатор `key-rate` раньше имел неверный `parser_type` или в `indicator_data` попали чужие ряды, выполните очистку точек для этого индикатора и обновите метаданные (как в `seed_data.py`: `parser_type=cbr_keyrate_html`, `frequency=daily`, …), затем снова запустите ETL.
