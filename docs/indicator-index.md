# Indicator index — карта индикаторов

> Генерируется `scripts/build-indicator-index.py`. НЕ редактировать руками. Полная машинная версия — `docs/indicator-index.json`. Подробности по каждому коду (files/derived_siblings) — в JSON.

**Сгенерировано:** 2026-11-09

**Scope файлов-ссылок:** Git tracked/index по умолчанию, включая новые git add файлы; untracked не входят.
Если Git недоступен, применяется filesystem fallback с прежними фильтрами; такой срез не подтверждает состав main.

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

- Всего кодов: **1685**
- in_both_viewmode_systems (дубль легаси+generic): **14**
- shadowed_legacy (перекрытая standalone-ветка): **24**
- unresolved (нет ui_stack): **27**
- derived_not_seeded: **0**

По стекам: `cpi`=32, `generic`=1613, `housing`=8, `null`=27, `ppi`=5

### Unresolved (ui_stack=null)

`cny-eur`, `employment-rate-age-25-54`, `employment-rate-age-55-64`, `employment-rate-youth`, `gbp-eur`, `labor-force-age-25-54`, `labor-force-age-55-64`, `labor-force-youth`, `long-term-unemployed`, `part-time-employed`, `registered-unemployment-share`, `registered-unemployment-share-quarterly`, `short-term-unemployed`, `steel`, `unemployed-higher-education-share`, `unemployed-higher-education-share-annual`, `unemployment-age-25-54`, `unemployment-age-25-54-men`, `unemployment-age-25-54-women`, `unemployment-age-55-64`, `unemployment-age-55-64-men`, `unemployment-age-55-64-women`, `unemployment-men`, `unemployment-women`, `unemployment-youth`, `unemployment-youth-men`, `unemployment-youth-women`

## Все индикаторы

