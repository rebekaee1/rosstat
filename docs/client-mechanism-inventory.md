# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 3393
- routes: 89
- functions: 10765
- hooks: 2168
- http: 91
- storage: 84
- events: 296
- jsx_handlers: 972
- registries: 533
- mcp_tools: 7
- files: 638
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:213](../frontend/src/App.jsx#L213) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:214](../frontend/src/App.jsx#L214) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:215](../frontend/src/App.jsx#L215) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:216](../frontend/src/App.jsx#L216) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:217](../frontend/src/App.jsx#L217) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:257](../frontend/src/App.jsx#L257) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:258](../frontend/src/App.jsx#L258) | "/about" | {<About />} |
| [frontend/src/App.jsx:259](../frontend/src/App.jsx#L259) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:260](../frontend/src/App.jsx#L260) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:261](../frontend/src/App.jsx#L261) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:262](../frontend/src/App.jsx#L262) | "/compare" | {<ComparePage />} |
| [frontend/src/App.jsx:263](../frontend/src/App.jsx#L263) | "/forecasts" | {<ForecastsPage />} |
| [frontend/src/App.jsx:264](../frontend/src/App.jsx#L264) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:265](../frontend/src/App.jsx#L265) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:266](../frontend/src/App.jsx#L266) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:267](../frontend/src/App.jsx#L267) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:268](../frontend/src/App.jsx#L268) | "/login" | {<Login />} |
| [frontend/src/App.jsx:269](../frontend/src/App.jsx#L269) | "/register" | {<Register />} |
| [frontend/src/App.jsx:270](../frontend/src/App.jsx#L270) | "/account" | {<Account />} |
| [frontend/src/App.jsx:271](../frontend/src/App.jsx#L271) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:274](../frontend/src/App.jsx#L274) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:275](../frontend/src/App.jsx#L275) | "/world/rating/:conceptSlug/:year?" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:277](../frontend/src/App.jsx#L277) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:278](../frontend/src/App.jsx#L278) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:279](../frontend/src/App.jsx#L279) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:282](../frontend/src/App.jsx#L282) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:283](../frontend/src/App.jsx#L283) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:284](../frontend/src/App.jsx#L284) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:285](../frontend/src/App.jsx#L285) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:286](../frontend/src/App.jsx#L286) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:287](../frontend/src/App.jsx#L287) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:288](../frontend/src/App.jsx#L288) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:289](../frontend/src/App.jsx#L289) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:290](../frontend/src/App.jsx#L290) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:291](../frontend/src/App.jsx#L291) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:292](../frontend/src/App.jsx#L292) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:293](../frontend/src/App.jsx#L293) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:294](../frontend/src/App.jsx#L294) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:295](../frontend/src/App.jsx#L295) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:296](../frontend/src/App.jsx#L296) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:297](../frontend/src/App.jsx#L297) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:298](../frontend/src/App.jsx#L298) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:301](../frontend/src/App.jsx#L301) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:302](../frontend/src/App.jsx#L302) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:304](../frontend/src/App.jsx#L304) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:307](../frontend/src/App.jsx#L307) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:308](../frontend/src/App.jsx#L308) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:309](../frontend/src/App.jsx#L309) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:310](../frontend/src/App.jsx#L310) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:313](../frontend/src/App.jsx#L313) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:314](../frontend/src/App.jsx#L314) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:315](../frontend/src/App.jsx#L315) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:317](../frontend/src/App.jsx#L317) | "/rankings" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:318](../frontend/src/App.jsx#L318) | "/ranking" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:319](../frontend/src/App.jsx#L319) | "/rankings/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:320](../frontend/src/App.jsx#L320) | "/ranking/gdp" | {<NavigateKeepSearch to={worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)} />} |
| [frontend/src/App.jsx:321](../frontend/src/App.jsx#L321) | "/calculators" | {<NavigateKeepSearch to="/calculator" />} |
| [frontend/src/App.jsx:322](../frontend/src/App.jsx#L322) | "/calculators/*" | {<CalculatorsAlias />} |
| [frontend/src/App.jsx:323](../frontend/src/App.jsx#L323) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:324](../frontend/src/App.jsx#L324) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:325](../frontend/src/App.jsx#L325) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:326](../frontend/src/App.jsx#L326) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:327](../frontend/src/App.jsx#L327) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:328](../frontend/src/App.jsx#L328) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:329](../frontend/src/App.jsx#L329) | "/russia/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:330](../frontend/src/App.jsx#L330) | "/countries" | {<CountriesToHome />} |
| [frontend/src/App.jsx:331](../frontend/src/App.jsx#L331) | "/countries/:slug" | {<RedirectTo build={({ slug }) => countryPath(slug)} />} |
| [frontend/src/App.jsx:332](../frontend/src/App.jsx#L332) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:333](../frontend/src/App.jsx#L333) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:334](../frontend/src/App.jsx#L334) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:335](../frontend/src/App.jsx#L335) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:336](../frontend/src/App.jsx#L336) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:340](../frontend/src/App.jsx#L340) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:341](../frontend/src/App.jsx#L341) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:346](../frontend/src/App.jsx#L346) | "*" | {<NotFound />} |
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
| [frontend/src/test/renderPage.jsx:36](../frontend/src/test/renderPage.jsx#L36) | {path} | {ui} |

## Границы

- Expressions are preserved, not evaluated. A declaration is not proof of mounting, execution or UI acceptance.
- Anonymous callbacks have enclosing source anchors; semantic review remains in the source ledger.
- Hook/state/HTTP/storage/event/JSX call sites are syntactic inventories, not a runtime dependency graph.
