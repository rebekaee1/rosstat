# Indicator index — карта индикаторов

> Генерируется `scripts/build-indicator-index.py`. НЕ редактировать руками. Полная машинная версия — `docs/indicator-index.json`. Подробности по каждому коду (files/derived_siblings) — в JSON.

## Как пользоваться (для агента)

1. `python scripts/locate-indicator.py <code>` — где код вообще встречается.
2. Найди запись `<code>` в `docs/indicator-index.json`.
3. Правь ТОЛЬКО стек из `ui_stack`. Если `flags.shadowed_legacy=true` — легаси-ветка МЁРТВАЯ (перекрыта generic early-return), правка там ни на что не влияет.

**ui_stack** определяется как реальный каскад `IndicatorDetail.jsx` (generic early-return проверяется первым):

| Стек | Где правится UI |
|------|-----------------|
| `generic` | `backend/app/data/view_model_families.py` → `viewModelFamilies.generated.json` → `GenericIndicatorView` |
| `cpi` | `frontend/src/lib/cpiViewMode*` + `CpiIndicatorControls` |
| `housing` | `frontend/src/lib/housingViewMode*` + `HousingIndicatorControls` |
| `ppi` | `frontend/src/lib/ppiViewMode*` + `PpiIndicatorControls` |
| `cbr-term` | `cbrTermSliceRate*` (ВНИМАНИЕ: shadowed_legacy — реально рендерится generic) |
| `unemployment` | `unemploymentViewMode*` (ВНИМАНИЕ: shadowed_legacy — реально generic) |
| `variant` | `frontend/src/lib/indicatorVariants.js` + `VariantGroupPicker` |

## Сводка

- Всего кодов: **520**
- in_both_viewmode_systems (дубль легаси+generic): **14**
- shadowed_legacy (мёртвая легаси-ветка): **24**
- unresolved (нет ui_stack): **1**
- derived_not_seeded: **0**

