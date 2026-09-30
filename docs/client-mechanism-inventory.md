# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 1707
- routes: 72
- functions: 5376
- hooks: 1339
- http: 64
- storage: 29
- events: 105
- jsx_handlers: 555
- registries: 316
- mcp_tools: 7
- files: 351
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:228](../frontend/src/App.jsx#L228) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:229](../frontend/src/App.jsx#L229) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:230](../frontend/src/App.jsx#L230) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:231](../frontend/src/App.jsx#L231) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:232](../frontend/src/App.jsx#L232) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:270](../frontend/src/App.jsx#L270) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:271](../frontend/src/App.jsx#L271) | "/about" | {<About />} |
| [frontend/src/App.jsx:272](../frontend/src/App.jsx#L272) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:273](../frontend/src/App.jsx#L273) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:274](../frontend/src/App.jsx#L274) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:275](../frontend/src/App.jsx#L275) | "/compare" | {<ComparePage />} |
| [frontend/src/App.jsx:276](../frontend/src/App.jsx#L276) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:277](../frontend/src/App.jsx#L277) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:278](../frontend/src/App.jsx#L278) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:279](../frontend/src/App.jsx#L279) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:280](../frontend/src/App.jsx#L280) | "/login" | {<Login />} |
| [frontend/src/App.jsx:281](../frontend/src/App.jsx#L281) | "/register" | {<Register />} |
| [frontend/src/App.jsx:282](../frontend/src/App.jsx#L282) | "/account" | {<Account />} |
| [frontend/src/App.jsx:283](../frontend/src/App.jsx#L283) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:286](../frontend/src/App.jsx#L286) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:287](../frontend/src/App.jsx#L287) | "/world/rating/:conceptSlug" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:289](../frontend/src/App.jsx#L289) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:290](../frontend/src/App.jsx#L290) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:291](../frontend/src/App.jsx#L291) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:294](../frontend/src/App.jsx#L294) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:295](../frontend/src/App.jsx#L295) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:296](../frontend/src/App.jsx#L296) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:297](../frontend/src/App.jsx#L297) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:298](../frontend/src/App.jsx#L298) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:299](../frontend/src/App.jsx#L299) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:300](../frontend/src/App.jsx#L300) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:301](../frontend/src/App.jsx#L301) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:302](../frontend/src/App.jsx#L302) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:304](../frontend/src/App.jsx#L304) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:305](../frontend/src/App.jsx#L305) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:306](../frontend/src/App.jsx#L306) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:307](../frontend/src/App.jsx#L307) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:308](../frontend/src/App.jsx#L308) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:309](../frontend/src/App.jsx#L309) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:310](../frontend/src/App.jsx#L310) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:313](../frontend/src/App.jsx#L313) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:314](../frontend/src/App.jsx#L314) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:315](../frontend/src/App.jsx#L315) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:316](../frontend/src/App.jsx#L316) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:319](../frontend/src/App.jsx#L319) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:320](../frontend/src/App.jsx#L320) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:321](../frontend/src/App.jsx#L321) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:322](../frontend/src/App.jsx#L322) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:326](../frontend/src/App.jsx#L326) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:327](../frontend/src/App.jsx#L327) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:328](../frontend/src/App.jsx#L328) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:329](../frontend/src/App.jsx#L329) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:330](../frontend/src/App.jsx#L330) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:331](../frontend/src/App.jsx#L331) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:334](../frontend/src/App.jsx#L334) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:335](../frontend/src/App.jsx#L335) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:337](../frontend/src/App.jsx#L337) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:338](../frontend/src/App.jsx#L338) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:342](../frontend/src/App.jsx#L342) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:343](../frontend/src/App.jsx#L343) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:348](../frontend/src/App.jsx#L348) | "*" | {<NotFound />} |
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
