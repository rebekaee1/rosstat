# Indicator index — карта индикаторов

> Генерируется `scripts/build-indicator-index.py`. НЕ редактировать руками. Полная машинная версия — `docs/indicator-index.json`. Подробности по каждому коду (files/derived_siblings) — в JSON.

## Как пользоваться (для агента)

1. `python scripts/locate-indicator.py <code>` — где код вообще встречается.
2. Найди запись `<code>` в `docs/indicator-index.json`.
3. Правь стек из `ui_stack`. `flags.shadowed_legacy=true` — standalone-ветка рендера в `IndicatorDetail.jsx` перекрыта generic, НО bespoke content/resolve часто переиспользуются общими секциями + держат старые URL-редиректы → НЕ удалять вслепую (см. `dead-code-report.md`).

**ui_stack** определяется как реальный каскад `IndicatorDetail.jsx` (generic early-return проверяется первым):

| Стек | Где правится UI |
|------|-----------------|
| `generic` | `backend/app/data/view_model_families.py` → `viewModelFamilies.generated.json` → `GenericIndicatorView` |
| `cpi` | `frontend/src/lib/cpiViewMode*` + `CpiIndicatorControls` |
| `housing` | `frontend/src/lib/housingViewMode*` + `HousingIndicatorControls` |
| `ppi` | `frontend/src/lib/ppiViewMode*` + `PpiIndicatorControls` |
| `cbr-term` | `cbrTermSliceRate*` — рендер через generic + общие секции; content/resolve ЖИВЫЕ (chart/table title, picker) |
| `unemployment` | `unemploymentViewMode*` — рендер через generic + общие секции; canonical-редирект старых URL ЖИВОЙ |
| `variant` | `frontend/src/lib/indicatorVariants.js` + `VariantGroupPicker` |

## Сводка

- Всего кодов: **908**
- in_both_viewmode_systems (дубль легаси+generic): **14**
- shadowed_legacy (мёртвая легаси-ветка): **24**
- unresolved (нет ui_stack): **1**
- derived_not_seeded: **0**

По стекам: `cpi`=32, `generic`=863, `housing`=8, `null`=1, `ppi`=4

### Unresolved (ui_stack=null)

`wages-nominal-annual`

## Все индикаторы

