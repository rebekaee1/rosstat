# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 4348
- routes: 94
- functions: 14176
- hooks: 2635
- http: 113
- storage: 215
- events: 440
- jsx_handlers: 1169
- registries: 667
- mcp_tools: 7
- files: 831
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:218](../frontend/src/App.jsx#L218) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:219](../frontend/src/App.jsx#L219) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:220](../frontend/src/App.jsx#L220) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:221](../frontend/src/App.jsx#L221) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:222](../frontend/src/App.jsx#L222) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:272](../frontend/src/App.jsx#L272) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:273](../frontend/src/App.jsx#L273) | "/about" | {<About />} |
| [frontend/src/App.jsx:274](../frontend/src/App.jsx#L274) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:275](../frontend/src/App.jsx#L275) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:276](../frontend/src/App.jsx#L276) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:277](../frontend/src/App.jsx#L277) | "/compare" | {<ComparePage renderSave={renderCompareSave} />} |
| [frontend/src/App.jsx:278](../frontend/src/App.jsx#L278) | "/forecasts" | {<ForecastsPage />} |
| [frontend/src/App.jsx:279](../frontend/src/App.jsx#L279) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:280](../frontend/src/App.jsx#L280) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:281](../frontend/src/App.jsx#L281) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:282](../frontend/src/App.jsx#L282) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:283](../frontend/src/App.jsx#L283) | "/login" | {<Login />} |
| [frontend/src/App.jsx:284](../frontend/src/App.jsx#L284) | "/register" | {<Register />} |
| [frontend/src/App.jsx:285](../frontend/src/App.jsx#L285) | "/account" | {<Account />} |
| [frontend/src/App.jsx:286](../frontend/src/App.jsx#L286) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:289](../frontend/src/App.jsx#L289) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:290](../frontend/src/App.jsx#L290) | "/world/rating/:conceptSlug/:year?" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:292](../frontend/src/App.jsx#L292) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:293](../frontend/src/App.jsx#L293) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:294](../frontend/src/App.jsx#L294) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:297](../frontend/src/App.jsx#L297) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:298](../frontend/src/App.jsx#L298) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:299](../frontend/src/App.jsx#L299) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:300](../frontend/src/App.jsx#L300) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:301](../frontend/src/App.jsx#L301) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:302](../frontend/src/App.jsx#L302) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:304](../frontend/src/App.jsx#L304) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:305](../frontend/src/App.jsx#L305) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:306](../frontend/src/App.jsx#L306) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:307](../frontend/src/App.jsx#L307) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:308](../frontend/src/App.jsx#L308) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:309](../frontend/src/App.jsx#L309) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:310](../frontend/src/App.jsx#L310) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:311](../frontend/src/App.jsx#L311) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:312](../frontend/src/App.jsx#L312) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:313](../frontend/src/App.jsx#L313) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:316](../frontend/src/App.jsx#L316) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:317](../frontend/src/App.jsx#L317) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:318](../frontend/src/App.jsx#L318) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:319](../frontend/src/App.jsx#L319) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:322](../frontend/src/App.jsx#L322) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:323](../frontend/src/App.jsx#L323) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:324](../frontend/src/App.jsx#L324) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:328](../frontend/src/App.jsx#L328) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:329](../frontend/src/App.jsx#L329) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:330](../frontend/src/App.jsx#L330) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/rankings" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/ranking" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:334](../frontend/src/App.jsx#L334) | "/rankings/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:335](../frontend/src/App.jsx#L335) | "/ranking/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/calculators" | {<NavigateKeepSearch to="/calculator" />} |
| [frontend/src/App.jsx:337](../frontend/src/App.jsx#L337) | "/calculators/*" | {<CalculatorsAlias />} |
| [frontend/src/App.jsx:338](../frontend/src/App.jsx#L338) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:339](../frontend/src/App.jsx#L339) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:340](../frontend/src/App.jsx#L340) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:341](../frontend/src/App.jsx#L341) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:342](../frontend/src/App.jsx#L342) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:343](../frontend/src/App.jsx#L343) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:344](../frontend/src/App.jsx#L344) | "/russia/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:345](../frontend/src/App.jsx#L345) | "/countries" | {<CountriesToHome />} |
| [frontend/src/App.jsx:346](../frontend/src/App.jsx#L346) | "/countries/:slug" | {<RedirectTo build={({ slug }) => countryPath(slug)} />} |
| [frontend/src/App.jsx:347](../frontend/src/App.jsx#L347) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:348](../frontend/src/App.jsx#L348) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:349](../frontend/src/App.jsx#L349) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:350](../frontend/src/App.jsx#L350) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:351](../frontend/src/App.jsx#L351) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:355](../frontend/src/App.jsx#L355) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:356](../frontend/src/App.jsx#L356) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:361](../frontend/src/App.jsx#L361) | "*" | {<NotFound />} |
| [frontend/src/components/IndicatorPage.w3.component.test.jsx:218](../frontend/src/components/IndicatorPage.w3.component.test.jsx#L218) | "/russia/indicator/:code/:year?" | {(
                <IndicatorDataTableSection
                  indicator={{ code: 'key-rate', frequency: 'daily', unit: '%', name: 'Ключевая ставка' }}
                  chartMode="cpi"
                  safeViewMode="level"
                  dataPoints={points}
                />
              )} |
| [frontend/src/pages/Account.test.jsx:59](../frontend/src/pages/Account.test.jsx#L59) | "/account" | {<Account />} |
| [frontend/src/pages/Account.test.jsx:60](../frontend/src/pages/Account.test.jsx#L60) | "/" | {<p>Home after success</p>} |
| [frontend/src/pages/AuthForms.analytics.component.test.jsx:46](../frontend/src/pages/AuthForms.analytics.component.test.jsx#L46) | "/register" | {<Register />} |
| [frontend/src/pages/AuthForms.analytics.component.test.jsx:46](../frontend/src/pages/AuthForms.analytics.component.test.jsx#L46) | "*" | {<span>next</span>} |
| [frontend/src/pages/AuthForms.analytics.component.test.jsx:51](../frontend/src/pages/AuthForms.analytics.component.test.jsx#L51) | "/login" | {<Login />} |
| [frontend/src/pages/AuthForms.analytics.component.test.jsx:51](../frontend/src/pages/AuthForms.analytics.component.test.jsx#L51) | "*" | {<span>next</span>} |
| [frontend/src/pages/AuthReturn.test.jsx:18](../frontend/src/pages/AuthReturn.test.jsx#L18) | {`/${page}`} | {<Component />} |
| [frontend/src/pages/AuthReturn.test.jsx:18](../frontend/src/pages/AuthReturn.test.jsx#L18) | "/indicator/cpi" | {<Destination />} |
| [frontend/src/pages/Login.component.test.jsx:25](../frontend/src/pages/Login.component.test.jsx#L25) | "/login" | {<Login />} |
| [frontend/src/pages/Register.component.test.jsx:35](../frontend/src/pages/Register.component.test.jsx#L35) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:36](../frontend/src/pages/Register.component.test.jsx#L36) | "/world/rating/gdp-usd" | {<span>destination</span>} |
| [frontend/src/pages/Register.component.test.jsx:52](../frontend/src/pages/Register.component.test.jsx#L52) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:59](../frontend/src/pages/Register.component.test.jsx#L59) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:73](../frontend/src/pages/Register.component.test.jsx#L73) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:108](../frontend/src/pages/Register.component.test.jsx#L108) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:127](../frontend/src/pages/Register.component.test.jsx#L127) | "/register" | {<Register />} |
| [frontend/src/test/renderPage.jsx:36](../frontend/src/test/renderPage.jsx#L36) | {path} | {ui} |

## Границы

- Expressions are preserved, not evaluated. A declaration is not proof of mounting, execution or UI acceptance.
- Anonymous callbacks have enclosing source anchors; semantic review remains in the source ledger.
- Hook/state/HTTP/storage/event/JSX call sites are syntactic inventories, not a runtime dependency graph.