| Код | Категория | Частота | Стек | Стратегия | Listed | Флаги |
|-----|-----------|---------|------|-----------|:------:|-------|
| `aed-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `aed-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `aed-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `aed-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `aed-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `aed-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `aed-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `aed-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `aed-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `aed-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `aed-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `aed-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `aed-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `aed-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `amd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `amd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `amd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `amd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `amd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `amd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `amd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `amd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `amd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `amd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `amd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `amd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `amd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `amd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `aud-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `aud-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `aud-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `aud-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `aud-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `aud-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `aud-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `aud-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `aud-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `aud-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `aud-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `aud-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `aud-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `aud-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `auto-loan-rate` | Ставки | monthly | `generic` | monthly_auto | ✓ | — |
| `auto-loan-rate-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `auto-loan-rate-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `auto-loan-rate-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `auto-loan-rate-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `azn-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `azn-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `azn-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `azn-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `azn-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `azn-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `azn-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `azn-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `azn-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `azn-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `azn-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `azn-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `azn-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `azn-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `bdt-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `bdt-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `bdt-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bdt-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `bdt-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `bdt-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `bdt-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bdt-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `bdt-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `bdt-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `bdt-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `bdt-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `bdt-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bdt-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `bhd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `bhd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `bhd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bhd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `bhd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `bhd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `bhd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bhd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `bhd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `bhd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `bhd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `bhd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `bhd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bhd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `birth-rate` | Население | annual | `generic` | annual_auto | ✓ | — |
| `birth-rate-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `births` | Население | annual | `generic` | annual_auto | ✓ | — |
| `births-index` | Население | annual | `generic` | derived_from_source | — | — |
| `births-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `bob-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `bob-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `bob-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bob-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `bob-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `bob-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `bob-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bob-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `bob-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `bob-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `bob-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `bob-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `bob-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `bob-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
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
| `brl-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `brl-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `brl-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `brl-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `brl-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `brl-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `brl-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `brl-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `brl-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `brl-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `brl-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `brl-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `brl-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `brl-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
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
| `budget-deficit` | Финансы | monthly | `generic` | derived_from_source | ✓ | — |
| `budget-deficit-mom` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-deficit-qoq` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-deficit-sum-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-deficit-sum-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-deficit-yoy` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-deficit-yoy-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-deficit-yoy-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-expenditure` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `budget-expenditure-mom` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-expenditure-qoq` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-expenditure-sum-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-expenditure-sum-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-expenditure-yoy` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-expenditure-yoy-quarter` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
| `budget-expenditure-yoy-year` | Бюджет | annual | `generic` | derived_from_source | — | — |
| `budget-revenue` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `budget-revenue-mom` | Бюджет | monthly | `generic` | derived_from_source | — | — |
| `budget-revenue-qoq` | Бюджет | quarterly | `generic` | derived_from_source | — | — |
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
| `business-credit-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `business-credit-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `business-credit-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `business-credit-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `business-credit-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `byn-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `byn-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `byn-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `byn-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `byn-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `byn-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `byn-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `byn-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `byn-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `byn-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `byn-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `byn-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `byn-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `byn-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `cad-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `cad-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `cad-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cad-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `cad-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `cad-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `cad-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cad-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `cad-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `cad-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `cad-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `cad-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `cad-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cad-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `capital-investment` | Бизнес | quarterly | `generic` | generic_quarterly | ✓ | — |
| `capital-investment-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `capital-investment-sum-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `capital-investment-yoy` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `capital-investment-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `chf-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `chf-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `chf-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `chf-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `chf-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `chf-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `chf-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `chf-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `chf-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `chf-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `chf-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `chf-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `chf-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `chf-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `cny-eur` | Валюты | daily | `null` | — | — | no-stack |
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
| `coal` | Товарные рынки | monthly | `generic` | — | ✓ | — |
| `coal-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `coal-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `coal-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `coal-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `coal-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `coal-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `coal-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `construction-work` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `construction-work-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `construction-work-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
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
| `consumer-credit-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `consumer-credit-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `consumer-credit-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `consumer-credit-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `consumer-credit-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `copper` | Товарные рынки | monthly | `generic` | — | ✓ | — |
| `copper-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `copper-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
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
| `credit-rate-corp-1to3y-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-1to3y-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-corp-over3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-over3y-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short` | Ставки | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `credit-rate-corp-short-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-corp-short-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-ind-1to3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-1to3y-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `credit-rate-ind-over3y-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-over3y-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short` | Ставки | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `credit-rate-ind-short-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `credit-rate-ind-short-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `cup-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `cup-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `cup-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cup-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `cup-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `cup-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `cup-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cup-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `cup-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `cup-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `cup-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `cup-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `cup-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `cup-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `current-account` | Торговля | quarterly | `generic` | signed_quarterly | ✓ | both, shadowed |
| `current-account-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `current-account-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `current-account-yoy` | Торговля | quarterly | `generic` | — | — | — |
| `current-account-yoy-abs` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `current-account-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `czk-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `czk-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `czk-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `czk-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `czk-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `czk-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `czk-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `czk-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `czk-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `czk-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `czk-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `czk-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `czk-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `czk-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `death-rate` | Население | annual | `generic` | annual_auto | ✓ | — |
| `death-rate-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `deaths` | Население | annual | `generic` | annual_auto | ✓ | — |
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
| `deposit-rate-long-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-long-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-medium` | Ставки | monthly | `generic` | monthly_auto | — | shadowed |
| `deposit-rate-medium-avg-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-avg-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-eop-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-eop-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-medium-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposit-rate-mom` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-qoq` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-yoy` | Ставки | monthly | `generic` | derived_from_source | — | — |
| `deposit-rate-yoy-quarter` | Ставки | quarterly | `generic` | derived_from_source | — | — |
| `deposit-rate-yoy-year` | Ставки | annual | `generic` | derived_from_source | — | — |
| `deposits-business` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `deposits-business-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-business-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-business-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-business-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-business-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-business-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-individual` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `deposits-individual-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-individual-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `deposits-individual-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-individual-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `deposits-individual-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `deposits-individual-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `depreciation-rate` | Бизнес | annual | `generic` | annual_auto | ✓ | — |
| `depreciation-rate-yoy` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `dkk-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `dkk-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `dkk-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `dkk-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `dkk-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `dkk-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `dkk-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `dkk-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `dkk-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `dkk-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `dkk-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `dkk-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `dkk-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `dkk-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `doctoral-students` | Наука | annual | `generic` | annual_auto | ✓ | — |
| `doctoral-students-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `doctoral-students-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `dzd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `dzd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `dzd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `dzd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `dzd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `dzd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `dzd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `dzd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `dzd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `dzd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `dzd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `dzd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `dzd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `dzd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `egp-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `egp-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `egp-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `egp-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `egp-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `egp-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `egp-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `egp-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `egp-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `egp-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `egp-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `egp-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `egp-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `egp-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `employment` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `employment-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `employment-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `employment-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `employment-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `employment-rate-age-25-54` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `employment-rate-age-55-64` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `employment-rate-youth` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `employment-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `employment-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `employment-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `etb-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `etb-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `etb-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `etb-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `etb-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `etb-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `etb-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `etb-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `etb-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `etb-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `etb-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `etb-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `etb-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `etb-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
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
| `eur-usd` | Валюты | daily | `generic` | — | ✓ | — |
| `eur-usd-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `eur-usd-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eur-usd-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `eur-usd-avg-year` | Валюты | annual | `generic` | — | — | — |
| `eur-usd-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `eur-usd-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eur-usd-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `eur-usd-eop-year` | Валюты | annual | `generic` | — | — | — |
| `eur-usd-mom` | Валюты | monthly | `generic` | — | — | — |
| `eur-usd-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `eur-usd-yoy` | Валюты | monthly | `generic` | — | — | — |
| `eur-usd-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `eur-usd-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `exports` | Торговля | quarterly | `generic` | generic_quarterly | ✓ | both, shadowed |
| `exports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `exports-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `exports-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
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
| `external-debt-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `external-debt-yoy` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `external-debt-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `fdi-net` | Бизнес | quarterly | `generic` | signed_quarterly | ✓ | — |
| `fdi-net-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
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
| `gbp-eur` | Валюты | daily | `null` | — | — | no-stack |
| `gbp-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `gbp-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `gbp-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gbp-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `gbp-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `gbp-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `gbp-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gbp-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `gbp-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `gbp-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `gbp-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `gbp-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `gbp-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gbp-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `gbp-usd` | Валюты | daily | `generic` | — | ✓ | — |
| `gbp-usd-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `gbp-usd-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gbp-usd-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `gbp-usd-avg-year` | Валюты | annual | `generic` | — | — | — |
| `gbp-usd-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `gbp-usd-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gbp-usd-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `gbp-usd-eop-year` | Валюты | annual | `generic` | — | — | — |
| `gbp-usd-mom` | Валюты | monthly | `generic` | — | — | — |
| `gbp-usd-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `gbp-usd-yoy` | Валюты | monthly | `generic` | — | — | — |
| `gbp-usd-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gbp-usd-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `gdp-consumption` | ВВП | quarterly | `generic` | gdp_consumption_quarterly | ✓ | — |
| `gdp-consumption-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-consumption-sum-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-consumption-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-consumption-yoy-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-government` | ВВП | quarterly | `generic` | gdp_government_quarterly | ✓ | — |
| `gdp-government-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-government-sum-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-government-yoy` | ВВП | quarterly | `generic` | derived_from_source | — | — |
| `gdp-government-yoy-year` | ВВП | annual | `generic` | derived_from_source | — | — |
| `gdp-investment` | ВВП | quarterly | `generic` | generic_quarterly | ✓ | — |
| `gdp-investment-qoq` | ВВП | quarterly | `generic` | derived_from_source | — | — |
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
| `gel-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `gel-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `gel-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gel-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `gel-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `gel-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `gel-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gel-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `gel-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `gel-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `gel-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `gel-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `gel-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `gel-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
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
| `grad-students` | Наука | annual | `generic` | annual_auto | ✓ | — |
| `grad-students-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `grad-students-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `hkd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `hkd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `hkd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `hkd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `hkd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `hkd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `hkd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `hkd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `hkd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `hkd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `hkd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `hkd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `hkd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `hkd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `housing-affordability` | Цены | monthly | `generic` | monthly_auto | ✓ | — |
| `housing-affordability-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-eop-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-eop-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-mom` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary` | Цены | monthly | `generic` | monthly_auto | — | — |
| `housing-affordability-primary-avg-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-avg-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-eop-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-eop-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-mom` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-qoq` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-yoy` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-yoy-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-primary-yoy-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-affordability-qoq` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-yoy` | Цены | monthly | `generic` | derived_from_source | — | — |
| `housing-affordability-yoy-quarter` | Цены | quarterly | `generic` | derived_from_source | — | — |
| `housing-affordability-yoy-year` | Цены | annual | `generic` | derived_from_source | — | — |
| `housing-annual-primary` | Цены | annual | `housing` | derived_from_source | — | — |
| `housing-annual-secondary` | Цены | annual | `housing` | derived_from_source | — | — |
| `housing-commissioned` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `housing-commissioned-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `housing-commissioned-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
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
| `huf-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `huf-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `huf-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `huf-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `huf-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `huf-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `huf-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `huf-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `huf-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `huf-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `huf-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `huf-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `huf-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `huf-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `idr-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `idr-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `idr-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `idr-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `idr-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `idr-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `idr-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `idr-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `idr-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `idr-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `idr-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `idr-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `idr-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `idr-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
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
| `imports-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `imports-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
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
| `innovation-activity` | Наука | annual | `generic` | annual_auto | ✓ | — |
| `innovation-activity-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `inr-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `inr-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `inr-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `inr-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `inr-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `inr-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `inr-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `inr-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `inr-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `inr-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `inr-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `inr-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `inr-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `inr-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
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
| `ipi-energy-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-energy-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
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
| `ipi-manufacturing-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-manufacturing-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mining` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `ipi-mining-avg-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-mining-avg-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mining-eop-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-mining-eop-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mining-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-mining-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-mining-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-mining-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-mining-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-water` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `ipi-water-avg-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-water-avg-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-water-eop-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-water-eop-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-water-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-water-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-water-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-water-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-water-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `ipi-yoy` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `ipi-yoy-quarter` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
| `ipi-yoy-year` | Бизнес | annual | `generic` | derived_from_source | — | — |
| `irr-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `irr-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `irr-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `irr-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `irr-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `irr-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `irr-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `irr-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `irr-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `irr-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `irr-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `irr-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `irr-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `irr-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `jpy-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `jpy-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `jpy-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `jpy-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `jpy-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `jpy-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `jpy-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `jpy-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `jpy-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `jpy-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `jpy-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `jpy-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `jpy-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `jpy-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
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
| `kgs-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `kgs-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `kgs-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `kgs-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `kgs-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `kgs-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `kgs-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `kgs-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `kgs-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `kgs-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `kgs-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `kgs-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `kgs-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `kgs-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `krw-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `krw-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `krw-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `krw-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `krw-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `krw-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `krw-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `krw-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `krw-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `krw-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `krw-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `krw-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `krw-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `krw-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `kzt-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `kzt-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `kzt-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `kzt-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `kzt-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `kzt-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `kzt-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `kzt-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `kzt-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `kzt-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `kzt-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `kzt-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `kzt-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `kzt-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `labor-force` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `labor-force-age-25-54` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `labor-force-age-55-64` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `labor-force-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `labor-force-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `labor-force-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `labor-force-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `labor-force-youth` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `labor-force-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `labor-force-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `labor-force-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `long-term-unemployed` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `m0` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m0-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m0-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m0-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m0-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m0-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m0-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m1` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m1-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m1-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m1-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m1-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-yoy` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m1-yoy-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m1-yoy-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m2` | Финансы | monthly | `generic` | monthly_auto | ✓ | — |
| `m2-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m2-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m2-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `m2-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `m2-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `m2-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
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
| `mdl-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `mdl-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `mdl-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mdl-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `mdl-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `mdl-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `mdl-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mdl-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `mdl-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `mdl-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `mdl-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `mdl-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `mdl-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mdl-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `mmk-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `mmk-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `mmk-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mmk-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `mmk-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `mmk-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `mmk-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mmk-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `mmk-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `mmk-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `mmk-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `mmk-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `mmk-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mmk-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `mnt-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `mnt-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `mnt-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mnt-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `mnt-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `mnt-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `mnt-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mnt-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `mnt-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `mnt-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `mnt-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `mnt-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `mnt-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `mnt-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `mortgage-rate` | Ставки | monthly | `generic` | monthly_auto | ✓ | — |
| `mortgage-rate-avg-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `mortgage-rate-avg-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `mortgage-rate-eop-quarter` | Финансы | quarterly | `generic` | derived_from_source | — | — |
| `mortgage-rate-eop-year` | Финансы | annual | `generic` | derived_from_source | — | — |
| `mortgage-rate-mom` | Финансы | monthly | `generic` | derived_from_source | — | — |
| `mortgage-rate-qoq` | Финансы | quarterly | `generic` | derived_from_source | — | — |
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
| `ngn-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `ngn-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `ngn-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `ngn-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `ngn-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `ngn-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `ngn-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `ngn-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `ngn-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `ngn-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `ngn-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `ngn-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `ngn-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `ngn-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `nok-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `nok-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `nok-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `nok-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `nok-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `nok-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `nok-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `nok-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `nok-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `nok-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `nok-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `nok-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `nok-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `nok-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `nzd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `nzd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `nzd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `nzd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `nzd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `nzd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `nzd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `nzd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `nzd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `nzd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `nzd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `nzd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `nzd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `nzd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `omr-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `omr-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `omr-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `omr-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `omr-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `omr-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `omr-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `omr-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `omr-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `omr-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `omr-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `omr-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `omr-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `omr-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `part-time-employed` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `pensioners` | Население | annual | `generic` | annual_auto | ✓ | — |
| `pensioners-index` | Население | annual | `generic` | derived_from_source | — | — |
| `pensioners-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `pln-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `pln-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `pln-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `pln-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `pln-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `pln-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `pln-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `pln-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `pln-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `pln-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `pln-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `pln-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `pln-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `pln-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `pop-over-working-age` | Население | annual | `generic` | annual_auto | ✓ | — |
| `pop-over-working-age-index` | Население | annual | `generic` | derived_from_source | — | — |
| `pop-over-working-age-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `pop-under-working-age` | Население | annual | `generic` | annual_auto | ✓ | — |
| `pop-under-working-age-index` | Население | annual | `generic` | derived_from_source | — | — |
| `pop-under-working-age-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `population` | Население | annual | `generic` | annual_auto | ✓ | — |
| `population-index` | Население | annual | `generic` | derived_from_source | — | — |
| `population-migration` | Население | annual | `generic` | annual_auto | ✓ | — |
| `population-migration-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `population-natural-growth` | Население | annual | `generic` | annual_auto | ✓ | — |
| `population-natural-growth-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `population-total-growth` | Население | annual | `generic` | annual_auto | ✓ | — |
| `population-total-growth-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `population-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `ppi` | Цены | monthly | `ppi` | ppi_monthly | ✓ | — |
| `ppi-annual` | Цены | annual | `ppi` | derived_from_source | — | — |
| `ppi-mom` | Цены | monthly | `ppi` | derived_from_source | — | — |
| `ppi-qoq` | Цены | quarterly | `ppi` | derived_from_source | — | — |
| `ppi-yoy` | Цены | monthly | `ppi` | derived_from_source | — | — |
| `qar-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `qar-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `qar-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `qar-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `qar-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `qar-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `qar-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `qar-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `qar-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `qar-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `qar-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `qar-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `qar-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `qar-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `rd-organizations` | Наука | annual | `generic` | annual_auto | ✓ | — |
| `rd-organizations-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `rd-organizations-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `rd-personnel` | Наука | annual | `generic` | annual_auto | ✓ | — |
| `rd-personnel-index` | Наука | annual | `generic` | derived_from_source | — | — |
| `rd-personnel-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `registered-unemployment-share` | Рынок труда | annual | `null` | — | ✓ | no-stack |
| `registered-unemployment-share-quarterly` | Рынок труда | quarterly | `null` | — | ✓ | no-stack |
| `retail-trade` | Бизнес | monthly | `generic` | monthly_auto | ✓ | — |
| `retail-trade-mom` | Бизнес | monthly | `generic` | derived_from_source | — | — |
| `retail-trade-qoq` | Бизнес | quarterly | `generic` | derived_from_source | — | — |
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
| `ron-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `ron-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `ron-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `ron-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `ron-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `ron-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `ron-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `ron-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `ron-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `ron-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `ron-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `ron-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `ron-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `ron-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `rsd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `rsd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `rsd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `rsd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `rsd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `rsd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `rsd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `rsd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `rsd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `rsd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `rsd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `rsd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `rsd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `rsd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
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
| `sar-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `sar-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `sar-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sar-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `sar-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `sar-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `sar-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sar-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `sar-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `sar-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `sar-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `sar-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `sar-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sar-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `sek-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `sek-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `sek-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sek-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `sek-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `sek-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `sek-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sek-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `sek-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `sek-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `sek-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `sek-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `sek-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sek-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `services-exports` | Торговля | quarterly | `generic` | generic_quarterly | ✓ | — |
| `services-exports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `services-exports-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-exports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-yoy-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-monthly-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-exports-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-exports-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-exports-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports` | Торговля | quarterly | `generic` | generic_quarterly | ✓ | — |
| `services-imports-monthly` | Торговля | monthly | `generic` | monthly_auto | — | both, shadowed |
| `services-imports-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-yoy-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-monthly-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `services-imports-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `services-imports-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `sgd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `sgd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `sgd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sgd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `sgd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `sgd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `sgd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sgd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `sgd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `sgd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `sgd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `sgd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `sgd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `sgd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `short-term-unemployed` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `silver` | Товарные рынки | monthly | `generic` | — | ✓ | — |
| `silver-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `silver-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `silver-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `silver-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `silver-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `silver-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `silver-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `small-business-innovation` | Наука | annual | `generic` | annual_auto | ✓ | — |
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
| `soybean` | Товарные рынки | monthly | `generic` | — | ✓ | — |
| `soybean-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `soybean-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `soybean-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `soybean-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `soybean-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `soybean-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `soybean-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `steel` | Товарные рынки | daily | `null` | — | — | no-stack |
| `tech-innovation-share` | Наука | annual | `generic` | annual_auto | ✓ | — |
| `tech-innovation-share-yoy` | Наука | annual | `generic` | derived_from_source | — | — |
| `thb-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `thb-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `thb-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `thb-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `thb-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `thb-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `thb-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `thb-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `thb-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `thb-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `thb-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `thb-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `thb-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `thb-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `tjs-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `tjs-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `tjs-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `tjs-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `tjs-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `tjs-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `tjs-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `tjs-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `tjs-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `tjs-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `tjs-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `tjs-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `tjs-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `tjs-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `tmt-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `tmt-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `tmt-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `tmt-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `tmt-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `tmt-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `tmt-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `tmt-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `tmt-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `tmt-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `tmt-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `tmt-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `tmt-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `tmt-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `trade-balance` | Торговля | quarterly | `generic` | derived_from_source | ✓ | both, shadowed |
| `trade-balance-monthly` | Торговля | monthly | `generic` | monthly_auto | — | — |
| `trade-balance-monthly-mom` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-sum-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-yoy` | Торговля | monthly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-yoy-quarter` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-monthly-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `trade-balance-qoq` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-sum-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `trade-balance-yoy` | Торговля | quarterly | `generic` | derived_from_source | — | — |
| `trade-balance-yoy-abs` | Торговля | quarterly | `generic` | — | — | both, shadowed |
| `trade-balance-yoy-year` | Торговля | annual | `generic` | derived_from_source | — | — |
| `try-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `try-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `try-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `try-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `try-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `try-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `try-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `try-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `try-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `try-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `try-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `try-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `try-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `try-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `uah-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `uah-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `uah-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `uah-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `uah-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `uah-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `uah-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `uah-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `uah-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `uah-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `uah-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `uah-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `uah-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `uah-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `unemployed-higher-education-share` | Рынок труда | quarterly | `null` | — | ✓ | no-stack |
| `unemployed-higher-education-share-annual` | Рынок труда | annual | `null` | — | ✓ | no-stack |
| `unemployment` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | shadowed |
| `unemployment-age-25-54` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-age-25-54-men` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-age-25-54-women` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-age-55-64` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-age-55-64-men` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-age-55-64-women` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-annual` | Рынок труда | monthly | `generic` | — | — | — |
| `unemployment-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `unemployment-eop-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-eop-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `unemployment-men` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `unemployment-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-quarterly` | Рынок труда | quarterly | `generic` | — | — | — |
| `unemployment-women` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-youth` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-youth-men` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-youth-women` | Рынок труда | monthly | `null` | — | ✓ | no-stack |
| `unemployment-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `unemployment-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `unemployment-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `usd-cny` | Валюты | daily | `generic` | — | ✓ | — |
| `usd-cny-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `usd-cny-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `usd-cny-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `usd-cny-avg-year` | Валюты | annual | `generic` | — | — | — |
| `usd-cny-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `usd-cny-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `usd-cny-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `usd-cny-eop-year` | Валюты | annual | `generic` | — | — | — |
| `usd-cny-mom` | Валюты | monthly | `generic` | — | — | — |
| `usd-cny-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `usd-cny-yoy` | Валюты | monthly | `generic` | — | — | — |
| `usd-cny-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `usd-cny-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `usd-index` | Индексы | daily | `generic` | — | ✓ | — |
| `usd-index-avg-month` | Индексы | monthly | `generic` | — | — | — |
| `usd-index-avg-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `usd-index-avg-week` | Индексы | weekly | `generic` | — | — | — |
| `usd-index-avg-year` | Индексы | annual | `generic` | — | — | — |
| `usd-index-eop-month` | Индексы | monthly | `generic` | — | — | — |
| `usd-index-eop-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `usd-index-eop-week` | Индексы | weekly | `generic` | — | — | — |
| `usd-index-eop-year` | Индексы | annual | `generic` | — | — | — |
| `usd-index-mom` | Индексы | monthly | `generic` | — | — | — |
| `usd-index-qoq` | Индексы | quarterly | `generic` | — | — | — |
| `usd-index-yoy` | Индексы | monthly | `generic` | — | — | — |
| `usd-index-yoy-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `usd-index-yoy-year` | Индексы | annual | `generic` | — | — | — |
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
| `ust-10y` | Индексы | daily | `generic` | — | ✓ | — |
| `ust-10y-avg-month` | Индексы | monthly | `generic` | — | — | — |
| `ust-10y-avg-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `ust-10y-avg-week` | Индексы | weekly | `generic` | — | — | — |
| `ust-10y-avg-year` | Индексы | annual | `generic` | — | — | — |
| `ust-10y-eop-month` | Индексы | monthly | `generic` | — | — | — |
| `ust-10y-eop-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `ust-10y-eop-week` | Индексы | weekly | `generic` | — | — | — |
| `ust-10y-eop-year` | Индексы | annual | `generic` | — | — | — |
| `ust-10y-mom` | Индексы | monthly | `generic` | — | — | — |
| `ust-10y-qoq` | Индексы | quarterly | `generic` | — | — | — |
| `ust-10y-yoy` | Индексы | monthly | `generic` | — | — | — |
| `ust-10y-yoy-quarter` | Индексы | quarterly | `generic` | — | — | — |
| `ust-10y-yoy-year` | Индексы | annual | `generic` | — | — | — |
| `uzs-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `uzs-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `uzs-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `uzs-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `uzs-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `uzs-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `uzs-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `uzs-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `uzs-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `uzs-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `uzs-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `uzs-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `uzs-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `uzs-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `vnd-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `vnd-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `vnd-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `vnd-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `vnd-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `vnd-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `vnd-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `vnd-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `vnd-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `vnd-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `vnd-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `vnd-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `vnd-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `vnd-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `wages-index` | Рынок труда | monthly | `generic` | — | — | — |
| `wages-nominal` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `wages-nominal-annual` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `wages-nominal-annual-yoy` | Рынок труда | annual | `generic` | — | — | — |
| `wages-nominal-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-nominal-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `wages-nominal-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-nominal-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-real` | Рынок труда | monthly | `generic` | monthly_auto | ✓ | — |
| `wages-real-avg-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-real-avg-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `wages-real-mom` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `wages-real-qoq` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-real-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `wages-real-yoy-quarter` | Рынок труда | quarterly | `generic` | derived_from_source | — | — |
| `wages-real-yoy-year` | Рынок труда | annual | `generic` | derived_from_source | — | — |
| `wages-yoy` | Рынок труда | monthly | `generic` | derived_from_source | — | — |
| `weo-budget-balance-gdp` | Государственные финансы | annual | `generic` | — | ✓ | — |
| `weo-budget-balance-gdp-yoy` | Государственные финансы | annual | `generic` | — | — | — |
| `weo-gdp-per-capita-usd` | ВВП | annual | `generic` | — | ✓ | — |
| `weo-gdp-per-capita-usd-index` | ВВП | annual | `generic` | — | — | — |
| `weo-gdp-per-capita-usd-yoy` | ВВП | annual | `generic` | — | — | — |
| `weo-gdp-usd` | ВВП | annual | `generic` | — | ✓ | — |
| `weo-gdp-usd-index` | ВВП | annual | `generic` | — | — | — |
| `weo-gdp-usd-yoy` | ВВП | annual | `generic` | — | — | — |
| `weo-government-debt-gdp` | Государственные финансы | annual | `generic` | — | ✓ | — |
| `weo-government-debt-gdp-yoy` | Государственные финансы | annual | `generic` | — | — | — |
| `wheat` | Товарные рынки | monthly | `generic` | — | ✓ | — |
| `wheat-avg-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `wheat-avg-year` | Товарные рынки | annual | `generic` | — | — | — |
| `wheat-mom` | Товарные рынки | monthly | `generic` | — | — | — |
| `wheat-qoq` | Товарные рынки | quarterly | `generic` | — | — | — |
| `wheat-yoy` | Товарные рынки | monthly | `generic` | — | — | — |
| `wheat-yoy-quarter` | Товарные рынки | quarterly | `generic` | — | — | — |
| `wheat-yoy-year` | Товарные рынки | annual | `generic` | — | — | — |
| `working-age-population` | Население | annual | `generic` | annual_auto | ✓ | — |
| `working-age-population-index` | Население | annual | `generic` | derived_from_source | — | — |
| `working-age-population-yoy` | Население | annual | `generic` | derived_from_source | — | — |
| `xdr-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `xdr-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `xdr-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `xdr-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `xdr-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `xdr-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `xdr-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `xdr-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `xdr-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `xdr-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `xdr-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `xdr-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `xdr-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `xdr-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |
| `zar-rub` | Валюты | daily | `generic` | — | ✓ | — |
| `zar-rub-avg-month` | Валюты | monthly | `generic` | — | — | — |
| `zar-rub-avg-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `zar-rub-avg-week` | Валюты | weekly | `generic` | — | — | — |
| `zar-rub-avg-year` | Валюты | annual | `generic` | — | — | — |
| `zar-rub-eop-month` | Валюты | monthly | `generic` | — | — | — |
| `zar-rub-eop-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `zar-rub-eop-week` | Валюты | weekly | `generic` | — | — | — |
| `zar-rub-eop-year` | Валюты | annual | `generic` | — | — | — |
| `zar-rub-mom` | Валюты | monthly | `generic` | — | — | — |
| `zar-rub-qoq` | Валюты | quarterly | `generic` | — | — | — |
| `zar-rub-yoy` | Валюты | monthly | `generic` | — | — | — |
| `zar-rub-yoy-quarter` | Валюты | quarterly | `generic` | — | — | — |
| `zar-rub-yoy-year` | Валюты | annual | `generic` | — | — | — |