| Код | Категория | Частота | Стек | Стратегия | Listed | Флаги |
|-----|-----------|---------|------|-----------|:------:|-------|
| `auto-loan-rate` | Ставки | monthly | `generic` | monthly_auto | ✓ | — |
| `auto-loan-rate-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `auto-loan-rate-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `auto-loan-rate-mom` | Финансы | monthly | `generic` | — | — | — |
| `auto-loan-rate-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `auto-loan-rate-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `birth-rate` | Население | annual | `generic` | — | ✓ | — |
| `birth-rate-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `births` | Население | annual | `generic` | — | ✓ | — |
| `births-index` | Население | annual | `generic` | derived_from_source | — | — |
| `births-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `brent` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `brent-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `brent-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `brent-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `brent-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `brent-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `brent-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `brent-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `brent-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `brent-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `brent-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `brent-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `brent-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `brent-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `btc-usd` | Валюты | daily | `generic` | — | ✓ | — |
| `btc-usd-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `btc-usd-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `btc-usd-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `btc-usd-avg-year` | Валюты | annual | `generic` | — | — | — |
| `btc-usd-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `btc-usd-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `btc-usd-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `btc-usd-eop-year` | Валюты | annual | `generic` | — | — | — |
| `btc-usd-mom` | Валюты | monthly | `generic` | — | — | — |
| `btc-usd-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `btc-usd-yoy` | Валюты | monthly | `generic` | — | — | — |
| `btc-usd-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `btc-usd-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `budget-deficit` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `budget-deficit-mom` | Бюджет | monthly | `generic` | — | — | — |
| `budget-deficit-qoq` | Бюджет | quarterly | `generic` | — | — | — |
| `budget-deficit-sum-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-deficit-sum-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-deficit-yoy` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-deficit-yoy-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-deficit-yoy-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-expenditure` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `budget-expenditure-mom` | Бюджет | monthly | `generic` | — | — | — |
| `budget-expenditure-qoq` | Бюджет | quarterly | `generic` | — | — | — |
| `budget-expenditure-sum-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-expenditure-sum-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-expenditure-yoy` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-expenditure-yoy-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-expenditure-yoy-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-revenue` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `budget-revenue-mom` | Бюджет | monthly | `generic` | — | — | — |
| `budget-revenue-qoq` | Бюджет | quarterly | `generic` | — | — | — |
| `budget-revenue-sum-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-revenue-sum-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-revenue-yoy` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-revenue-yoy-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-revenue-yoy-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `business-credit` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `business-credit-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `business-credit-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `business-credit-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `business-credit-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `business-credit-mom` | Финансы | monthly | `generic` | — | — | — |
| `business-credit-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `business-credit-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `business-credit-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `business-credit-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `capital-investment` | Бизнес | quarterly | `generic` | — | ✓ | — |
| `capital-investment-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `capital-investment-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `capital-investment-yoy` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `capital-investment-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `cny-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `cny-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `cny-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cny-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `cny-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `cny-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `cny-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cny-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `cny-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `cny-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `cny-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `cny-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `cny-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cny-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `coal` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `coal-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `coal-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `coal-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `coal-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `coal-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `coal-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `coal-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `coal-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `coal-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `coal-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `coal-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `coal-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `coal-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `construction-work` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `construction-work-mom` | Бизнес | monthly | `generic` | — | — | — |
| `construction-work-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `construction-work-sum-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `construction-work-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `construction-work-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `construction-work-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `construction-work-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `consumer-credit` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `consumer-credit-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `consumer-credit-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `consumer-credit-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `consumer-credit-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `consumer-credit-mom` | Финансы | monthly | `generic` | — | — | — |
| `consumer-credit-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `consumer-credit-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `consumer-credit-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `consumer-credit-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `copper` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `copper-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `copper-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `copper-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `copper-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `copper-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `copper-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `copper-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `copper-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `copper-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `copper-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `copper-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `copper-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `copper-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `corp-bond-index` | Индексы | daily | `generic` | — | ✓ | — |
| `corp-bond-index-avg-month` | Индексы | monthly | `generic` | — | — | — |
| `corp-bond-index-avg-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `corp-bond-index-avg-week` | Индексы | weekly | `generic` | — | — | — |
| `corp-bond-index-avg-year` | Индексы | annual | `generic` | — | — | — |
| `corp-bond-index-eop-month` | Индексы | monthly | `generic` | — | — | — |
| `corp-bond-index-eop-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `corp-bond-index-eop-week` | Индексы | weekly | `generic` | — | — | — |
| `corp-bond-index-eop-year` | Индексы | annual | `generic` | — | — | — |
| `corp-bond-index-mom` | Индексы | monthly | `generic` | — | — | — |
| `corp-bond-index-qoq` | Индексы | quarterly | `generic` | — | — | — |
| `corp-bond-index-yoy` | Индексы | monthly | `generic` | — | — | — |
| `corp-bond-index-yoy-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `corp-bond-index-yoy-year` | Индексы | annual | `generic` | — | — | — |
| `cpi` | Цены | monthly | `cpi` | cpi_combined | ✓ | — |
| `cpi-food` | Цены | monthly | `cpi` | cpi_combined | ✓ | — |
| `cpi-food-annual` | Цены | annual | `cpi` | derived_from_source | — | — |
| `cpi-food-period-monthly` | Цены | monthly | `cpi` | derived_from_source | — | — |
| `cpi-food-period-weekly` | Цены | weekly | `cpi` | derived_from_source | — | — |
| `cpi-food-qoq` | Цены | quarterly | `cpi` | derived_from_source | — | — |
| `cpi-food-quarterly` | Цены | quarterly | `cpi` | — | — | — |
| `cpi-food-yoy` | Цены | monthly | `cpi` | derived_from_source | — | — |
| `cpi-nonfood` | Цены | monthly | `cpi` | cpi_combined | ✓ | — |
| `cpi-nonfood-annual` | Цены | annual | `cpi` | derived_from_source | — | — |
| `cpi-nonfood-period-monthly` | Цены | monthly | `cpi` | derived_from_source | — | — |
| `cpi-nonfood-period-weekly` | Цены | weekly | `cpi` | derived_from_source | — | — |
| `cpi-nonfood-qoq` | Цены | quarterly | `cpi` | derived_from_source | — | — |
| `cpi-nonfood-quarterly` | Цены | quarterly | `cpi` | — | — | — |
| `cpi-nonfood-yoy` | Цены | monthly | `cpi` | derived_from_source | — | — |
| `cpi-period-monthly` | Цены | monthly | `cpi` | derived_from_source | — | — |
| `cpi-period-weekly` | Цены | weekly | `cpi` | derived_from_source | — | — |
| `cpi-qoq` | Цены | quarterly | `cpi` | derived_from_source | — | — |
| `cpi-services` | Цены | monthly | `cpi` | cpi_combined | ✓ | — |
| `cpi-services-annual` | Цены | annual | `cpi` | derived_from_source | — | — |
| `cpi-services-period-monthly` | Цены | monthly | `cpi` | derived_from_source | — | — |
| `cpi-services-period-weekly` | Цены | weekly | `cpi` | derived_from_source | — | — |
| `cpi-services-qoq` | Цены | quarterly | `cpi` | derived_from_source | — | — |
| `cpi-services-quarterly` | Цены | quarterly | `cpi` | — | — | — |
| `cpi-services-yoy` | Цены | monthly | `cpi` | derived_from_source | — | — |
| `cpi-yoy` | Цены | monthly | `cpi` | derived_from_source | — | — |
| `credit-rate-corp-1to3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-corp-1to3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-mom` | Ставки | monthly | `generic` | — | — | — |
| `credit-rate-corp-1to3y-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `credit-rate-corp-1to3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-corp-over3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-mom` | Ставки | monthly | `generic` | — | — | — |
| `credit-rate-corp-over3y-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `credit-rate-corp-over3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short` | Ставки | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `credit-rate-corp-short-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-mom` | Ставки | monthly | `generic` | — | — | — |
| `credit-rate-corp-short-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `credit-rate-corp-short-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-ind-1to3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-mom` | Ставки | monthly | `generic` | — | — | — |
| `credit-rate-ind-1to3y-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `credit-rate-ind-1to3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-ind-over3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-mom` | Ставки | monthly | `generic` | — | — | — |
| `credit-rate-ind-over3y-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `credit-rate-ind-over3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short` | Ставки | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `credit-rate-ind-short-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-mom` | Ставки | monthly | `generic` | — | — | — |
| `credit-rate-ind-short-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `credit-rate-ind-short-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `current-account` | Торговля | quarterly | `generic` | signed_quarterly | ✓ | both, shadowed |
| `current-account-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `current-account-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `current-account-yoy` | Торговля | quarterly | `generic` | — | — | — |
| `current-account-yoy-abs` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `current-account-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `death-rate` | Население | annual | `generic` | — | ✓ | — |
| `death-rate-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `deaths` | Население | annual | `generic` | — | ✓ | — |
| `deaths-index` | Демография | annual | `generic` | derived_from_source | — | — |
| `deaths-yoy` | Демография | annual | `generic` | derived_from_source | — | — |
| `deposit-rate` | Ставки | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `deposit-rate-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-long` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `deposit-rate-long-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-long-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-long-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-long-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-long-mom` | Ставки | monthly | `generic` | — | — | — |
| `deposit-rate-long-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `deposit-rate-long-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-long-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-long-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-medium` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `deposit-rate-medium-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-mom` | Ставки | monthly | `generic` | — | — | — |
| `deposit-rate-medium-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `deposit-rate-medium-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-mom` | Ставки | monthly | `generic` | — | — | — |
| `deposit-rate-qoq` | Ставки | quarterly | `generic` | — | — | — |
| `deposit-rate-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposits-business` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `deposits-business-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-business-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-business-mom` | Финансы | monthly | `generic` | — | — | — |
| `deposits-business-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `deposits-business-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-business-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-individual` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `deposits-individual-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-individual-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-individual-mom` | Финансы | monthly | `generic` | — | — | — |
| `deposits-individual-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `deposits-individual-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-individual-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `depreciation-rate` | Бизнес | annual | `generic` | — | ✓ | — |
| `depreciation-rate-yoy` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `doctoral-students` | Наука | annual | `generic` | — | ✓ | — |
| `doctoral-students-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `doctoral-students-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `employment` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `employment-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `employment-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `employment-mom` | Рынок труда | monthly | `generic` | — | — | — |
| `employment-qoq` | Рынок труда | quarterly | `generic` | — | — | — |
| `employment-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `employment-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `employment-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `eth-usd` | Валюты | daily | `generic` | — | ✓ | — |
| `eth-usd-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `eth-usd-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eth-usd-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `eth-usd-avg-year` | Валюты | annual | `generic` | — | — | — |
| `eth-usd-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `eth-usd-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eth-usd-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `eth-usd-eop-year` | Валюты | annual | `generic` | — | — | — |
| `eth-usd-mom` | Валюты | monthly | `generic` | — | — | — |
| `eth-usd-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `eth-usd-yoy` | Валюты | monthly | `generic` | — | — | — |
| `eth-usd-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eth-usd-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `eur-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `eur-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `eur-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eur-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `eur-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `eur-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `eur-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eur-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `eur-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `eur-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `eur-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `eur-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `eur-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eur-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `exports` | Торговля | quarterly | `generic` | generic_quarterly | ✓ | both, shadowed |
| `exports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `exports-monthly-mom` | Торговля | monthly | `generic` | — | — | — |
| `exports-monthly-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `exports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `exports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `exports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `exports-monthly-yoy-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `exports-monthly-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `exports-qoq` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `exports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `exports-yoy` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `exports-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `external-debt` | Финансы | quarterly | `generic` | generic_quarterly | ✓ | — |
| `external-debt-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `external-debt-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `external-debt-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `external-debt-yoy` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `external-debt-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `fdi-net` | Бизнес | quarterly | `generic` | — | ✓ | — |
| `fdi-net-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `fdi-net-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `fdi-net-yoy` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `fdi-net-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `fuel-ai92` | Цены | weekly | `generic` | — | ✓ | — |
| `fuel-ai92-avg-month` | Цены | monthly | `generic` | monthly_auto | — | — |
| `fuel-ai92-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `fuel-ai92-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `fuel-ai92-eop-month` | Цены | monthly | `generic` | — | — | — |
| `fuel-ai92-eop-quarter` | Цены | quarterly | `generic` | — | — | — |
| `fuel-ai92-eop-year` | Цены | annual | `generic` | — | — | — |
| `fuel-ai92-mom` | Цены | monthly | `generic` | — | — | — |
| `fuel-ai92-qoq` | Цены | quarterly | `generic` | — | — | — |
| `fuel-ai92-yoy` | Цены | monthly | `generic` | — | — | — |
| `fuel-ai92-yoy-quarter` | Цены | quarterly | `generic` | — | — | — |
| `fuel-ai92-yoy-year` | Цены | annual | `generic` | — | — | — |
| `fuel-ai95` | Цены | weekly | `generic` | — | — | — |
| `fuel-ai95-avg-month` | Цены | monthly | `generic` | monthly_auto | — | — |
| `fuel-ai95-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `fuel-ai95-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `fuel-ai95-eop-month` | Цены | monthly | `generic` | — | — | — |
| `fuel-ai95-eop-quarter` | Цены | quarterly | `generic` | — | — | — |
| `fuel-ai95-eop-year` | Цены | annual | `generic` | — | — | — |
| `fuel-ai95-mom` | Цены | monthly | `generic` | — | — | — |
| `fuel-ai95-qoq` | Цены | quarterly | `generic` | — | — | — |
| `fuel-ai95-yoy` | Цены | monthly | `generic` | — | — | — |
| `fuel-ai95-yoy-quarter` | Цены | quarterly | `generic` | — | — | — |
| `fuel-ai95-yoy-year` | Цены | annual | `generic` | — | — | — |
| `fuel-diesel` | Цены | weekly | `generic` | — | — | — |
| `fuel-diesel-avg-month` | Цены | monthly | `generic` | monthly_auto | — | — |
| `fuel-diesel-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `fuel-diesel-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `fuel-diesel-eop-month` | Цены | monthly | `generic` | — | — | — |
| `fuel-diesel-eop-quarter` | Цены | quarterly | `generic` | — | — | — |
| `fuel-diesel-eop-year` | Цены | annual | `generic` | — | — | — |
| `fuel-diesel-mom` | Цены | monthly | `generic` | — | — | — |
| `fuel-diesel-qoq` | Цены | quarterly | `generic` | — | — | — |
| `fuel-diesel-yoy` | Цены | monthly | `generic` | — | — | — |
| `fuel-diesel-yoy-quarter` | Цены | quarterly | `generic` | — | — | — |
| `fuel-diesel-yoy-year` | Цены | annual | `generic` | — | — | — |
| `gdp-consumption` | ВВП | quarterly | `generic` | gdp_consumption_quarterly | ✓ | — |
| `gdp-consumption-qoq` | ВВП | quarterly | `generic` | — | — | — |
| `gdp-consumption-sum-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-consumption-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-consumption-yoy-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-government` | ВВП | quarterly | `generic` | gdp_government_quarterly | ✓ | — |
| `gdp-government-qoq` | ВВП | quarterly | `generic` | — | — | — |
| `gdp-government-sum-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-government-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-government-yoy-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-investment` | ВВП | quarterly | `generic` | — | ✓ | — |
| `gdp-investment-qoq` | ВВП | quarterly | `generic` | — | — | — |
| `gdp-investment-sum-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-investment-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-investment-yoy-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-nominal` | ВВП | quarterly | `generic` | gdp_nominal_quarterly | ✓ | — |
| `gdp-nominal-annual` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-nominal-yoy-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-real` | ВВП | quarterly | `generic` | gdp_real_quarterly | ✓ | — |
| `gdp-real-annual` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-real-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-real-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-real-yoy-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gold-price` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `gold-price-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `gold-price-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `gold-price-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `gold-price-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `gold-price-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `gold-price-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `gold-price-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `gold-price-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `gold-price-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `gold-price-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `gold-price-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `gold-price-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `gold-price-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `grad-students` | Наука | annual | `generic` | — | ✓ | — |
| `grad-students-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `grad-students-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `housing-affordability` | Цены | monthly | `generic` | monthly_auto | ✓ | — |
| `housing-affordability-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-eop-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-eop-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-mom` | Цены | monthly | `generic` | — | — | — |
| `housing-affordability-primary` | Цены | monthly | `generic` | monthly_auto | — | — |
| `housing-affordability-primary-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-eop-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-eop-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-mom` | Цены | monthly | `generic` | — | — | — |
| `housing-affordability-primary-qoq` | Цены | quarterly | `generic` | — | — | — |
| `housing-affordability-primary-yoy` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-yoy-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-yoy-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-qoq` | Цены | quarterly | `generic` | — | — | — |
| `housing-affordability-yoy` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-yoy-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-yoy-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-annual-primary` | Цены | annual | `housing` | derived_from_source | — | — |
| `housing-annual-secondary` | Цены | annual | `housing` | derived_from_source | — | — |
| `housing-commissioned` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `housing-commissioned-mom` | Бизнес | monthly | `generic` | — | — | — |
| `housing-commissioned-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `housing-commissioned-sum-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `housing-commissioned-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `housing-commissioned-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `housing-commissioned-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `housing-commissioned-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `housing-price-primary` | Цены | quarterly | `housing` | housing_quarterly | ✓ | — |
| `housing-price-secondary` | Цены | quarterly | `housing` | housing_quarterly | ✓ | — |
| `housing-qoq-primary` | Цены | quarterly | `housing` | derived_from_source | — | — |
| `housing-qoq-secondary` | Цены | quarterly | `housing` | derived_from_source | — | — |
| `housing-yoy-primary` | Цены | quarterly | `housing` | derived_from_source | — | — |
| `housing-yoy-secondary` | Цены | quarterly | `housing` | derived_from_source | — | — |
| `imoex` | Индексы | daily | `generic` | — | ✓ | — |
| `imoex-avg-month` | Индексы | monthly | `generic` | — | — | — |
| `imoex-avg-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `imoex-avg-week` | Индексы | weekly | `generic` | — | — | — |
| `imoex-avg-year` | Индексы | annual | `generic` | — | — | — |
| `imoex-eop-month` | Индексы | monthly | `generic` | — | — | — |
| `imoex-eop-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `imoex-eop-week` | Индексы | weekly | `generic` | — | — | — |
| `imoex-eop-year` | Индексы | annual | `generic` | — | — | — |
| `imoex-mom` | Индексы | monthly | `generic` | — | — | — |
| `imoex-qoq` | Индексы | quarterly | `generic` | — | — | — |
| `imoex-yoy` | Индексы | monthly | `generic` | — | — | — |
| `imoex-yoy-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `imoex-yoy-year` | Индексы | annual | `generic` | — | — | — |
| `imports` | Торговля | quarterly | `generic` | generic_quarterly | ✓ | both, shadowed |
| `imports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `imports-monthly-mom` | Торговля | monthly | `generic` | — | — | — |
| `imports-monthly-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `imports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `imports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `imports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `imports-monthly-yoy-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `imports-monthly-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `imports-qoq` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `imports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `imports-yoy` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `imports-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `inflation-annual` | Цены | annual | `cpi` | derived_from_source | — | — |
| `inflation-quarterly` | Цены | quarterly | `cpi` | — | — | — |
| `inflation-weekly` | Цены | weekly | `cpi` | generic_ols | — | — |
| `inflation-weekly-food` | Цены | weekly | `cpi` | generic_ols | — | — |
| `inflation-weekly-nonfood` | Цены | weekly | `cpi` | generic_ols | — | — |
| `inflation-weekly-services` | Цены | weekly | `cpi` | generic_ols | — | — |
| `innovation-activity` | Наука | annual | `generic` | — | ✓ | — |
| `innovation-activity-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `international-reserves` | Финансы | weekly | `generic` | — | ✓ | — |
| `international-reserves-avg-month` | Финансы | monthly | `generic` | — | — | — |
| `international-reserves-avg-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `international-reserves-avg-year` | Финансы | annual | `generic` | — | — | — |
| `international-reserves-eop-month` | Финансы | monthly | `generic` | — | — | — |
| `international-reserves-eop-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `international-reserves-eop-year` | Финансы | annual | `generic` | — | — | — |
| `international-reserves-mom` | Финансы | monthly | `generic` | — | — | — |
| `international-reserves-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `international-reserves-yoy` | Финансы | monthly | `generic` | — | — | — |
| `international-reserves-yoy-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `international-reserves-yoy-year` | Финансы | annual | `generic` | — | — | — |
| `ipi` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `ipi-avg-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-avg-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-energy` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `ipi-energy-avg-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-energy-avg-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-energy-eop-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-energy-eop-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-energy-mom` | Бизнес | monthly | `generic` | — | — | — |
| `ipi-energy-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `ipi-energy-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-energy-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-energy-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-eop-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-eop-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-manufacturing` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `ipi-manufacturing-avg-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-avg-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-eop-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-eop-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-mom` | Бизнес | monthly | `generic` | — | — | — |
| `ipi-manufacturing-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `ipi-manufacturing-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mining` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `ipi-mining-avg-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-mining-avg-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mining-eop-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-mining-eop-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mining-mom` | Бизнес | monthly | `generic` | — | — | — |
| `ipi-mining-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `ipi-mining-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-mining-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-mining-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mom` | Бизнес | monthly | `generic` | — | — | — |
| `ipi-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `ipi-water` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `ipi-water-avg-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-water-avg-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-water-eop-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-water-eop-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-water-mom` | Бизнес | monthly | `generic` | — | — | — |
| `ipi-water-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `ipi-water-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-water-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-water-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `key-rate` | Ставки | daily | `generic` | — | ✓ | — |
| `key-rate-avg-month` | Финансы | monthly | `generic` | — | — | — |
| `key-rate-avg-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `key-rate-avg-week` | Финансы | weekly | `generic` | — | — | — |
| `key-rate-avg-year` | Финансы | annual | `generic` | — | — | — |
| `key-rate-eop-month` | Финансы | monthly | `generic` | — | — | — |
| `key-rate-eop-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `key-rate-eop-week` | Финансы | weekly | `generic` | — | — | — |
| `key-rate-eop-year` | Финансы | annual | `generic` | — | — | — |
| `key-rate-mom` | Финансы | monthly | `generic` | — | — | — |
| `key-rate-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `key-rate-yoy` | Финансы | monthly | `generic` | — | — | — |
| `key-rate-yoy-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `key-rate-yoy-year` | Финансы | annual | `generic` | — | — | — |
| `labor-force` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `labor-force-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `labor-force-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `labor-force-mom` | Рынок труда | monthly | `generic` | — | — | — |
| `labor-force-qoq` | Рынок труда | quarterly | `generic` | — | — | — |
| `labor-force-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `labor-force-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `labor-force-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `m0` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m0-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m0-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m0-mom` | Финансы | monthly | `generic` | — | — | — |
| `m0-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `m0-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m0-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m1` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m1-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m1-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m1-mom` | Финансы | monthly | `generic` | — | — | — |
| `m1-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `m1-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m1-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m2` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m2-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m2-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m2-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m2-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m2-mom` | Финансы | monthly | `generic` | — | — | — |
| `m2-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `m2-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m2-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m2-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `mcftr` | Индексы | daily | `generic` | — | ✓ | — |
| `mcftr-avg-month` | Индексы | monthly | `generic` | — | — | — |
| `mcftr-avg-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `mcftr-avg-week` | Индексы | weekly | `generic` | — | — | — |
| `mcftr-avg-year` | Индексы | annual | `generic` | — | — | — |
| `mcftr-eop-month` | Индексы | monthly | `generic` | — | — | — |
| `mcftr-eop-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `mcftr-eop-week` | Индексы | weekly | `generic` | — | — | — |
| `mcftr-eop-year` | Индексы | annual | `generic` | — | — | — |
| `mcftr-mom` | Индексы | monthly | `generic` | — | — | — |
| `mcftr-qoq` | Индексы | quarterly | `generic` | — | — | — |
| `mcftr-yoy` | Индексы | monthly | `generic` | — | — | — |
| `mcftr-yoy-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `mcftr-yoy-year` | Индексы | annual | `generic` | — | — | — |
| `mortgage-rate` | Ставки | monthly | `generic` | monthly_auto | ✓ | — |
| `mortgage-rate-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `mortgage-rate-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `mortgage-rate-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `mortgage-rate-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `mortgage-rate-mom` | Финансы | monthly | `generic` | — | — | — |
| `mortgage-rate-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `mortgage-rate-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `mortgage-rate-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `mortgage-rate-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `natural-gas` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `natural-gas-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `natural-gas-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `natural-gas-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `natural-gas-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `natural-gas-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `natural-gas-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `natural-gas-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `natural-gas-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `natural-gas-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `natural-gas-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `natural-gas-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `natural-gas-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `natural-gas-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `pensioners` | Население | annual | `generic` | — | ✓ | — |
| `pensioners-index` | Население | annual | `generic` | derived_from_source | — | — |
| `pensioners-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `pop-over-working-age` | Население | annual | `generic` | — | ✓ | — |
| `pop-over-working-age-index` | Население | annual | `generic` | derived_from_source | — | — |
| `pop-over-working-age-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `pop-under-working-age` | Население | annual | `generic` | — | ✓ | — |
| `pop-under-working-age-index` | Население | annual | `generic` | derived_from_source | — | — |
| `pop-under-working-age-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `population` | Население | annual | `generic` | — | ✓ | — |
| `population-index` | Население | annual | `generic` | derived_from_source | — | — |
| `population-migration` | Население | annual | `generic` | — | ✓ | — |
| `population-migration-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `population-natural-growth` | Население | annual | `generic` | — | ✓ | — |
| `population-natural-growth-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `population-total-growth` | Население | annual | `generic` | — | ✓ | — |
| `population-total-growth-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `population-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `ppi` | Цены | monthly | `ppi` | ppi_monthly | ✓ | — |
| `ppi-annual` | Цены | annual | `ppi` | derived_from_source | — | — |
| `ppi-qoq` | Цены | quarterly | `ppi` | derived_from_source | — | — |
| `ppi-yoy` | Цены | monthly | `ppi` | derived_from_source | — | — |
| `rd-organizations` | Наука | annual | `generic` | — | ✓ | — |
| `rd-organizations-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `rd-organizations-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `rd-personnel` | Наука | annual | `generic` | — | ✓ | — |
| `rd-personnel-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `rd-personnel-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `retail-trade` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `retail-trade-mom` | Бизнес | monthly | `generic` | — | — | — |
| `retail-trade-qoq` | Бизнес | quarterly | `generic` | — | — | — |
| `retail-trade-sum-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `retail-trade-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `retail-trade-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `retail-trade-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `retail-trade-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `rgbi` | Индексы | daily | `generic` | — | ✓ | — |
| `rgbi-avg-month` | Индексы | monthly | `generic` | — | — | — |
| `rgbi-avg-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `rgbi-avg-week` | Индексы | weekly | `generic` | — | — | — |
| `rgbi-avg-year` | Индексы | annual | `generic` | — | — | — |
| `rgbi-eop-month` | Индексы | monthly | `generic` | — | — | — |
| `rgbi-eop-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `rgbi-eop-week` | Индексы | weekly | `generic` | — | — | — |
| `rgbi-eop-year` | Индексы | annual | `generic` | — | — | — |
| `rgbi-mom` | Индексы | monthly | `generic` | — | — | — |
| `rgbi-qoq` | Индексы | quarterly | `generic` | — | — | — |
| `rgbi-yoy` | Индексы | monthly | `generic` | — | — | — |
| `rgbi-yoy-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `rgbi-yoy-year` | Индексы | annual | `generic` | — | — | — |
| `rtsi` | Индексы | daily | `generic` | — | ✓ | — |
| `rtsi-avg-month` | Индексы | monthly | `generic` | — | — | — |
| `rtsi-avg-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `rtsi-avg-week` | Индексы | weekly | `generic` | — | — | — |
| `rtsi-avg-year` | Индексы | annual | `generic` | — | — | — |
| `rtsi-eop-month` | Индексы | monthly | `generic` | — | — | — |
| `rtsi-eop-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `rtsi-eop-week` | Индексы | weekly | `generic` | — | — | — |
| `rtsi-eop-year` | Индексы | annual | `generic` | — | — | — |
| `rtsi-mom` | Индексы | monthly | `generic` | — | — | — |
| `rtsi-qoq` | Индексы | quarterly | `generic` | — | — | — |
| `rtsi-yoy` | Индексы | monthly | `generic` | — | — | — |
| `rtsi-yoy-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `rtsi-yoy-year` | Индексы | annual | `generic` | — | — | — |
| `ruonia` | Ставки | daily | `generic` | — | ✓ | — |
| `ruonia-avg-month` | Финансы | monthly | `generic` | — | — | — |
| `ruonia-avg-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `ruonia-avg-week` | Финансы | weekly | `generic` | — | — | — |
| `ruonia-avg-year` | Финансы | annual | `generic` | — | — | — |
| `ruonia-eop-month` | Финансы | monthly | `generic` | — | — | — |
| `ruonia-eop-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `ruonia-eop-week` | Финансы | weekly | `generic` | — | — | — |
| `ruonia-eop-year` | Финансы | annual | `generic` | — | — | — |
| `ruonia-mom` | Финансы | monthly | `generic` | — | — | — |
| `ruonia-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `ruonia-yoy` | Финансы | monthly | `generic` | — | — | — |
| `ruonia-yoy-quarter` | Финансы | quarterly | `generic` | — | — | — |
| `ruonia-yoy-year` | Финансы | annual | `generic` | — | — | — |
| `services-exports` | Торговля | quarterly | `generic` | — | ✓ | — |
| `services-exports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `services-exports-monthly-mom` | Торговля | monthly | `generic` | — | — | — |
| `services-exports-monthly-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `services-exports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-exports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-yoy-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-exports-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `services-exports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-exports-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports` | Торговля | quarterly | `generic` | — | ✓ | — |
| `services-imports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `services-imports-monthly-mom` | Торговля | monthly | `generic` | — | — | — |
| `services-imports-monthly-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `services-imports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-yoy-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `services-imports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `silver` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `silver-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `silver-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `silver-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `silver-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `silver-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `silver-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `silver-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `silver-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `silver-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `silver-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `silver-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `silver-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `silver-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `small-business-innovation` | Наука | annual | `generic` | — | ✓ | — |
| `small-business-innovation-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `sol-usd` | Валюты | daily | `generic` | — | ✓ | — |
| `sol-usd-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `sol-usd-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sol-usd-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `sol-usd-avg-year` | Валюты | annual | `generic` | — | — | — |
| `sol-usd-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `sol-usd-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sol-usd-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `sol-usd-eop-year` | Валюты | annual | `generic` | — | — | — |
| `sol-usd-mom` | Валюты | monthly | `generic` | — | — | — |
| `sol-usd-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `sol-usd-yoy` | Валюты | monthly | `generic` | — | — | — |
| `sol-usd-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sol-usd-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `soybean` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `soybean-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `soybean-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `soybean-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `soybean-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `soybean-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `soybean-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `soybean-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `soybean-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `soybean-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `soybean-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `soybean-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `soybean-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `soybean-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `steel` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `steel-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `steel-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `steel-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `steel-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `steel-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `steel-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `steel-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `steel-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `steel-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `steel-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `steel-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `steel-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `steel-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `tech-innovation-share` | Наука | annual | `generic` | — | ✓ | — |
| `tech-innovation-share-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `trade-balance` | Торговля | quarterly | `generic` | derived_from_source | ✓ | both, shadowed |
| `trade-balance-monthly` | Торговля | monthly | `generic` | monthly_auto | — | — |
| `trade-balance-monthly-mom` | Торговля | monthly | `generic` | — | — | — |
| `trade-balance-monthly-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `trade-balance-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-yoy-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `trade-balance-qoq` | Торговля | quarterly | `generic` | — | — | — |
| `trade-balance-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `trade-balance-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-yoy-abs` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `trade-balance-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `unemployment` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `unemployment-annual` | Рынок труда | monthly | `generic` | — | — | — |
| `unemployment-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `unemployment-eop-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-eop-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `unemployment-mom` | Рынок труда | monthly | `generic` | — | — | — |
| `unemployment-qoq` | Рынок труда | quarterly | `generic` | — | — | — |
| `unemployment-quarterly` | Рынок труда | quarterly | `generic` | — | — | — |
| `unemployment-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `unemployment-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `usd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `usd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `usd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `usd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `usd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `usd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `usd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `usd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `usd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `usd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `usd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `usd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `usd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `usd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `wages-index` | Рынок труда | monthly | `generic` | — | — | — |
| `wages-nominal` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `wages-nominal-annual` | Рынок труда | annual | `null` | — | — | no-stack |
| `wages-nominal-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-nominal-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `wages-nominal-mom` | Рынок труда | monthly | `generic` | — | — | — |
| `wages-nominal-qoq` | Рынок труда | quarterly | `generic` | — | — | — |
| `wages-nominal-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-nominal-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `wages-real` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `wages-real-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-real-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `wages-real-mom` | Рынок труда | monthly | `generic` | — | — | — |
| `wages-real-qoq` | Рынок труда | quarterly | `generic` | — | — | — |
| `wages-real-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `wages-real-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-real-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `wages-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `wheat` | Товарные рынки | daily | `generic` | — | ✓ | — |
| `wheat-avg-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `wheat-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `wheat-avg-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `wheat-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `wheat-eop-month` | Товарные рынки | monthly | `generic` | — | — | — |
| `wheat-eop-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `wheat-eop-week` | Товарные рынки | weekly | `generic` | — | — | — |
| `wheat-eop-year` | Товарные рынки | annual | `generic` | — | — | — |
| `wheat-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `wheat-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `wheat-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `wheat-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `wheat-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `working-age-population` | Население | annual | `generic` | — | ✓ | — |
| `working-age-population-index` | Население | annual | `generic` | derived_from_source | — | — |
| `working-age-population-yoy` | Население | annual | `generic` | derived_from_source | — | — |


