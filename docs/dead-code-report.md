# Dead / duplicate view-mode code report

> Генерируется `scripts/build-indicator-index.py` из флагов карты. НЕ редактировать руками. В ЭТОЙ итерации НИЧЕГО не удалялось — это список-кандидат на будущую вычистку. Источник флагов — `docs/indicator-index.json`.

## Что значат флаги

- **in_both_viewmode_systems** — код объявлен И в легаси `frontend/src/lib/viewModeFamilies.js`, И в config-driven движке (`view_model_families.py` → `viewModelFamilies.generated.json`).
- **shadowed_legacy** — реально рендерится generic-движком, потому что `IndicatorDetail.jsx` делает `getViewModeFamily(code)` early-return ПЕРВЫМ. Легаси-ветка для кода недостижима — правка там ни на что не влияет.

Итог: in_both=14, shadowed_legacy=24.

## in_both_viewmode_systems — дубли легаси-trade vs generated

Все эти коды есть и в `viewModeFamilies.js`, и в generated-конфиге; из-за early-return generic легаси-запись мёртвая. Кандидат на удаление — соответствующая запись в `frontend/src/lib/viewModeFamilies.js`.

| Код | ui_stack | Легаси-запись (файл:строка) | Перекрыто (generated) |
|-----|----------|------------------------------|------------------------|
| `current-account` | `generic` | `frontend/src/lib/viewModeFamilies.js:43`; `frontend/src/lib/viewModeFamilies.js:82`; `frontend/src/lib/viewModeFamilies.js:85` | `view_model_families.py` (generic base `current-account`) |
| `current-account-yoy-abs` | `generic` | `frontend/src/lib/viewModeFamilies.js:86` | `view_model_families.py` (generic base `current-account`) |
| `exports` | `generic` | `frontend/src/lib/viewModeFamilies.js:9`; `frontend/src/lib/viewModeFamilies.js:43`; `frontend/src/lib/viewModeFamilies.js:59`; `frontend/src/lib/viewModeFamilies.js:62` | `view_model_families.py` (generic base `exports`) |
| `exports-monthly` | `generic` | `frontend/src/lib/viewModeFamilies.js:91`; `frontend/src/lib/viewModeFamilies.js:94`; `frontend/src/lib/viewModeFamilies.js:95` | `view_model_families.py` (generic base `exports-monthly`) |
| `exports-qoq` | `generic` | `frontend/src/lib/viewModeFamilies.js:9`; `frontend/src/lib/viewModeFamilies.js:64` | `view_model_families.py` (generic base `exports`) |
| `exports-yoy` | `generic` | `frontend/src/lib/viewModeFamilies.js:9`; `frontend/src/lib/viewModeFamilies.js:63` | `view_model_families.py` (generic base `exports`) |
| `imports` | `generic` | `frontend/src/lib/viewModeFamilies.js:43`; `frontend/src/lib/viewModeFamilies.js:67`; `frontend/src/lib/viewModeFamilies.js:70` | `view_model_families.py` (generic base `imports`) |
| `imports-monthly` | `generic` | `frontend/src/lib/viewModeFamilies.js:98`; `frontend/src/lib/viewModeFamilies.js:101`; `frontend/src/lib/viewModeFamilies.js:102` | `view_model_families.py` (generic base `imports-monthly`) |
| `imports-qoq` | `generic` | `frontend/src/lib/viewModeFamilies.js:72` | `view_model_families.py` (generic base `imports`) |
| `imports-yoy` | `generic` | `frontend/src/lib/viewModeFamilies.js:71` | `view_model_families.py` (generic base `imports`) |
| `services-exports-monthly` | `generic` | `frontend/src/lib/viewModeFamilies.js:105`; `frontend/src/lib/viewModeFamilies.js:108`; `frontend/src/lib/viewModeFamilies.js:109` | `view_model_families.py` (generic base `services-exports-monthly`) |
| `services-imports-monthly` | `generic` | `frontend/src/lib/viewModeFamilies.js:112`; `frontend/src/lib/viewModeFamilies.js:115`; `frontend/src/lib/viewModeFamilies.js:116` | `view_model_families.py` (generic base `services-imports-monthly`) |
| `trade-balance` | `generic` | `frontend/src/lib/viewModeFamilies.js:75`; `frontend/src/lib/viewModeFamilies.js:78` | `view_model_families.py` (generic base `trade-balance`) |
| `trade-balance-yoy-abs` | `generic` | `frontend/src/lib/viewModeFamilies.js:79` | `view_model_families.py` (generic base `trade-balance`) |

## shadowed_legacy — мёртвые легаси-ветки (полный список)

Bespoke-стеки `cbr-term` (ставки по сроку) и `unemployment` целиком перекрыты generic-движком (`view_model_families.py` содержит эти базы как T2y-семьи). Легаси-файлы `cbrTermSliceRate*` и `unemploymentViewMode*` + их ветки в `IndicatorDetail.jsx` — мёртвые для рендера (могут оставаться только canonical-редиректы).