# Аудит полноты семейств — паспорт полноты

> Генерируется `scripts/build-indicator-index.py` (модуль `scripts/completeness.py`). НЕ редактировать руками. Read-only аудит: пробел = КАНДИДАТ на добавление режима, не дефект — владелец решает, осмыслен ли он для природы ряда. Ожидания — функция `expected_matrix` в `completeness.py` (единая точка истины). Доменная модель — `CONTEXT.md::Матрица представлений`.

## Оси матрицы

- **Тип** (верх, эталон — переключатель ИПЦ): `value` Уровень/значение · `pop` К прошлому периоду · `yoy` К соотв. периоду пред. года · `index` Индекс
- **Частота** (низ): `day` дн · `week` нед · `month` мес · `quarter` кв · `year` год

Корней-семейств: **198** · с полной матрицей: **159** · с пробелами: **39**. Покрытие: {'bespoke': 7, 'bespoke-data': 4, 'generic': 160, 'orphan': 27}.

## Систематические пробелы по типам

Семьи одного типа делят матрицу. `shared_missing` — ячейки, которых нет НИ У ОДНОГО члена типа (системный пробел типа).

| тип | природа | нативная | членов | общий пробел (shared_missing) |
|---|---|---|---|---|
| bespoke-data/CPI-weekly | index | week | 4 | `index:month`, `index:quarter`, `index:year`, `pop:month`, `pop:quarter`, `pop:year`, `value:week`, `yoy:month`, `yoy:quarter`, `yoy:year` |
| bespoke/CPI | index | month | 4 | `yoy:quarter`, `yoy:year` |
| bespoke/HOUSING | index | quarter | 2 | `pop:year` |
| bespoke/PPI | index | month | 1 | `yoy:quarter`, `yoy:year` |
| generic/T1 | rate | day | 72 | — |
| generic/T10 | annual-count | year | 13 | — |
| generic/T10a | annual-signed | year | 11 | — |
| generic/T12 | ratio-index | month | 2 | — |
| generic/T2y | rate | month | 12 | — |
| generic/T3 | index | month | 5 | — |
| generic/T3 | stock | month | 7 | — |
| generic/T4 | stock | quarter | 1 | — |
| generic/T5 | stock | week | 4 | — |
| generic/T6 | flow | month | 10 | — |
| generic/T7 | signed-flow | month | 1 | — |
| generic/T8 | avg-level | month | 8 | — |
| generic/T8 | index | month | 1 | `pop:year` |
| generic/T9 | gdp | quarter | 10 | — |
| generic/T9s | signed-flow | quarter | 3 | — |
| orphan/- | avg-level | day | 3 | `pop:month`, `pop:quarter`, `value:month`, `value:quarter`, `value:week`, `value:year`, `yoy:month`, `yoy:quarter`, `yoy:year` |
| orphan/- | avg-level | month | 6 | `pop:month`, `pop:quarter`, `value:quarter`, `value:year`, `yoy:month`, `yoy:quarter`, `yoy:year` |
| orphan/- | rate | month | 14 | `pop:month`, `pop:quarter`, `value:quarter`, `value:year`, `yoy:month`, `yoy:quarter`, `yoy:year` |
| orphan/- | rate | quarter | 2 | `pop:quarter`, `value:year`, `yoy:quarter`, `yoy:year` |
| orphan/- | rate | year | 2 | `yoy:year` |

