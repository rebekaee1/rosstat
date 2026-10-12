# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 4374
- routes: 94
- functions: 14243
- hooks: 2645
- http: 113
- storage: 216
- events: 445
- jsx_handlers: 1170
- registries: 669
- mcp_tools: 7
- files: 836
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:219](../frontend/src/App.jsx#L219) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:220](../frontend/src/App.jsx#L220) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:221](../frontend/src/App.jsx#L221) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:222](../frontend/src/App.jsx#L222) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:223](../frontend/src/App.jsx#L223) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:275](../frontend/src/App.jsx#L275) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:276](../frontend/src/App.jsx#L276) | "/about" | {<About />} |
| [frontend/src/App.jsx:277](../frontend/src/App.jsx#L277) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:278](../frontend/src/App.jsx#L278) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:279](../frontend/src/App.jsx#L279) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:280](../frontend/src/App.jsx#L280) | "/compare" | {<ComparePage renderSave={renderCompareSave} />} |
| [frontend/src/App.jsx:281](../frontend/src/App.jsx#L281) | "/forecasts" | {<ForecastsPage />} |
| [frontend/src/App.jsx:282](../frontend/src/App.jsx#L282) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:283](../frontend/src/App.jsx#L283) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:284](../frontend/src/App.jsx#L284) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:285](../frontend/src/App.jsx#L285) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:286](../frontend/src/App.jsx#L286) | "/login" | {<Login />} |
| [frontend/src/App.jsx:287](../frontend/src/App.jsx#L287) | "/register" | {<Register />} |
| [frontend/src/App.jsx:288](../frontend/src/App.jsx#L288) | "/account" | {<Account />} |
| [frontend/src/App.jsx:289](../frontend/src/App.jsx#L289) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:292](../frontend/src/App.jsx#L292) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:293](../frontend/src/App.jsx#L293) | "/world/rating/:conceptSlug/:year?" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:295](../frontend/src/App.jsx#L295) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:296](../frontend/src/App.jsx#L296) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:297](../frontend/src/App.jsx#L297) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:300](../frontend/src/App.jsx#L300) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:301](../frontend/src/App.jsx#L301) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:302](../frontend/src/App.jsx#L302) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:304](../frontend/src/App.jsx#L304) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:305](../frontend/src/App.jsx#L305) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:306](../frontend/src/App.jsx#L306) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:307](../frontend/src/App.jsx#L307) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:308](../frontend/src/App.jsx#L308) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:309](../frontend/src/App.jsx#L309) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:310](../frontend/src/App.jsx#L310) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:311](../frontend/src/App.jsx#L311) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:312](../frontend/src/App.jsx#L312) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:313](../frontend/src/App.jsx#L313) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:314](../frontend/src/App.jsx#L314) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:315](../frontend/src/App.jsx#L315) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:316](../frontend/src/App.jsx#L316) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:319](../frontend/src/App.jsx#L319) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:320](../frontend/src/App.jsx#L320) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:321](../frontend/src/App.jsx#L321) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:322](../frontend/src/App.jsx#L322) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:326](../frontend/src/App.jsx#L326) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:327](../frontend/src/App.jsx#L327) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:328](../frontend/src/App.jsx#L328) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:331](../frontend/src/App.jsx#L331) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:335](../frontend/src/App.jsx#L335) | "/rankings" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/ranking" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:337](../frontend/src/App.jsx#L337) | "/rankings/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:338](../frontend/src/App.jsx#L338) | "/ranking/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:339](../frontend/src/App.jsx#L339) | "/calculators" | {<NavigateKeepSearch to="/calculator" />} |
| [frontend/src/App.jsx:340](../frontend/src/App.jsx#L340) | "/calculators/*" | {<CalculatorsAlias />} |
| [frontend/src/App.jsx:341](../frontend/src/App.jsx#L341) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:342](../frontend/src/App.jsx#L342) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:343](../frontend/src/App.jsx#L343) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:344](../frontend/src/App.jsx#L344) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:345](../frontend/src/App.jsx#L345) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:346](../frontend/src/App.jsx#L346) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:347](../frontend/src/App.jsx#L347) | "/russia/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:348](../frontend/src/App.jsx#L348) | "/countries" | {<CountriesToHome />} |
| [frontend/src/App.jsx:349](../frontend/src/App.jsx#L349) | "/countries/:slug" | {<RedirectTo build={({ slug }) => countryPath(slug)} />} |
| [frontend/src/App.jsx:350](../frontend/src/App.jsx#L350) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:351](../frontend/src/App.jsx#L351) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:352](../frontend/src/App.jsx#L352) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:353](../frontend/src/App.jsx#L353) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:354](../frontend/src/App.jsx#L354) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:358](../frontend/src/App.jsx#L358) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:359](../frontend/src/App.jsx#L359) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:364](../frontend/src/App.jsx#L364) | "*" | {<NotFound />} |
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
