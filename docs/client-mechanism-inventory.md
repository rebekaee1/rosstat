# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 4873
- routes: 100
- functions: 15511
- hooks: 2867
- http: 127
- storage: 244
- events: 458
- jsx_handlers: 1258
- registries: 719
- mcp_tools: 7
- files: 922
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:225](../frontend/src/App.jsx#L225) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:226](../frontend/src/App.jsx#L226) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:227](../frontend/src/App.jsx#L227) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:228](../frontend/src/App.jsx#L228) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:229](../frontend/src/App.jsx#L229) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:281](../frontend/src/App.jsx#L281) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:282](../frontend/src/App.jsx#L282) | "/about" | {<About />} |
| [frontend/src/App.jsx:283](../frontend/src/App.jsx#L283) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:284](../frontend/src/App.jsx#L284) | "/research" | {<ResearchPage />} |
| [frontend/src/App.jsx:285](../frontend/src/App.jsx#L285) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:286](../frontend/src/App.jsx#L286) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:287](../frontend/src/App.jsx#L287) | "/compare" | {<ComparePage renderSave={renderCompareSave} />} |
| [frontend/src/App.jsx:288](../frontend/src/App.jsx#L288) | "/forecasts" | {<ForecastsPage />} |
| [frontend/src/App.jsx:289](../frontend/src/App.jsx#L289) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:290](../frontend/src/App.jsx#L290) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:291](../frontend/src/App.jsx#L291) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:292](../frontend/src/App.jsx#L292) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:293](../frontend/src/App.jsx#L293) | "/login" | {<Login />} |
| [frontend/src/App.jsx:294](../frontend/src/App.jsx#L294) | "/register" | {<Register />} |
| [frontend/src/App.jsx:295](../frontend/src/App.jsx#L295) | "/account" | {<Account />} |
| [frontend/src/App.jsx:296](../frontend/src/App.jsx#L296) | "/account/forgot-password" | {<ForgotPassword />} |
| [frontend/src/App.jsx:297](../frontend/src/App.jsx#L297) | "/account/reset-password" | {<ResetPassword />} |
| [frontend/src/App.jsx:298](../frontend/src/App.jsx#L298) | "/account/verify-email" | {<VerifyEmail />} |
| [frontend/src/App.jsx:299](../frontend/src/App.jsx#L299) | "/account/unsubscribe" | {<Unsubscribe />} |
| [frontend/src/App.jsx:300](../frontend/src/App.jsx#L300) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:304](../frontend/src/App.jsx#L304) | "/world/rating/:conceptSlug/:year?" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:306](../frontend/src/App.jsx#L306) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:307](../frontend/src/App.jsx#L307) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:308](../frontend/src/App.jsx#L308) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:311](../frontend/src/App.jsx#L311) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:312](../frontend/src/App.jsx#L312) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:313](../frontend/src/App.jsx#L313) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:314](../frontend/src/App.jsx#L314) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:315](../frontend/src/App.jsx#L315) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:316](../frontend/src/App.jsx#L316) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:317](../frontend/src/App.jsx#L317) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:318](../frontend/src/App.jsx#L318) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:319](../frontend/src/App.jsx#L319) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:320](../frontend/src/App.jsx#L320) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:321](../frontend/src/App.jsx#L321) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:322](../frontend/src/App.jsx#L322) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:323](../frontend/src/App.jsx#L323) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:324](../frontend/src/App.jsx#L324) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:326](../frontend/src/App.jsx#L326) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:327](../frontend/src/App.jsx#L327) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:330](../frontend/src/App.jsx#L330) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:331](../frontend/src/App.jsx#L331) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:337](../frontend/src/App.jsx#L337) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:338](../frontend/src/App.jsx#L338) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:339](../frontend/src/App.jsx#L339) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:342](../frontend/src/App.jsx#L342) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:343](../frontend/src/App.jsx#L343) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:344](../frontend/src/App.jsx#L344) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:346](../frontend/src/App.jsx#L346) | "/rankings" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:347](../frontend/src/App.jsx#L347) | "/ranking" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:348](../frontend/src/App.jsx#L348) | "/rankings/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:349](../frontend/src/App.jsx#L349) | "/ranking/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:350](../frontend/src/App.jsx#L350) | "/calculators" | {<NavigateKeepSearch to="/calculator" />} |
| [frontend/src/App.jsx:351](../frontend/src/App.jsx#L351) | "/calculators/*" | {<CalculatorsAlias />} |
| [frontend/src/App.jsx:352](../frontend/src/App.jsx#L352) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:353](../frontend/src/App.jsx#L353) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:354](../frontend/src/App.jsx#L354) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:355](../frontend/src/App.jsx#L355) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:356](../frontend/src/App.jsx#L356) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:357](../frontend/src/App.jsx#L357) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:358](../frontend/src/App.jsx#L358) | "/russia/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:359](../frontend/src/App.jsx#L359) | "/countries" | {<CountriesToHome />} |
| [frontend/src/App.jsx:360](../frontend/src/App.jsx#L360) | "/countries/:slug" | {<RedirectTo build={({ slug }) => countryPath(slug)} />} |
| [frontend/src/App.jsx:361](../frontend/src/App.jsx#L361) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:362](../frontend/src/App.jsx#L362) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:363](../frontend/src/App.jsx#L363) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:364](../frontend/src/App.jsx#L364) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:365](../frontend/src/App.jsx#L365) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:369](../frontend/src/App.jsx#L369) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:370](../frontend/src/App.jsx#L370) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:375](../frontend/src/App.jsx#L375) | "*" | {<NotFound />} |
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
| [frontend/src/pages/AccountMail.component.test.jsx:26](../frontend/src/pages/AccountMail.component.test.jsx#L26) | {path.split('?')[0]} | {element} |
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