| Код | ui_stack | Легаси-файлы (file:line) |
|-----|----------|--------------------------|
| `credit-rate-corp-1to3y` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:16`; `frontend/src/lib/cbrTermSliceRateResolve.js:8` |
| `credit-rate-corp-over3y` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:23`; `frontend/src/lib/cbrTermSliceRateResolve.js:9` |
| `credit-rate-corp-short` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:9`; `frontend/src/lib/cbrTermSliceRateContent.jsx:75`; `frontend/src/lib/cbrTermSliceRateContent.jsx:115`; `frontend/src/lib/cbrTermSliceRateResolve.js:7` |
| `credit-rate-ind-1to3y` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:37`; `frontend/src/lib/cbrTermSliceRateResolve.js:14` |
| `credit-rate-ind-over3y` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:44`; `frontend/src/lib/cbrTermSliceRateResolve.js:15` |
| `credit-rate-ind-short` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:30`; `frontend/src/lib/cbrTermSliceRateContent.test.js:11`; `frontend/src/lib/cbrTermSliceRateContent.test.js:18`; `frontend/src/lib/cbrTermSliceRateResolve.js:13` |
| `current-account` | `generic` | `frontend/src/lib/viewModeFamilies.js:43`; `frontend/src/lib/viewModeFamilies.js:82`; `frontend/src/lib/viewModeFamilies.js:85` |
| `current-account-yoy-abs` | `generic` | `frontend/src/lib/viewModeFamilies.js:86` |
| `deposit-rate` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:51`; `frontend/src/lib/cbrTermSliceRateContent.test.js:17`; `frontend/src/lib/cbrTermSliceRateContent.test.js:38`; `frontend/src/lib/cbrTermSliceRateResolve.js:19` |
| `deposit-rate-long` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:65`; `frontend/src/lib/cbrTermSliceRateContent.test.js:12`; `frontend/src/lib/cbrTermSliceRateResolve.js:21` |
| `deposit-rate-medium` | `generic` | `frontend/src/lib/cbrTermSliceRateContent.jsx:58`; `frontend/src/lib/cbrTermSliceRateContent.test.js:30`; `frontend/src/lib/cbrTermSliceRateResolve.js:20` |
| `exports` | `generic` | `frontend/src/lib/viewModeFamilies.js:9`; `frontend/src/lib/viewModeFamilies.js:43`; `frontend/src/lib/viewModeFamilies.js:59`; `frontend/src/lib/viewModeFamilies.js:62` |
| `exports-monthly` | `generic` | `frontend/src/lib/viewModeFamilies.js:91`; `frontend/src/lib/viewModeFamilies.js:94`; `frontend/src/lib/viewModeFamilies.js:95` |
| `exports-qoq` | `generic` | `frontend/src/lib/viewModeFamilies.js:9`; `frontend/src/lib/viewModeFamilies.js:64` |
| `exports-yoy` | `generic` | `frontend/src/lib/viewModeFamilies.js:9`; `frontend/src/lib/viewModeFamilies.js:63` |
| `imports` | `generic` | `frontend/src/lib/viewModeFamilies.js:43`; `frontend/src/lib/viewModeFamilies.js:67`; `frontend/src/lib/viewModeFamilies.js:70` |
| `imports-monthly` | `generic` | `frontend/src/lib/viewModeFamilies.js:98`; `frontend/src/lib/viewModeFamilies.js:101`; `frontend/src/lib/viewModeFamilies.js:102` |
| `imports-qoq` | `generic` | `frontend/src/lib/viewModeFamilies.js:72` |
| `imports-yoy` | `generic` | `frontend/src/lib/viewModeFamilies.js:71` |
| `services-exports-monthly` | `generic` | `frontend/src/lib/viewModeFamilies.js:105`; `frontend/src/lib/viewModeFamilies.js:108`; `frontend/src/lib/viewModeFamilies.js:109` |
| `services-imports-monthly` | `generic` | `frontend/src/lib/viewModeFamilies.js:112`; `frontend/src/lib/viewModeFamilies.js:115`; `frontend/src/lib/viewModeFamilies.js:116` |
| `trade-balance` | `generic` | `frontend/src/lib/viewModeFamilies.js:75`; `frontend/src/lib/viewModeFamilies.js:78` |
| `trade-balance-yoy-abs` | `generic` | `frontend/src/lib/viewModeFamilies.js:79` |
| `unemployment` | `generic` | `frontend/src/lib/unemploymentViewModeContent.test.js:11`; `frontend/src/lib/unemploymentViewModeContent.test.js:18`; `frontend/src/lib/unemploymentViewModeContent.test.js:21`; `frontend/src/lib/unemploymentViewModeResolve.js:5`; `frontend/src/lib/viewModeFamilies.js:45`; `frontend/src/lib/viewModeFamilies.js:127` |

## Рекомендации (на будущую отдельную задачу, НЕ сейчас)

1. Удалить из `frontend/src/lib/viewModeFamilies.js` записи trade-кодов (`exports/imports/trade-balance/current-account` + `*-monthly`), перекрытые generated-конфигом, и связанную ветку `findViewModeFamily` в `IndicatorDetail.jsx`.
2. Свернуть bespoke `cbrTermSliceRate*` и `unemploymentViewMode*`, оставив только canonical-редиректы старых URL (если нужны для SEO).
3. После любой такой правки — `python scripts/build-indicator-index.py` и сверить, что shadowed_legacy уменьшился.

