# Независимый инвентарь клиента

Источник: Babel AST текущих tracked frontend/MCP файлов. Генератор не исполняет приложение и не присваивает reviewed.

- imports: 2573
- routes: 77
- functions: 7819
- hooks: 1717
- http: 80
- storage: 62
- events: 210
- jsx_handlers: 734
- registries: 375
- mcp_tools: 7
- files: 501
- parse_errors: 0

Полные call sites, выражения, anonymous callbacks, owner и строки — [JSON](client-mechanism-inventory.json). Смысл, loading/empty/error/access и исключения — [досье клиента](code-review/client-mechanism-acceptance-2026-09-30.md) и рецензии соответствующего файла.

## Объявления маршрутов

| Источник | path / index | element |
|---|---|---|
| [frontend/src/App.jsx:182](../frontend/src/App.jsx#L182) | "/embed/chart/:code" | {<EmbedChart />} |
| [frontend/src/App.jsx:183](../frontend/src/App.jsx#L183) | "/embed/card/:code" | {<EmbedCard />} |
| [frontend/src/App.jsx:184](../frontend/src/App.jsx#L184) | "/embed/table/:code" | {<EmbedTable />} |
| [frontend/src/App.jsx:185](../frontend/src/App.jsx#L185) | "/embed/ticker" | {<EmbedTicker />} |
| [frontend/src/App.jsx:186](../frontend/src/App.jsx#L186) | "/embed/compare" | {<EmbedCompare />} |
| [frontend/src/App.jsx:225](../frontend/src/App.jsx#L225) | "/" | {<Dashboard />} |
| [frontend/src/App.jsx:226](../frontend/src/App.jsx#L226) | "/about" | {<About />} |
| [frontend/src/App.jsx:227](../frontend/src/App.jsx#L227) | "/methodology" | {<Methodology />} |
| [frontend/src/App.jsx:228](../frontend/src/App.jsx#L228) | "/privacy" | {<Privacy />} |
| [frontend/src/App.jsx:229](../frontend/src/App.jsx#L229) | "/terms" | {<Terms />} |
| [frontend/src/App.jsx:230](../frontend/src/App.jsx#L230) | "/compare" | {<ComparePage />} |
| [frontend/src/App.jsx:231](../frontend/src/App.jsx#L231) | "/widgets" | {<EmbedBuilder />} |
| [frontend/src/App.jsx:232](../frontend/src/App.jsx#L232) | "/calculator" | {<CalculatorPage />} |
| [frontend/src/App.jsx:233](../frontend/src/App.jsx#L233) | "/calculator/mortgage" | {<MortgageCalculatorPage />} |
| [frontend/src/App.jsx:234](../frontend/src/App.jsx#L234) | "/calculator/compound" | {<CompoundCalculatorPage />} |
| [frontend/src/App.jsx:235](../frontend/src/App.jsx#L235) | "/login" | {<Login />} |
| [frontend/src/App.jsx:236](../frontend/src/App.jsx#L236) | "/register" | {<Register />} |
| [frontend/src/App.jsx:237](../frontend/src/App.jsx#L237) | "/account" | {<Account />} |
| [frontend/src/App.jsx:238](../frontend/src/App.jsx#L238) | "/admin/bi" | {<AdminBI />} |
| [frontend/src/App.jsx:241](../frontend/src/App.jsx#L241) | "/world/rating" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:242](../frontend/src/App.jsx#L242) | "/world/rating/:conceptSlug" | {<WorldRatingPage />} |
| [frontend/src/App.jsx:244](../frontend/src/App.jsx#L244) | "/currencies" | {<CategoryPage fixedSlug="currencies" />} |
| [frontend/src/App.jsx:245](../frontend/src/App.jsx#L245) | "/currencies/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:246](../frontend/src/App.jsx#L246) | "/currencies/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:249](../frontend/src/App.jsx#L249) | "/russia" | {<RussiaHome />} |
| [frontend/src/App.jsx:250](../frontend/src/App.jsx#L250) | "/russia/category" | {<CategoriesHub />} |
| [frontend/src/App.jsx:251](../frontend/src/App.jsx#L251) | "/russia/category/:slug" | {<CategoryPage />} |
| [frontend/src/App.jsx:252](../frontend/src/App.jsx#L252) | "/russia/indicator/:code" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:253](../frontend/src/App.jsx#L253) | "/russia/indicator/:code/:year" | {<IndicatorDetailKeyed />} |
| [frontend/src/App.jsx:254](../frontend/src/App.jsx#L254) | "/russia/today" | {<TodayHub />} |
| [frontend/src/App.jsx:255](../frontend/src/App.jsx#L255) | "/russia/today/:code" | {<TodayIndicatorPage />} |
| [frontend/src/App.jsx:256](../frontend/src/App.jsx#L256) | "/russia/calendar" | {<CalendarPage />} |
| [frontend/src/App.jsx:257](../frontend/src/App.jsx#L257) | "/russia/calendar/:year/:month" | {<CalendarMonthPage />} |
| [frontend/src/App.jsx:258](../frontend/src/App.jsx#L258) | "/russia/demographics" | {<DemographicsPage />} |
| [frontend/src/App.jsx:259](../frontend/src/App.jsx#L259) | "/russia/region/map/:code" | {<RegionsHome />} |
| [frontend/src/App.jsx:260](../frontend/src/App.jsx#L260) | "/russia/region" | {<RegionsHome />} |
| [frontend/src/App.jsx:261](../frontend/src/App.jsx#L261) | "/russia/region/:slug" | {<RegionProfile />} |
| [frontend/src/App.jsx:262](../frontend/src/App.jsx#L262) | "/russia/region/:slug/:code" | {<RegionIndicatorPage />} |
| [frontend/src/App.jsx:263](../frontend/src/App.jsx#L263) | "/russia/region-rating" | {<RegionRatingsHub />} |
| [frontend/src/App.jsx:264](../frontend/src/App.jsx#L264) | "/russia/region-rating/:code" | {<RegionRatingPage />} |
| [frontend/src/App.jsx:265](../frontend/src/App.jsx#L265) | "/russia/region-vs/:pair" | {<RegionComparePage />} |
| [frontend/src/App.jsx:268](../frontend/src/App.jsx#L268) | "/:countrySlug/regions" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:269](../frontend/src/App.jsx#L269) | "/:countrySlug/region/map/:code" | {<WorldRegionsHome />} |
| [frontend/src/App.jsx:270](../frontend/src/App.jsx#L270) | "/:countrySlug/region/:slug/:code" | {<WorldRegionIndicatorPage />} |
| [frontend/src/App.jsx:271](../frontend/src/App.jsx#L271) | "/:countrySlug/region/:slug" | {<WorldRegionProfile />} |
| [frontend/src/App.jsx:274](../frontend/src/App.jsx#L274) | "/:countrySlug/indicator/:code/:year" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:275](../frontend/src/App.jsx#L275) | "/:countrySlug/indicator/:code" | {<WorldIndicatorRoute />} |
| [frontend/src/App.jsx:276](../frontend/src/App.jsx#L276) | "/:countrySlug/category/:slug" | {<NotFound />} |
| [frontend/src/App.jsx:277](../frontend/src/App.jsx#L277) | "/:countrySlug" | {<WorldCountryRoute />} |
| [frontend/src/App.jsx:280](../frontend/src/App.jsx#L280) | "/category/:slug" | {<RedirectTo build={({ slug }) => russiaCategoryPath(slug)} />} |
| [frontend/src/App.jsx:281](../frontend/src/App.jsx#L281) | "/indicator/:code/:year" | {<RedirectTo build={({ code, year }) => russiaIndicatorYearPath(code, year)} />} |
| [frontend/src/App.jsx:282](../frontend/src/App.jsx#L282) | "/indicator/:code" | {<RedirectTo build={({ code }) => russiaIndicatorPath(code)} />} |
| [frontend/src/App.jsx:283](../frontend/src/App.jsx#L283) | "/today" | {<NavigateKeepSearch to={todayPath()} />} |
| [frontend/src/App.jsx:284](../frontend/src/App.jsx#L284) | "/today/:code" | {<RedirectTo build={({ code }) => todayPath(code)} />} |
| [frontend/src/App.jsx:285](../frontend/src/App.jsx#L285) | "/calendar" | {<NavigateKeepSearch to={calendarPath()} />} |
| [frontend/src/App.jsx:286](../frontend/src/App.jsx#L286) | "/calendar/:year/:month" | {<RedirectTo build={({ year, month }) => calendarPath(year, month)} />} |
| [frontend/src/App.jsx:287](../frontend/src/App.jsx#L287) | "/demographics" | {<NavigateKeepSearch to={demographicsPath()} />} |
| [frontend/src/App.jsx:288](../frontend/src/App.jsx#L288) | "/regions" | {<NavigateKeepSearch to={regionHubPath()} />} |
| [frontend/src/App.jsx:289](../frontend/src/App.jsx#L289) | "/regions/map/:code" | {<RedirectTo build={({ code }) => regionMapPath(code)} />} |
| [frontend/src/App.jsx:290](../frontend/src/App.jsx#L290) | "/region/:slug" | {<RedirectTo build={({ slug }) => regionPath(slug)} />} |
| [frontend/src/App.jsx:291](../frontend/src/App.jsx#L291) | "/region/:slug/:code" | {<RedirectTo build={({ slug, code }) => regionIndicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:292](../frontend/src/App.jsx#L292) | "/region-rating/:code" | {<RedirectTo build={({ code }) => regionRatingPath(code)} />} |
| [frontend/src/App.jsx:293](../frontend/src/App.jsx#L293) | "/region-vs/:pair" | {<RedirectTo build={({ pair }) => {
              const m = String(pair &#124;&#124; '').match(/^(.+)-vs-(.+)$/);
              return m ? regionVsPath(m[1], m[2]) : regionHubPath();
            }} />} |
| [frontend/src/App.jsx:297](../frontend/src/App.jsx#L297) | "/world/:slug/:code" | {<RedirectTo build={({ slug, code }) => indicatorPath(slug, code)} />} |
| [frontend/src/App.jsx:298](../frontend/src/App.jsx#L298) | "/world/:slug" | {<RedirectTo build={({ slug }) => {
              if (slug === 'rating') return '/world/rating';
              return countryPath(slug);
            }} />} |
| [frontend/src/App.jsx:303](../frontend/src/App.jsx#L303) | "*" | {<NotFound />} |
| [frontend/src/components/IndicatorPage.w3.component.test.jsx:198](../frontend/src/components/IndicatorPage.w3.component.test.jsx#L198) | "/russia/indicator/:code/:year?" | {(
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
| [frontend/src/pages/Register.component.test.jsx:64](../frontend/src/pages/Register.component.test.jsx#L64) | "/register" | {<Register />} |
| [frontend/src/test/renderPage.jsx:36](../frontend/src/test/renderPage.jsx#L36) | {path} | {ui} |

## Границы

- Expressions are preserved, not evaluated. A declaration is not proof of mounting, execution or UI acceptance.
- Anonymous callbacks have enclosing source anchors; semantic review remains in the source ledger.
- Hook/state/HTTP/storage/event/JSX call sites are syntactic inventories, not a runtime dependency graph.