## Корни с пробелами матрицы

| код | покрытие | природа | нативная | score | missing | тексты | прогноз | seo |
|---|---|---|---|---|---|---|---|---|
| `inflation-weekly` | bespoke-data/CPI-weekly | index | week | 0.0 | `value:week`, `pop:month`, `pop:quarter`, `pop:year`, `yoy:month`, `yoy:quarter`, `yoy:year`, `index:month`, `index:quarter`, `index:year` | partial | yes | curated |
| `inflation-weekly-food` | bespoke-data/CPI-weekly | index | week | 0.0 | `value:week`, `pop:month`, `pop:quarter`, `pop:year`, `yoy:month`, `yoy:quarter`, `yoy:year`, `index:month`, `index:quarter`, `index:year` | partial | yes | curated |
| `inflation-weekly-nonfood` | bespoke-data/CPI-weekly | index | week | 0.0 | `value:week`, `pop:month`, `pop:quarter`, `pop:year`, `yoy:month`, `yoy:quarter`, `yoy:year`, `index:month`, `index:quarter`, `index:year` | partial | yes | curated |
| `inflation-weekly-services` | bespoke-data/CPI-weekly | index | week | 0.0 | `value:week`, `pop:month`, `pop:quarter`, `pop:year`, `yoy:month`, `yoy:quarter`, `yoy:year`, `index:month`, `index:quarter`, `index:year` | partial | yes | curated |
| `cny-eur` | orphan/- | avg-level | day | 0.1 | `value:week`, `value:month`, `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `gbp-eur` | orphan/- | avg-level | day | 0.1 | `value:week`, `value:month`, `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `steel` | orphan/- | avg-level | day | 0.1 | `value:week`, `value:month`, `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | curated |
| `employment-rate-age-25-54` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `employment-rate-age-55-64` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `employment-rate-youth` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `labor-force-age-25-54` | orphan/- | avg-level | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `labor-force-age-55-64` | orphan/- | avg-level | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `labor-force-youth` | orphan/- | avg-level | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `long-term-unemployed` | orphan/- | avg-level | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `part-time-employed` | orphan/- | avg-level | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `short-term-unemployed` | orphan/- | avg-level | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-age-25-54` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-age-25-54-men` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-age-25-54-women` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-age-55-64` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-age-55-64-men` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-age-55-64-women` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-men` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-women` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-youth` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-youth-men` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployment-youth-women` | orphan/- | rate | month | 0.125 | `value:quarter`, `value:year`, `pop:month`, `pop:quarter`, `yoy:month`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `registered-unemployment-share-quarterly` | orphan/- | rate | quarter | 0.2 | `value:year`, `pop:quarter`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `unemployed-higher-education-share` | orphan/- | rate | quarter | 0.2 | `value:year`, `pop:quarter`, `yoy:quarter`, `yoy:year` | full | no | generic |
| `cpi` | bespoke/CPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | full | yes | curated |
| `cpi-food` | bespoke/CPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | full | yes | curated |
| `cpi-nonfood` | bespoke/CPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | full | yes | curated |
| `cpi-services` | bespoke/CPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | full | yes | curated |
| `ppi` | bespoke/PPI | index | month | 0.8 | `yoy:quarter`, `yoy:year` | full | yes | curated |
| `housing-price-primary` | bespoke/HOUSING | index | quarter | 0.857 | `pop:year` | full | yes | curated |
| `housing-price-secondary` | bespoke/HOUSING | index | quarter | 0.857 | `pop:year` | full | yes | curated |
| `registered-unemployment-share` | orphan/- | rate | year | 0.5 | `yoy:year` | full | no | generic |
| `unemployed-higher-education-share-annual` | orphan/- | rate | year | 0.5 | `yoy:year` | full | no | generic |
| `wages-real` | generic/T8 | index | month | 0.9 | `pop:year` | full | yes | curated |

