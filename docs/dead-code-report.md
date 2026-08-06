# Dead / duplicate view-mode code report

> Генерируется `scripts/build-indicator-index.py` из флагов карты. НЕ редактировать руками. Это **список на расследование, НЕ слепой delete-list**. Флаги ловят shadowing standalone-ветки рендера в `IndicatorDetail.jsx`, но НЕ доказывают, что легаси-код мёртв: см. раздел «Почему это НЕ delete-list» ниже. Источник флагов — `docs/indicator-index.json`.

**Сгенерировано:** 2026-08-06

## Почему это НЕ delete-list (расследование 2026-06-24)

Попытка чистки view-mode показала, что помеченное флагами легаси **живое** по двум независимым причинам — удалять нельзя без эскалации:

1. **Живые canonical-редиректы старых URL.** `IndicatorDetail.jsx` редиректит старые derived-URL на родительскую карточку через легаси `viewModeCanonicalTarget` / `unemploymentCanonicalTarget`. Коды `trade-balance-yoy-abs`, `current-account-yoy-abs`, `unemployment-quarterly`, `unemployment-annual` **отсутствуют** в generated-конфиге → их редирект держится ТОЛЬКО на легаси. Эти URL в sitemap (индексируются) — удаление тихо ломает SEO, тесты не ловят. ЭСКАЛАЦИЯ.
2. **bespoke content переиспользуется живыми секциями.** `cbrTermSliceRate*` / `unemploymentViewMode*` импортируются в `IndicatorChartSection.jsx`, `IndicatorDataTableSection.jsx`, `cpiViewModeContent.jsx`, `useIndicatorViewModeData.js`, picker-groups — т.е. заголовки графика/таблицы и резолв режимов живут через общие секции, а не только через standalone-ветку. Файлы НЕ мёртвые.

Вывод: `shadowed_legacy`/`in_both` = «standalone-ветка рендера перекрыта», НЕ «файл можно удалить». Перед любым удалением — проверить (а) покрывает ли generated-движок старый URL, (б) импорты экспортов.

## Что значат флаги

- **in_both_viewmode_systems** — код объявлен И в легаси `frontend/src/lib/viewModeFamilies.js`, И в config-driven движке (`view_model_families.py` → `viewModelFamilies.generated.json`).
- **shadowed_legacy** — standalone-ветка рендера в `IndicatorDetail.jsx` недостижима (generic early-return ПЕРВЫМ). НЕ значит, что легаси-файл мёртв — см. раздел выше (живые редиректы + переиспользование секциями).

Итог: in_both=14, shadowed_legacy=24.

## in_both_viewmode_systems — легаси-trade vs generated

Коды есть и в `viewModeFamilies.js`, и в generated-конфиге. Для `*-yoy`/`*-qoq`/`*-mom`, покрытых движком, легаси-запись мёртвая. Но `*-yoy-abs` движок НЕ покрывает → их легаси canonical-редирект живой (см. раздел выше). Удаление — только после эскалации по старым URL.

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

## shadowed_legacy — standalone-ветка перекрыта (НЕ значит «удалить»)

Bespoke-стеки `cbr-term` (ставки по сроку) и `unemployment`: их standalone-ветка рендера в `IndicatorDetail.jsx` перекрыта generic-движком (`view_model_families.py` содержит эти базы как T2y-семьи). НО файлы `cbrTermSliceRate*` / `unemploymentViewMode*` **живые** — их content/resolve переиспользуются общими секциями (chart/table title, режимы, picker), а canonical-редиректы держат старые URL `unemployment-quarterly/-annual`. Удалять нельзя (см. раздел «Почему это НЕ delete-list»).

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

## Рекомендации (требуют продуктового решения — ЭСКАЛАЦИЯ)

Чистка этого слоя НЕ автономна: упирается в старые индексируемые URL. Прежде чем резать — решить с владельцем:

1. **Старые derived-URL** `trade-balance-yoy-abs`, `current-account-yoy-abs`, `unemployment-quarterly`, `unemployment-annual` (в sitemap, движком НЕ покрыты): держим легаси-редирект как есть, или консолидируем ряды в движок (`*-yoy-abs` → `*-yoy`) с 301-картой? Второе — отдельная задача с правкой seed/derived/sitemap.
2. Только ПОСЛЕ решения по (1): живые редиректы вынести в явную redirect-карту, затем убрать мёртвую standalone-ветку рендера. content/resolve, переиспользуемые секциями, НЕ трогать.
3. После любой правки — `python scripts/build-indicator-index.py` и `./scripts/check-all.sh`.