# Аудит полноты семейств — паспорт полноты

> Генерируется `scripts/build-indicator-index.py` (модуль `scripts/completeness.py`). НЕ редактировать руками. Read-only аудит: пробел = КАНДИДАТ на добавление режима, не дефект — владелец решает, осмыслен ли он для природы ряда. Ожидания — таблица `MAXIMAL_BY_NATURE` в `completeness.py` (единая точка истины). Доменная модель — `CONTEXT.md::Матрица представлений`.

## Оси матрицы

- **Тип** (верх, эталон — переключатель ИПЦ): `value` Уровень/значение · `pop` К прошлому периоду · `yoy` К соотв. периоду пред. года · `index` Индекс
- **Частота** (низ): `day` дн · `week` нед · `month` мес · `quarter` кв · `year` год

Корней-семейств: **113** · с полной матрицей: **101** · с пробелами: **12**. Покрытие: {'bespoke': 7, 'bespoke-data': 4, 'generic': 101, 'orphan': 1}.

## Систематические пробелы по типам

Семьи одного типа делят матрицу. `shared_missing` — ячейки, которых нет НИ У ОДНОГО члена типа (системный пробел типа).

| тип | природа | нативная | членов | общий пробел (shared_missing) |
|---|---|---|---|---|
| bespoke-data/CPI-weekly | index | week | 4 | `index:month`, `index:quarter`, `index:year`, `pop:month`, `pop:quarter`, `pop:year`, `value:week`, `yoy:month`, `yoy:quarter`, `yoy:year` |
| bespoke/CPI | index | month | 4 | `yoy:quarter`, `yoy:year` |
| bespoke/HOUSING | index | quarter | 2 | `pop:year` |
| bespoke/PPI | index | month | 1 | `yoy:quarter`, `yoy:year` |
| generic/T1 | rate | day | 22 | — |
| generic/T10 | annual-count | year | 11 | — |
| generic/T10a | annual-signed | year | 9 | — |
| generic/T12 | ratio-index | month | 2 | — |
| generic/T2y | rate | month | 12 | — |
| generic/T3 | index | month | 5 | — |
| generic/T3 | stock | month | 7 | — |
| generic/T4 | stock | quarter | 1 | — |
| generic/T5 | stock | week | 4 | — |
| generic/T6 | flow | month | 10 | — |
| generic/T7 | signed-flow | month | 1 | — |
| generic/T8 | avg-level | month | 3 | — |
| generic/T8 | index | month | 1 | — |
| generic/T9 | gdp | quarter | 10 | — |
| generic/T9s | signed-flow | quarter | 3 | — |
| orphan/- | annual-count | year | 1 | `index:year`, `yoy:year` |