## Измерения паспорта (агрегат)

- **Без полных текстов** (18): `birth-rate`, `death-rate`, `exports-monthly`, `imports-monthly`, `inflation-weekly`, `inflation-weekly-food`, `inflation-weekly-nonfood`, `inflation-weekly-services`, `pensioners`, `pop-over-working-age`, `pop-under-working-age`, `population-migration`, `population-natural-growth`, `population-total-growth`, `services-exports-monthly`, `services-imports-monthly`, `trade-balance-monthly`, `working-age-population`
- **Без прогноза** (39): `cny-eur`, `coal`, `copper`, `employment-rate-age-25-54`, `employment-rate-age-55-64`, `employment-rate-youth`, `fuel-ai92`, `fuel-ai95`, `fuel-diesel`, `gbp-eur`, `labor-force-age-25-54`, `labor-force-age-55-64`, `labor-force-youth`, `long-term-unemployed`, `part-time-employed`, `registered-unemployment-share`, `registered-unemployment-share-quarterly`, `short-term-unemployed`, `silver`, `soybean`, `steel`, `unemployed-higher-education-share`, `unemployed-higher-education-share-annual`, `unemployment-age-25-54`, `unemployment-age-25-54-men`, `unemployment-age-25-54-women`, `unemployment-age-55-64`, `unemployment-age-55-64-men`, `unemployment-age-55-64-women`, `unemployment-men`, `unemployment-women`, `unemployment-youth`, `unemployment-youth-men`, `unemployment-youth-women`, `weo-budget-balance-gdp`, `weo-gdp-per-capita-usd`, `weo-gdp-usd`, `weo-government-debt-gdp`, `wheat`
- **SEO не curated** (34): `cny-eur`, `deposit-rate-long`, `deposit-rate-medium`, `employment-rate-age-25-54`, `employment-rate-age-55-64`, `employment-rate-youth`, `exports-monthly`, `gbp-eur`, `housing-affordability-primary`, `imports-monthly`, `labor-force-age-25-54`, `labor-force-age-55-64`, `labor-force-youth`, `long-term-unemployed`, `part-time-employed`, `registered-unemployment-share`, `registered-unemployment-share-quarterly`, `services-exports-monthly`, `services-imports-monthly`, `short-term-unemployed`, `trade-balance-monthly`, `unemployed-higher-education-share`, `unemployed-higher-education-share-annual`, `unemployment-age-25-54`, `unemployment-age-25-54-men`, `unemployment-age-25-54-women`, `unemployment-age-55-64`, `unemployment-age-55-64-men`, `unemployment-age-55-64-women`, `unemployment-men`, `unemployment-women`, `unemployment-youth`, `unemployment-youth-men`, `unemployment-youth-women`