По стекам: `cpi`=32, `generic`=475, `housing`=8, `null`=1, `ppi`=4

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
| `auto-loan-rate-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `birth-rate` | Население | annual | `generic` | — | ✓ | — |
| `birth-rate-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `births` | Население | annual | `generic` | — | ✓ | — |
| `births-index` | Население | annual | `generic` | derived_from_source | — | — |
| `births-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `brent` | Финансы | daily | `generic` | — | ✓ | — |
| `brent-avg-month` | Сырьё | monthly | `generic` | — | — | — |
| `brent-avg-quarter` | Сырьё | quarterly | `generic` | — | — | — |
| `brent-avg-week` | Сырьё | weekly | `generic` | — | — | — |
| `brent-avg-year` | Сырьё | annual | `generic` | — | — | — |
| `brent-eop-month` | Сырьё | monthly | `generic` | — | — | — |
| `brent-eop-quarter` | Сырьё | quarterly | `generic` | — | — | — |
| `brent-eop-week` | Сырьё | weekly | `generic` | — | — | — |
| `brent-eop-year` | Сырьё | annual | `generic` | — | — | — |
| `brent-mom` | Сырьё | monthly | `generic` | — | — | — |
| `brent-qoq` | Сырьё | quarterly | `generic` | — | — | — |
| `brent-yoy` | Сырьё | monthly | `generic` | — | — | — |
| `btc-usd` | Валюты | daily | `generic` | — | ✓ | — |
| `btc-usd-avg-month` | Сырьё | monthly | `generic` | — | — | — |
| `btc-usd-avg-quarter` | Сырьё | quarterly | `generic` | — | — | — |
| `btc-usd-avg-week` | Сырьё | weekly | `generic` | — | — | — |
| `btc-usd-avg-year` | Сырьё | annual | `generic` | — | — | — |
| `btc-usd-eop-month` | Сырьё | monthly | `generic` | — | — | — |
| `btc-usd-eop-quarter` | Сырьё | quarterly | `generic` | — | — | — |
| `btc-usd-eop-week` | Сырьё | weekly | `generic` | — | — | — |
| `btc-usd-eop-year` | Сырьё | annual | `generic` | — | — | — |
| `btc-usd-mom` | Сырьё | monthly | `generic` | — | — | — |
| `btc-usd-qoq` | Сырьё | quarterly | `generic` | — | — | — |
| `btc-usd-yoy` | Сырьё | monthly | `generic` | — | — | — |
| `budget-deficit` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `budget-deficit-mom` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-deficit-qoq` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-deficit-sum-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-deficit-sum-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-deficit-yoy` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-expenditure` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `budget-expenditure-mom` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-expenditure-qoq` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-expenditure-sum-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-expenditure-sum-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-expenditure-yoy` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-revenue` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `budget-revenue-mom` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-revenue-qoq` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-revenue-sum-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-revenue-sum-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-revenue-yoy` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `business-credit` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `business-credit-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `business-credit-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `business-credit-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `business-credit-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `business-credit-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `business-credit-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `business-credit-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `capital-investment` | Бизнес | quarterly | `generic` | — | ✓ | — |
| `capital-investment-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `capital-investment-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `capital-investment-yoy` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
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
| `construction-work` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `construction-work-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `construction-work-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `construction-work-sum-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `construction-work-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `construction-work-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `consumer-credit` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `consumer-credit-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `consumer-credit-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `consumer-credit-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `consumer-credit-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `consumer-credit-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `consumer-credit-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `consumer-credit-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
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
| `credit-rate-corp-1to3y-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-corp-over3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short` | Ставки | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `credit-rate-corp-short-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-ind-1to3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-ind-over3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short` | Ставки | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `credit-rate-ind-short-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `current-account` | Торговля | quarterly | `generic` | — | ✓ | both, shadowed |
| `current-account-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `current-account-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `current-account-yoy` | Торговля | quarterly | `generic` | — | — | — |
| `current-account-yoy-abs` | Торговля | quarterly | `generic` | — | — | both, shadowed |
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
| `deposit-rate-long-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-long-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-long-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `deposit-rate-medium-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposits-business` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `deposits-business-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-business-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-business-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-business-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-individual` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `deposits-individual-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-individual-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-individual-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-individual-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `depreciation-rate` | Бизнес | annual | `generic` | — | ✓ | — |
| `depreciation-rate-yoy` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `doctoral-students` | Наука | annual | `generic` | — | ✓ | — |
| `doctoral-students-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `doctoral-students-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `employment` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `employment-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `employment-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `employment-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `employment-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `employment-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
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
| `exports` | Торговля | quarterly | `generic` | — | ✓ | both, shadowed |
| `exports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `exports-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `exports-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `exports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `exports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `exports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `exports-qoq` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `exports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `exports-yoy` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `external-debt` | Финансы | quarterly | `generic` | — | ✓ | — |
| `external-debt-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `external-debt-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `external-debt-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `external-debt-yoy` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `fdi-net` | Бизнес | quarterly | `generic` | — | ✓ | — |
| `fdi-net-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `fdi-net-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `fdi-net-yoy` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `gdp-consumption` | ВВП | quarterly | `generic` | gdp_consumption_quarterly | ✓ | — |
| `gdp-consumption-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-consumption-sum-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-consumption-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-government` | ВВП | quarterly | `generic` | gdp_government_quarterly | ✓ | — |
| `gdp-government-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-government-sum-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-government-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-investment` | Бизнес | quarterly | `generic` | — | ✓ | — |
| `gdp-investment-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-investment-sum-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-investment-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-nominal` | ВВП | quarterly | `generic` | gdp_nominal_quarterly | ✓ | — |
| `gdp-nominal-annual` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-real` | ВВП | quarterly | `generic` | gdp_real_quarterly | ✓ | — |
| `gdp-real-annual` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-real-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-real-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gold-price` | Финансы | daily | `generic` | — | ✓ | — |
| `gold-price-avg-month` | Сырьё | monthly | `generic` | — | — | — |
| `gold-price-avg-quarter` | Сырьё | quarterly | `generic` | — | — | — |
| `gold-price-avg-week` | Сырьё | weekly | `generic` | — | — | — |
| `gold-price-avg-year` | Сырьё | annual | `generic` | — | — | — |
| `gold-price-eop-month` | Сырьё | monthly | `generic` | — | — | — |
| `gold-price-eop-quarter` | Сырьё | quarterly | `generic` | — | — | — |
| `gold-price-eop-week` | Сырьё | weekly | `generic` | — | — | — |
| `gold-price-eop-year` | Сырьё | annual | `generic` | — | — | — |
| `gold-price-mom` | Сырьё | monthly | `generic` | — | — | — |
| `gold-price-qoq` | Сырьё | quarterly | `generic` | — | — | — |
| `gold-price-yoy` | Сырьё | monthly | `generic` | — | — | — |
| `grad-students` | Наука | annual | `generic` | — | ✓ | — |
| `grad-students-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `grad-students-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `housing-affordability` | Цены | monthly | `generic` | monthly_auto | ✓ | — |
| `housing-affordability-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-mom` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary` | Цены | monthly | `generic` | monthly_auto | — | — |
| `housing-affordability-primary-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-mom` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-qoq` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-yoy` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-qoq` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-yoy` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-annual-primary` | Цены | annual | `housing` | derived_from_source | — | — |
| `housing-annual-secondary` | Цены | annual | `housing` | derived_from_source | — | — |
| `housing-commissioned` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `housing-commissioned-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `housing-commissioned-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `housing-commissioned-sum-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `housing-commissioned-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `housing-commissioned-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `housing-price-primary` | Цены | quarterly | `housing` | housing_quarterly | ✓ | — |
| `housing-price-secondary` | Цены | quarterly | `housing` | housing_quarterly | ✓ | — |
| `housing-qoq-primary` | Цены | quarterly | `housing` | derived_from_source | — | — |
| `housing-qoq-secondary` | Цены | quarterly | `housing` | derived_from_source | — | — |
| `housing-yoy-primary` | Цены | quarterly | `housing` | derived_from_source | — | — |
| `housing-yoy-secondary` | Цены | quarterly | `housing` | derived_from_source | — | — |
| `imports` | Торговля | quarterly | `generic` | — | ✓ | both, shadowed |
| `imports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `imports-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `imports-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `imports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `imports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `imports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `imports-qoq` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `imports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `imports-yoy` | Торговля | quarterly | `generic` | — | — | both, shadowed |
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
| `international-reserves-qoq` | Финансы | quarterly | `generic` | — | — | — |
| `international-reserves-yoy` | Финансы | monthly | `generic` | — | — | — |
| `ipi` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `ipi-avg-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-avg-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-eop-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-eop-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
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
| `labor-force` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `labor-force-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `labor-force-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `labor-force-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `labor-force-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `labor-force-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `m0` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m0-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m0-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m0-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m0-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m1` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m1-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m1-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m1-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m1-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m2` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m2-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m2-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m2-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m2-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m2-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m2-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m2-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `mortgage-rate` | Ставки | monthly | `generic` | monthly_auto | ✓ | — |
| `mortgage-rate-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `mortgage-rate-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `mortgage-rate-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `mortgage-rate-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `mortgage-rate-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `mortgage-rate-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `mortgage-rate-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
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
| `retail-trade-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `retail-trade-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `retail-trade-sum-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `retail-trade-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `retail-trade-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
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
| `services-exports` | Торговля | quarterly | `generic` | — | ✓ | — |
| `services-exports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `services-exports-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-exports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-exports-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-exports-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports` | Торговля | quarterly | `generic` | — | ✓ | — |
| `services-imports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `services-imports-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-imports-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `small-business-innovation` | Наука | annual | `generic` | — | ✓ | — |
| `small-business-innovation-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `tech-innovation-share` | Наука | annual | `generic` | — | ✓ | — |
| `tech-innovation-share-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `trade-balance` | Торговля | quarterly | `generic` | — | ✓ | both, shadowed |
| `trade-balance-monthly` | Торговля | monthly | `generic` | monthly_auto | — | — |
| `trade-balance-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `trade-balance-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `trade-balance-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-yoy-abs` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `unemployment` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `unemployment-annual` | Рынок труда | monthly | `generic` | — | — | — |
| `unemployment-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `unemployment-eop-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-eop-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `unemployment-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `unemployment-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-quarterly` | Рынок труда | quarterly | `generic` | — | — | — |
| `unemployment-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
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
| `wages-index` | Рынок труда | monthly | `generic` | — | — | — |
| `wages-nominal` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `wages-nominal-annual` | Рынок труда | annual | `null` | — | — | no-stack |
| `wages-nominal-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-nominal-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `wages-nominal-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `wages-nominal-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-real` | Рынок труда | monthly | `generic` | — | — | — |
| `wages-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `working-age-population` | Население | annual | `generic` | — | ✓ | — |
| `working-age-population-index` | Население | annual | `generic` | derived_from_source | — | — |
| `working-age-population-yoy` | Население | annual | `generic` | derived_from_source | — | — |

