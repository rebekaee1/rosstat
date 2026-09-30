# Клиент: состав, элементы и связи — 30 сентября 2026

Основа: tracked frontend текущей локальной main `05302ff` (runtime JS не менялся
в этом продолжении). Независимый [AST-инвентарь](../client-mechanism-inventory.md)
собран до сопоставления с ledger. [Сверка каждого call site](client-inventory-reconciliation-2026-09-30.json)
содержит исходный файл/строки/owner, точный SHA прежнего ручного чтения и ближайшую
аннотацию либо содержательную рецензию файла. Это получение существующих
оснований, а не автоматический reviewed stamp.

## Состав

351 tracked JS/JSX/TS файлов: 232 runtime, 114 тестов/помощников и 5 build/config.
Всего 5376 функций, включая **3905 anonymous callbacks**; 1339 hook-вызовов,
64 HTTP call sites, 29 browser storage операций, 105 event/transport операций,
555 JSX event handlers, 316 синтаксических реестров. Эти числа включают тесты;
runtime без тестов: 3716 функций, 1328 hooks, 23 storage, 95 events, 527 handlers,
263 реестра. `functions` не равняется прежнему счётчику именованных определений.

72 декларации Route: **66 в App.jsx**, остальные 6 — тестовые маршрутизаторы.
Все 1707 import/export declarations имеют exact specifier; нет неразрешённых
относительных импортов. Generated JSON — отдельный существующий target, а не
самостоятельный авторский источник. Каждый перечисленный call site находится
в сохранённом read range актуальной ручной рецензии; пропущенных файлов/диапазонов
при этой независимой сверке нет. Реестр именованных элементов и полное чтение
охватывают также тела вложенных callback’ов; inventory добавляет адреса к ним,
но не доказывает исполнение всех ветвей.

## Семейства маршрутов и пользовательских механизмов

| Семейство | Данные и действие | Существенные состояния/исключения и источники |
|---|---|---|
| Shell, главная, статические страницы | `main.jsx`/`SpaRoot.jsx`/`App.jsx`, bootstrap → QueryClient, Locale/Auth providers | Mount через `createRoot`; SSR заменяется после React commit, не hydrateRoot. Suspense/ErrorBoundary; отдельные pure SSR страницы не монтируют SPA. Metadata/locale и cleaned analytics hits имеют собственные эффекты. |
| Каталог РФ и валюты | `CategoryPage`, `categories.js`, `hooks.js`, API catalog | Локаль/flags входят в list key, inactive/unlisted разделены; данные листинга не равны всему поиску. `/currencies` зарезервирован раньше country routes. |
| Карточка РФ/валюты | `IndicatorDetail`, generic `viewModeEngine`/generated families → `useGenericViewModeData`/API | Единица/частота выбранного кода; mode/variant — разные операции. CPI/PPI/housing bespoke; shadowed legacy содержит действующие resolve/content/redirect consumers. Empty/error/loading и forecast gates сохраняются. |
| Страна/мировая карточка/рейтинги | `WorldCountry`, `WorldIndicatorPage`, `WorldRatingPage`, `worldApi.js` | Официальные частоты; locale в keys. Mock fallback только DEV и только 404/502/503, отмена не подменяется fixture. В production ошибка не становится выдуманным HICP. Catalog timeout45s, retry поверх общего Axios. |
| Сравнение | `ComparePage`, `useCountryComparison`, `compareRepresentation` | Общая concept-группа и сопоставимость; index base100 по первой общей положительной фактической дате внутри окна; отсутствие даты — empty. Проценты и signed series не rebased. Денежный USD-план R-3 пока отдельная будущая возможность. |
| Регионы РФ | `RegionsHome`, `RegionProfile`, `RegionIndicatorPage`, рейтинги/сравнение, `regionsApi` | Region×indicator×year; месячный endpoint может законно404, без бесконечного retry. Heatmap/series отдельные keys; null не превращается в0. Axis formatting сокращает число, не меняет единицу. |
| Субнациональные регионы | `WorldRegionsHome`, `WorldRegionProfile`, `WorldRegionIndicatorPage`, world subnational API | Отдельный bounded context от RegionData РФ, официальные passports, country/region/code/mode в выборе. Не переносить российский parser/UI контракт автоматически. |
| Календарь/сегодня/демография | `CalendarPage`, `CalendarMonthPage`, `Today*`, `DemographicsPage`; hooks→API | Календарь — подтверждённые официальные события, не вычисленная новость. Пустая fast landing может404 по SSR, SPA и прямой HTTP различаются. Демография требует согласованной полной популяции/периода. |
| Калькуляторы | Inflation/Mortgage/Compound pages, чистые math libraries, CalcSlider | Вход/единицы/ставка/период и допущения видимы; график/таблица/экспорт используют одинаковый результат. Это вычисление по заданным условиям, не официальный факт ряда. |
| Identity/BI/выгрузка | `AuthProvider`, Login/Register/Account/AdminBI, `api.js`/`excel.js` | `/auth/me` guest401/403→null; UI admin flag не заменяет серверную проверку. Mutations CSRF; export Blob403→typed download_limit, remaining header может быть неизвестным. OAuth — полный переход с same-origin next. |
| Виджеты | 5 EmbedRoutes, builder, `Embed*`, SVG API | Отдельные Locale/ErrorBoundary/Suspense без обычного AuthProvider/consent/chrome; passive behavior выключен на /embed. Impression/auth/rate-limit проверяются сервером отдельно. |
| MCP аналитики | `mcp/forecast-analytics-mcp/src/index.ts`:7 registerTool → analytics HTTP API → stdio | URL/token берутся из process.env при старте; отсутствующий token — error. Zod ограничивает input; response text→JSON, non-ok/error JSON бросает exception. Собственных timeout/retry нет. `propose_analytics_action` записывает предложение, не применяет внешнее действие. |
| Ошибки/переходы/legacy | `NotFound`, `RedirectTo`, `NavigateKeepSearch`, sitePaths/legacy redirects | query сохраняется; специальные маршруты впереди `/:countrySlug`; неизвестный country/category и catchall —404/noindex. SPA annual path монтирует карточку, SSR годовая landing имеет собственный period contract. |

