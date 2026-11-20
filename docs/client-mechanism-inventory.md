# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 5194
- routes: 104
- functions: 16850
- hooks: 3050
- http: 134
- storage: 274
- events: 483
- jsx_handlers: 1334
- registries: 759
- mcp_tools: 7
- files: 997
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:260](../frontend/src/App.jsx#L260) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:261](../frontend/src/App.jsx#L261) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:262](../frontend/src/App.jsx#L262) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:263](../frontend/src/App.jsx#L263) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:264](../frontend/src/App.jsx#L264) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:319](../frontend/src/App.jsx#L319) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:320](../frontend/src/App.jsx#L320) | "/about" | {<About />} |
| [frontend/src/App.jsx:321](../frontend/src/App.jsx#L321) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:322](../frontend/src/App.jsx#L322) | "/research" | {<ResearchPage />} |
| [frontend/src/App.jsx:323](../frontend/src/App.jsx#L323) | "/research/:slug" | {<ResearchArticlePage />} |
| [frontend/src/App.jsx:324](../frontend/src/App.jsx#L324) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:326](../frontend/src/App.jsx#L326) | "/compare" | {<ComparePage renderSave={renderCompareSave} />} |
| [frontend/src/App.jsx:327](../frontend/src/App.jsx#L327) | "/forecasts" | {<ForecastsPage />} |
| [frontend/src/App.jsx:328](../frontend/src/App.jsx#L328) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:329](../frontend/src/App.jsx#L329) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:330](../frontend/src/App.jsx#L330) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:331](../frontend/src/App.jsx#L331) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/login" | {<Login />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/register" | {<Register />} |
| [frontend/src/App.jsx:334](../frontend/src/App.jsx#L334) | "/account" | {<Account />} |
| [frontend/src/App.jsx:335](../frontend/src/App.jsx#L335) | "/account/forgot-password" | {<ForgotPassword />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/account/reset-password" | {<ResetPassword />} |
| [frontend/src/App.jsx:337](../frontend/src/App.jsx#L337) | "/account/verify-email" | {<VerifyEmail />} |
| [frontend/src/App.jsx:338](../frontend/src/App.jsx#L338) | "/account/unsubscribe" | {<Unsubscribe />} |
| [frontend/src/App.jsx:339](../frontend/src/App.jsx#L339) | "/account/topic-confirm" | {<TopicConfirm />} |
| [frontend/src/App.jsx:340](../frontend/src/App.jsx#L340) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:343](../frontend/src/App.jsx#L343) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:344](../frontend/src/App.jsx#L344) | "/world/rating/:conceptSlug/:year?" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:346](../frontend/src/App.jsx#L346) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:347](../frontend/src/App.jsx#L347) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:348](../frontend/src/App.jsx#L348) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:351](../frontend/src/App.jsx#L351) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:352](../frontend/src/App.jsx#L352) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:353](../frontend/src/App.jsx#L353) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:354](../frontend/src/App.jsx#L354) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:355](../frontend/src/App.jsx#L355) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:356](../frontend/src/App.jsx#L356) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:357](../frontend/src/App.jsx#L357) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:358](../frontend/src/App.jsx#L358) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:359](../frontend/src/App.jsx#L359) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:360](../frontend/src/App.jsx#L360) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:361](../frontend/src/App.jsx#L361) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:362](../frontend/src/App.jsx#L362) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:363](../frontend/src/App.jsx#L363) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:364](../frontend/src/App.jsx#L364) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:365](../frontend/src/App.jsx#L365) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:366](../frontend/src/App.jsx#L366) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:367](../frontend/src/App.jsx#L367) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:370](../frontend/src/App.jsx#L370) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:371](../frontend/src/App.jsx#L371) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:372](../frontend/src/App.jsx#L372) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:373](../frontend/src/App.jsx#L373) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:376](../frontend/src/App.jsx#L376) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:377](../frontend/src/App.jsx#L377) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:378](../frontend/src/App.jsx#L378) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:379](../frontend/src/App.jsx#L379) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:382](../frontend/src/App.jsx#L382) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:383](../frontend/src/App.jsx#L383) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:384](../frontend/src/App.jsx#L384) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:386](../frontend/src/App.jsx#L386) | "/rankings" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:387](../frontend/src/App.jsx#L387) | "/ranking" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:388](../frontend/src/App.jsx#L388) | "/rankings/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:389](../frontend/src/App.jsx#L389) | "/ranking/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:390](../frontend/src/App.jsx#L390) | "/calculators" | {<NavigateKeepSearch to="/calculator" />} |
| [frontend/src/App.jsx:391](../frontend/src/App.jsx#L391) | "/calculators/*" | {<CalculatorsAlias />} |
| [frontend/src/App.jsx:392](../frontend/src/App.jsx#L392) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:393](../frontend/src/App.jsx#L393) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:394](../frontend/src/App.jsx#L394) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:395](../frontend/src/App.jsx#L395) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:396](../frontend/src/App.jsx#L396) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:397](../frontend/src/App.jsx#L397) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:398](../frontend/src/App.jsx#L398) | "/russia/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:399](../frontend/src/App.jsx#L399) | "/countries" | {<CountriesToHome />} |
| [frontend/src/App.jsx:400](../frontend/src/App.jsx#L400) | "/countries/:slug" | {<RedirectTo build={({ slug }) => countryPath(slug)} />} |
| [frontend/src/App.jsx:401](../frontend/src/App.jsx#L401) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:402](../frontend/src/App.jsx#L402) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:403](../frontend/src/App.jsx#L403) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:404](../frontend/src/App.jsx#L404) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:405](../frontend/src/App.jsx#L405) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:409](../frontend/src/App.jsx#L409) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:410](../frontend/src/App.jsx#L410) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:415](../frontend/src/App.jsx#L415) | "*" | {<NotFound />} |
| [frontend/src/components/IndicatorPage.w3.component.test.jsx:211](../frontend/src/components/IndicatorPage.w3.component.test.jsx#L211) | "/russia/indicator/:code/:year?" | {(
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