## Корни с пробелами матрицы

| код | покрытие | природа | нативная | score | missing | тексты | прогноз | seo |
|---|---|---|---|---|---|---|---|---|
| `inflation-weekly` | bespoke-data/CPI-weekly | index | week | 0.0 | `value:week`, `pop:month`, `pop:quarter`, `pop:year`, `yoy:month`, `yoy:quarter`, `yoy:year`, `index:month`, `index:quarter`, `index:year` | partial | yes | curated |
| `inflation-weekly-food` | bespoke-data/CPI-weekly | index | week | 0.0 | `value:week`, `pop:month`, `pop:quarter`, `pop:year`, `yoy:month`, `yoy:quarter`, `yoy:year`, `index:month`, `index:quarter`, `index:year` | partial | yes | curated |
| `inflation-weekly-nonfood` | bespoke-data/CPI-weekly | index | week | 0.0 | `value:week`, `pop:month`, `pop:quarter`, `pop:year`, `yoy:month`, `yoy:quarter`, `yoy:year`, `index:month`, `index:quarter`, `index:year` | partial | yes | curated |
| `inflation-weekly-services` | bespoke-data/CPI-weekly | index | week | 0.0 | `value:week`, `pop:month`, `pop:quarter`, `pop:year`, `yoy:month`, `yoy:quarter`, `yoy:year`, `index:month`, `index:quarter`, `index:year` | partial | yes | curated |
| `cpi` | bespoke/CPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | full | yes | curated |
| `cpi-food` | bespoke/CPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | partial | yes | curated |
| `cpi-nonfood` | bespoke/CPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | partial | yes | curated |
| `cpi-services` | bespoke/CPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | partial | yes | curated |
| `ppi` | bespoke/PPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | full | yes | curated |
| `wages-nominal-annual` | orphan/- | annual-count | year | 0.333 | `yoy:year`, `index:year` | partial | no | generic |
| `housing-price-primary` | bespoke/HOUSING | index | quarter | 0.857 | `pop:year` | full | yes | curated |
| `housing-price-secondary` | bespoke/HOUSING | index | quarter | 0.857 | `pop:year` | full | yes | curated |