Для каждого файла подробные входы/выходы/эффекты/ошибки/зависимости/тесты находятся
в `reviews.jsonl`. Поиск по `file`, `owner`, `kind`, `line` в reconciliation JSON
ведёт к конкретному обработчику; перечень Routes в Markdown не требует чтения
многомегабайтного JSON. Рецепты индикатора и source/generated цепочка —
[agent-recipes](../agent-recipes.md), [playbook](../indicator-family-playbook.md)
и [contracts](../data-contracts.md).

## Общие транспортные и lifecycle ограничения

- Axios `/api/v1`, timeout15s, cookies, `X-FE-Locale`; mutating методы отправляют
  XSRF token. Network retry только GET и не auth, но 429/503 retry для non-auth
  **не ограничен GET**: POST export может повториться. Это установленное условие
  исходника, не доказанный production duplicate. TanStack может добавить retry.
- В `hooks.js` metadata/list локализованы в key; numerical point/stats/forecast
  keys имеют code/params и свои stale/gc времена. World/regions keys добавляют
  locale; server Redis TTL и browser staleTime — разные механизмы.
- Behavior telemetry не читает поля ввода, ограничивает путь/текст/выборки;
  ordinary failed batches могут теряться. Session-start подтверждается HTTPok;
  fetch timing wrapper не измеряет Axios XHR. Passive analytics, Metrika,
  admin analytics и bot/server requests не являются одной популяцией.
- LocalStorage/sessionStorage/события перечислены с key expressions и source
  anchor. Динамический key не вычисляется из пользовательских данных при анализе.
  Cookie/security/consent механизмы дополнительно описаны в рецензиях api/auth/
  locale/behavior, потому что не вся работа со storage является вызовом getItem.

## Связи Graphify

[Классификация всех пропусков](graph-omission-classification-2026-09-30.json)
сохраняет каждый исходный edge и anchor. 2476 missing_endpoint и 2224 endpoints
без owned file разобраны по import/type/dynamic/document/generated категориям.
9 ссылок на каталоги/extensionless Caddyfile Graphify кодирует как несуществующий
`.md` node; реальные ссылки существуют. 10 коллизий нормализованных `.md`/`.json`
targets сохраняются явно. Связь на внешний тип не означает пропущенную функцию
проекта. Внутрифайловые edges остаются в symbol graph; HTTP/БД/Redis lifecycle
подтверждается source inventories/contracts, а не придуманным callee.

## Проверка и границы

Source-only Babel:0 parse errors. 3 regression tests проверили anonymous owner,
Route/handler/storage, JSON import и отказ stale check после изменения маршрута;
также сохранение unresolved type и ambiguous document без выдуманного target.
Полный frontend test/build выполнен в предыдущем этапе на этих runtime исходниках:
924 tests/112files, build успешен; текущий интеграционный gate повторяется после
обновления всех карт. Браузерный visitor smoke и исполнение каждого callback’а
этим составным разбором не установлены. Это полное адресное сопоставление
доступного исходного клиента, а не доказательство отсутствия всех UI дефектов.
