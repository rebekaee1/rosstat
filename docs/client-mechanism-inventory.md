# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 1856
- routes: 72
- functions: 6510
- hooks: 1488
- http: 80
- storage: 56
- events: 160
- jsx_handlers: 631
- registries: 327
- mcp_tools: 7
- files: 381
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:230](../frontend/src/App.jsx#L230) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:231](../frontend/src/App.jsx#L231) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:232](../frontend/src/App.jsx#L232) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:233](../frontend/src/App.jsx#L233) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:234](../frontend/src/App.jsx#L234) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:275](../frontend/src/App.jsx#L275) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:276](../frontend/src/App.jsx#L276) | "/about" | {<About />} |
| [frontend/src/App.jsx:277](../frontend/src/App.jsx#L277) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:278](../frontend/src/App.jsx#L278) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:279](../frontend/src/App.jsx#L279) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:280](../frontend/src/App.jsx#L280) | "/compare" | {<ComparePage />} |
| [frontend/src/App.jsx:281](../frontend/src/App.jsx#L281) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:282](../frontend/src/App.jsx#L282) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:283](../frontend/src/App.jsx#L283) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:284](../frontend/src/App.jsx#L284) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:285](../frontend/src/App.jsx#L285) | "/login" | {<Login />} |
| [frontend/src/App.jsx:286](../frontend/src/App.jsx#L286) | "/register" | {<Register />} |
| [frontend/src/App.jsx:287](../frontend/src/App.jsx#L287) | "/account" | {<Account />} |
| [frontend/src/App.jsx:288](../frontend/src/App.jsx#L288) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:291](../frontend/src/App.jsx#L291) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:292](../frontend/src/App.jsx#L292) | "/world/rating/:conceptSlug" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:294](../frontend/src/App.jsx#L294) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:295](../frontend/src/App.jsx#L295) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:296](../frontend/src/App.jsx#L296) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:299](../frontend/src/App.jsx#L299) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:300](../frontend/src/App.jsx#L300) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:301](../frontend/src/App.jsx#L301) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:302](../frontend/src/App.jsx#L302) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:304](../frontend/src/App.jsx#L304) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:305](../frontend/src/App.jsx#L305) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:306](../frontend/src/App.jsx#L306) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:307](../frontend/src/App.jsx#L307) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:308](../frontend/src/App.jsx#L308) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:309](../frontend/src/App.jsx#L309) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:310](../frontend/src/App.jsx#L310) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:311](../frontend/src/App.jsx#L311) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:312](../frontend/src/App.jsx#L312) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:313](../frontend/src/App.jsx#L313) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:314](../frontend/src/App.jsx#L314) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:315](../frontend/src/App.jsx#L315) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:318](../frontend/src/App.jsx#L318) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:319](../frontend/src/App.jsx#L319) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:320](../frontend/src/App.jsx#L320) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:321](../frontend/src/App.jsx#L321) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:324](../frontend/src/App.jsx#L324) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:326](../frontend/src/App.jsx#L326) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:327](../frontend/src/App.jsx#L327) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:330](../frontend/src/App.jsx#L330) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:331](../frontend/src/App.jsx#L331) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:334](../frontend/src/App.jsx#L334) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:335](../frontend/src/App.jsx#L335) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:337](../frontend/src/App.jsx#L337) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:338](../frontend/src/App.jsx#L338) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:339](../frontend/src/App.jsx#L339) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:340](../frontend/src/App.jsx#L340) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:341](../frontend/src/App.jsx#L341) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:342](../frontend/src/App.jsx#L342) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:343](../frontend/src/App.jsx#L343) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:347](../frontend/src/App.jsx#L347) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:348](../frontend/src/App.jsx#L348) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:353](../frontend/src/App.jsx#L353) | "*" | {<NotFound />} |
| [frontend/src/pages/Account.test.jsx:18](../frontend/src/pages/Account.test.jsx#L18) | "/account" | {<Account />} |
| [frontend/src/pages/Account.test.jsx:18](../frontend/src/pages/Account.test.jsx#L18) | "/" | {<p>Home after success</p>} |
| [frontend/src/pages/AuthReturn.test.jsx:18](../frontend/src/pages/AuthReturn.test.jsx#L18) | {`/${page}`} | {<Component />} |
| [frontend/src/pages/AuthReturn.test.jsx:18](../frontend/src/pages/AuthReturn.test.jsx#L18) | "/indicator/cpi" | {<Destination />} |
| [frontend/src/pages/Register.component.test.jsx:32](../frontend/src/pages/Register.component.test.jsx#L32) | "/register" | {<Register />} |
| [frontend/src/test/renderPage.jsx:36](../frontend/src/test/renderPage.jsx#L36) | {path} | {ui} |

## Границы

- Expressions are preserved, not evaluated. A declaration is not proof of mounting, execution or UI acceptance.
- Anonymous callbacks have enclosing source anchors; semantic review remains in the source ledger.
- Hook/state/HTTP/storage/event/JSX call sites are syntactic inventories, not a runtime dependency graph.
