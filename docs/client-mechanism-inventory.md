# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 3711
- routes: 90
- functions: 11838
- hooks: 2271
- http: 91
- storage: 113
- events: 348
- jsx_handlers: 1014
- registries: 573
- mcp_tools: 7
- files: 697
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:215](../frontend/src/App.jsx#L215) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:216](../frontend/src/App.jsx#L216) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:217](../frontend/src/App.jsx#L217) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:218](../frontend/src/App.jsx#L218) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:219](../frontend/src/App.jsx#L219) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:262](../frontend/src/App.jsx#L262) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:263](../frontend/src/App.jsx#L263) | "/about" | {<About />} |
| [frontend/src/App.jsx:264](../frontend/src/App.jsx#L264) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:265](../frontend/src/App.jsx#L265) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:266](../frontend/src/App.jsx#L266) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:267](../frontend/src/App.jsx#L267) | "/compare" | {<ComparePage />} |
| [frontend/src/App.jsx:268](../frontend/src/App.jsx#L268) | "/forecasts" | {<ForecastsPage />} |
| [frontend/src/App.jsx:269](../frontend/src/App.jsx#L269) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:270](../frontend/src/App.jsx#L270) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:271](../frontend/src/App.jsx#L271) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:272](../frontend/src/App.jsx#L272) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:273](../frontend/src/App.jsx#L273) | "/login" | {<Login />} |
| [frontend/src/App.jsx:274](../frontend/src/App.jsx#L274) | "/register" | {<Register />} |
| [frontend/src/App.jsx:275](../frontend/src/App.jsx#L275) | "/account" | {<Account />} |
| [frontend/src/App.jsx:276](../frontend/src/App.jsx#L276) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:279](../frontend/src/App.jsx#L279) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:280](../frontend/src/App.jsx#L280) | "/world/rating/:conceptSlug/:year?" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:282](../frontend/src/App.jsx#L282) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:283](../frontend/src/App.jsx#L283) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:284](../frontend/src/App.jsx#L284) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:287](../frontend/src/App.jsx#L287) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:288](../frontend/src/App.jsx#L288) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:289](../frontend/src/App.jsx#L289) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:290](../frontend/src/App.jsx#L290) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:291](../frontend/src/App.jsx#L291) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:292](../frontend/src/App.jsx#L292) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:293](../frontend/src/App.jsx#L293) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:294](../frontend/src/App.jsx#L294) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:295](../frontend/src/App.jsx#L295) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:296](../frontend/src/App.jsx#L296) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:297](../frontend/src/App.jsx#L297) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:298](../frontend/src/App.jsx#L298) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:299](../frontend/src/App.jsx#L299) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:300](../frontend/src/App.jsx#L300) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:301](../frontend/src/App.jsx#L301) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:302](../frontend/src/App.jsx#L302) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:306](../frontend/src/App.jsx#L306) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:307](../frontend/src/App.jsx#L307) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:308](../frontend/src/App.jsx#L308) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:309](../frontend/src/App.jsx#L309) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:312](../frontend/src/App.jsx#L312) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:313](../frontend/src/App.jsx#L313) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:314](../frontend/src/App.jsx#L314) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:315](../frontend/src/App.jsx#L315) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:318](../frontend/src/App.jsx#L318) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:319](../frontend/src/App.jsx#L319) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:320](../frontend/src/App.jsx#L320) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:322](../frontend/src/App.jsx#L322) | "/rankings" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:323](../frontend/src/App.jsx#L323) | "/ranking" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:324](../frontend/src/App.jsx#L324) | "/rankings/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/ranking/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:326](../frontend/src/App.jsx#L326) | "/calculators" | {<NavigateKeepSearch to="/calculator" />} |
| [frontend/src/App.jsx:327](../frontend/src/App.jsx#L327) | "/calculators/*" | {<CalculatorsAlias />} |
| [frontend/src/App.jsx:328](../frontend/src/App.jsx#L328) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:329](../frontend/src/App.jsx#L329) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:330](../frontend/src/App.jsx#L330) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:331](../frontend/src/App.jsx#L331) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:334](../frontend/src/App.jsx#L334) | "/russia/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:335](../frontend/src/App.jsx#L335) | "/countries" | {<CountriesToHome />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/countries/:slug" | {<RedirectTo build={({ slug }) => countryPath(slug)} />} |
| [frontend/src/App.jsx:337](../frontend/src/App.jsx#L337) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:338](../frontend/src/App.jsx#L338) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:339](../frontend/src/App.jsx#L339) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:340](../frontend/src/App.jsx#L340) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:341](../frontend/src/App.jsx#L341) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:345](../frontend/src/App.jsx#L345) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:346](../frontend/src/App.jsx#L346) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:351](../frontend/src/App.jsx#L351) | "*" | {<NotFound />} |
| [frontend/src/components/IndicatorPage.w3.component.test.jsx:218](../frontend/src/components/IndicatorPage.w3.component.test.jsx#L218) | "/russia/indicator/:code/:year?" | {(
                <IndicatorDataTableSection
                  indicator={{ code: 'key-rate', frequency: 'daily', unit: '%', name: 'Ключевая ставка' }}
                  chartMode="cpi"
                  safeViewMode="level"
                  dataPoints={points}
                />
              )} |
| [frontend/src/pages/Account.test.jsx:18](../frontend/src/pages/Account.test.jsx#L18) | "/account" | {<Account />} |
| [frontend/src/pages/Account.test.jsx:18](../frontend/src/pages/Account.test.jsx#L18) | "/" | {<p>Home after success</p>} |
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