## Измерения паспорта (агрегат)

- **Без полных текстов** (43): `birth-rate`, `births`, `cpi-food`, `cpi-nonfood`, `cpi-services`, `current-account`, `death-rate`, `deaths`, `deposit-rate`, `deposits-business`, `depreciation-rate`, `doctoral-students`, `exports`, `exports-monthly`, `fdi-net`, `grad-students`, `housing-commissioned`, `imports`, `imports-monthly`, `inflation-weekly`, `inflation-weekly-food`, `inflation-weekly-nonfood`, `inflation-weekly-services`, `innovation-activity`, `pensioners`, `pop-over-working-age`, `pop-under-working-age`, `population-migration`, `population-natural-growth`, `population-total-growth`, `rd-organizations`, `rd-personnel`, `retail-trade`, `services-exports`, `services-exports-monthly`, `services-imports`, `services-imports-monthly`, `small-business-innovation`, `tech-innovation-share`, `trade-balance`, `trade-balance-monthly`, `wages-nominal-annual`, `working-age-population`
- **Без прогноза** (4): `fuel-ai92`, `fuel-ai95`, `fuel-diesel`, `wages-nominal-annual`
- **SEO не curated** (10): `deposit-rate-long`, `deposit-rate-medium`, `exports-monthly`, `housing-affordability`, `housing-affordability-primary`, `imports-monthly`, `services-exports-monthly`, `services-imports-monthly`, `trade-balance-monthly`, `wages-nominal-annual`

