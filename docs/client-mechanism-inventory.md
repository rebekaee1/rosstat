# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 5085
- routes: 103
- functions: 16393
- hooks: 3013
- http: 132
- storage: 259
- events: 478
- jsx_handlers: 1332
- registries: 747
- mcp_tools: 7
- files: 968
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:238](../frontend/src/App.jsx#L238) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:239](../frontend/src/App.jsx#L239) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:240](../frontend/src/App.jsx#L240) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:241](../frontend/src/App.jsx#L241) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:242](../frontend/src/App.jsx#L242) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:294](../frontend/src/App.jsx#L294) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:295](../frontend/src/App.jsx#L295) | "/about" | {<About />} |
| [frontend/src/App.jsx:296](../frontend/src/App.jsx#L296) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:297](../frontend/src/App.jsx#L297) | "/research" | {<ResearchPage />} |
| [frontend/src/App.jsx:298](../frontend/src/App.jsx#L298) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:299](../frontend/src/App.jsx#L299) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:300](../frontend/src/App.jsx#L300) | "/compare" | {<ComparePage renderSave={renderCompareSave} />} |
| [frontend/src/App.jsx:301](../frontend/src/App.jsx#L301) | "/forecasts" | {<ForecastsPage />} |
| [frontend/src/App.jsx:302](../frontend/src/App.jsx#L302) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:304](../frontend/src/App.jsx#L304) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:305](../frontend/src/App.jsx#L305) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:306](../frontend/src/App.jsx#L306) | "/login" | {<Login />} |
| [frontend/src/App.jsx:307](../frontend/src/App.jsx#L307) | "/register" | {<Register />} |
| [frontend/src/App.jsx:308](../frontend/src/App.jsx#L308) | "/account" | {<Account />} |
| [frontend/src/App.jsx:309](../frontend/src/App.jsx#L309) | "/account/forgot-password" | {<ForgotPassword />} |
| [frontend/src/App.jsx:310](../frontend/src/App.jsx#L310) | "/account/reset-password" | {<ResetPassword />} |
| [frontend/src/App.jsx:311](../frontend/src/App.jsx#L311) | "/account/verify-email" | {<VerifyEmail />} |
| [frontend/src/App.jsx:312](../frontend/src/App.jsx#L312) | "/account/unsubscribe" | {<Unsubscribe />} |
| [frontend/src/App.jsx:313](../frontend/src/App.jsx#L313) | "/account/topic-confirm" | {<TopicConfirm />} |
| [frontend/src/App.jsx:314](../frontend/src/App.jsx#L314) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:317](../frontend/src/App.jsx#L317) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:318](../frontend/src/App.jsx#L318) | "/world/rating/:conceptSlug/:year?" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:320](../frontend/src/App.jsx#L320) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:321](../frontend/src/App.jsx#L321) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:322](../frontend/src/App.jsx#L322) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:326](../frontend/src/App.jsx#L326) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:327](../frontend/src/App.jsx#L327) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:328](../frontend/src/App.jsx#L328) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:329](../frontend/src/App.jsx#L329) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:330](../frontend/src/App.jsx#L330) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:331](../frontend/src/App.jsx#L331) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:334](../frontend/src/App.jsx#L334) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:335](../frontend/src/App.jsx#L335) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:337](../frontend/src/App.jsx#L337) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:338](../frontend/src/App.jsx#L338) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:339](../frontend/src/App.jsx#L339) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:340](../frontend/src/App.jsx#L340) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:341](../frontend/src/App.jsx#L341) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:344](../frontend/src/App.jsx#L344) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:345](../frontend/src/App.jsx#L345) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:346](../frontend/src/App.jsx#L346) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:347](../frontend/src/App.jsx#L347) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:350](../frontend/src/App.jsx#L350) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:351](../frontend/src/App.jsx#L351) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:352](../frontend/src/App.jsx#L352) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:353](../frontend/src/App.jsx#L353) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:356](../frontend/src/App.jsx#L356) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:357](../frontend/src/App.jsx#L357) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:358](../frontend/src/App.jsx#L358) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:360](../frontend/src/App.jsx#L360) | "/rankings" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:361](../frontend/src/App.jsx#L361) | "/ranking" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:362](../frontend/src/App.jsx#L362) | "/rankings/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:363](../frontend/src/App.jsx#L363) | "/ranking/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:364](../frontend/src/App.jsx#L364) | "/calculators" | {<NavigateKeepSearch to="/calculator" />} |
| [frontend/src/App.jsx:365](../frontend/src/App.jsx#L365) | "/calculators/*" | {<CalculatorsAlias />} |
| [frontend/src/App.jsx:366](../frontend/src/App.jsx#L366) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:367](../frontend/src/App.jsx#L367) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:368](../frontend/src/App.jsx#L368) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:369](../frontend/src/App.jsx#L369) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:370](../frontend/src/App.jsx#L370) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:371](../frontend/src/App.jsx#L371) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:372](../frontend/src/App.jsx#L372) | "/russia/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:373](../frontend/src/App.jsx#L373) | "/countries" | {<CountriesToHome />} |
| [frontend/src/App.jsx:374](../frontend/src/App.jsx#L374) | "/countries/:slug" | {<RedirectTo build={({ slug }) => countryPath(slug)} />} |
| [frontend/src/App.jsx:375](../frontend/src/App.jsx#L375) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:376](../frontend/src/App.jsx#L376) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:377](../frontend/src/App.jsx#L377) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:378](../frontend/src/App.jsx#L378) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:379](../frontend/src/App.jsx#L379) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:383](../frontend/src/App.jsx#L383) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:384](../frontend/src/App.jsx#L384) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:389](../frontend/src/App.jsx#L389) | "*" | {<NotFound />} |
| [frontend/src/components/IndicatorPage.w3.component.test.jsx:218](../frontend/src/components/IndicatorPage.w3.component.test.jsx#L218) | "/russia/indicator/:code/:year?" | {(
                <IndicatorDataTableSection
                  indicator={{ code: 'key-rate', frequency: 'daily', unit: '%', name: 'Ключевая ставка' }}
                  chartMode="cpi"
                  safeViewMode="level"
                  dataPoints={points}
                />
              )} |
| [frontend/src/components/TopicMailForm.component.test.jsx:110](../frontend/src/components/TopicMailForm.component.test.jsx#L110) | "/account/topic-confirm" | {<TopicConfirm />} |
| [frontend/src/components/TopicMailForm.component.test.jsx:123](../frontend/src/components/TopicMailForm.component.test.jsx#L123) | "/account/topic-confirm" | {<TopicConfirm />} |
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
| [frontend/src/pages/Register.component.test.jsx:36](../frontend/src/pages/Register.component.test.jsx#L36) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:37](../frontend/src/pages/Register.component.test.jsx#L37) | "/world/rating/gdp-usd" | {<span>destination</span>} |
| [frontend/src/pages/Register.component.test.jsx:53](../frontend/src/pages/Register.component.test.jsx#L53) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:60](../frontend/src/pages/Register.component.test.jsx#L60) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:74](../frontend/src/pages/Register.component.test.jsx#L74) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:109](../frontend/src/pages/Register.component.test.jsx#L109) | "/register" | {<Register />} |
| [frontend/src/pages/Register.component.test.jsx:128](../frontend/src/pages/Register.component.test.jsx#L128) | "/register" | {<Register />} |
| [frontend/src/test/renderPage.jsx:36](../frontend/src/test/renderPage.jsx#L36) | {path} | {ui} |

## Границы

- Expressions are preserved, not evaluated. A declaration is not proof of mounting, execution or UI acceptance.
- Anonymous callbacks have enclosing source anchors; semantic review remains in the source ledger.
- Hook/state/HTTP/storage/event/JSX call sites are syntactic inventories, not a runtime dependency graph.
