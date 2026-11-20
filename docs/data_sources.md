# Data sources — точная карта индикатор → файл/endpoint

**World extension last verified:** 2026-08-29 (IMF WEO `NGDPD`/`NGDPDPC`/`GGXCNL_NGDP`/`GGXWDG_NGDP`/`LP`/`LUR`/`PCPIPCH`
via SDMX 3.0; правило года наблюдений: поточные WEO-серии — только закрытые годы,
стоковые LP/LUR — текущий год допустим; census PEP 2000–2025; Eurostat `reg_area3`
+ national statistical/cadastre sources; население США/Бразилии — адаптеры
`census` (PEP CSV) и `ibge` (SIDRA 6579+1209), инжест `world_pop_ingest`).

**Last updated:** 2026-11-20 (туризм по России в целом — раздел «Туризм по России в целом»). Ранее 2026-11-19 (помесячные ряды регионов ЕМИСС 57693/34118/57806/31076 — раздел «ЕМИСС — помесячные ряды регионов»). Ранее 2026-11-18 (недельные цены на топливо по субъектам — ЕМИСС 37426, раздел «Недельные цены на топливо по субъектам»). Ранее 2026-11-13 (недельный ИПЦ: бюллетени Росстата с октября 2026 выходят в PDF, поиск бюллетеня по заголовку ленты; признак «Росстат восстановлен частично» — раздел «Росстат — недельная инфляция» и `rosstat_outage.py`). Ранее 2026-11-08 (все 54 валюты ведомости ЦБ — справочник `cbr_currencies.py`; все позиции средних потребительских цен ЕМИСС 31448 по субъектам — `emiss_price_goods.py`). Ранее 2026-10-28 (national-core: сеть ряда читается до транзакции БД, commit после каждого ряда; ключи Banxico/ECOS/e-Stat на проде отсутствуют; RBA/NBS/RBI отвечают 403 с IP прода). Ранее 2026-09-29 (штаты США без наложения BLS API — 403 на IP прода; Eurostat: отбор задачи только M/Q/A, наборы без разреза по странам — «пропуск»). Ранее 2026-09-20 (субнациональные регионы США, ADR-0014; ранее США national-core: 59 курируемых рядов FRED). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` / `weo-government-debt-gdp` — карточки каталога; ingest пишет всем `world_countries`; LP/LUR/PCPIPCH — карта населения/безработицы/инфляции без RU-overlay). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` — карточки каталога, T10/T10a; ingest пишет всем `world_countries`). Ранее 2026-08-28 (мировой блок: национальные паспорта national-core перенесены из worktree в репозиторий как постоянный ежедневный ETL — 19 официальных провайдеров по 10 странам, job `world_national_core` 02:10 МСК, раздел «Национальные паспорта» ниже). Ранее 2026-08-27 (региональный блок: помесячные цены на топливо по субъектам — раздел «Региональный блок» ниже; ЕМИСС 31448/57699/59002). Ранее 2026-08-23 (IMF WEO: добавлен `GGXCNL_NGDP` — баланс бюджета сектора государственного управления, overlay `weo-budget-balance-gdp`; source 117 / seed 939). Ранее 2026-08-16 (демография/наука: discovery со страниц разделов + EDN_12 для лагов demo21; сырьё: Yahoo desk снят с витрины — `natural-gas` → EIA `DHHNGSP` через `fred_csv`; `coal`/`copper`/`silver`/`wheat`/`soybean` → World Bank Pink Sheet monthly `world_bank_pink_sheet`; `steel` деактивирован / unlisted. Ранее тем же днём: FRED CSV `fred_csv` для `usd-index`/`ust-10y`/`brent`; `gold-usd` не заведён — нет свободного дневного ряда). Ранее 2026-07-06 (CTO-аудит, Волна 5: счётчик source-индикаторов актуализирован — 109 (было заявлено 75); добавленные с 2026-05-31 семейства покрыты соответствующими разделами ниже и docstrings парсеров: демография (`rosstat_demo`), наука/инновации (`rosstat_science`), основные фонды (`rosstat_fixed_assets`), ИПП-разделы (`rosstat_ind`), крипта BTC/ETH/SOL (`binance_btcusdt`), биржевые индексы и товарные MOEX (`moex_index`, `moex_brent_daily`), недельные цены топлива (`rosstat_weekly_price`), денежные агрегаты M0/M1/M2 (`cbr_monetary_agg`). Два parser_type зарегистрированы, но в seed не используются (задел): `cbr_dataservice_sum` — суммирование нескольких DataService-элементов по дате, `cbr_monetary_html` — HTML-таблицы денежной статистики ЦБ; не удалять без ревизии прод-БД. Ранее 2026-05-31: T13 — данный файл стал основным местом хранения технических деталей источников — имена файлов, листы, строки/колонки, API-id; публичные `methodology` поля индикаторов в `seed_data.py` не выдают этих внутренностей, см. правило [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc).)
**Last updated:** 2026-11-19 (цены производителей стали в России из ЕМИСС 57606 — раздел «ЕМИСС — цены производителей стали», парсер `emiss_steel_parser.py`). Ранее 2026-11-18 (распределение доходов населения и заработных плат России из ЕМИСС — раздел «ЕМИСС — распределение доходов населения и заработных плат», парсер `emiss_income_parser.py`). Ранее 2026-11-13 (недельный ИПЦ: бюллетени Росстата с октября 2026 выходят в PDF, поиск бюллетеня по заголовку ленты; признак «Росстат восстановлен частично» — раздел «Росстат — недельная инфляция» и `rosstat_outage.py`). Ранее 2026-11-08 (все 54 валюты ведомости ЦБ — справочник `cbr_currencies.py`; все позиции средних потребительских цен ЕМИСС 31448 по субъектам — `emiss_price_goods.py`). Ранее 2026-10-28 (national-core: сеть ряда читается до транзакции БД, commit после каждого ряда; ключи Banxico/ECOS/e-Stat на проде отсутствуют; RBA/NBS/RBI отвечают 403 с IP прода). Ранее 2026-09-29 (штаты США без наложения BLS API — 403 на IP прода; Eurostat: отбор задачи только M/Q/A, наборы без разреза по странам — «пропуск»). Ранее 2026-09-20 (субнациональные регионы США, ADR-0014; ранее США national-core: 59 курируемых рядов FRED). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` / `weo-government-debt-gdp` — карточки каталога; ingest пишет всем `world_countries`; LP/LUR/PCPIPCH — карта населения/безработицы/инфляции без RU-overlay). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` — карточки каталога, T10/T10a; ingest пишет всем `world_countries`). Ранее 2026-08-28 (мировой блок: национальные паспорта national-core перенесены из worktree в репозиторий как постоянный ежедневный ETL — 19 официальных провайдеров по 10 странам, job `world_national_core` 02:10 МСК, раздел «Национальные паспорта» ниже). Ранее 2026-08-27 (региональный блок: помесячные цены на топливо по субъектам — раздел «Региональный блок» ниже; ЕМИСС 31448/57699/59002). Ранее 2026-08-23 (IMF WEO: добавлен `GGXCNL_NGDP` — баланс бюджета сектора государственного управления, overlay `weo-budget-balance-gdp`; source 117 / seed 939). Ранее 2026-08-16 (демография/наука: discovery со страниц разделов + EDN_12 для лагов demo21; сырьё: Yahoo desk снят с витрины — `natural-gas` → EIA `DHHNGSP` через `fred_csv`; `coal`/`copper`/`silver`/`wheat`/`soybean` → World Bank Pink Sheet monthly `world_bank_pink_sheet`; `steel` деактивирован / unlisted. Ранее тем же днём: FRED CSV `fred_csv` для `usd-index`/`ust-10y`/`brent`; `gold-usd` не заведён — нет свободного дневного ряда). Ранее 2026-07-06 (CTO-аудит, Волна 5: счётчик source-индикаторов актуализирован — 109 (было заявлено 75); добавленные с 2026-05-31 семейства покрыты соответствующими разделами ниже и docstrings парсеров: демография (`rosstat_demo`), наука/инновации (`rosstat_science`), основные фонды (`rosstat_fixed_assets`), ИПП-разделы (`rosstat_ind`), крипта BTC/ETH/SOL (`binance_btcusdt`), биржевые индексы и товарные MOEX (`moex_index`, `moex_brent_daily`), недельные цены топлива (`rosstat_weekly_price`), денежные агрегаты M0/M1/M2 (`cbr_monetary_agg`). Два parser_type зарегистрированы, но в seed не используются (задел): `cbr_dataservice_sum` — суммирование нескольких DataService-элементов по дате, `cbr_monetary_html` — HTML-таблицы денежной статистики ЦБ; не удалять без ревизии прод-БД. Ранее 2026-05-31: T13 — данный файл стал основным местом хранения технических деталей источников — имена файлов, листы, строки/колонки, API-id; публичные `methodology` поля индикаторов в `seed_data.py` не выдают этих внутренностей, см. правило [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc).)
**Last updated:** 2026-11-18 (недельные цены на топливо по субъектам — ЕМИСС 37426, раздел «Недельные цены на топливо по субъектам»). Ранее 2026-11-13 (недельный ИПЦ: бюллетени Росстата с октября 2026 выходят в PDF, поиск бюллетеня по заголовку ленты; признак «Росстат восстановлен частично» — раздел «Росстат — недельная инфляция» и `rosstat_outage.py`). Ранее 2026-11-08 (все 54 валюты ведомости ЦБ — справочник `cbr_currencies.py`; все позиции средних потребительских цен ЕМИСС 31448 по субъектам — `emiss_price_goods.py`). Ранее 2026-10-28 (national-core: сеть ряда читается до транзакции БД, commit после каждого ряда; ключи Banxico/ECOS/e-Stat на проде отсутствуют; RBA/NBS/RBI отвечают 403 с IP прода). Ранее 2026-09-29 (штаты США без наложения BLS API — 403 на IP прода; Eurostat: отбор задачи только M/Q/A, наборы без разреза по странам — «пропуск»). Ранее 2026-09-20 (субнациональные регионы США, ADR-0014; ранее США national-core: 59 курируемых рядов FRED). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` / `weo-government-debt-gdp` — карточки каталога; ingest пишет всем `world_countries`; LP/LUR/PCPIPCH — карта населения/безработицы/инфляции без RU-overlay). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` — карточки каталога, T10/T10a; ingest пишет всем `world_countries`). Ранее 2026-08-28 (мировой блок: национальные паспорта national-core перенесены из worktree в репозиторий как постоянный ежедневный ETL — 19 официальных провайдеров по 10 странам, job `world_national_core` 02:10 МСК, раздел «Национальные паспорта» ниже). Ранее 2026-08-27 (региональный блок: помесячные цены на топливо по субъектам — раздел «Региональный блок» ниже; ЕМИСС 31448/57699/59002). Ранее 2026-08-23 (IMF WEO: добавлен `GGXCNL_NGDP` — баланс бюджета сектора государственного управления, overlay `weo-budget-balance-gdp`; source 117 / seed 939). Ранее 2026-08-16 (демография/наука: discovery со страниц разделов + EDN_12 для лагов demo21; сырьё: Yahoo desk снят с витрины — `natural-gas` → EIA `DHHNGSP` через `fred_csv`; `coal`/`copper`/`silver`/`wheat`/`soybean` → World Bank Pink Sheet monthly `world_bank_pink_sheet`; `steel` деактивирован / unlisted. Ранее тем же днём: FRED CSV `fred_csv` для `usd-index`/`ust-10y`/`brent`; `gold-usd` не заведён — нет свободного дневного ряда). Ранее 2026-07-06 (CTO-аудит, Волна 5: счётчик source-индикаторов актуализирован — 109 (было заявлено 75); добавленные с 2026-05-31 семейства покрыты соответствующими разделами ниже и docstrings парсеров: демография (`rosstat_demo`), наука/инновации (`rosstat_science`), основные фонды (`rosstat_fixed_assets`), ИПП-разделы (`rosstat_ind`), крипта BTC/ETH/SOL (`binance_btcusdt`), биржевые индексы и товарные MOEX (`moex_index`, `moex_brent_daily`), недельные цены топлива (`rosstat_weekly_price`), денежные агрегаты M0/M1/M2 (`cbr_monetary_agg`). Два parser_type зарегистрированы, но в seed не используются (задел): `cbr_dataservice_sum` — суммирование нескольких DataService-элементов по дате, `cbr_monetary_html` — HTML-таблицы денежной статистики ЦБ; не удалять без ревизии прод-БД. Ранее 2026-05-31: T13 — данный файл стал основным местом хранения технических деталей источников — имена файлов, листы, строки/колонки, API-id; публичные `methodology` поля индикаторов в `seed_data.py` не выдают этих внутренностей, см. правило [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc).)
**Last updated:** 2026-11-19 (квартальный слой регионов: цена 1 м² жилья и индексы цен, цена 1 м² в центрах субъектов, доходы к прожиточному минимуму, прожиточный минимум по группам — ЕМИСС 31452/30925/61781/58537/30957, раздел «Квартальные ряды регионов»; цены производителей стали в России из ЕМИСС 57606 — раздел «ЕМИСС — цены производителей стали», парсер `emiss_steel_parser.py`). Ранее 2026-11-18 (распределение доходов населения и заработных плат России из ЕМИСС — раздел «ЕМИСС — распределение доходов населения и заработных плат», парсер `emiss_income_parser.py`). Ранее 2026-11-13 (недельный ИПЦ: бюллетени Росстата с октября 2026 выходят в PDF, поиск бюллетеня по заголовку ленты; признак «Росстат восстановлен частично» — раздел «Росстат — недельная инфляция» и `rosstat_outage.py`). Ранее 2026-11-08 (все 54 валюты ведомости ЦБ — справочник `cbr_currencies.py`; все позиции средних потребительских цен ЕМИСС 31448 по субъектам — `emiss_price_goods.py`). Ранее 2026-10-28 (national-core: сеть ряда читается до транзакции БД, commit после каждого ряда; ключи Banxico/ECOS/e-Stat на проде отсутствуют; RBA/NBS/RBI отвечают 403 с IP прода). Ранее 2026-09-29 (штаты США без наложения BLS API — 403 на IP прода; Eurostat: отбор задачи только M/Q/A, наборы без разреза по странам — «пропуск»). Ранее 2026-09-20 (субнациональные регионы США, ADR-0014; ранее США national-core: 59 курируемых рядов FRED). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` / `weo-government-debt-gdp` — карточки каталога; ingest пишет всем `world_countries`; LP/LUR/PCPIPCH — карта населения/безработицы/инфляции без RU-overlay). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` — карточки каталога, T10/T10a; ingest пишет всем `world_countries`). Ранее 2026-08-28 (мировой блок: национальные паспорта national-core перенесены из worktree в репозиторий как постоянный ежедневный ETL — 19 официальных провайдеров по 10 странам, job `world_national_core` 02:10 МСК, раздел «Национальные паспорта» ниже). Ранее 2026-08-27 (региональный блок: помесячные цены на топливо по субъектам — раздел «Региональный блок» ниже; ЕМИСС 31448/57699/59002). Ранее 2026-08-23 (IMF WEO: добавлен `GGXCNL_NGDP` — баланс бюджета сектора государственного управления, overlay `weo-budget-balance-gdp`; source 117 / seed 939). Ранее 2026-08-16 (демография/наука: discovery со страниц разделов + EDN_12 для лагов demo21; сырьё: Yahoo desk снят с витрины — `natural-gas` → EIA `DHHNGSP` через `fred_csv`; `coal`/`copper`/`silver`/`wheat`/`soybean` → World Bank Pink Sheet monthly `world_bank_pink_sheet`; `steel` деактивирован / unlisted. Ранее тем же днём: FRED CSV `fred_csv` для `usd-index`/`ust-10y`/`brent`; `gold-usd` не заведён — нет свободного дневного ряда). Ранее 2026-07-06 (CTO-аудит, Волна 5: счётчик source-индикаторов актуализирован — 109 (было заявлено 75); добавленные с 2026-05-31 семейства покрыты соответствующими разделами ниже и docstrings парсеров: демография (`rosstat_demo`), наука/инновации (`rosstat_science`), основные фонды (`rosstat_fixed_assets`), ИПП-разделы (`rosstat_ind`), крипта BTC/ETH/SOL (`binance_btcusdt`), биржевые индексы и товарные MOEX (`moex_index`, `moex_brent_daily`), недельные цены топлива (`rosstat_weekly_price`), денежные агрегаты M0/M1/M2 (`cbr_monetary_agg`). Два parser_type зарегистрированы, но в seed не используются (задел): `cbr_dataservice_sum` — суммирование нескольких DataService-элементов по дате, `cbr_monetary_html` — HTML-таблицы денежной статистики ЦБ; не удалять без ревизии прод-БД. Ранее 2026-05-31: T13 — данный файл стал основным местом хранения технических деталей источников — имена файлов, листы, строки/колонки, API-id; публичные `methodology` поля индикаторов в `seed_data.py` не выдают этих внутренностей, см. правило [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc).)
**Last updated:** 2026-11-19 (топливо: бюллетень Росстата в PDF для федерального ряда и последней недели по субъектам; разделы «Росстат — еженедельные средние цены на топливо» и «Недельные цены на топливо по субъектам»). Ранее 2026-11-18 (недельные цены на топливо по субъектам — ЕМИСС 37426, раздел «Недельные цены на топливо по субъектам»). Ранее 2026-11-13 (недельный ИПЦ: бюллетени Росстата с октября 2026 выходят в PDF, поиск бюллетеня по заголовку ленты; признак «Росстат восстановлен частично» — раздел «Росстат — недельная инфляция» и `rosstat_outage.py`). Ранее 2026-11-08 (все 54 валюты ведомости ЦБ — справочник `cbr_currencies.py`; все позиции средних потребительских цен ЕМИСС 31448 по субъектам — `emiss_price_goods.py`). Ранее 2026-10-28 (national-core: сеть ряда читается до транзакции БД, commit после каждого ряда; ключи Banxico/ECOS/e-Stat на проде отсутствуют; RBA/NBS/RBI отвечают 403 с IP прода). Ранее 2026-09-29 (штаты США без наложения BLS API — 403 на IP прода; Eurostat: отбор задачи только M/Q/A, наборы без разреза по странам — «пропуск»). Ранее 2026-09-20 (субнациональные регионы США, ADR-0014; ранее США national-core: 59 курируемых рядов FRED). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` / `weo-government-debt-gdp` — карточки каталога; ingest пишет всем `world_countries`; LP/LUR/PCPIPCH — карта населения/безработицы/инфляции без RU-overlay). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` — карточки каталога, T10/T10a; ingest пишет всем `world_countries`). Ранее 2026-08-28 (мировой блок: национальные паспорта national-core перенесены из worktree в репозиторий как постоянный ежедневный ETL — 19 официальных провайдеров по 10 странам, job `world_national_core` 02:10 МСК, раздел «Национальные паспорта» ниже). Ранее 2026-08-27 (региональный блок: помесячные цены на топливо по субъектам — раздел «Региональный блок» ниже; ЕМИСС 31448/57699/59002). Ранее 2026-08-23 (IMF WEO: добавлен `GGXCNL_NGDP` — баланс бюджета сектора государственного управления, overlay `weo-budget-balance-gdp`; source 117 / seed 939). Ранее 2026-08-16 (демография/наука: discovery со страниц разделов + EDN_12 для лагов demo21; сырьё: Yahoo desk снят с витрины — `natural-gas` → EIA `DHHNGSP` через `fred_csv`; `coal`/`copper`/`silver`/`wheat`/`soybean` → World Bank Pink Sheet monthly `world_bank_pink_sheet`; `steel` деактивирован / unlisted. Ранее тем же днём: FRED CSV `fred_csv` для `usd-index`/`ust-10y`/`brent`; `gold-usd` не заведён — нет свободного дневного ряда). Ранее 2026-07-06 (CTO-аудит, Волна 5: счётчик source-индикаторов актуализирован — 109 (было заявлено 75); добавленные с 2026-05-31 семейства покрыты соответствующими разделами ниже и docstrings парсеров: демография (`rosstat_demo`), наука/инновации (`rosstat_science`), основные фонды (`rosstat_fixed_assets`), ИПП-разделы (`rosstat_ind`), крипта BTC/ETH/SOL (`binance_btcusdt`), биржевые индексы и товарные MOEX (`moex_index`, `moex_brent_daily`), недельные цены топлива (`rosstat_weekly_price`), денежные агрегаты M0/M1/M2 (`cbr_monetary_agg`). Два parser_type зарегистрированы, но в seed не используются (задел): `cbr_dataservice_sum` — суммирование нескольких DataService-элементов по дате, `cbr_monetary_html` — HTML-таблицы денежной статистики ЦБ; не удалять без ревизии прод-БД. Ранее 2026-05-31: T13 — данный файл стал основным местом хранения технических деталей источников — имена файлов, листы, строки/колонки, API-id; публичные `methodology` поля индикаторов в `seed_data.py` не выдают этих внутренностей, см. правило [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc).)
**Last updated:** 2026-11-18 (распределение доходов населения и заработных плат России из ЕМИСС — раздел «ЕМИСС — распределение доходов населения и заработных плат», парсер `emiss_income_parser.py`). Ранее 2026-11-13 (недельный ИПЦ: бюллетени Росстата с октября 2026 выходят в PDF, поиск бюллетеня по заголовку ленты; признак «Росстат восстановлен частично» — раздел «Росстат — недельная инфляция» и `rosstat_outage.py`). Ранее 2026-11-08 (все 54 валюты ведомости ЦБ — справочник `cbr_currencies.py`; все позиции средних потребительских цен ЕМИСС 31448 по субъектам — `emiss_price_goods.py`). Ранее 2026-10-28 (national-core: сеть ряда читается до транзакции БД, commit после каждого ряда; ключи Banxico/ECOS/e-Stat на проде отсутствуют; RBA/NBS/RBI отвечают 403 с IP прода). Ранее 2026-09-29 (штаты США без наложения BLS API — 403 на IP прода; Eurostat: отбор задачи только M/Q/A, наборы без разреза по странам — «пропуск»). Ранее 2026-09-20 (субнациональные регионы США, ADR-0014; ранее США national-core: 59 курируемых рядов FRED). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` / `weo-government-debt-gdp` — карточки каталога; ingest пишет всем `world_countries`; LP/LUR/PCPIPCH — карта населения/безработицы/инфляции без RU-overlay). Ранее 2026-08-29 (IMF WEO: российские `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` — карточки каталога, T10/T10a; ingest пишет всем `world_countries`). Ранее 2026-08-28 (мировой блок: национальные паспорта national-core перенесены из worktree в репозиторий как постоянный ежедневный ETL — 19 официальных провайдеров по 10 странам, job `world_national_core` 02:10 МСК, раздел «Национальные паспорта» ниже). Ранее 2026-08-27 (региональный блок: помесячные цены на топливо по субъектам — раздел «Региональный блок» ниже; ЕМИСС 31448/57699/59002). Ранее 2026-08-23 (IMF WEO: добавлен `GGXCNL_NGDP` — баланс бюджета сектора государственного управления, overlay `weo-budget-balance-gdp`; source 117 / seed 939). Ранее 2026-08-16 (демография/наука: discovery со страниц разделов + EDN_12 для лагов demo21; сырьё: Yahoo desk снят с витрины — `natural-gas` → EIA `DHHNGSP` через `fred_csv`; `coal`/`copper`/`silver`/`wheat`/`soybean` → World Bank Pink Sheet monthly `world_bank_pink_sheet`; `steel` деактивирован / unlisted. Ранее тем же днём: FRED CSV `fred_csv` для `usd-index`/`ust-10y`/`brent`; `gold-usd` не заведён — нет свободного дневного ряда). Ранее 2026-07-06 (CTO-аудит, Волна 5: счётчик source-индикаторов актуализирован — 109 (было заявлено 75); добавленные с 2026-05-31 семейства покрыты соответствующими разделами ниже и docstrings парсеров: демография (`rosstat_demo`), наука/инновации (`rosstat_science`), основные фонды (`rosstat_fixed_assets`), ИПП-разделы (`rosstat_ind`), крипта BTC/ETH/SOL (`binance_btcusdt`), биржевые индексы и товарные MOEX (`moex_index`, `moex_brent_daily`), недельные цены топлива (`rosstat_weekly_price`), денежные агрегаты M0/M1/M2 (`cbr_monetary_agg`). Два parser_type зарегистрированы, но в seed не используются (задел): `cbr_dataservice_sum` — суммирование нескольких DataService-элементов по дате, `cbr_monetary_html` — HTML-таблицы денежной статистики ЦБ; не удалять без ревизии прод-БД. Ранее 2026-05-31: T13 — данный файл стал основным местом хранения технических деталей источников — имена файлов, листы, строки/колонки, API-id; публичные `methodology` поля индикаторов в `seed_data.py` не выдают этих внутренностей, см. правило [`.cursor/rules/methodology-language.mdc`](../.cursor/rules/methodology-language.mdc).)
**Part of:** [`AGENTS.md`](../AGENTS.md), [`CONTEXT.md`](../CONTEXT.md).
**Related:** docstrings парсеров `backend/app/services/{cbr_*,minfin_*,rosstat_*}_parser.py` (per-parser internals: traps, схема `model_config_json`, особенности формата), [`docs/adr/0004`](adr/0004-rosstat-russian-canonical-sdds-deprecated.md) (Rosstat русский canonical).

> **Single source of truth** для актуальных URL/файлов, откуда тянется каждый из 304 source-индикаторов. Если меняется источник в коде парсера или `seed_data.py` — **обязательно** актуализировать этот файл (см. [`AGENTS.md::Шаг 4`](../AGENTS.md#шаг-4--протокол-актуализации-документации-критично)).
>
> Derived-индикаторы (28) не входят — они не имеют внешнего источника, считаются из source через `DERIVED_SPECS`.

---

## Convention

- **CBR base**: `https://www.cbr.ru`
- **Rosstat base**: `https://rosstat.gov.ru/storage/mediabank/`
- **Минфин base**: `https://minfin.gov.ru/opendata/`
- В таблицах URL сокращён до пути от соответствующего base.
- Конфигурация per-indicator живёт в `Indicator.model_config_json` (PostgreSQL JSONB).

---

## ЦБ РФ — платёжный баланс (CbrBopParser)

Файл: `cbr.ru/vfs/statistics/credit_statistics/bop/bal_of_payments_standart.xlsx` (общий для 6 индикаторов, селектор `bop_target` в `model_config`). Лист «Кварталы». Глубина с 1994-Q1.

| Индикатор | bop_target |
|-----------|------------|
| `exports` | `exports` |
| `imports` | `imports` |
| `services-exports` | `services-exports` |
| `services-imports` | `services-imports` |
| `trade-balance` | `trade-balance` |
| `fdi-net` | `fdi-net` |

## ЦБ РФ — внешняя торговля **товарами** monthly (CbrTradeGoodsMonthlyParser)

Файл: `cbr.ru/vfs/statistics/credit_statistics/trade/trade.xls` (legacy XLS), лист «Ежемесячные», 17 columns. **Глубина с 1997-01**. Селектор `bop_target` в `model_config`.

| Индикатор | bop_target | Источник колонка |
|-----------|------------|------------------|
| `exports-monthly` | `exports-monthly` | col 2 (Экспорт ФОБ Всего, млн $) |
| `imports-monthly` | `imports-monthly` | col 8 (Импорт ФОБ Всего, млн $) |
| `trade-balance-monthly` | `trade-balance-monthly` | col 14 (Сальдо торгового баланса, млн $) |

Цель: монтлы-разбивка для frequency switcher на карточках `exports`/`imports`/`trade-balance` (`alternate_frequencies.monthly` в parent `model_config`). См. `docs/adr/0004` для аргументации canonical Russian sources. `is_listed=False` — карточки доступны через switcher из родителя, не дублируем в листинге категории «Торговля».

**Cross-check c TradingEconomics (2026-05-12)**: последние точки сходятся 1:1 (Feb 2026: exports=30,123 / imports=24,770 / balance=5,353 — копия из ЦБ РФ). Исторические extremes: max exports Dec 2021 = 58,148, max imports Dec 2025 = 34,011 — также 1:1. **Единственная разница**: TE имеет историю с **1994-01** (3 года глубже нашего 1997-01). Это потому что `trade.xls` ЦБ сам начинается с 1997-01; ранее 1994-1996 ЦБ публиковал только через bulletin'ы платёжного баланса (другой формат, требует отдельного парсера). Backfill 1994-1996 = **P2 priority** (29 лет покрытия уже более чем достаточно).

## ЦБ РФ — внешняя торговля **услугами** monthly (CbrTradeServicesMonthlyParser)

Файл: `cbr.ru/vfs/statistics/credit_statistics/trade/trade_monthly.xlsx`, лист «месяцы » (с trailing-пробелом). **Transposed layout**: row 4 — даты в headers (datetime cells + последние 1-2 cell = estimate strings типа «янв.26\n(оценка)»), col 1 — labels. **Глубина с 2018-01**.

| Индикатор | bop_target | Источник row label |
|-----------|------------|---------------------|
| `services-exports-monthly` | `services-exports-monthly` | «Экспорт услуг» |
| `services-imports-monthly` | `services-imports-monthly` | «Импорт услуг» |

## ЦБ РФ — внешний долг (CbrDebtParser)

| Индикатор | File |
|-----------|------|
| `external-debt` | `cbr.ru/vfs/statistics/credit_statistics/debt/debt_new.xlsx` |

## ЦБ РФ — курсы валют (CbrFxParser)

Endpoint: `cbr.ru/scripts/XML_dynamic.asp?date_req1={from}&date_req2={to}&VAL_NM_RQ={code}`.

| Индикатор | VAL_NM_RQ | Пол истории (`backfill_from`) |
|-----------|-----------|-------------------------------|
| `usd-rub` | `R01235` | `1998-01-01` |
| `eur-rub` | `R01239` | `1999-01-01` (евро у ЦБ с 1999) |
| `cny-rub` | `R01375` | `1998-01-01` |
| `try-rub` | `R01700J` | `2005-01-01` (глубже ЦБ не отдаёт); номинал 10: ЦБ публикует рубли за 10 лир, парсер делит на номинал (круг 9, 08.10.2026; код сверен по `XML_valFull.asp` и `XML_daily.asp`, 17,3777 ₽ за 10 лир на 09.10.2026) |
| `kzt-rub` | `R01335` | `1998-01-01`; номинал 100; значение хранится в рублях за один тенге с четырьмя знаками (колонка `Numeric(12,4)`, шаг 0,0001 при курсе около 0,19 ₽, то есть до 0,05 % ошибки округления) |

> **Валюты, которые не взяты (08.10.2026):** дирхам ОАЭ (`R01230`): у ЦБ ряд месячный до 2009, дыра 2010–2022, ежедневный лишь с 2023 (проверено `XML_dynamic`), это нарушило бы «максимальную историю» и частоту; йена (`R01820`), франк (`R01775`), белорусский рубль (`R01090B`), лари (`R01210`) в справочнике ЦБ есть и добавляются тем же шаблоном (`CURRENCY_MAP` + `seed_data.py` + `FamilyDef` + `site_paths._CURRENCY_BASE_CODES` и зеркало `frontend/src/lib/sitePaths.js`), но владелец назвал только лиру и тенге. Прогноза у новых курсов нет (`forecast_steps: 0`, как у юаня).

> **Все валюты ведомости ЦБ (08.11.2026, слово владельца «как можно больше информации… из официальных источников»).** К пяти парам добавлены 49: справочник `backend/app/data/cbr_currencies.py` — одна точка истины для `CURRENCY_MAP`, строк seed, `FamilyDef` (T1), SEO, EN-копии, путей `/currencies`, поиска и выхода со страницы страны (`COUNTRY_CURRENCY_RATE_CODES`). Коды `R…`, номиналы и первая дата сверены живыми `XML_daily`/`XML_dynamic` 08.11.2026 (ведомость на 07.11.2026, 54 валюты). Решение 08.10 «дирхам не берём из-за месячной истории» пересмотрено: ряд объявлен дневным, старая часть — помесячные точки ЦБ (в методологии карточки указан год, с которого курс ежедневный: `daily_since`). Единица котировки: мелкие валюты хранятся за 100 / 1 000 / 10 000 / 1 000 000 единиц, как в ведомости (`quote_units`, единица ряда «руб. за 10 000»), потому что `indicator_data.value` — `Numeric(12,4)`; конвертер раздела валют делит на неё (`quoteUnitsOf` в `currencyRates.js`). Поздний пол: TJS с 2000-11 (до этого таджикский рубль, скачок ×900), CUP и IRR с 2025-07-11 (ЦБ сменил базу курса, скачок ×10 и ×23; прежний режим остался в первоисточнике), AZN/RON/RSD/TMT/BYN — с нового кода после деноминации, MMK котируется с 2025-07-11. Инкрементальность: полная история грузится, только пока ряд пуст или не дотянут до `backfill_from` (+45 дней); дальше ежедневный прогон берёт окно `incremental_fetch_days` (60). Прогноза нет (`forecast_steps: 0`).

> **Пол истории = деноминация рубля 1000:1 (1998-01-01).** XML_dynamic отдаёт курсы с 1992-07, но до 1998 они в «старых» рублях (1997-12-30 USD = 5960). Сплайс со «новыми» дал бы разрыв ×1000 и не прошёл бы `validation.max=500`. Поэтому floor = 1998-01-01 (`backfill_from` в `model_config_json`); ряд непрерывен и захватывает кризисы 1998/2008/2014/2022. Среднее/агрегаты по периодам (avg-week/month/quarter/year) автоматически тянутся с 1998.

## ЦБ РФ — драгметаллы (CbrGoldParser)

| Индикатор | Endpoint | Пол истории |
|-----------|----------|-------------|
| `gold-price` | `cbr.ru/scripts/xml_metall.asp?date_req1={from}&date_req2={to}` | `1998-01-01` (`backfill_from`; `validation.min` 100→40 — ранний-1998 ≈ 52 руб/г до девальвации) |

## Binance — crypto daily (BinanceBtcUsdtParser)

Тикер config-driven через `model_config_json.binance_symbol`. Прогноз не строится (`forecast_steps=0`), категория «Валюты».

Глубина истории (2026-08-05, self-healing): Binance BTCUSDT/ETHUSDT листингованы с 2017-08-17, SOLUSDT — с 2020-08-11; более ранний сегмент добирается с Coinbase Exchange (`api.exchange.coinbase.com/products/<sym>/candles`, дневные, ≤300 свечей/запрос) по `model_config_json.pre_binance`. Парсер дозапрашивает окно `[backfill_from, earliest)`, когда самая ранняя точка БД позже `backfill_from` — расширение истории делается сменой конфига + ETL, без одноразовых скриптов. На пересечении дат побеждает Binance (канон свежей эпохи).

| Индикатор | Endpoint | История |
|-----------|----------|---------|
| `btc-usd` | `api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d` — поле `close`, дата = календарный торговый день (UTC). Live-тикер — отдельно `ticker_sources/binance.py`. | 2015-07-20 → (Coinbase BTC-USD до 2017-08-16, дальше Binance) |
| `eth-usd` | то же, `symbol=ETHUSDT`. | 2016-05-18 → (Coinbase ETH-USD до 2017-08-16, дальше Binance) |
| `sol-usd` | то же, `symbol=SOLUSDT`. | 2020-08-11 → (Binance; монета запущена 2020-03, раньше первоисточника нет) |

## World Bank Pink Sheet monthly (`WorldBankPinkSheetParser`, `parser_type=world_bank_pink_sheet`)

Официальная месячная сводка цен на сырьё Всемирного банка (Commodity Markets / Pink Sheet). URL xlsx **меняется каждый месяц** — парсер открывает `worldbank.org/en/research/commodity-markets` и ищет ссылку `CMO-Historical-Data-Monthly.xlsx`. Лист `Monthly Prices`: строка имён, строка единиц, строки `YYYYMmm`. Колонка — `model_config_json.pink_sheet_column`. `replace_series=True` (полный снимок, срезает хвост старого Yahoo daily). Лицензия: CC-BY 4.0 Всемирного банка (attribution); публичное поле `source` = «Всемирный банк». Прогноз не строится; семья view-mode — T8 (месячный уровень).

| Индикатор | pink_sheet_column | Единица | Заметки |
|-----------|-------------------|---------|---------|
| `coal` | `Coal, Australian` | USD/т | Бенчмарк Ньюкасл; с 1970M01. Ранее Yahoo ICE Rotterdam `MTF=F` (мёртв с 2025-12-26). |
| `copper` | `Copper` | USD/т | Было USD/фунт daily Yahoo `HG=F`. |
| `silver` | `Silver` | USD/унция | Было daily Yahoo `SI=F`. |
| `wheat` | `Wheat, US HRW` | USD/т | Было US¢/бушель Yahoo `ZW=F`. |
| `soybean` | `Soybeans` | USD/т | Было US¢/бушель Yahoo `ZS=F`. |

**Снято с витрины:** `steel` (`is_active=False`, в `INDICATOR_HIDDEN_FROM_LISTING`) — нет свободного официального ряда HRC: CME/LME требуют коммерческой лицензии на историю; в Pink Sheet колонки HRC нет; индекс BLS PPI — не цена в USD/т. С 19.11.2026 адрес `steel` и его срезы ведут 301 на `steel-hot-rolled` — цену производителей горячекатаного листа в России (раздел «ЕМИСС — цены производителей стали»); строка `steel` и её 2 923 дневные точки в USD в боевой базе не тронуты.

**Brent, дневной источник (проверено 12.10.2026, круг 12).** Фьючерс BR на Мосбирже (ISS `engines/futures/markets/forts/securities`, ближайший контракт по `LASTTRADEDATE`, поля `LAST`/`SETTLEPRICE`) с ноутбука отвечает, цена обновляется в течение дня. Но условия Мосбиржи разрешают бесплатные данные ISS «только для ознакомления»; любое иное использование, в том числе показ на сайте с рекламой и подпиской, возможно только по договору с биржей (moex.com/a2193). Договора нет, поэтому по умолчанию Brent остаётся спотом EIA (FRED `DCOILBRENTEU`, выпуск раз в неделю, данные до вторника, подпись в ленте «официальные данные выходят раз в неделю»). **Круг 13 (R-BRENT, 12.10.2026):** коннектор написан — `backend/app/services/ticker_sources/moex_brent.py` (ближайший BR по `LASTTRADEDATE` строго позже сегодняшнего, цена `LAST`/`SETTLEPRICE`, изменение к `PREVSETTLEPRICE`, задержка из `SYSTIME − UPDATETIME`, на 12.10 ровно 15 минут, резерв EIA при сбое или старше 5 суток) — и подключён **флагом `RUSTATS_MOEX_BRENT_LIVE_ENABLED`, по умолчанию выключен**; при выключенном флаге запросов к бирже за нефтью нет ([ADR-0025](adr/0025-oil-quote-source-legality.md)). Условия биржи: показ биржевых данных на сайте — по информационному договору (moex.com/ru/products/publicdata); цены и объёмы заявок распространять нельзя; по тарифам (приказ МБ-П-2026-2794 от 09.07.2026, с 19.07.2026, п. 2.2, резидент, без НДС) задержанный информационный поток 25 500 руб./мес., реальное время 300 000, итоги торгов 15 000; задержка не менее 15 минут. Контакты: itsales@moex.com (договор), help@moex.com (техвопросы). Входит ли BR в задержанный поток, можно ли платить за один инструмент и какие требования к подписи и рекламе — публично не указано (вопросы в письме, черновик в отчёте зоны). Включать флаг только после подписания.

**Нефть: бесплатные официальные источники (проверено 12.10.2026, круг 13, R-BRENT2).** Подробная таблица и цитаты условий — в отчёте круга 13 `impl-r-brent2.md`; решение о допустимых источниках — [ADR-0025](adr/0025-oil-quote-source-legality.md). Флаг `RUSTATS_OPEC_ORB_ENABLED` и загрузчик корзины **не созданы** (условия запрещающие). Итог: бесплатного официального *реального времени* нет. Корзина ОПЕК (ORB) выходит ежедневно (`opec.org/basket/basketDayArchives.xml`, `<BasketList data= val=/>`, на 12.10 последнее значение 09.10, лаг 1 рабочий день), но её не заведено и заводить нельзя: условия ОПЕК (`opec.org/terms-and-conditions.html`, п. 6 и 8) запрещают показ, распространение и хранение материалов в общей базе, коммерческое использование — только по письменному разрешению; файл за проверкой Cloudflare (403 для скриптов) и сертификат сайта отдаётся без промежуточного звена цепочки. ORB — корзина из 12 сортов, не Brent, и называть её «Brent» нельзя. Спот Brent EIA: общественное достояние США, но источник цен у EIA — Refinitiv (LSEG) (страница определений `pet_pri_spt_tbldef2.asp`), оговорка про материалы третьих лиц в `eia.gov/about/copyrights_reuse.php`. Месячное среднее Brent: World Bank Pink Sheet (CC BY 4.0 на `data.worldbank.org/summary-terms-of-use`, с оговоркой про данные третьих сторон; в Pink Sheet источники — Bloomberg, S&P Global). Прогноз Brent: EIA STEO (выпуск 06.10.2026, следующий 10.11.2026). Минфин России Urals ежемесячно не публикует (страница `statistics/fedbud/oil` — только файл дополнительных нефтегазовых доходов, лицензия сайта CC BY 4.0); средняя цена Urals для НДПИ — у Минэкономразвития, сайт `economy.gov.ru` из сети проверки не открылся. Цен нефти у ЦБ РФ и у СПбМТСБ (только внутренние территориальные индексы; п. 4.2.3 пользовательского соглашения запрещает использование с целью извлечения прибыли) нет, Oil Bulletin ЕК — розничные цены на топливо, не нефть, IEA — отчёт платный.

**Legacy:** `parser_type=moex_brent_daily` (Yahoo chart) оставлен в реестре для тестов и неактивного `steel`; новые listed-ряды на Yahoo не заводить.

## FRED graph CSV (`FredCsvParser`, `parser_type=fred_csv`)

Публичный CSV без API-ключа: `fred.stlouisfed.org/graph/fredgraph.csv?id={fred_series_id}`. Заголовок `observation_date` (алиас `DATE`); пропуски — `.` (строки пропускаются). `backfill_from` обрезает более ранние точки после parse. Полная история приходит одним ответом; upsert идемпотентен (ADR-0002). `replace_series=True`. Пустой или нераспознанный ответ (21.10 17:11 UTC – 22.10 03:09 UTC три ряда подряд — `DGS10`, `DHHNGSP`, `DTWEXBGS` — вернули «0 точек» без причины, 22.10 17:09 ожили сами; Brent шёл через EIA и не пострадал) повторяется через 4 и 15 секунд; если точек нет и после повторов, прогон получает `failed` с началом тела ответа в `fetch_log.error_message`, а не `parsed_zero` с ложным «вероятна смена layout» (`mark_fetch_failed`). Что именно вернул FRED в то окно, не сохранилось (логи ротированы); с Mac 27.10.2026 все три адреса отдают валидный CSV. Канал доставки — FRED; публичное поле `source` называет **первоисточник** (ФРС / Минфин США / EIA), не St. Louis Fed.

Правовое основание для рядов ниже: данные ведомств США в public domain (EIA Copyrights and Reuse; Fed/Treasury H.10/H.15). FRED — redistributor. Ряды IMF Primary Commodity Prices на FRED (`PCOPPUSDM` и др.) **не используем** для витрины: copyright IMF, нужна отдельная лицензия на commercial redistribution — вместо них Pink Sheet напрямую от Всемирного банка.

| Индикатор | fred_series_id | Первоисточник (публичное поле) | Заметки |
|-----------|----------------|--------------------------------|---------|
| `usd-index` | `DTWEXBGS` | ФРС, релиз H.10 | Nominal Broad U.S. Dollar Index, база янв. 2006 = 100; с 2006-01-02. |
| `ust-10y` | `DGS10` | Минфин США | Доходность 10-летних Treasury; с 1962-01-02. |
| `brent` | `DCOILBRENTEU` | EIA | Europe Brent Spot Price FOB, USD/bbl; с 1987-05-20. Ранее Yahoo `BZ=F`. |
| `natural-gas` | `DHHNGSP` | EIA | Henry Hub Natural Gas Spot Price, USD/млн БТЕ; с 1997-01-07. Ранее Yahoo `NG=F`. |

> **Brent приходит раз в неделю (сверено 08.10.2026).** Спот Brent EIA публикует недельным выпуском (страница `RBRTEd.htm`: «Release Date 10/7/2026, Next Release Date 10/15/2026», данные по вторник включительно; книга `RBRTED.xls`, лист `Data 1`), поэтому в ленте курсов и на карточке нефть честно отстаёт на 1–9 суток; порог «давнее значение» для `brent` в `api/ticker.py` — 12 суток (`STALE_AFTER_DAYS_BY_CODE`), для остальных рядов ленты 3. Загрузка EIA и зеркала FRED идёт через ETL-сессию `create_session()` (с 08.10.2026, раньше голый `httpx`). Живого источника нефти в обход EIA платформа не берёт: решение P0 запрещает биржевую нефть в ленте. Подпись в ленте — «Brent». Контракт — [data-contracts](data-contracts.md#c10-data-2026-10-08).

Официального свободного дневного ряда цены золота (USD/унция) на FRED/ЕЦБ/LBMA без лицензии нет: `gold-usd` не заведён. Месячный ряд золота есть в Pink Sheet (`Gold`, $/troy oz) — отдельная задача, в оперативный срез главной не ставится.

## MOEX ISS — биржевые индексы daily (MoexIndexParser, `parser_type=moex_index_daily`)

Тикер config-driven через `model_config_json.moex_secid`. Прогноз не строится, категория «Индексы». Endpoint: `iss.moex.com/iss/history/engines/stock/markets/index/securities/<SECID>.json` с пагинацией по `start` (страница 100 строк). **Пагинация по сырому числу строк страницы, не по отфильтрованным точкам** — ранняя история индексов (напр. RGBI) содержит строки с `CLOSE=null`, и остановка по короткому отфильтрованному списку обрезала бы ряд.

| Индикатор | moex_secid | Заметки |
|-----------|-----------|---------|
| `imoex` | `IMOEX` | Индекс МосБиржи. |
| `mcftr` | `MCFTR` | Индекс полной доходности. |
| `rtsi` | `RTSI` | Индекс РТС (в долларах). |
| `rgbi` | `RGBI` | Индекс гособлигаций (ОФЗ), история с 2003. |
| `corp-bond-index` | `RUCBTRNS` | Индекс корпоративных облигаций. |

## ЦБ РФ — HTML-таблицы (CbrKeyRateParser, CbrReservesParser, CbrRuoniaParser)

| Индикатор | URL |
|-----------|-----|
| `key-rate` | `cbr.ru/hd_base/KeyRate/` (UniDbQuery `DD.MM.YYYY`) |
| `international-reserves` | `cbr.ru/hd_base/mrrf/mrrf_7d/` (monthpicker `MM.YYYY`, пол с 29.05.1998; `backfill_from=1998-05-01`) |
| `ruonia` | `cbr.ru/hd_base/ruonia/dynamics/` (UniDbQuery `DD.MM.YYYY`) |
| `deposit-rate-max` (19.11.2026, `cbr_deposit_max_html`) | `cbr.ru/statistics/avgprocstav/` (UniDbQuery `DD.MM.YYYY`, с 01.07.2009 — 624 декады, ~95 КБ); строка «I.11.2026 — 13,3050» → точка 01.11.2026 (II → 11-е, III → 21-е). Частота карточки `weekly` (ближайшая к «раз в 10 дней»), первая загрузка — вся история, дальше запрос «120 дней» (страница отдаёт не меньше двух последних лет) |

### ЦБ РФ — инфляционные ожидания и потребительские настроения (CbrInflationExpectationsParser, 19.11.2026)

`inflation-expected`, `inflation-observed`, `consumer-sentiment` (`parser_type=cbr_inflation_expectations_xlsx`,
реестр `app.data.cbr_household_rates`). Опрос «инФОМ» для Банка России; файл к каждому месяцу содержит всю историю
с декабря 2009 года (лист «Данные за все годы»: строка 2 — даты, строки «Прямые оценки годовой инфляции: медианные
значения» → «наблюдаемая инфляция (в %)» / «ожидаемая инфляция (в %)», «Индекс потребительских настроений (ИПН)» →
«индекс потребительских настроений (в пунктах)»). Адрес файла меняется каждый месяц: `cbr.ru/analytics/dkp/inflationary_expectations/`
→ самая поздняя `Infl_exp_YY-MM/` → ссылка `/Collection/Collection/File/<id>/Infl_exp_YY-MM.xlsx` (~2 МБ, разбор
<1 с; три ряда читают один файл — кэш в процессе 30 минут). Живая сверка 19.11.2026: октябрь 2026 — ожидаемая 13,22 %
(в тексте выпуска 13,2 %, сентябрь 14,2 %), наблюдаемая 14,47 % (14,5 %), ИПН 95,07. До 2014 года опрос шёл не каждый
месяц: ожидания — 163 точки, ИПН — 164. Боевой сервер отвечает 200 на раздел, avgprocstav и xlsx (19.11.2026).

## ЦБ РФ — DataService JSON (CbrDataServiceParser)

Endpoint: `cbr.ru/dataservice/data?publicationId={pub}&datasetId={ds}&measureId={measure}&y1={from}&y2={to}` → фильтр по `element_id`.

| Индикатор | publicationId / datasetId / measureId / element_id | date_offset_months |
|-----------|----------------------------------------------------|--------------------|
| `mortgage-rate` | 14 / 29 / — / 36 | -1 (default) |
| `auto-loan-rate` | 14 / 28 / 2 / 110 | -1 |
| `credit-rate-corp-short` | 14 / 25 / 2 / 7 | -1 |
| `credit-rate-corp-1to3y` | 14 / 25 / 2 / 9 | -1 |
| `credit-rate-corp-over3y` | 14 / 25 / 2 / 10 | -1 |
| `credit-rate-ind-short` | 14 / 27 / 2 / 7 | -1 |
| `credit-rate-ind-1to3y` | 14 / 27 / 2 / 9 | -1 |
| `credit-rate-ind-over3y` | 14 / 27 / 2 / 10 | -1 |
| `deposit-rate` | 18 / 37 / 2 / 7 | -1 |
| `consumer-credit` | 20 / 42 / 22 / 35 | -1 (остаток на 1-е число = конец прошлого месяца; value_divisor=10⁶ → трлн) |
| `consumer-loans-issued` | 20 / 41 / 22 / 35 | -1 (value_divisor=10³ → млрд за месяц) |
| `consumer-credit-overdue` | 20 / 43 / 22 / 35 | -1 (10³ → млрд) |
| `mortgage-issued-count` | 21 / 44 / 22 / 35 | -1 (10³ → тыс. кредитов) |
| `mortgage-issued` | 21 / 45 / 22 / 35 | -1 (10³ → млрд за месяц) |
| `mortgage-debt` | 21 / 46 / 22 / 35 | -1 (10⁶ → трлн) |
| `mortgage-overdue` | 21 / 47 / 22 / 35 | -1 (10³ → млрд) |
| `mortgage-term` | 21 / 48 / 22 / 36 (в рублях; «всего» у набора нет) | -1 (месяцы) |
| `business-credit` | 22 / 50 / 22 / 35 | 0 (value_divisor=10⁶ → трлн) |
| `current-account` | 8 / 9 / — / — | 0 |
| `m0` | 5 / 5 / — / — | 0 |
| `m1` | 5 / 6 / — / 12 | 0 |
| `m2` | 5 / 7 / — / 12 | 0 |

> **Глубина истории (Фаза 3, 2026-06-24).** `current-account` — `backfill_from_year=1998` (API-пол ряда 1998-04, понижено с 2000). Ставки/кредиты/ипотека (`credit-rate-*`, `deposit-rate*`, `auto-loan-rate`, `consumer-credit`, `business-credit`, `mortgage-rate`) — API-floor = текущему `backfill` (2014/2017/2019): это начало датасета CBR по данной методологии, глубже официально нет (пред-2014 ставки — иной ряд, сплайс = методологический разрыв). `m0/m1/m2` денежные агрегаты с 2026-05 живут в `cbr_monetary_agg_xlsx` (отдельный парсер, см. ниже), не в DataService; `m2` понижен до `backfill_from_year=1992` (xlsx содержит M2 с 1992-12).

**Сумма-композит** (CbrDataServiceSumParser, `dataservice_components` массив):

| Индикатор | Components (pub/ds/element_id) |
|-----------|--------------------------------|
| `deposits-business` | sum(5/6/15, 5/7/21, 5/8/25) |
| `deposits-individual` | sum(5/6/16, 5/7/22, 5/8/26) |

## Минфин — федеральный бюджет (MinfinBudgetParser)

Каталог OpenData: `minfin.gov.ru/opendata/7710168360-fedbud_month/` → находит latest CSV → парсит.

**Trap (in-place content update)**: timestamp в имени CSV (`data-YYYYMMDDTHHMM-structure-…csv`) — это дата создания паспорта, а **не** snapshot content. Минфин дополняет тот же URL новыми месяцами в течение дня. Поэтому утренний `daily_update_job` (03:00 MSK) может получить ещё «вчерашнюю» версию того же URL. Контрмеры: `late_minfin_etl_job` (APScheduler 15:00 MSK) перезапускает все `parser_type=minfin_budget_csv` индикаторы; парсер логирует `last_parsed_date` + `last_db_date`. См. `docs/enterprise_resilience.md::Парсеры и источники`.

**Trap (503 + `/ru/` CSV path, 2026-07)**: каталог Минфина периодически отвечает 503; глобальный `http_client` (total=3) исчерпывался → падали сразу три индикатора (`budget-*`), каждый раз заново долбя каталог. Контрмеры в `minfin_budget_parser`: Minfin-specific Retry, process TTL-кэш URL (10 мин, один hit на тройку), last-good URL в state Redis. **CSV всегда без `/ru/`**: `…/opendata/…/data-*.csv` (200); `…/ru/opendata/…/data-*.csv` → 404.

**Trap (Росстат не принимает соединения, 2026-10-07)**: rosstat.gov.ru ~8 ч отбрасывал TCP (ConnectTimeout напрямую и через Tor). До фикса каждый файл-кандидат стоил ~11 мин, индикатор `ind` — до часа, daily ETL шёл 9 ч и блокировал планировщик. Сейчас `http_client` ограничивает connect и после отказа всех хопов 20 мин отвечает по хосту мгновенной ошибкой — индикаторы Росстата в таком окне падают быстро и догоняются вечерним/следующим прогоном. Подробно — `CONTEXT.md` (Scheduler event-loop block).

**Состояние 2026-10-08 — живого пути к Минфину с прода нет.** Блок явный: страница nginx «Доступ к сайту временно ограничен владельцем веб-ресурса», IP `201.51.11.170` (ID запроса `25d49ac6f21296edb192b7b50fa96c5a`). Tor с этого хоста не работает: два свежих временных экземпляра (выходы RU/BY/KZ и любые) за 2 мин не прошли bootstrap дальше 45%/10% — Tor режется на уровне провайдера; рабочий экземпляр держится на старых guard-ах и цепочки до minfin не строит. Последняя живая загрузка — 2026-08-19 (`data-20260812…csv`); с тех пор только снимок из репозитория, а прогоны снимком до 26.09 (до `keep_after`) стёрли июль. `budget.gov.ru` с прода тоже не отвечает. Снимок `backend/app/data/minfin/fedbud_month.csv` обновлён 2026-10-08 с Mac владельца из `data-20260910T0100-structure-20210312T0100.csv` (июль, август 2026, ревизия июня) и вручную загружен на прод (docker cp + `run_etl_for_indicator`). Минфин выпускает файл ~10-го числа. **Tor как обход (июль 2026) исчерпан:** в консенсусе Tor на 2026-10-08 один выход RU/BY/KZ (`eden`, 194.55.167.14), и до Минфина он не достаёт; адреса ДЦ, прокси и WARP Минфин режет (проверено ещё 12.07). **Доставка с Mac владельца (с 2026-10-08):** `scripts/minfin-sync-from-mac.sh` берёт свежий `data-*.csv` с сайта Минфина (домашний IP пропускается), проверяет парсером (заголовок, ни одна дата текущего прод-снимка не пропала), при изменении sha кладёт файл в контейнеры scheduler/backend и прогоняет `budget-*`. Расписание — launchd-агент `~/Library/LaunchAgents/com.forecasteconomy.minfin-sync.plist` (11:30 и 16:30, пропуск догоняется после пробуждения), журнал `~/Library/Application Support/ForecastEconomy/minfin-sync/sync.log`, сбой — уведомление macOS. Ограничения: Mac должен включаться; `fetch_log` при этом честно `fallback_used` (живой путь с прода закрыт); пересоздание контейнера возвращает снимок из образа до следующего запуска скрипта (точки новее снимка не удаляются).

**Состояние 2026-10-12 (круг 12) — снимок бюджета обновляется руками.** `minfin.gov.ru` по-прежнему отвечает 503 адресам Timeweb (AS9123/210976), Tor даёт ConnectTimeout, поэтому ежедневный сбор бюджета идёт по упакованному снимку `backend/app/data/minfin/fedbud_month.csv` и пишет «Fallback source». Снимок обновлён с ноутбука из официального OpenData (паспорт 7710168360-fedbud_month, файл от 09.10.2026): 189 точек, добавлен сентябрь 2026, август пересмотрен; тест `test_minfin_budget.py` проверяет покрытие сентября. Следующая публикация Минфина (данные за октябрь) — около 10–15 ноября; до этого снимок кончается сентябрём. Обновлять руками раз в месяц: единственный способ без прокси.

**Trap (прод-IP ban на весь minfin.gov.ru, 2026-07-12)**: с `201.51.11.170` и с OpenRouter-прокси `5.129.210.89` — стабильный 503; с обычных сетей — 200. `http_client.ProxyFallbackSession`: direct → HTTP (`RUSTATS_ETL_HTTP_PROXY_URL` / `OPENROUTER`) → SOCKS (`RUSTATS_ETL_SOCKS_PROXY_URL`). На проде SOCKS = host Tor `socks5h://172.18.0.1:9050` (Tor `SocksPort` на gateway сети `rosstat_default`; из контейнера нужен PySocks). Live-проверка: catalog+CSV через Tor = 200 (в июле; с 08.10 Tor до Минфина не достаёт). **28.10.2026:** на проде HTTP-звено ETL было выключено (`RUSTATS_ETL_HTTP_PROXY_URL=off`), поэтому ЕМИСС (`fedstat.ru`, 403 на IP прода) оставался без обхода — региональные цены на топливо стояли на июле. Включено (пусто = релей `OPENROUTER_PROXY_URL`, сервер `vps` 5.129.210.89 на Timeweb): через релей fedstat отдаёт 200 и на GET, и на POST `dataGrid.do`, Росстат 200; Минфин и через релей 403 (одна сеть Timeweb), для него остаётся `scripts/minfin-sync-from-mac.sh`. Цена включения: запрос к Минфину теперь проходит звенья direct → релей → Tor (до ~60 с), дальше предохранитель звена на 20 минут. Packaged snapshot `backend/app/data/minfin/fedbud_month.csv` остаётся последним fallback. **Не ставить Cloudflare WARP на хост** — ломает весь сетевой стек. **Trap (ночные timeout 300с, 2026-07-13)**: urllib3 Retry(connect/read=3) × timeout 45–90с сжигал бюджет `wait_for` до artifact; укорочены Minfin retries (total/connect/read=1, timeout 25–40с), `ETL_TIMEOUT_BY_PARSER[minfin_budget_csv]=600`. **Update (2026-08-27)**: внешний релей `5.129.210.89:8888` был молча убит вручную 22.08 (root-сессия, SIGKILL tinyproxy без автоперезапуска; CONNECT-тест «висит», а tcp-ping ложно успешен из-за SYN-proxy хостера); восстановлен, юнит получил `Restart=always`. ETL-фолбэк на SOCKS/Tor не страдал. OpenRouter-egress Пульса — снова штатный релей; горячий резерв — локальный мост `tor-http-bridge` на host-Tor прод-сервера (`172.18.0.1:8888`) — см. `CONTEXT.md::traps`.

| Индикатор | budget_target |
|-----------|---------------|
| `budget-revenue` | `revenue` |
| `budget-expenditure` | `expenditure` |
| `budget-deficit` | (default = revenue − expenditure) |

---

## Минфин — ФНБ и государственный долг (MinfinDebtParser, `parser_type=minfin_debt_xlsx`, 19.11.2026)

Реестр `backend/app/data/minfin_debt.py`, парсер `backend/app/services/minfin_debt_parser.py`; ряд выбирается `model_config_json.minfin_series`. Лицензия сайта Минфина — CC BY 4.0. Все даты — «на 1-е число месяца».

| Индикатор | Файл (страница) | Что берётся |
|-----------|-----------------|-------------|
| `nwf-volume` | `Dannye_YYYYMMDD.xlsx` (`perfomance/nationalwealthfund/statistics`) | «Объем на конец периода», млрд руб.; месяц M → 1-е число M+1 |
| `nwf-liquid` | то же | «Объем на конец периода» − «Размещено в иные разрешенные активы» = средства на счетах в Банке России |
| `nwf-volume-usd` | то же | «Объем средств фонда … (млрд. долларов США)» |
| `nwf-gdp` | то же | «в т.ч. в процентах к ВВП» × 100 |
| `gov-debt-domestic` | `Obem_gosdolga_s_garantiyami_god_polnostu_na_DD_MM_YYYY.xls` (`public_debt/internal/structure`) | лист на год с 2009, строка «… внутренний долг … — всего», млрд руб. |
| `gov-debt-external` | `GVD_YYYYMMDD.xlsx` (`public_debt/external/structure`) | столбец «Всего», млн $ → млрд $, с 2011 |

Живые значения 19.11.2026: ФНБ на 01.11.2026 — 13 055,34 млрд ₽ (5,6% ВВП, 162,06 млрд $), ликвидная часть 3 578,48; внутренний долг на 01.11.2026 — 36 919,143 млрд ₽; внешний — 57,984 млрд $. Две ячейки ФНБ в рублях — текст со сноской («12 405,77³», апрель и октябрь 2020): знак сноски отбрасывается.

**Trap (шапка дат во внутреннем долге):** с 2023 года суммы долга (20–37 тыс. млрд) попадают в диапазон чисел дат Excel; шапкой считается только строка без подписи в первом столбце.

**Доставка.** Боевому серверу Минфин отвечает 503/403 (как и бюджету, раздел выше), живой путь в парсере сохранён на случай снятия блока. Резерв — снимки `backend/app/data/minfin/{nwf.xlsx, gov_debt_domestic.xls, gov_debt_external.xlsx}` (файлы 19.11.2026); прогон по снимку пишет `fallback_used`, точки новее снимка не удаляются. Файл и неудача живого пути кэшируются в процессе на 10 минут на источник: четыре ряда ФНБ ждут цепочку прокси один раз. Свежие файлы доставляет `scripts/minfin-debt-sync-from-mac.sh` (страница → ссылка тем же `latest_link` → проверка парсером: точки есть, даты прод-снимка не пропали → `docker cp` в scheduler/backend → ETL рядов источника). Расписание — launchd-агент `com.forecasteconomy.minfin-sync` (копия `scripts/mac/com.forecasteconomy.minfin-sync.plist`): бюджет и ФНБ/госдолг, 11:30 и 16:30. **19.11.2026 агента в `~/Library/LaunchAgents` не было** (лежали только backup-pull и db-refresh), поэтому бюджет на проде стоит на сентябре 2026; установка — команда в комментарии plist. Минфин обновляет файлы ФНБ и госдолга в первые две недели месяца.

---

## Росстат — потребительские цены (RosstatCpiParser)

Шаблон файла из `settings.rosstat_cpi_template`: `ipc_mes_{MM}-{YYYY}.xlsx` (resolve latest через `RosstatFetcher.fetch_latest`).

| Индикатор | Sheet |
|-----------|-------|
| `cpi` | `01` |
| `cpi-food` | `02` |
| `cpi-nonfood` | `03` |
| `cpi-services` | `04` |

## Росстат — недельная инфляция (RosstatWeeklyCpiParser)

> **Бюллетени в PDF и восстановленный сайт (13.11.2026).** С октября 2026 недельный бюллетень «Об оценке индекса потребительских цен…» лежит как `mediabank/<num>_DD-MM-YYYY.pdf` (пример: `172_11-11-2026.pdf`, период и значение в первом абзаце). После аварии 01–10.11.2026 часть файлов названа произвольно (`168ozen28.pdf`, `ipc11_02.pdf`), а ссылки в ленте бывают абсолютными. Парсер узнаёт бюллетень по заголовку ссылки в `/central-news`, год берёт из имени файла или из заголовка, текст PDF читает `pypdf` (первые две страницы), разбор идёт и по тексту без пробелов: `pypdf` рвёт слова. До этой правки общий ряд `inflation-weekly` стоял на 26.10.2026, сегменты из `nedel_Ipc.xlsx` дошли до 09.11, а прогон считался успешным; живая проверка 13.11 дала шесть точек, включая 02.11 (99,96) и 09.11 (100,12). Разрыв «сегменты новее общего ряда дольше четырёх дней» теперь поднимается как zero-parse (`_headline_lag_reason`).

Multi-source merge:

1. **Primary HTML-бюллетени** `mediabank/<num>_DD-MM-YYYY.html`. Discovery (union):
   - **central-news crawler**: пагинированный список `rosstat.gov.ru/central-news?page=1..N` с заголовками. Архив 2023-05-04 → today (page=1). page=66+ возвращают пустую ленту.
   - **search API fallback**: `rosstat.gov.ru/search?q=оценке индекса потребительских цен <месяц> <год>` для edge cases когда новый bulletin ещё не на page=1.
2. **XLSX продкорзина** `mediabank/Nedel_ipc.xlsx` + веса из `mediabank/ipc_spr_{MM}-{YYYY}.xlsx` — applied только для дат **≥ `weekly_cutoff_date`** (current 2023-01-09).

| Индикатор | Files |
|-----------|-------|
| `inflation-weekly` | `Nedel_ipc.xlsx` + `ipc_spr_{MM}-{YYYY}.xlsx` + bulletin HTMLs |
| `inflation-weekly-food` | тот же `Nedel_ipc` + `ipc_spr` (сегмент продовольствие, local code 10–4099); ETL пишет primary `inflation-weekly` |
| `inflation-weekly-nonfood` | то же (сегмент непродовольствие, code ≥4100 &lt;9000) |
| `inflation-weekly-services` | то же (сегмент услуги, code ≥9000) |

**Глубина**: 2023-01-09 → present. **Cutoff введён 2026-05-12**: до 2023-01-09 у Росстата нет публично доступных bulletins (rosstat.gov.ru 404 на старые номера, search API возвращает 0 results за 2022, Wayback CDX empty для `mediabank/*-2022.html`). XLSX-approximation за 2022 расходилась с monthly CPI до 3 pp (март 2022) — введение явно. См. `docs/missed_data_audit.md::Nedel_ipc` для развёрнутой research-сводки.

**Deep dive 2026-05-12 — bulletin coverage увеличена до 169/170**:
1. **Открытие**: Росстат начал публиковать **отдельные weekly bulletin'ы** только в **январе 2023 года**. До 2023 — только monthly «Об индексе потребительских цен в <месяц>». Утверждение «бюллетени с 2003 года» — заблуждение. Подтверждено через Wayback Machine CDX `rosstat.gov.ru/storage/mediabank/*.htm` за 2020-2023: 174 candidate URLs, 0 weekly bulletin'ов за 2020-2022, первый weekly bulletin за 2023-01-09.
2. **Bug fix**: `bulletin_years = [today.year]` → `[2023..today.year]`. Раньше 135 точек 2023-2025 в БД были XLSX-агрегатом (расхождение с bulletin до 0.12pp). После backfill — все 153 точки 2023-05+ = bulletin.
3. **Wayback backfill 2023-01..04**: для 16 недель до начала central-news архива (2023-05-04) восстановили bulletin через `web.archive.org/web/<ts>id_/<url>` + `_parse_bulletin_html`. Заменили XLSX → bulletin.
4. **Итог**: 169/170 точек = подлинные значения Росстатовских bulletin'ов. Единственный gap — 2023-05-02 (XLSX-fallback, в Wayback нет snapshot bulletin'а за эту неделю).

## Росстат — производственные цены (RosstatPpiParser)

| Индикатор | File |
|-----------|------|
| `ppi` | `mediabank/osn-{MM}-{YYYY}.pdf` (chain MoM% from socioeconomic report PDF) |

## Росстат — цены на жильё (RosstatHousingParser)

| Индикатор | File |
|-----------|------|
| `housing-price-primary` | `mediabank/osn-{MM}-{YYYY}.pdf` (chain QoQ% primary) |
| `housing-price-secondary` | `mediabank/osn-{MM}-{YYYY}.pdf` (chain QoQ% secondary) |

## Росстат — ВВП (RosstatGdpParser)

Два источника + ratio-splice через `gdp_overlap_year=2011` (см. ADR-0004).

| Индикатор | gdp_source | File | Modern sheet | History sheet | Row |
|-----------|------------|------|--------------|---------------|-----|
| `gdp-nominal` | official_quarterly | `mediabank/VVP_kvartal_s-1995-{YYYY}.xlsx` (следующий год → текущий → прошлый; зафиксирован `-2026`) | `2` | `1` | — |
| `gdp-real` | official_quarterly | `mediabank/VVP_kvartal_s-1995-{YYYY}.xlsx` (как выше) | `9` | `3` | — |
| `gdp-consumption` | official_use | `mediabank/GDP-quarters-of-use-1995_{N}kv-{YYYY}.xls` (самый свежий из 6 кварталов вниз от текущего; зафиксирован `1kv-2026`) | `2` | `1` | 7 |
| `gdp-government` | official_use | `mediabank/GDP-quarters-of-use-1995_{N}kv-{YYYY}.xls` (самый свежий из 6 кварталов вниз от текущего; зафиксирован `1kv-2026`) | `2` | `1` | 8 |
| `gdp-investment` | official_use | `mediabank/GDP-quarters-of-use-1995_{N}kv-{YYYY}.xls` (самый свежий из 6 кварталов вниз от текущего; зафиксирован `1kv-2026`) | `2` | `1` | 11 |

История ВВП: 1995-Q1 → present (~125 точек на каждый индикатор после Q1-2026).

**Trap (ВВП по использованию, 2026-10-28):** имя файла несёт номер последнего квартала, и Росстат кладёт новый файл рядом со старым. Зашитый `..._1kv-2026.xls` отдавал 200 и после выхода II квартала: `gdp-consumption`, `gdp-government`, `gdp-investment` стояли на 2026-03-01, когда `gdp-nominal` и `gdp-real` уже были на II квартале. `fetch_rosstat_gdp_use_latest` перебирает 6 кварталов вниз от текущего, затем зафиксированный адрес; сетевой отказ — `RosstatUnreachable`, а не «файл не найден».

**Trap (год в имени «ВВП по кварталам», 2026-10-28):** имя несёт год последних кварталов (`-2026` отдаёт II квартал, `-2027` ещё 404). Со сменой года Росстат может выложить файл под новым именем, а старый продолжит отдавать 200 без свежих кварталов, поэтому `fetch_rosstat_gdp_quarterly_latest` проверяет следующий год первым; зафиксированный адрес — запасной.

**Trap (имя файла, 2026-07):** на `/statistics/accounts` канон — `VVP_kvartal_s-1995-2026.xlsx` (дефис после `s`). Старый URL `VVP_kvartal_s_1995-2026.xlsx` (подчёркивание) всё ещё 200, но без I кв. 2026 — ETL молча `no_new_data`. URL в `ROSSTAT_STATIC_URLS['gdp_quarterly']`. Аналогично use-side: канон `GDP-quarters-of-use-1995_1kv-2026.xls`; старый `…-4kv-2025.xls` остаётся без I кв. 2026.

## Росстат — промышленность (RosstatIpiParser)

Chain MoM% из двух XLSX (база 2018 + база 2023).

Раздел ОКВЭД2 config-driven через `model_config_json.okved_section` (точный код в колонке «Код ОКВЭД2», лист «1»): `BCDE` агрегат (default), `B`/`C`/`D`/`E` — составляющие. Chain/anchor (2023 avg=100) общий. Прогноз — `monthly_auto` (12 мес), generic-семья T3 разворачивает уровень/средние/приросты/Г-г.

| Индикатор | okved_section | Files |
|-----------|---------------|-------|
| `ipi` | `BCDE` | `mediabank/ind_baza_2018_12-2025.xlsx` (history) + `mediabank/ind_baza_2023_{MM}-{YYYY}.xlsx` (current; с 28.10.2026 обязателен — сбой текущего файла = `failed`, история в БД не трогается) |
| `ipi-mining` | `B` | те же файлы |
| `ipi-manufacturing` | `C` | те же файлы |
| `ipi-energy` | `D` | те же файлы |
| `ipi-water` | `E` | те же файлы |

## Росстат — еженедельные средние цены на топливо (RosstatWeeklyPriceParser)

Источник: `mediabank/nedel_sred_cen.xlsx` — «Еженедельные средние потребительские цены (на конец периода)», листы по годам (2022→текущий), абсолютная цена в руб./единицу. Целевая строка config-driven через `model_config_json.product_label` (точное совпадение col 0 → подстрока). Частота weekly, категория «Цены», прогноз `generic_ols` (8 недель, transform absolute). Generic-семья T5 (как резервы): уровень на конец периода + средние мес/кв/год + Г/г.

| Индикатор | product_label |
|-----------|---------------|
| `fuel-ai92` | «Бензин автомобильный марки АИ-92, л» |
| `fuel-ai95` | «Бензин автомобильный марки АИ-95, л» |
| `fuel-diesel` | «Дизельное топливо, л» |

**Бюллетень в PDF (19.11.2026).** Свежая неделя выходит сначала в бюллетене «О потребительских ценах на нефтепродукты» (среда, иногда четверг), xlsx догоняет позже. С октября 2026 бюллетень — PDF (`175_18-11-2026.pdf`, `169n-ben28.pdf`), ссылки в ленте бывают абсолютными. Парсер искал только `…_DD-MM-YYYY.html`, поэтому бюллетень молча пропускался: 18–19.11 цена на 16.11 стояла в PDF, а на сайте оставалась цена на 9.11. Теперь ссылка узнаётся по заголовку (общий шаблон с недельным ИПЦ), текст первой страницы читает pypdf, таблица «… дизельное топливо по Российской Федерации» даёт две даты регистрации. Сбой xlsx (404 в дни частичного восстановления Росстата) больше не отменяет бюллетень; ошибка остаётся ошибкой, только если нет и бюллетеня. Образцы — `backend/tests/fixtures/rosstat_fuel/`.

Журнал загрузки дизеля 30.10–19.11.2026 (51 прогон: 2 успешных, 15 `failed`, 11 `parsed_zero`, 23 `no_new_data`): все `failed` и `parsed_zero` — недоступность Росстата 01–12.11 (заглушка, старая копия, 404 xlsx; см. `rosstat_outage.py`), а не вёрстка. Единственный собственный дефект — пропуск PDF-бюллетеня выше.

**Сбой сети не равен смене вёрстки (2026-10-12).** 09.10 03:02 `rosstat.gov.ru` не принял соединение, предохранитель хоста сработал, парсеры проглотили `RequestException` и вернули 0 точек: статус `parsed_zero`, ложное «смена layout» (вёрстка не менялась: живой xlsx даёт 242 точки до 28.09, бюллетень недельной инфляции — 156 до 05.10). Теперь `http_client` ведёт журнал сетевых сбоев прогона, и `BaseParser.run` ставит `failed` («Source unreachable»), если 0 точек и был сбой источника. В репозитории лежат усечённые образцы `backend/tests/fixtures/rosstat_fuel/` (xlsx и бюллетень №156 от 07.10.2026) и тесты разбора `test_rosstat_fuel_samples.py`.

> Тот же файл содержит ещё ~110 товаров (продовольствие, лекарства, стройматериалы) — при необходимости любой расширяется одной seed-строкой с нужным `product_label`, без правки парсера.

**Продукты и АИ-98 (19.11.2026).** Из того же файла заведён ходовой набор — реестр `backend/app/data/rosstat_weekly_goods.py` (`GOODS`, seed через `seed_indicators()`): 20 продуктов (`price-eggs`, `price-sugar`, `price-buckwheat`, `price-rice`, `price-bread`, `price-milk`, `price-butter`, `price-sunflower-oil`, `price-cheese`, `price-chicken`, `price-beef`, `price-pork`, `price-potatoes`, `price-cabbage`, `price-onions`, `price-carrots`, `price-cucumbers`, `price-tomatoes`, `price-bananas`, `price-apples`) и `fuel-ai98` («Бензин автомобильный марки АИ-98 и выше, л»). Простые недельные ряды без семьи view-mode и без прогноза (`forecast_steps: 0`), категория «Цены». Файл получен 19.11.2026 через ETL-сессию прода (с Mac `rosstat.gov.ru` не открывался ни через VPN, ни через `en0`): последняя неделя — 9 ноября 2026, яйца 111,46 ₽ за 10 шт., сахар 80,78 ₽/кг, гречка 93,87 ₽/кг, АИ-98 103,97 ₽/л; 5 157 точек на 21 ряд. Сыр — с 2023 года (на листе 2022 другая строка, «Сыры сычужные твердые и мягкие»). Файл качается один раз на прогон (кэш процесса 10 минут в `_weekly_xlsx`), а не на каждый из 24 рядов. Фикстура `backend/tests/fixtures/rosstat_weekly_goods/nedel_sred_cen_2026-11-19.xlsx`, тест `test_zone_i_sources.py`. Лекарства, одежда, услуги, алкоголь и табак не заведены: спроса во фразах Яндекса за 90 дней нет.

## Росстат — труд (RosstatLaborParser)

Все 4 индикатора из одного PDF доклада СЭП (`fetch_latest_socioeconomic_report_pdf`).

| Индикатор | File |
|-----------|------|
| `employment` | `mediabank/osn-{MM}-{YYYY}.pdf` |
| `labor-force` | `mediabank/osn-{MM}-{YYYY}.pdf` |
| `unemployment` | `mediabank/osn-{MM}-{YYYY}.pdf` |
| `wages-nominal` | `mediabank/osn-{MM}-{YYYY}.pdf` |

## Росстат — мес. промышленные показатели (RosstatIndParser)

Шаблон файла: `mediabank/ind_{MM}-{YYYY}.xlsx`.

| Индикатор | Sheet |
|-----------|-------|
| `capital-investment` | `1.6 ` — `quarterly_flow`: лист до ~2016 с помесячными потоками, с 2016 только кварталы; парсер сворачивает в квартальные суммы и `prune` старых месячных дат |
| `construction-work` | `1.7 ` |
| `housing-commissioned` | `1.8 ` |
| `retail-trade` | `1.12 ` |

## Росстат — основные фонды (RosstatFixedAssetsParser)

| Индикатор | File template |
|-----------|---------------|
| `depreciation-rate` | discovery: `folder/11186` → `St_izn_of_{YYYY}.xlsx` (fallback year-probe) |

## Росстат — демография (RosstatDemoParser)

Каталог раздела: `https://rosstat.gov.ru/folder/12781`. Имена файлов резолвятся
со страницы (regex), затем fallback year-probe — Росстат периодически меняет
точное имя (`demo21_2023.xlsx` и т.п.).

| Индикатор | demo_file | File |
|-----------|-----------|------|
| `births` | `demo21` | `mediabank/demo21_{YYYY}.xlsx` + при лаге годовой таблицы — полный год из `Edn_12-{YYYY}_t1.xlsx` (оперативные итоги ЕДН) |
| `deaths` | `demo21` | то же |
| `birth-rate` | `demo21` | то же |
| `death-rate` | `demo21` | то же |
| `working-age-population` | `demo14` | `mediabank/demo14.xlsx` |
| `pop-under-working-age` | `demo14` | `mediabank/demo14.xlsx` |
| `pop-over-working-age` | `demo14` | `mediabank/demo14.xlsx` |
| `pensioners` | `pensioners` | `mediabank/Sp_2.1_{YYYY}.xlsx` |

> **demo21:** в файле три блока (всё / город / село) с повторяющимися годами —
> парсер берёт первое вхождение каждого года (= «Все население»). Годовая
> таблица на август 2026 опубликована как `demo21_2023.xlsx` (ряд до 2023);
> календарный 2024 подтягивается из оперативного ЕДН за декабрь, пока Росстат
> не выложит `demo21_2024.xlsx`. Возрастные группы `demo14` — последний год
> источника 2023 (естественный лаг публикации).

## Росстат — население (RosstatPopulationParser)

Multi-source merge: история (1897+) + components (1990+) + latest актуальный год.

| Индикатор | Files |
|-----------|-------|
| `population` | `mediabank/Popul_1897+.xlsx` + `mediabank/Popul components_1990+.xlsx` + `mediabank/OkPopul_Comp{YYYY}_Site.xlsx` |
| `population-total-growth` | `mediabank/Popul components_1990+.xlsx` (обновлено 25.04.2025, последний год ряда — 2024) |
| `population-natural-growth` | `mediabank/Popul components_1990+.xlsx` |
| `population-migration` | `mediabank/Popul components_1990+.xlsx` |

## Росстат — наука и инновации (RosstatScienceParser)

Каталоги: `https://rosstat.gov.ru/statistics/science`, кадры ВО —
`https://rosstat.gov.ru/statistics/education`. Discovery по regex со страницы
раздела (устойчиво к `Kadry_VO`↔`Kadry-VO`, `innov-mp_1`↔`Innov_mp_1`).

| Индикатор | File | Sheet/Row |
|-----------|------|-----------|
| `grad-students` | `mediabank/Kadry-VO.xls` (fallback `Kadry_VO.xls`) | sheet 1 |
| `doctoral-students` | то же | sheet 4 |
| `rd-organizations` | `mediabank/nauka_1_{YYYY}.xlsx` (с 31.08.2026, данные по 2025 год; прежний `Nauka_1.xls` — запасной, остановился на 2024) | sheet 1, "всего" row |
| `rd-personnel` | `mediabank/nauka_2_{YYYY}.xlsx` (с 31.08.2026, данные по 2025 год; прежний `nauka_2.xls` — запасной, остановился на 2024) | sheet 1, "всего" row |
| `innovation-activity` | `mediabank/innov_1_{YYYY}.xls` | sheet 1, RF row; `min_year=2018` |
| `tech-innovation-share` | `mediabank/innov_2_{YYYY}.xls` | sheet 1, RF row; `min_year=2018` |
| `small-business-innovation` | `mediabank/Innov_mp_1.xls` (fallback `innov-mp_1.xls`) | sheet 5, RF row |

> **Методологический разрыв (Осло 3→4, приказ Росстата № 788).** С перерасчёта
> за 2017 показатели инноваций считаются по 4-й редакции Руководства Осло и
> несопоставимы со старым рядом (`tech-innovation-share` ≤2017 ~7-9% → ≥2018
> ~20-24%; `innovation-activity` аналогично, мягче). У нас значения за ≤2017
> остались по старой методике → ложный вертикальный «обрыв» на графике. Лечится
> `min_year=2018` в `SCIENCE_CONFIG` (`rosstat_science_parser.py`): парсер
> отдаёт только новый ряд. Существующие старые точки на проде вычищены разово
> (DELETE date < 2018). `small-business-innovation` уже идёт с 2019 — не затронут.

---

## Туризм по России в целом (20.11.2026; реестр `app/data/tourism_russia.py`)

207 рядов `tour-*`, категория «Туризм» (`/russia/category/tourism`), 30 на витрине, остальные — срезы групп
(`indicatorVariants.js`) или месячные/годовые пары через переключатель частоты.

| Ряды | Источник | Парсер | Где в файле |
|------|----------|--------|-------------|
| `tour-travel-exports/-imports/-balance` (квартал с 1994), `tour-travel-{business,personal}-{exports,imports}` (с 1999) | ЦБ, `bal_of_payments_standart.xlsx` | `cbr_bop_xlsx`, `bop_target=travel-*` | лист «Кварталы»: «Поездки» после «Услуги», «Экспорт»/«Импорт» под ней; «Деловые поездки», «Личные поездки». Ведущие нули — непубликация, отбрасываются. «Медицинское обслуживание», «Услуги образования», «Прочие личные поездки», приграничные работники — нули за всю историю, не берутся |
| `tour-travel-*-monthly` (с 2018) | ЦБ, `trade_monthly.xlsx` | `cbr_trade_services_monthly`, `bop_target=travel-*-monthly` | лист «месяцы »: строка «Поездки» и две строки под ней (подписи «Экспорт»/«Импорт » повторяются у каждой статьи — поиск после заголовка статьи) |
| `tour-inbound-trips`, `tour-outbound-trips`, 24 страны `tour-{inbound,outbound}-<страна>` (квартал с 2015) | Росстат по данным ФСБ России, `Poezdki_MM-YYYY.xlsx` | `rosstat_tourism_trips` | ссылка со страницы `rosstat.gov.ru/statistics/turizm`; листы `1.ГГГГ` (въезд), `2.ГГГГ` (выезд): нарастающие итоги, квартал = разность. 2014 без I квартала — не берётся |
| `tour-inbound-trips-monthly` (с 2022) | там же | `rosstat_tourism_trips`, `trips_monthly` | листы `3.ГГГГ`, млн → тыс.; с 2023 итог округлён до 0,01 млн |
| `tour-gva` (квартал), `tour-gva-share` (квартал) / `-annual`, `tour-gva-volume` (с 2017–2018) | Росстат, `VDS_ti_OKVED2_vvp.xlsx` | `rosstat_tourism_gva` | листы 2, 4, 3, 6; год со сноской «20222)» |
| `tour-air-passengers` (+ `-domestic`, `-international`, `-charter`), `tour-air-load-factor` (с 2009) | Росавиация через ЕМИСС 37022, 37020/37019 | `rosstat_emiss_tourism` | сумма регулярных и нерегулярных, внутренних и международных; занятость = 37020 / 37019 × 100 |
| `tour-airport-<аэропорт>` ×6 (с 2018) | ЕМИСС 37015 | `rosstat_emiss_tourism` | отправлено + принято, все виды рейсов |
| `tour-rail-passengers`, `tour-rail-passenger-km` (с 2016) | ЕМИСС 31315, 31313 | `rosstat_emiss_tourism` | вид транспорта «Железнодорожный транспорт» |
| `tour-hotel-{guests,nights,count,rooms,beds,revenue}` (с 2002), `tour-sanatorium-{guests,nights,revenue}`, `tour-agencies` (с 2004) | ЕМИСС 31560, 31587, 31579, 31586, 31583, 31003, 42102, 42103, 42101, 31615 | `rosstat_emiss_tourism` | «значение показателя за год», Россия (с 2023 — без учёта новых субъектов) |
| `tour-hotel-nights-monthly` (с 2023) | ЕМИСС 62301 | `rosstat_emiss_tourism`, `ytd_monthly` | нарастающий итог «январь–…», месяц = разность |
| `tour-dest-{egypt,thailand,uzbekistan,kazakhstan}` | статистика стран назначения: ОЭСР по данным Египта (2008–2025), Минтуризма Таиланда (помесячно 2025–2026), Нацкомстат Узбекистана (2014–2025), Бюро нацстатистики Казахстана (кварталы 2026) | `tourism_destination_file` | файл `tourism_snapshots/destinations_russians.csv` (собран агентами 20.11.2026, обновляется заменой файла); строка Таиланда «2025-11 = 1 418 101» — сумма января–октября, исключена. Кипр, Грузия, Турция — на страницах этих стран |
| `tour-dest-*` c5 (16 рядов): Вьетнам (2012–2026-10), Мальдивы (годы 2012–2025, месяцы 2018–2025), Индонезия (2017–2026-09), Шри-Ланка, Беларусь (организованные туристы 2021–2025), Сейшелы (2000–2026-10), Доминикана (авиа, 2000–2026-09), Монголия (годы 1999–2025, месяцы 2023+), Маврикий (годы 1996–2025, месяцы 2025+), Занзибар (2015+), Куба (1993–2022), Таджикистан (2025), Дубай (СНГ и Вост. Европа вместе с Россией, 2025) | национальные ведомства стран (c5) | `tourism_destination_file` | дописаны скриптом `.artifacts/…/build/t1-mk_destinations_c5.py` из `c5/raw/*/tidy.csv`. Ловушки: Шри-Ланка 2020-09…12 — одно значение 49 397 (годовой итог) — исключено; Вьетнам 2008 со сноской «*» не взят; Маврикий — по стране проживания; Доминикана 2025–2026 — оценки ЦБ, округлены. Ряды с пропусками месяцев без режима «за год». Не взяты: Киргизия (только доля России, без числа), Гонконг (Россия отдельно не публикуется), Куба 2025–2026 (только январь–октябрь, без ряда) |
| g2/g3 (ночь 20.11): `tour-hist-{inbound,outbound}[-tourism]` 1993–2013; `tour-airport-annual-{sochi,kazan,mineralnye-vody,kaliningrad}`; `tour-dest-{uzbekistan-monthly,hong-kong,philippines,philippines-monthly,kyrgyzstan,abu-dhabi,dubai-russia,abkhazia}`; `tour-dest-sri-lanka` заменён рядом g3 | ежегодники Росстата 2003–2014 (ФСБ); Росавиация 2020–2021 + аэропорты/рейтинги (вторичные); национальные ведомства; статистика Абхазии | `tourism_static_file`, `tourism_destination_file` | скрипт `.artifacts/…/build/t1-mk_gaps_g2g3.py`. Пересечения 1993–2013 — только дальнее зарубежье, другой учёт, чем с 2014: отдельные ряды. Шри-Ланка c5 имела сдвиг года у части отчётов — заменена (сумма месяцев = годовым итогам). Абхазия 2014 (= 2013, перенос) не показан; оценка Минтуризма Абхазии — только в методологии. Добавлены 21.11 (g1): отрасли туризма по ОКВЭД по России — ВДС гостиниц и общепита, культуры и досуга (ЕМИСС 58250, кварталы с 2011), оборот и работники гостиниц и турфирм (57710, 57848, месяцы с 2017), инвестиции (59084, годы с 2017); пассажиропоток аэропортов России 2019-01…2022-02 и помесячно Сочи, Казань, Минводы, Калининград (архив ФАВТ). Ловушка архива ФАВТ: по аэропорту ячейка декабря — итог за год (месяц = итог − январь…ноябрь; годовые 2020–2021 исправлены), январь–февраль 2022 в выгрузке g1 сдвинуты — взяты из файла g2. Добавлены (поздно 20.11): въезд и выезд 2002–2013 по 24–25 странам (`tour-hist-{inbound,outbound}-<страна>`, страны, бывшие в таблице ≥3 лет), Макао за 2020 и 2025 и нарастающим итогом (`tour-dest-macao`, `-ytd`). Не взяты: Египет по группам стран (России нет), Китай и Япония (страницы стран — t3), помесячные аэропорты 2020–2022-02 |
| `tour-cpi-*` ×23 (изменение к тому же месяцу прошлого года, %, с 2025; гостиницы по звёздам, хостел, санаторий, дом отдыха — с 2026) | Росстат, `ipc_spr_MM-YYYY.xlsx` | `rosstat_tourism_cpi`, `cpi_item` = локальный код позиции | ссылка со страницы `statistics/price`; лист на месяц («0922025» = сентябрь 2025); столбец «к соответствующему месяцу» − 100. Файл хранит только 2 года — история копится в базе. Снимок с туристскими строками — `tourism_snapshots/ipc_spr_09-2026.xlsx` |
| `tour-tax` (квартал поступления, с 2025) | ФНС, 1-НМ (сводка a5) | `tourism_static_file` | нарастающий итог → квартал; итог 2025 = 5 635,3 млн, Казначейство 0503317 — 5 636,5 млн; в Москве налог не введён (у ФНС 0, у Казначейства строки нет) |
| `tour-resort-fee` (2018–2024) | Казначейство, 0503317, КБК 1 15 08000 02 | `tourism_static_file` | итог РФ; остаток 2025 (208 млн) и старый сбор КБК 1 09 07020 не берутся |
| `tour-price-sanatorium`, `tour-price-rest-house` (1991–2025) | Росстат, `sred_potreb_cen_1991-2025.xlsx` | `tourism_static_file` | 1991–1997 ÷ 1000 (деноминация) |
| `tour-packages*`, `tour-package-price*`, `tour-firm-tourists-*`, `tour-household-spending*`, `tour-hotel-workers`, `tour-new-hotel-beds` (2014–2023) | Росстат, сборник «Туризм в России» 2024 (веб-архив; на сайте 404, нового выпуска нет) | `tourism_static_file` | R3t1, R3t2, R4t4, R2t19, R4t15 |

ЕМИСС: живой ход — страница витрины (справочник фильтров) + `dataGrid.do` через `_post_grid`, территории — только
Россия. С 20.11.2026 fedstat отвечает 403; пока у ряда нет ни одной точки, сбой заменяется снимком ответа 20.11.2026
(`app/data/tourism_snapshots/emiss_<id>.json`, статус `fallback_used`); при уже загруженной истории снимок не
применяется. Так же устроен запасной файл Росстата (`Poezdki_10-2026.xlsx`, `VDS_ti_OKVED2_vvp.xlsx`).

Не взяты: `Turpotok` (три разных итога России за 2025 год: 170,0 / 168,0 / 173,7 млн; с 2022 года), РЖД из
пресс-релизов (40 пропусков, нарастающие итоги вперемешку), квартальные ЕМИСС по средствам размещения (обрыв в
2022, охват не совпадает с годовым), старый ряд ВДС по ОКВЭД-2007 (2011–2016, другая методика); годовые перевозки
Росавиации 2023–2024 (повторяют помесячный ряд ЕМИСС 37022, который идёт до 2026-09); ~260 аэропортов помесячно до
2022-02 (публикация прекращена, шесть крупнейших есть до 2026 в ЕМИСС 37015). Все разовые ряды
(`tourism_static.csv`) собраны скриптом из файлов `.artifacts/tourism-2026-11-20/c4/raw` и обновляются заменой файла.

---

## Мировой блок — Eurostat и официальный multi-provider contract

Мировой bounded context не входит в счётчик 118 российских source-индикаторов.
Первый действующий provider — официальный Eurostat; подключение национальных
ведомств выполняется отдельными adapters по ADR-0012.

| Provider | Официальный источник | Каталог/версии | Наблюдения |
|----------|----------------------|----------------|------------|
| `eurostat` | Eurostat, Statistical Office of the European Union | `https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc/txt?lang=en` (`last update of data`, `last table structure change`) | Eurostat Dissemination API; ссылка конкретного dataset хранится в `WorldIndicator.source_url` |
| `census` | U.S. Census Bureau, Population Estimates Program | CSV-датасеты PEP на `www2.census.gov` (Data API `api.census.gov` требует ключ для любых data-запросов — не используется): межпереписной national totals 2000–2010 (`2000-2010/intercensal/national/us-est00int-tot.csv`, только июль; широкий `nst-est2010-alldata.csv` 404 на 2026-08-29) + винтаж 2020 (`2010-2020/national/totals/nst-est2020-alldata.csv`) + текущий винтаж (`2020-2025/state/totals/NST-EST2025-ALLDATA.csv`, национальная строка `SUMLEV=010`) | Широкие таблицы: колонка `POPESTIMATE{year}` = оценка на 1 июля, человек; межпереписной файл — `YEAR,MONTH,TOT_POP`, берём месяц 7. Винтажи объединяются, пересечённые годы — от свежего винтажа. Ряд `us-population-census` (annual, 2000–2025), инжест `app.services.world_pop_ingest.run_world_pop_ingest`, в концепт population — через `NATIONAL_CONCEPT_INDICATOR_CODES`. Публичный `source_url`: страница PEP на `census.gov`. |
| `ibge` | Instituto Brasileiro de Geografia e Estatística (IBGE) | SIDRA values API `https://apisidra.ibge.gov.br/values` (v1 API `servicodados.ibge.gov.br/api/v1/populacao` нестабилен — 503): таблица 6579 `t/6579/n1/all/v/9324/p/all` (годовые оценки, 2001–2025; 2007/2010/2022/2023 отсутствуют — переписные годы) + таблица 1209 `t/1209/n1/all/v/606/p/all` (переписи, 1872–2022) | Оценки на 1 июля (6579) + переписные итоги (1209, с 1980); переписной год перекрывает оценку. **2023 года в ряде нет официально**: после переписи 2022 IBGE не публиковал межпереписную оценку 2023 ни в 6579, ни в переписных таблицах (проверено 2026-08-27; PNAD-таблицы 6407/7561 — опросные тысячи человек, не подставлять). Ряд `br-population-ibge` (annual, 1980–2025 кроме 2023), инжест и NATCON — как у `census`. Публичный `source_url`: страница оценок населения на `ibge.gov.br`. |
| `imf` | International Monetary Fund, World Economic Outlook | SDMX 3.0 dataflow `IMF.RES/WEO` (latest), без ключа: `https://api.imf.org/external/sdmx/3.0` | Ряды `NGDPD` (ВВП в текущих $, млрд), `NGDPDPC` (ВВП на душу, $), `GGXCNL_NGDP` (сальдо бюджета сектора государственного управления, % ВВП), `GGXWDG_NGDP` (валовый долг сектора государственного управления, % ВВП), `LP` (население, человек; SCALE 6 в SDMX — подпись витрины, значения приходят уже в человеках, divisor не применяем), `LUR` (уровень безработицы, % экономически активного населения) и `PCPIPCH` (среднегодовое изменение потребительских цен, уже % за год). Ключ COUNTRY.INDICATOR.FREQUENCY, например `USA.NGDPD.A`. Публичный `source_url`: `https://www.imf.org/en/Publications/WEO`. Сбой шлюза: 23.10.2026 в 03:11 UTC три российских ряда (`weo-gdp-usd`, `weo-gdp-per-capita-usd`, `weo-budget-balance-gdp`) подряд получили «401 Unauthorized» на публичный адрес без ключа; ночной мировой ingest в тот же день и все прогоны до и после прошли — разовый сбой шлюза, не смена доступа. `_fetch_weo_json` повторяет 401/403/408/425/429/5xx, обрыв сети и не-JSON с паузами 5, 20, 60 с (404 и прочие 4xx — сразу ошибка); сбой после повторов — `failed` с причиной (`mark_fetch_failed`), а не `parsed_zero`. Ingest: `app.services.world_imf_ingest.run_imf_weo_ingest` (все `world_countries`, не только `is_active`). Россия — карточки каталога `weo-gdp-usd` / `weo-gdp-per-capita-usd` / `weo-budget-balance-gdp` / `weo-government-debt-gdp` (`parser_type=imf_weo`), не `WorldCountry` RU. LP/LUR/PCPIPCH в российский каталог не пишем: есть национальные ряды населения, безработицы и ИПЦ. WEO не отдаёт `LUR` для Черногории (`ME`) — в выпуске серии нет, `une_rt_m` в listed-витрине ME тоже нет; на карте безработицы ME отсутствует без выдуманных точек. **Правило года наблюдений** (`weo_max_observation_year(weo_code)`, словарь `WEO_YEAR_POLICY_BY_CODE` в `imf_weo_adapter.py`): поточные серии (NGDPD/NGDPDPC/GGXCNL_NGDP/GGXWDG_NGDP/PCPIPCH, политика "closed") пишутся только по закрытым календарным годам; стоковые (LP/LUR, "stock") допускают текущий год. Карта: national-core → listed Eurostat → unlisted Eurostat того же среза → listed IMF. Смешение методологий оговорено в публичной методологии серии. В `world_forecasts` WEO-ряды не пишем. |

**МВФ WEO: проекции и официальный прогноз (круг 12, 2026-10-12).** `imf_weo_adapter.parse_imf_weo_projections` читает проекции того же SDMX-потока (`fetch_weo_bundle` — наблюдения и проекции одним запросом; дата выпуска из `COUNTRY_UPDATE_DATE`), два новых ряда: `NGDP_RPCH` (рост реального ВВП) и `BCA_NGDPD` (счёт текущих операций, % ВВП). Ближайший год проекции пишется в `world_forecasts` как официальный прогноз (`strategy='imf_weo'`, флаг `world_imf_official_forecast_enabled`) после проверки согласованности с нашей историей; на 12.10.2026 SDMX отдаёт выпуск с датой стран 25–30.09.2025 (октябрь 2025), он проходит проверку возраста (не старше 460 дней) до 29.12.2026, новый выпуск подхватится ingest'ом. Со стенда `api.imf.org` недоступен (TLS), ответы получены с ноутбука; боевой ingest ходит ежедневно, один раз проверить после выкладки.

**Состояние 2026-10-12 (круг 12).** (1) Срезы пяти наборов, стоявших в карантине структуры с конца сентября (`prc_hpi_q`, `prc_hpi_ooq`, `prc_hpi_hsnq`, `prc_hpi_hsvq`, `tour_dem_exac`: Евростат добавил единицу `RCH_A` и сдвинул порядок кодов, общий приоритет выбрал другой срез), закреплены в `app/data/eurostat_headline.py` (`I15_Q`, `NR`, `EUR`, `DOM`, `N1-3`), `slice_hash` совпадает с опубликованными карточками; карантин снимется на ближайшем ночном прогоне. (2) Недельные и дневные наборы вне охвата загрузчика (M/Q/A: `demo_r_mwk*`, `ert_*_d`) дают `skipped` «Selected 0 datasets», а не `error`. (3) ECOICOP ver.1 закрыт Евростатом 06.02.2026: `prc_hicp_cind`, `cann`, `cmon` — остановленные дубли `prc_hicp_minr` (список `app/data/world_superseded.py`, 301 и снятие с листинга скриптом, [контракт](data-contracts.md#c12-2026-10-12)). (4) **С 2024 Евростат ведёт 61 набор `sts_*`/`ei_*`/`isoc_ciegi_ac` на базе 2021=100 (`I21`), наши срезы закреплены на `I15` и стоят на декабре 2023: 6 511 листингованных рядов «Устарело» при живых данных у источника** — починка в работе DATA2, не в этой ветке ([U15](knowledge-unknowns.md)). Закрыто у источника и не наша вина: BEA `SAINC5N/6N/7N:904` (последняя точка 2006), `nrg_chdd_m`; RBA, RBI, NBS отвечают 403 серверному адресу.

**Росстат после техработ, 09.11.2026.** С 01.11 сайт стоял на заглушке «технические работы», затем вернулся из старой копии: лента /central-news заканчивается 13.03.2026, страницы разделов ссылаются на файлы февраля-марта, сами файлы (`ind_*`, `demo*`, `Popul*`, `VVP_*`, `ipc_*`) отвечают 404, `nedel_sred_cen.xlsx` отдаётся в версии 2022 года. Признак старой копии — свежий бюллетень ленты старше 21 дня (`backend/app/services/rosstat_outage.py`); ряды Росстата в это время — «источник недоступен» и догружаются `rosstat_recovery_job` после возвращения файлов. Росстат отвечает 403 на `curl`/`python-requests` User-Agent, наш `ForecastEconomy/1.0` пропускает. Подробности — [backlog](backlog.md#pulse-signals-2026-11-09).

**Состояние 2026-10-12 (круг 13).** (1) **Евростат: база индекса 2021=100.** Для 64 наборов краткосрочной статистики (`sts_trtu_*`, `sts_sepr_*`, `sts_trlb_q`, `sts_rb_q`, `ei_isind_q`, `ei_isrt_m`, `ei_isset_q`, `sts_inpi_q`, `sts_selb_*` и др.; у `ei_isbu_*` `I2015`→`I2021`) источник ведёт данные на `I21`, а `I15` оставил в кодлисте без новых наблюдений; загрузчик при включённом `RUSTATS_EUROSTAT_REBASE_ENABLED` берёт самую новую живую базу того же вида ([ADR-0023](adr/0023-eurostat-index-base-rebase-in-place.md)). Не меняются (проба подтвердила, что живая база совпадает со срезом, отстают отдельные страны): `nama_10_cp_a21`, `nama_10_lp_ulc`, `namq_10_lp_ulc`, `nrg_ind_eff`, `ei_hppi_q`, `prc_hpi_q`, `sdg_07_10/11`, `ei_isppi_q`. Срезы, которые источник по нашему срезу больше не публикует (343 ряда, 8 наборов: `isoc_ciegi_ac`, `isoc_r_gov_i`, `bop_exms6_q`, `nrg_te_oilm`, `nrg_ti_oilm`), и наборы вне оглавления (11 наборов, 311 рядов: `tec00116`, `tin00180`, `tin00186`, `tin00194`, `tps00204` и др.) оставлены: без точного преемника снятие потеряло бы историю и адреса. Оглавление Евростата идёт записями `dataset` и `table` (`ei_*`, `tec*`, `tps*`, `tin*`); запрос оглавления в загрузчике повторяется до трёх раз. С хоста тестового стенда Евростат по IPv4 не отвечает (только IPv6), на боевом IPv4 работает. (2) **Дубли:** `prc_ppp_ind` (COICOP 1999, данные до 2024, 360 публичных, из них 252 «Устарело») против `prc_ppp_ind_1` (COICOP 2018, до 2025, 108) не обработан; `prc_hicp_ct` (постоянные налоги, версия 2) — отдельная мера, оставлен. (3) **МВФ WEO:** ответ SDMX со стенда недоступен (TLS), на боевом ingest ходит в IMF сам; на стенде по 55 странам создано 485 официальных прогнозов (9 рядов × 55 минус 10 сочетаний без данных), выпуск сентября 2025 (правило возраста 460 дней сохраняет прогноз до 29.12.2026, октябрьский выпуск 2026 подхватится адресом `latest`). (4) **Ключи Banxico, ECOS, e-Stat на боевом пусты** (проверено `test -n`, значения не читались): запись от 29.08 «токен задан» устарела, токен Banxico пропал 12.08.2026 (`last_success_at` 12.08, затем «requires RUSTATS_BANXICO_API_TOKEN»), поэтому Мексика (6 из 7 рядов) без обновления 61+ дней, Корея (8 рядов) и Япония (3 ряда) пусты; адреса выдачи ключей и шаги — [workflow](workflow.md#circle13-2026-10-12). (5) **Яндекс.Вебмастер API** недоступен по TCP с наших серверов 11–12.10, **Метрика** пуста с 11.10 на стороне Яндекса ([analytics_api_inventory](analytics_api_inventory/yandex_webmaster.md)).

**Состояние 2026-10-27 (круг починки, участок 23).** (1) **`tour_dem_exac` — карантин с 26.09 из-за ошибочного закрепления круга 12.** Карточки на проде построены от заголовочного среза `duration=N_GE1` (расходы AVG_NGT и AVG_TRP стоят поверх N_GE1; N1-3 и N_GE4 — разрезы длительности). Закрепление `duration=N1-3` сдвигало разрезы статистики на N1-3: 58 из 145 публичных карточек (2 среза × 29 стран) не находили срез. План срезов по живому ответу API 27.10.2026 с исправленным закреплением (`c_dest=DOM`, `duration=N_GE1`) даёт ровно пять опубликованных срезов; настоящая причина карантина — порядок `c_dest` (первым в кодлисте стал `EU27_2020_FOR`), его держит `DOM`. (2) **`ei_isin_m` — карантин из-за карточек, у которых ряд закончился до смены структуры.** Германия, Люксембург, Румыния, Словакия, Финляндия и Исландия перестали сдавать индексы заработной платы, часов и занятости после 2023 года (живая база `I2021` по ним пуста, проверено на API 27.10.2026): 14 публичных карточек «Устарело» превысили порог 20 % (12 из 60) и держали набор в карантине вместе с 36 живыми рядами на `I2021`. `plan_structure_migration` теперь не считает в разлом карточку без замены, чья последняя точка отстаёт от самой свежей точки новой версии набора больше года (месячные), ~1,5 года (квартальные), ~2 лет (годовые): `orphans_stale` в вердикте и в журнале, карточка остаётся с прежней историей. (3) **`tec00116` — набор переименован, а не закрыт.** Из оглавления пропал 22.10.2026 (сверка 27.10.2026 всех листингованных наборов Евростата с оглавлением: вне него только он; десять других наборов из списка круга 13 вернулись в оглавление), но API отдаёт данные по старому коду, обновлено 22.10; значения среза `na_item=NLPR_PER` набора `tesem160` («Labour productivity per person employed and hour worked, EU27_2020=100») совпадают с `tec00116` до знака (Германия 2023–2025: 103,9 / 103,4 / 103,4). `TOC_SUCCESSOR_ALIASES` берёт дату версии у преемника и грузит по прежнему коду, чтобы 33 карточки обновлялись, а адреса и история сохранились. Карточек набора `tesem160` нет (префикс `tes` вне `DEFAULT_THEMES`) — не заводились сознательно: дубль смысла.

Техническая identity ряда:
`provider × country × dataset_id × slice_hash`; slice включает все значимые
dimensions, единицу и частоту. `world_dataset_state` хранит версии источника по
паре `provider × dataset_id`. Parser internals Eurostat — docstrings
`app/services/eurostat_parser.py`, обновление — `world_eurostat_ingest.py`.

**Периодичность и контроль версий (проверено 2026-09-24).** Eurostat обновляет
Dissemination API дважды в день, около 11:00 и 23:00 по центральноевропейскому
времени; это окна API, а не обещание двух новых выпусков каждого ряда в сутки
([официальное описание](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction)).
Планировщик проверяет TOC после этих окон, сравнивает `last update of data` и
`last table structure change`, обрабатывает до 200 наборов за прогон, сохраняет
успешную версию в `world_dataset_state`; изменённый, но ещё не загруженный набор
помечается pending, и его прогноз скрывается. Ошибка/смена структуры не сдвигает
применённую версию. Исторические наблюдения сверяются idempotent upsert, включая
пересмотры. Первый backfill после включения большой: исходный TOC показал 1853
кандидата; это очередь, а не число уже обновлённых наборов.

**HICP / ECOICOP ver.2 (проверено 2026-09-24).** С февраля 2026 Eurostat публикует
гармонизированный ИПЦ в наборах `prc_hicp_minr` (месячный) и `prc_hicp_ainr`
(годовой): измерение корзины `coicop18=TOTAL` (не `coicop=CP00`), база
индекса `I15` (2015=100; `I25` равноглубока, на витрине не параллелим).
Замороженные `prc_hicp_midx` / `manr` / `mmor` / `aind` / `fp` (1996–2025)
сняты с листинга. Из 38 прежних публичных `midx` I15 URL 36 ведут 301 на
сопоставимый `minr` I15 (включая годовые URL); Великобритания и США без
действующего нового ряда сохраняют архивные SSR/OG страницы с историей.
Карточка страны и концепт `hicp-index`
берут живой ряд до последнего месяца источника. Темпы `RCH_A`/`RCH_M` того же
набора — режимы карточки, не срезы variant-пикера (как `manr`/`mmor` раньше).

**Национальные паспорта (national-core, ежедневный ETL).** Регулярный контур
19 официальных провайдеров по 10 странам не из ЕС/ЕАСТ: StatCan + Банк Канады,
ONS + Банк Англии, ABS + RBA, FRED/BLS/BEA (США, 62 курируемых ряда
keyless CSV в `us.yaml`), BOJ + e-Stat (Япония),
ECOS Банка Кореи, BCB (Бразилия), Banxico (Мексика), NBS + CFETS (Китай),
MOSPI + RBI (Индия). Курируемые pick-листы — `backend/app/data/world_national_core/<cc>.yaml`
(код/имя/единица/частота/series-id/публичные тексты на каждый ряд); wire-протокол
источника остаётся внутри адаптера `backend/app/services/world_adapters/<provider>.py`
(контракт `WorldSourceAdapter`); оркестрация и upsert — `world_national_ingest.py`.
Расписание: job `world_national_core` ежедневно 02:10 МСК (перед Eurostat-очередью),
запись аудита — `world_ingest_runs.source='world_national_core'`. Ручной прогон:
`docker compose exec backend python /app/scripts/load-world-national.py --country ca`.
Для США: `docker compose exec backend python /app/scripts/load-world-national.py --country us`.
Key-gated адаптеры (e-Stat Японии `RUSTATS_ESTAT_APP_ID`, ECOS Кореи
`RUSTATS_ECOS_API_KEY`, RBA за 403 с нашего IP) падают изолированно по ряду,
не вали остальные; их ряды помечены `world_dataset_state.status='error'` до
появления ключей. Host `.env` на 2026-08-29: `RUSTATS_BANXICO_API_TOKEN`
задан (CPI Мексики в витрине); `RUSTATS_ESTAT_APP_ID` и
`RUSTATS_ECOS_API_KEY` отсутствуют — JP/KR CPI и безработица national-core
не заливаются, дыры инфляции/безработицы на карте закрывает IMF WEO
`PCPIPCH`/`LUR`, не выдуманные точки. **Прод 28.10.2026 (чтение, без секретов):** в контейнере
scheduler `RUSTATS_BANXICO_API_TOKEN`, `RUSTATS_ECOS_API_KEY`, `RUSTATS_ESTAT_APP_ID` пусты, и ни в
`/opt/rosstat/.env`, ни в его резервных копиях с 27.08 этих строк нет — 18 рядов (MX 7, KR 8, JP 3)
не заливаются, `world_dataset_state.status='error'`; запись про токен Banxico «задан» от 29.08 выше
устарела. NBS (Китай), RBA (Австралия) и RBI (Индия) отвечают 403 с IP прода — внешний отказ, не
ошибка парсера. **Сеть сервера закрыта у новых источников (20.11.2026, проверено чтением с прода):**
StatCan WDS с 17.11 отвечает серверу 403 «Security Check», MoSPI (`api.mospi.gov.in`) с 18.11 не
принимает соединение, CFETS (`chinamoney.com.cn`) с 19.11 молчит до read timeout; с Mac и через
ETL-релей (`resolve_etl_proxy_url`, тот же HTTP-хоп, что у ЕМИСС) все три отдают 200, RBI-архив ставки
тоже 200, RBA и NBS — 403 и через релей, Tor из контейнера не соединяется. Адаптеры StatCan, MoSPI
(и MoSPI-часть RBI), CFETS и HTML-архив RBI берут `http_client.create_source_session()`: direct →
релей → SOCKS, сработавший хоп запоминается на хост на 20 минут (без этого MoSPI ждал бы прямой
таймаут на каждой странице). ABS 19.11 отвечал 504 на всё за ночь — сбой источника, 20.11 прямой
запрос снова 200. Журнал `world_ingest_runs` с 20.11 считает страной с ошибкой только настоящую
ошибку (нет ключа и закрытый источник — строка «известно») и пишет причину на страну.
**Коммит после каждого ряда (28.10.2026):** `ingest_series` читает сеть до SAVEPOINT,
`run_national_core_ingest` коммитит после ряда (`ingest_country(..., commit_each_series=True)`);
до этого транзакция страны ждала медленный BCB SGS дольше `idle_in_transaction_session_timeout`
(120 с), Postgres рвал соединение (`PendingRollbackError`), и данные Бразилии откатывались целиком
(запуски `world_ingest_runs` 158, 170, 174 — 23, 26, 27.10). **BCB SGS (28.10.2026):** дневные окна по 3 года начиная с 1984 (раньше 10 лет с 1900: шлюз BCB считает окно в 10 лет дольше ~30 с и отвечает HTML вместо JSON); временные сбои (5xx, 429, не-JSON, обрыв) повторяются 2 раза, свежее окно обязательно, старые при стойком сбое пропускаются с WARNING и догружаются в следующий прогон; «мягко» пропускаются только явные «значений нет» (404, «Value(s) not found»). До этого не-JSON окно пропускалось молча, и у `br-policy-rate` (Selic) в проде осталась дыра 2000–2018. Тесты — `test_world_national_core_job.py` + 17 файлов
`test_world_<provider>_adapter.py`.

**Площадь территории (карточка страны):** курируемый справочник
`backend/app/data/world_country_area.py` — не ETL и не таблица БД. Для стран
ЕС/ЕАСТ/кандидатов с покрытием Eurostat — dataset `reg_area3`, мера Total area
(`landuse=TOTAL`, км²), ссылка на databrowser. Для остальных — национальное
статистическое ведомство или картография/кадастр (SORS, BHAS, BNS Moldova,
Geostat, US Census Bureau, NRCan Atlas, GSI/Statistics Bureau Japan, NBS China,
India.gov/Survey of India, IBGE, INEGI «Mexico at a glance» (замер территории
1998, публикация 2014), Geoscience Australia). Публичная подпись `source` —
по-русски, латиница допускается только аббревиатурой ведомства; guard —
`test_world_country_area_sources_are_public_ready`. Китай — единственное
округление: ведомство публикует «около 9,6 млн км²». Население на карточке —
последнее значение курируемого concept `population` из `world_data_points`
(источник и URL берутся с `WorldIndicator`).

**Инвариант источника:** национальная статистика берётся прежде всего из
официального национального ведомства, центрального банка, таможни или
министерства. OECD/World Bank разрешены только как канонический международный
издатель конкретного ряда или контрольная сверка; коммерческий/новостной
агрегатор не может быть source. Проверенные, но ещё не подключённые источники из
исследовательских Excel не считаются production provider до реализации adapter,
golden-series теста и фиксации здесь.

### Международные издатели: BIS, Всемирный банк, МОТ (2026-11-19)

Модули `backend/app/services/world_intl_sources.py` (описание рядов, разбор ответов) и
`world_intl_ingest.py` (запись, задача `world_intl_ingest`, ежедневно 02:50 МСК; откат —
`RUSTATS_WORLD_INTL_INGEST_ENABLED=false`). Страны — все `world_countries` (55); Россия — через
`world_concept_russia` (ключевая ставка Банка России, безработица 15–24 лет Росстата).

| Издатель | Набор / адрес | Ряды (код карточки) | Частота, история | Условия |
|---|---|---|---|---|
| Банк международных расчётов | `WS_CBPOL`, `stats.bis.org/api/v1/data/WS_CBPOL/M.{страны}/all?format=csv` | `{cc}-bis-policy-rate` — ключевая ставка ЦБ на конец месяца | месяц; с 1945–2005 по стране; последний — октябрь 2026 (Индия — сентябрь) | data.bis.org/help/legal (19.11.2026): свободно, в т. ч. коммерчески, без отдельной платы за сами цифры; ссылка на BIS; перевод — не официальный BIS; не инвестиционная рекомендация |
| Всемирный банк | WDI API `api.worldbank.org/v2/country/{ISO3;…}/indicator/{код}?format=json` | `{cc}-wb-gini` (SI.POV.GINI), `{cc}-wb-poverty-3usd` (SI.POV.DDAY, 3 $ в день, ППС 2021), `{cc}-wb-income-top10` (SI.DST.10TH.10), `{cc}-wb-life-expectancy` (SP.DYN.LE00.IN) | год; с 1960; обследования — до 2024, не каждый год; обновление WDI 11.11.2026 | CC BY 4.0 |
| Международная организация труда | ILOSTAT `rplumber.ilo.org/data/indicator/?id=UNE_2EAP_SEX_AGE_RT_A&…&classif1=AGE_YTHADULT_Y15-24&format=.csv` | `{cc}-ilo-youth-unemployment` — безработица 15–24 лет (модельные оценки МОТ) | год; с 1991; последний закрытый — 2025, годы прогноза МОТ (2026–2027) отбрасываются | CC BY 4.0 |

Правила:

- **Национальный ряд важнее.** Для ставки crosswalk `world_concept_national["policy-rate"]` (US FEDFUNDS,
  UK, CA, BR Selic, MX, JP, CN LPR 1 год, IN репо). Если национальный ряд публичен и обновлялся за 400 дней,
  ряд BIS пишется с `is_listed=false` (запас); иначе — публичен. 19.11.2026: `in-policy-rate` (РБИ) — 1 точка
  1970 г., `is_listed=false` (сайт РБИ отвечает 403 с прода), поэтому у Индии публичен ряд BIS.
- **Прекращённые месячные ряды не заводятся:** у BIS ставки стран еврозоны заканчиваются 1998–2000 г.
  (дальше — ставка ЕЦБ, ряд BIS «XM»), Хорватия — июлем 2022. Месячный ряд без точек за 730 дней пропускается.
  Страны еврозоны в рейтинге ставок пока без значения (решение о ставке ЕЦБ для членов — открыто).
- **Безработица в целом от МОТ не заводится:** на 19.11.2026 у всех 54 активных стран каталога рейтинг
  безработицы уже заполнен (Евростат, национальные ряды, МВФ `LUR`) — ряд МОТ дублировал бы карточку.
- **Россия:** Джини Росстата (коэффициент по балансу доходов, 0,40) и индекс Всемирного банка
  (обследования, 33) не сопоставимы — в рейтинг Джини Россия не входит; бедность — национальная черта ≠ 3 $.
- Объём: ≈ 23 тыс. точек на всю историю (BIS 25 живых стран ≈ 14 тыс., WDI 4 ряда ≈ 7,5 тыс., МОТ ≈ 1,9 тыс.),
  запись порциями по 5000 точек. Все три адреса отвечают с прода (проверено 19.11.2026; Всемирный банк один
  раз не ответил за 30 с, повтор — 200).
- Тест — `backend/tests/test_world_intl_sources.py` с фикстурами живых ответов `tests/fixtures/world_intl/`.

### Туризм в мире: МВФ, UN Tourism, ОЭСР, Евростат, страны назначения (2026-11-20)

Модули `backend/app/services/world_tourism_sources.py` (ряды, тексты ru/en, разбор файлов) и
`world_tourism_ingest.py` (запись через общий `world_intl_ingest.upsert_series`, задача `world_tourism_ingest`,
понедельник 02:55 МСК за флагом `RUSTATS_WORLD_TOURISM_INGEST_ENABLED`, по умолчанию выключен до первой загрузки).
Раздел страны — `category_ru = "Туризм"` (EN «Tourism»); сюда же переведены наборы Евростата `tour_*`
(было «Общество»; `CATEGORY_BY_PREFIX` + миграция `20261120_world_tourism_cat`). Собрано агентом a4
20.11.2026 (`.artifacts/tourism-2026-11-20/a4/raw/`); все адреса, кроме Турции, отвечают с прода (проверено 20.11).

| Издатель (provider) | Адрес | Ряды (код карточки) | Частота, история |
|---|---|---|---|
| МВФ, платёжный баланс (`imf_bop`) | `api.imf.org/external/sdmx/2.1/data/IMF.STA,BOP/{ISO3+…}.CD_T+DB_T.SD+SDA+SDB+SDB1+SDB2.USD.Q+A`, заголовок `Accept: application/vnd.sdmx.data+csv` | `{cc}-imf-travel-receipts/-payments` (поездки: траты иностранцев в стране / жителей за рубежом), `-business-`, `-personal-`, `-health-`, `-education-` × `receipts/payments` | квартал (год, если кварталов нет); с 1990; последний — II–III кв. 2026; значения издателя в долларах ÷ 10⁶ |
| UN Tourism (`untourism`) | архив со страницы `untourism.int/tourism-statistics/tourism-statistics-database` (имя `UN_Tourism_bulk_data_download_MM_YYYY.zip` меняется — ищется на странице) | `{cc}-unt-inbound-tourists`, `-inbound-visitors`, `-inbound-hotel-guests`, `-inbound-hotel-nights`, `-domestic-trips`, `-domestic-hotel-nights`, `-outbound-tourists`, `-outbound-visitors`, `-hotels`, `-hotel-rooms`, `-hotel-beds`, `-hotel-occupancy`, `-hotel-stay`, `-tourism-employment` (тыс. чел.), `{cc}-tourism-gdp-share` (SDG 8.9.1, если нет ОЭСР) | год; 1995–2024 |
| ОЭСР (`oecd_tourism`) | `sdmx.oecd.org/public/rest/data/OECD.CFE.TOU,DSD_TOURISM_KEY@DF_KEY_IND_PC,/all`; `…DSD_TOURISM_INTER@DF_INBOUND,/.RUS.TOP_MKT....` | `{cc}-tourism-gdp-share`, `{cc}-oecd-tourism-employment-share`, `{cc}-tour-arrivals-russia` (туристы из России; из двух источников страны — более свежий, при равенстве опрос `TDS`) | год; 2008–2025 |
| Евростат (`eurostat_travel`, отдельный provider, чтобы общий загрузчик Евростата не считал набор своим) | `bop_its6_det/A.MIO_EUR.SD.CRE+DEB.RU.?format=SDMX-CSV` | `{cc}-estat-travel-russia-receipts` (траты жителей России в стране), `-payments` (траты жителей страны в России) | год; 2010–2025; конфиденциальные значения — пропуск |
| CYSTAT (`cystat`) | PxWeb `cystatdb.cystat.gov.cy/api/v1/en/8.CYSTAT-DB/Tourism/Tourists/Monthly/2021010E.px`, POST `{"query":[],"response":{"format":"csv"}}` | `cy-tour-arrivals-russia`, `cy-tour-arrivals-total` | месяц; 2002-01…2026-10; «u» (ненадёжно) и «...» — пропуск |
| Geostat (`geostat`) | xlsx `0505EN0204` со страницы `geostat.ge/en/modules/categories/102/inbound-tourism-statistics` | `ge-tour-visits-russia`, `ge-tour-visits-total` — визиты в среднем за месяц квартала, тыс. | квартал; 2014 III…2026 III |
| Национальные службы стран назначения (`ktb_tr`, `armstat`, `azstat`, `mot_india`, `cbs_israel`, `jnto`, `kto_korea`, `monstat`, `rzs_serbia`, `ine_spain`) и Евростат по стране проживания (`eurostat_residence`) | снимок `backend/app/data/world_tourism_national.csv.gz` (72 КБ, 10,6 тыс. строк) — нужные строки таблиц сбора c5 20.11.2026 `raw/<страна>/tidy.csv`; обычный запуск и еженедельная задача берут его сами; пересборка — `--build-snapshot <c5/raw>,<g3/raw>` и коммит | TR — `tour-arrivals-russia`, `-total` и 17 ведущих гражданств `tour-arrivals-{de,uk,ir,bg,pl,us,ge,nl,ro,fr,iq,ua,az,sa,it,kz,by}`, месяц 2014-01…2026-09; AM — Россия квартал 2023–2026 (из нарастающих итогов), всего квартал 2006–2026; AZ — год 2008–2025; IN — год 2001–2025; IL — месяц 2022–2026 (тыс. × 1000); JP — месяц 2003–2026, всего; KR — месяц 2013–2026; ME — коллективное размещение (прибытия, ночёвки) месяц 2016–2026; RS — месяц 2025–2026; ES — FRONTUR Россия до 2022-02, всего до 2026-09, гостиницы 1999–2022; Евростат `estat-accommodation-{arrivals,nights}-russia` — год, 35 стран каталога; сбор g3: JP — `tour-arrivals-russia-leisure`/`-business` 2004–2025, `tour-arrivals-total-annual` и `tour-outbound-residents` 1964–2025; CN (`nbs_china_yearbook`) — Россия и всего 1995–2018 без 1996–1997, ×10 000 из «10 тыс. въездов». Закрытая история национальных служб не отсекается правилом 8 лет | см. слева |

Правила (`world_tourism_ingest.plan_writes`):

- **Подписи стран** в таблицах сбора сравниваются без регистра, точек, пробелов и уточнения в скобках
  («RUSYA FED.», «Rusya», «Rusya Fed.» — одна Россия; «Beyaz Rusya» — Беларусь). Грузия GNTA (помесячно
  2018–2022, с пропусками) не взята: квартальный ряд Geostat свежее. Страны без страницы на сайте — у t1.
- **Один смысл — один ряд у страны.** «Туристы из России»: у Кипра, Турции и Израиля — национальная служба, ряд ОЭСР не
  пишется никогда. «Доля туризма в ВВП»: ОЭСР важнее UN Tourism; если ОЭСР в этот прогон не ответила, ряд
  UN Tourism не пишется (карточка не перескакивает между издателями).
- **Расходы туристов из архива UN Tourism не берём** — тот же смысл, что поездки МВФ, а МВФ свежее (квартал 2026).
- **Молчащий ряд не заводится:** последняя точка старше 8 лет (Канада по лечению — 2011).
- **Россия** в мировом каталоге отсутствует — её строки у МВФ/UN Tourism пропускаются (данные России — ЦБ/Росстат).
- **Страны без страницы на сайте** (Египет, ОАЭ, Таиланд, Казахстан, Узбекистан, Вьетнам) в этот раз не
  заводятся: новая страна — это карта, флаг, валюта, национальные ряды и SEO-страницы, а туристских рядов о
  россиянах у них 1–2. Их цифры о туристах из России (Таиланд — месяц 2025–2026, Узбекистан — год 2014–2025,
  Казахстан — январь–сентябрь 2026 нарастающим, Египет — ОЭСР 2008–2025) сведены в
  `.artifacts/tourism-2026-11-20/build/t3-destinations-without-country-page.csv` для раздела «Туризм» России и статей.
- Понятия рейтинга (годовые): `tourist-arrivals`, `outbound-trips`, `tourism-gdp-share`, `tourism-employment-share`.
  Прибытия и выезды UN Tourism хранятся в миллионах («млн прибытий», «млн поездок»; круг наблюдателей 20.11,
  правки 9 и 47). Россия в этих двух рейтингах — поездки ФСБ (`tour-inbound-trips`, `tour-outbound-trips`):
  сумма закрытого года, тысячи → миллионы, с пометкой о другом источнике (`RussiaConceptLink.annual_sum`).
  Ряды стран назначения начинаются с «По данным принимающей страны» (правка 41).
- Тексты карточек на EN — из описания ряда (`curated_copy_en`): в базе мировых рядов английских описаний нет.
- Тест — `backend/tests/test_world_tourism_sources.py`, фикстуры — выборки из файлов сбора `tests/fixtures/world_tourism/`.

---

## Региональный блок — сборник «Регионы России» (ADR-0008, вне ETL)

Отдельный bounded context (`regions`/`region_indicators`/`region_data`), данные заливаются из закоммиченного артефакта `backend/app/data/regional/`, а не парсером по расписанию. Полная механика — [`docs/adr/0008`](adr/0008-regional-bounded-context.md) + docstrings скриптов `scripts/regional/*.py`.

| Стадия | Источник (rosstat.gov.ru) | Что берёт |
|--------|---------------------------|-----------|
| `parse_pril_2025.py` | `folder/210/document/47652` → архив `Pril_Region_Pokaz_2025.rar` (20 файлов `Раздел N - *.xlsx`, ~460 листов) | 461 показатель, 2000–2024 |
| `backfill_pril_2022_2023.py` | те же приложения изданий 2023/2022 (`Pril_2023`, `Pril_2022`) | 25 показателей, исключённых из 2025: внешняя торговля ФТС (21.x), госслужащие (2.15–2.18), ПИИ (10.4), лён (13.8/13.17/13.18), ж/д грузы (16.1), прожиточный минимум пенсионера (3.14), зарплата муниципальных служащих (3.5), интернет/ПК в организациях (17.2/17.6), темпы прироста населения (1.8) |
| `backfill_word.py` | Word-редакции: `TOM2.rar` (изд. 2003), `soc-pok18.rar` (изд. 2018), `soc-pok2019` (изд. 2019); .doc → .docx через LibreOffice headless | раздел «Правонарушения» (8.1/8.4/8.5, 1990–2018) + продление 24 рядов в 1990-е с кросс-сверкой на overlap (медиана расхождения ≤ 5%) |

Ежегодное обновление: скачать новый архив приложения, прогнать три стадии по порядку, закоммитить артефакт, `seed_regional.py` подхватит на деплое. Денежные ряды глубже 1998 не продлеваются (деноминация).

### Помесячные цены на топливо по субъектам (раздел 16, 2026-08)

Первый помесячный слой regional bounded context: отдельная таблица `region_monthly_data` (модель `RegionMonthlyPoint`, месяц как YYYYMM), не годовая сетка `region_data` — смешение частот в одной таблице это trap (CONTEXT.md, annual-in-monthly mixing).

| Код | Показатель | ЕМИСС dataset | Период | Частота |
|-----|-----------|---------------|--------|---------|
| `ceni-ai92` | Потребительские цены на бензин АИ-92, руб./л | `31448` (OKPD2 1700128) | 2003-01 → наст. | месячная |
| `ceni-ai95` | Потребительские цены на бензин АИ-95, руб./л | `31448` (OKPD2 1700133) | 2003-01 → наст. | месячная |
| `ceni-dt` | Потребительские цены на дизельное топливо, руб./л | `31448` (OKPD2 1700154) | 2006-01 → наст. | месячная |
| `roznica-dt` | Розничные продажи дизтоплива, тыс. руб. | `57699` (OKPD2 1700657) | 2017–2021 | годовая |
| `opt-benzin` | Оптовые продажи бензина, тыс. руб. | `59002` (OKPD2 1704128) | 2017 | годовая |
| `opt-dt` | Оптовые продажи дизтоплива, тыс. руб. | `59002` (OKPD2 1692982) | 2017 | годовая |

Территориальный охват — все субъекты РФ + сводка «Россия»: с 2023 это отдельная строка ЕМИСС «Российская Федерация без учета новых субъектов» (ОКАТО 1849012), до 2022 — канонический РФ-агрегат (1688487); фетчер сшивает оба ID в один slug `russia`.

Механика:

- Фетчер `scripts/regional/fetch_emiss_fuel.py`: POST `fedstat.ru/dataGrid.do` по схеме «год × месяц» (мульти-месяц в одном запросе ЕМИСС не отдаёт — возвращает только последний), 45 c timeout, 4 ретрая; карта ОКАТО→slug снапшотится в `emiss_okato_31448.json`, имена — в `emiss_dimnames.json`.
- Помесячные точки → `backend/app/data/regional/fuel_points.csv` (73 740 точек), годовые (57699/59002) → `data.csv.gz` через `scripts/regional/append_fuel_to_artifact.py`.
- Обновление помесячного слоя — раз в месяц после публикации ЕМИСС (обычно 5–8 число): `python3 scripts/regional/fetch_emiss_fuel.py --skip-annual`, затем пересборка backend-образа (артефакт вшит) и `seed_regional.py` на старте.
- **Прод 28.10.2026:** после включения HTTP-звена ETL через релей `emiss_regional_job` догрузил август и сентябрь 2026 (по 282 строки: 94 региона × 3 вида топлива; до этого последним был июль).
- **Все товары и услуги витрины 31448 (08.11.2026).** Витрина — «Средние потребительские цены (тарифы) на товары и услуги»: в справочнике измерения 58273 884 позиции, за сентябрь 2026 опубликовано 560 по 94 территориям (живой запрос с Mac 08.11.2026: 6,4 с, 2,1 МБ на месяц со всеми позициями). Пол: РФ с 2000-01, субъекты с 2003-01. Отбор: 80 ходовых позиций с ручными названиями и EN-переводом (`PRICE_GOODS` в `backend/app/data/emiss_price_goods.py`) + все остальные позиции, у которых в полном проходе истории нашлась хотя бы одна цена (артефакт `backend/app/data/regional/emiss_price_goods.json`, собирает `scripts/regional/build_price_goods.py` из сохранённых ответов dataGrid.do; он же перезаписывает строки `20.m*` в `indicators.json`). Раздел регионального каталога 20 «Цены и тарифы», слой `region_monthly_data`, коды `ceni-…`. Парсер грузит топливо и товары одним запросом на месяц (`PRICE_SERIES`); план фетча строится по самому короткому ряду РФ, поэтому ряд без истории запускает догрузку с 2000 года, а у полных рядов остаётся «хвост + ревизия». У части позиций Росстат с 2022 года завёл новые oid с новым описанием товара — такие ряды начинаются с даты нового описания, старые описания не сшиваются. Английского названия у автоматически заведённых позиций нет (EN-страницы показывают русское).
- **Автообновление (`app.services.emiss_regional_parser`, круг починки 27.10.2026).** Job `emiss_regional` идёт 15, 20, 25 и 28-го числа в 07:40 МСК (прогон идемпотентен, 3–4 запроса). Цены стояли на 2026-07: каждый месяц разбирался в 0 точек, потому что в ответе `dim57831` — **название** территории, а справочник знал только ОКАТО-oid (теперь `load_dimnames()`: oid и названия, файл `backend/app/data/regional/emiss_dimnames.json` рядом с `emiss_okato_31448.json`, `scripts/` в образ backend не попадает); запрос шёл прямым `httpx` мимо ETL-сессии, а fedstat отвечает адресу прода **403** (проверено с хоста 27.10.2026; Tor-мост хоста до fedstat не дотянулся: через `172.18.0.1:9050` соединение сброшено, через `127.0.0.1:9050` таймаут 90 с) — теперь запрос идёт через `create_session` (прямой ход → HTTP-прокси → SOCKS), 403/404 не повторяются, 5xx/429/сеть повторяются 4 раза. Ответ со строками, но без разобранных цен, — `EmissFormatError` и `unparsed` в итоге прогона (алерт «ответ получен, цены не разобраны»). Алерт «парсер упал» несёт причину и не чаще раза в трое суток. С Mac (UPHOST) запрос проходит: август и сентябрь 2026 опубликованы (282 точки в месяц, как у июля в базе), октябрь пока пуст.
- API: `/api/v1/regions/{slug}/i/{code}/monthly` (точки {year, month, value, label} + ряд РФ для сравнения; рейтинг цен по регионам не строится осознанно — «место в рейтинге цен» вводило бы в заблуждение).
- SSR/OG: `seo_regional.py` рендерит месяц-карточку (таблица по месяцам, сравнение к прошлому месяцу и к году назад), `sitemap.py::og_image_region_indicator` рисует помесячный постер.
- Мост в федеральный блок: `16.20/16.21/16.22` → `MACRO_BY_TABLE` → карточки `fuel-ai92`/`fuel-ai95`/`fuel-diesel`. Годовые опт/розница без моста — федерального аналога той же методологии нет.
- Обратный мост (18.11.2026): федеральные страницы `fuel-*` и их годовые страницы показывают цену всех субъектов на последнюю недельную запись (года) со ссылками на «топливо × регион» (`regional_weekly.fuel_regions_section`).

<a id="weekly-fuel-regions"></a>

### Недельные цены на топливо по субъектам (ЕМИСС 37426, 2026-11-18)

Зачем: из Яндекса приходят за ценой топлива на дату и по городу («ДТ в СПб на 01.01.2026», «стоимость дизтоплива в Вологде 10.01.2025»); за 90 дней до 18.11.2026 — 3 229 заходов по топливным фразам, 36 % с датой или месяцем, 13 % с городом или регионом, 4 % с названием сети АЗС. Месячный ряд 31448 отвечает только месяцем, федеральный недельный — только по России.

| Показатель | Позиция 58273 | Период | Частота |
|---|---|---|---|
| `ceni-ai92` | 1709730 «Бензин автомобильный марки АИ-92, л» | 2022-01-10 → наст. | недельная |
| `ceni-ai95` | 1709750 «… марки АИ-95, л» | 2022-01-10 → наст. | недельная |
| `ceni-ai98` | 1755184 «… марки АИ-98 и выше, л» | 2022-01-10 → наст. | недельная |
| `ceni-dt` | 1755196 «Дизельное топливо, л» | 2022-01-10 → наст. | недельная |

Витрина — «Еженедельные средние потребительские цены (тарифы) на отдельные товары и услуги» (fedstat.ru/indicator/37426): с 2008 года, «представляется: среда», 162 позиции, территории ОКАТО 57831 (РФ, округа, субъекты). Живая проверка с Mac 18.11.2026: последнее обновление витрины 29.10.2026, последняя неделя — 26.10.2026; федеральный файл `nedel_sred_cen.xlsx` к тому дню шёл до 09.11.2026 (витрина отстаёт на одну-две недели).

Механика (`app.services.emiss_weekly_fuel`, таблица `region_weekly_data`, третья частота регионального контура):

- Период в колонках вместе с годом: один POST `dataGrid.do` отдаёт все недели года по всем территориям и четырём маркам (ключ ячейки `dim<год>_<oid недели>_d…_i…`, около минуты на год).
- Подписи недель с 2022 года без даты («1 неделя 2025»), oid новой недели появляется в справочнике с публикацией. Поэтому каждый прогон сначала читает страницу витрины (~600 КБ) и берёт oid недель оттуда, а не из снимка.
- Дата недели — день регистрации Росстата из федерального недельного ряда (`fuel-ai92/95/diesel`): строка России 37426 совпадает с ним до копейки. Неделя k получает k-ю дату федерального ряда года, если цены России совпали не меньше чем по двум маркам (допуск 0,006); иначе неделя пропускается (`undated`), дата не угадывается. Первая запись года бывает не в понедельник (9 января 2025, 5 ноября 2025 после праздника), поэтому правило «каждый понедельник» не годится.
- Строка России: «Российская Федерация» (1688487) до 2022 года, «без учета новых субъектов» (1849012) с 2023-го, как в федеральном ряду и месячной витрине; пишется в slug `russia`.
- Глубина — с 2022 года: до 2022 подписи недель несут дату текстом в разных видах («на 1 декабря», «01 неделя ( на 10 января)», «1 неделя (на 11 января 2016 года)»), а спрос на годы до 2022 почти нулевой (5 заходов из 3 229).
- План: пустая таблица → 2022…текущий год; иначе год последней даты России по `ceni-dt` и все следующие. Год — одна транзакция под общим региональным advisory lock; сеть — вне транзакции (`idle_in_transaction_session_timeout`).
- Job `emiss_weekly_fuel` — четверг и суббота 08:20 МСК; алерты «упал» и «ответ не разобран» с заглушкой трое суток.
- Первый живой прогон с Mac в проверочную базу 18.11.2026: 5 лет, 246 недель с датой, 0 без даты, 91 758 точек за 235 с; 94 территории (85 субъектов, 8 округов, Россия), у АИ-98 — 91.

Цен по сетям АЗС (Роснефть, Лукойл, Газпромнефть) в официальной статистике нет: витрина даёт среднюю по заправкам субъекта. На странице это сказано прямо.

### Помесячный ИПЦ и стоимость наборов по субъектам (ЕМИСС 31074, 31052, 31481, 2026-11-19)

Зачем: ИПЦ региона — самый просматриваемый региональный показатель (53 человека за 30 дней до 19.11.2026), а в
Яндексе ищут ИПЦ региона за месяц («ИПЦ по липецкой области в июле 2026»). Годовой ряд сборника (20.1) кончается
2024 годом. Пустой внутренний запрос «индекс стоимости жизни». Исследование — `.artifacts/pulse-fixes-2026-11-19/emiss-catalog-2026-11-19.md`, №1–3.

| Коды | Витрина | Что | История | Последний период (живой запрос 19.11.2026) |
|---|---|---|---|---|
| `ipc-{vse,bazovyy,prodovolstvennye,neprodovolstvennye,uslugi}-{za-god,k-mesyacu,k-dekabryu}` | [31074](https://www.fedstat.ru/indicator/31074) | ИПЦ: все товары и услуги, базовый, продукты, непродовольственные, услуги; к тому же месяцу прошлого года, к прошлому месяцу, к декабрю | 2002-01 (базовый — 2003-01) | 2026-09 |
| `ipc-<группа>-za-god` (20 групп) | 31074 | мясо, молоко, хлеб, яйца, сахар, плодоовощная, алкоголь, табак, одежда, медикаменты, бензин, стройматериалы, коммунальные услуги, пассажирский транспорт, связь, медицинские услуги, образование, детский сад, зарубежный туризм, бытовые услуги — только «за год» | 2002-01 (связь — новая группа «Услуги телекоммуникационные», с 2023-01) | 2026-09 |
| `nabor-fiksirovannyy` | [31052](https://www.fedstat.ru/indicator/31052) | стоимость фиксированного набора товаров и услуг, рубли, конец месяца | 2002-01 | 2026-09 |
| `nabor-minimalnyy-produktov` | [31481](https://www.fedstat.ru/indicator/31481) | стоимость условного (минимального) набора продуктов питания, рубли | 2001-01 | 2026-09 |

Решения отбора (19.11.2026):

- Базовый ИПЦ берётся из 31074 (позиция 1788790 «Базовый индекс потребительских цен»), отдельный набор 33568 не нужен: один транспорт, один разбор.
- 40532 («изменение стоимости фиксированного набора», %) не взят: это 31052 в процентах; изменения страница считает от рублёвого ряда.
- «Жилищно-коммунальные услуги» (1788749) и «Услуги связи» (1788722) с 2024 года пусты — Росстат сменил группировку. Взяты «Коммунальные услуги» (1788723, непрерывно с 2002) и «Услуги телекоммуникационные» (1848536). Старая и новая связь не сшиваются.
- Группы только «за год»: так понятнее и втрое меньше строк. Из 1105 позиций набора взяты 25.

Механика (`app.services.emiss_regional_cpi_parser`, справочник `app.data.emiss_regional_cpi`, слой `region_monthly_data`, раздел 20, table_code `20.c1…20.c37`):

- Запрос «год целиком»: строки — территория × позиция × вид индекса, столбцы — год × месяц (ключ `dim<год>_<oid месяца>_d…`), кварталы не запрашиваются. Четыре запроса на год: главные индексы (15 рядов), группы (20), 31052, 31481. Время ответа с Mac — от 0,3 до 30 с, ответ 31074 — около 1 МБ.
- Территории и названия — `emiss_okato_31448.json` + `emiss_dimnames.json` (как у 31448): 85 субъектов, 8 округов, Россия; новые субъекты пропускаются. Россия — 1688487 до 2022 года, 1849012 («без учёта новых субъектов») с 2023-го, обе в slug `russia`.
- План: пустая база или новый ряд — вся история (~100 запросов); дальше — годы без точек России (сбой прошлого прогона) и хвост от последнего загруженного года; если в нём только январь — и прошлый год. Сбой сети на одном годе не отменяет остальные: год повторит следующий прогон, в конце — ошибка для алерта. Транспорт `_post_grid` (ETL-сессия; адрес прода fedstat режет 403).
- Job `emiss_regional_cpi` — 15, 20, 25, 28-го в 08:00 МСК (цены 31448 — в 07:40). Алерты «упал» и «не разобран» с заглушкой трое суток.
- **Ложный «HTTP 403» (20.11.2026, Пульс, пункт 3).** Первый прогон 20.11 08:00 МСК: «не загружено запросов: 90 … HTTP 403», в 08:10 все шесть наборов `emiss_regional_sets` — тоже «HTTP 403». Механизм: адрес прода fedstat режет 403 всегда, данные идут через HTTP-релей (`vps` 5.129.210.89). Сетку ИПЦ за год fedstat считает дольше 60 с (проверка 20.11 с прода: 2013 — два обрыва по 60 с, третья попытка 32 с); `ReadTimeout` релея взводил предохранитель хопа на 20 минут, и все следующие запросы к fedstat возвращали прямой 403 без релея (журнал tinyproxy: ни одного соединения к fedstat с 05:07 до 08:09 UTC; запрос 57693 через релей в 11:09 МСК — 200, 6 387 точек). Исправлено: `ReadTimeout` хопа не взводит предохранитель и не подменяется 403 (`http_client._via_next_hop`), чтение сетки ждёт до 180 с, повтор чтения — только цикл `_ATTEMPTS` (`emiss_regional_parser._GRID_RETRY`). Tor с прода до fedstat не доходит (ConnectTimeout).
- **Остановка после серии сбоев (20.11.2026, Пульс, пункт 6).** В том же прогоне 11 лет главных индексов (2002–2012, 171 234 точки) загрузились, дальше 79 запросов подряд получили отказ: цикл шёл по всем оставшимся годам без паузы. Теперь `run_emiss_regional_cpi_update` после трёх сбоев подряд (`_MAX_FAILURES_IN_ROW`) останавливает прогон и после сбоя тоже ждёт `_PAUSE_BETWEEN_REQUESTS`; недогруженные годы план берёт в следующем прогоне (15/20/25/28-е). Одиночный сбой года прогон не останавливает. До догрузки страницы `ipc-*` показывают последней точкой декабрь 2012 (проверено 20.11 на `/russia/region/moskva/ipc-vse-za-god`), группы и наборы пусты — после выпуска нужен ручной прогон.
- **Тяжёлые годы по кварталам; обрыв хостом не выключает релей (20.11.2026, Пульс, пункт 6b).** После выпуска пунктов 3 и 6 ручные прогоны догрузили ИПЦ до 2021 года, а 2022–2026 падали каждый раз: fedstat закрывает соединение без ответа (`RemoteDisconnected`), если сетка считается дольше 30–70 с (журнал tinyproxy 20.11: соединения к fedstat рвутся на 43–61 с). Проверено чтением с прода: ИПЦ 2022 за 12 месяцев — обрыв, за I квартал — 3,7 с, за III — 11 с; группы 2024 — четыре квартала по 10–14 с, 22 500 точек; 57806 за 2016 год — обрыв на 70 с, за I квартал — 6,9 с. Теперь год ИПЦ (31074/31052/31481) и год наборов `emiss_regional_sets` идёт четырьмя квартальными запросами (`emiss_regional_parser.post_grid_by_quarters`), ответы склеиваются; сбой квартала роняет год целиком (без половины года в базе). urllib3 2.x оборачивает такой обрыв в `ProxyError('Unable to connect to proxy', RemoteDisconnected)`, поэтому прежде он взводил предохранитель релея на 20 минут и выдавался за прямой «HTTP 403»; в 13:30 так же упали наборы 31076, 57788, 62900 после одного обрыва 57806. Теперь `http_client._via_next_hop` по `RemoteDisconnected` в цепочке бросает `HostDisconnected`: релей и хост остаются рабочими, 403 не подставляется, `_post_grid_sync` повторяет запрос.
- Объём всей истории (живой прогон разбора 19.11.2026 по всем годам 2002–2026): 967 686 строк (главные индексы 400 344, группы 513 548, наборы 26 892 и 26 902; плюс ~1 тыс. за 2001 год у минимального набора); на проде ~170 Б на строку `region_monthly_data` вместе с индексами — около 165 МБ. Базовый ИПЦ — с 2003-01, связь — с 2023-01.
- Сверка: стоимость наборов за декабрь 2024 совпадает с годовыми рядами сборника 20.2.1/20.3.1 (Россия 23 780,25 и 7 093,00 ₽; Липецкая 20 600,28 и 6 206,83 ₽). Декабрь 2022 к декабрю 2021 совпадает с годовым ИПЦ сборника (Россия 111,94 / 111,9; Липецкая 112,96 / 113,0; Москва 111,7 / 111,7). Россия, сентябрь 2026: 106,35 % к сентябрю 2025, 100,35 % к августу.
- Подача: у рядов «% к …» страница и SSR не пишут «изменение индекса за год» и не пересчитывают «без инфляции» — значение уже изменение цен. Мост к федеральным карточкам `cpi`, `cpi-food`, `cpi-nonfood`, `cpi-services` (`MACRO_BY_TABLE`). Поиск «инфляция <регион>» ведёт к `ipc-vse-za-god`, «потребительская корзина» — к `nabor-minimalnyy-produktov`, «индекс стоимости жизни» — к `nabor-fiksirovannyy`.
### Квартальные ряды регионов (ЕМИСС 31452, 30925, 61781, 58537, 30957; 2026-11-19)

Зачем: цену 1 м² жилья в своём регионе ищут постоянно, а на сайте она была годовой до 2024 года; бедность и
прожиточный минимум по регионам — около 100 показов в Яндексе за месяц (каталог ЕМИСС 19.11.2026). Решение — ADR-0008,
раздел «2026-11-19 — квартальный слой».

| Набор | Что | Ряды сайта | Слой | История | Последний период (19.11.2026) |
|---|---|---|---|---|---|
| 31452 | средняя цена 1 м² квартир | `cena-m2-zhilya-{pervichnyy,vtorichnyy}` + типы квартир (9) | квартал | 2000 | III 2026 |
| 30925 | индекс цен на жильё «к соответствующему кварталу предыдущего года» (oid 1698421), все типы | `indeks-cen-zhilya-{pervichnyy,vtorichnyy}-god` | квартал | 2000 | III 2026 |
| 61781 | цена 1 м² в центре субъекта (61782 = 1846504), все типы | `cena-m2-zhilya-centr-{pervichnyy,vtorichnyy}` | квартал | 2021 | III 2026 |
| 58537 | доходы к прожиточному минимуму, % | `dohody-k-prozhitochnomu-minimumu` | квартал | 1992 | II 2026 |
| 30957 | прожиточный минимум, «значение показателя за год» (1558883) | `prozhitochnyy-minimum-{deti,pensionery,trudosposobnye}`; «все население» → `…-3-11` с 2025 | год | 1992 | 2026 (2027 — плановый, отрезан) |

Механика (`app.services.emiss_quarterly_parser`, реестр `app.data.emiss_quarterly`, таблица `region_quarterly_data`):

- Запрос `dataGrid.do`: строки — территория 57831, измерения ряда (рынок 63148, тип квартир 58849, группа 58812) и год
  3; столбец — период 33560. Ключ ячейки — `dim<oid периода>_d…_i…`, год — в `dim3` строки. Кварталы: 1540222,
  1540224, 1540226, 1540227. Территории — справочник цен 31448 (`emiss_okato_31448.json`) + «Российская Федерация»
  1688487; у 61781 центр Архангельской и Тюменской областей подписан «областью без автономных округов» (1692939,
  1692940) — пишется в субъект, если у субъекта нет своей строки.
- Россия: до 2022 года — «Российская Федерация», с 2023 — «без учета новых субъектов»; нет одной — берётся другая.
- План: первая загрузка — вся история кусками по 6 лет; дальше — год до последнего сохранённого и новые. Кусок лет —
  одна транзакция под общим региональным advisory lock; сеть вне транзакции.
- Живая проверка с Mac 19.11.2026 (полная история, без базы): 23 запроса, 9,1 МБ, самый тяжёлый — 31452 за 6 лет,
  1,5 МБ за 19 с; 102 919 точек: 31452 — 70 421, 30925 — 18 183, 61781 — 3 544, 58537 — 7 711, 30957 — 3 060.
  Сверка с сайтом ЕМИСС: Россия, вторичный рынок, все типы, III 2026 — 149 231,93 ₽/м²; первичный — 226 498,1;
  прожиточный минимум России 2024 — 15 453 (совпадает с таблицей 3.11 сборника), 2025 — 17 733, 2026 — 18 939.
- Job `emiss_quarterly` — 5, 15 и 25-го в 07:55 МСК; алерты «не обновились» и «ответ не разобран» с заглушкой трое суток.

### Ставки по вкладам и кредитам по регионам (Банк России, DataService «В территориальном разрезе», 2026-11-19)

Зачем: `deposit-rate` — 179 входов людей за 30 дней, фразы Яндекса про вклады — 180 человек, ипотека в Google — 74
показа; ставки были только по России. Реестр `app.data.cbr_regional_rates`, загрузчик
`app.services.cbr_regional_rates_parser`, слой `region_monthly_data`, раздел 19 «Финансы», table_code `19.s{N}`.

| Ряд | pub / ds / element | Территории | История | Последний период (19.11.2026) |
|---|---|---|---|---|
| `stavka-ipoteki` (19.s1, мост к `mortgage-rate`) | 15 / 34 / 36 (рубли) | Россия, 8 округов, все субъекты, АО и «области без АО» — 96 | 2019-01 | 2026-09 |
| `stavka-vkladov-do-1-goda` (19.s2) | 19 / 39 / 7 | только 8 федеральных округов | 2019-01 | 2026-09 |
| `stavka-vkladov-svyshe-1-goda` (19.s3) | 19 / 39 / 11 | 8 округов | 2019-01 | 2026-09 |
| `stavka-kreditov-fizlitsam` (19.s4) | 15 / 32 / 110 (все сроки) | 8 округов | 2019-01 | 2026-09 |
| `stavka-avtokreditov` (19.s5) | 15 / 33 / 110 | 8 округов | 2019-01 | 2026-09 |

- Запрос `cbr.ru/dataservice/data?publicationId&datasetId&measureId&y1&y2` — по одному на территорию (без `measureId`
  ответ пустой); список территорий — `dataservice/measures?datasetId`. Названия → slug: `emiss_dimnames.json`,
  таблица регионов и `MEASURE_ALIASES` («Архангельская область, в том числе НАО» — строка самого НАО: сентябрь 2026
  область 6,23 %, «в т. ч. НАО» 6,76 %, «без НАО» 6,20 %; так же Тюменская область и её округа).
- Месяц — из `dt` («Сентябрь 2026»); поле `date` у ставок на месяц позже. Ноль — кредитов не выдавали, не пишется.
- План: пустой ряд — история с 2019 года (≈120 запросов, пауза 0,3 с); дальше — прошлый и текущий год. Сбой
  территории не отменяет остальные, в конце — алерт. Запись — `_upsert_monthly_points` ЕМИСС порциями.
- Живой прогон с Mac 19.11.2026: 11 904 точки на всю историю (<2 МБ). Сверка: Россия, ипотека, сентябрь 2026 — 8,61 %,
  как у федеральной `mortgage-rate` на боевом. Боевой сервер отвечает 200 (DataService).
- Не взяты: ставки по кредитам организациям и МСП (ds 30, 31), по вкладам организаций (ds 40) — не про людей.
- Job `cbr_regional_rates` — 4, 12 и 18-го в 07:30 МСК (ипотека выходит в начале месяца, остальное около 10-го).

---

## ФНС — малый и средний бизнес по регионам (реестр МСП, 19.11.2026)

Реестр `backend/app/data/fns_msp.py`, загрузчик `backend/app/services/fns_msp_regional.py`, слой `region_monthly_data`, раздел 11 «Организации» (`11.m1.1–7`). Источник — сводка Единого реестра субъектов МСП ФНС на 10-е число месяца: страница `rmsp.nalog.ru/statistics.html` (список дат — `select#statDate`, 124 даты с 01.08.2016), данные — POST `statistics-proc.json` с полем `statDate=ДД.ММ.ГГГГ` (так делает сама страница). Открытые данные ФНС; боевому серверу отвечает 200.

Ряды: `msp-chislo` (всего), `msp-yurlica`, `msp-ip`, `msp-mikro`, `msp-malye`, `msp-srednie` (юрлица + ИП своей категории), `msp-rabotniki` (численность работников; нули первых сводок 2016 года не пишутся). Месяц — по дате сводки (10.11.2026 → 202611). Россия — строка `cnt_level` 2, по всем субъектам, включая присоединённые в 2022 году (на сайте их нет, строки и округ «Юго-Западные субъекты» пропускаются; «Крымский федеральный округ» сводки 01.08.2016 — тоже). Названия ФНС без пробела («г.Москва») — `TERRITORY_ALIASES`.

Живые значения: Россия на 10.11.2025 — 6 707 476 субъектов МСП, из них средних 22 201, работников 15 178 797; на 10.11.2026 — 6 895 487. Объём всей истории ≈ 75 тыс. строк. Прогон: даты без месяца в базе плюс две последние; первая загрузка — 124 запроса с паузой 0,5 с. Job `fns_msp` — 11 и 14-го в 07:40 МСК; алерты «обновлено не всё» и «упала» с заглушкой трое суток. Фикстуры `backend/tests/fixtures/fns_msp/`, тест `test_zone_i_sources.py`.
**Последняя неделя из бюллетеня Росстата (19.11.2026, флаг `RUSTATS_REGIONAL_FUEL_BULLETIN_ENABLED`, по умолчанию выкл.).** Витрина отстаёт: 19.11 в ней последняя неделя — 26.10, а PDF-бюллетень «О потребительских ценах на нефтепродукты» уже несёт таблицу «Средние потребительские цены на бензин автомобильный и дизельное топливо на 16 ноября 2026 года» по 94 территориям (пять колонок: бензин всего, АИ-92, АИ-95, АИ-98 и выше, дизельное топливо). После прогона витрины тот же job читает свежие бюллетени первой страницы ленты и пишет последнюю дату в `region_weekly_data` (`run_bulletin_regional_update`). Сверка на боевом: бюллетень за 26.10 (`169n-ben28.pdf`) совпал с точками витрины за 26.10 во всех 373 парах «марка × территория» без расхождений, поэтому витрина затем перезаписывает те же точки без изменений.
- Название субъекта бывает разорвано на 2–3 строки PDF; строки шапки обрывают имя. Справочник — `emiss_dimnames.json` без пояснений в скобках, «авт. округ» → «автономный округ», плюс псевдонимы (`г. Москва`, `Чувашская Республика`, `Кемеровская область` …). Строки «… (кроме …)» пропускаются: целый субъект идёт отдельной строкой. «…», «...», «-» — нет данных.
- Нераспознанные названия пишутся в журнал и в счётчик `unmatched`; точки по ним не пишутся.

---

## Субнациональные регионы мира (ADR-0014 и ADR-0015)

Отдельный bounded context `subnational_*` для стран кроме России. Российский
годовой сборник (раздел выше) не расширяем: здесь месячные / квартальные /
годовые ряды. Паспорт страны — `backend/app/data/world_subnational/<cc>.yaml`.
Загрузчик `backend/scripts/load-world-subnational.py --country us`.

### США (50 штатов + округ Колумбия)

**Выпуски и опрос источника.** BLS LAUS публикует месячные оценки штатов по
[календарю](https://www.bls.gov/schedule/news_release/laus.htm); дата выпуска
сдвигается, поэтому ingest ежедневно проверяет FRED. Наложение свежих значений
BLS API (`bls_series_template`) снято из паспорта 2026-09-29: `api.bls.gov`
отвечает 403 (Akamai) на IP прода, а зеркало LASST во FRED той же свежести.
BEA публикует GDP штатов поквартально с пересмотрами
([серия и календарь](https://www.bea.gov/data/gdp/gdp-state)); ежедневный опрос
не означает ежедневного нового наблюдения. FRED служит официальным транспортом
ФРБ Сент-Луиса для историй BLS/BEA/Census/FHFA, а ведомство-первоисточник
указано на карточке. На выборке 2026-09-24 все 62 национальных FRED ряда США
(55 880 дат/значений) совпали с CSV источника до исправления единиц; также
проверены BLS LAUS CA/TX и BEA state GDP. Это проверка текущей выборки, а не
доказательство отсутствия ошибок во всех будущих выпусках.

Транспорт: публичный CSV FRED без ключа `https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}`.
FRED редистрибуирует официальные ряды BLS LAUS/CES, BEA, Census, FHFA. Публичные
поля карточки называют ведомство-первоисточник, не идентификатор серии.

**Национальные ряды США через FRED (14.11.2026).** До этой даты 62 ряда
`world_national_core/us.yaml` (`provider: fred`) подписывались «Федеральный резервный
банк Сент-Луиса» — агрегатором, вопреки правилу первоисточника (нашёл редактор рассылки
на безработице США). Теперь у каждого ряда поле `origin_ru` — ведомство из методологии
(BLS, BEA, Census, Совет управляющих ФРС, EIA, Минфин США, Минтруд США, FHFA, Freddie Mac,
OMB), а публичный `source` = «<ведомство> (через FRED)», на английском «… (via FRED)»
(`public_source_for_spec`, `translate_source`, `localizeSource`). Записанное в базе поле
обновляется при очередной загрузке national-core.

`{geo}` — почтовый код штата (CA, NY, DC); `{fips}` — двузначный FIPS (06, 36, 11).

| Код | Шаблон серии | Частота | Единица | Первоисточник |
|-----|--------------|---------|---------|---------------|
| `unemployment-rate` | `{geo}UR` | monthly | % | BLS LAUS |
| `nonfarm-employment` | `{geo}NA` | monthly | тыс. чел. | BLS CES |
| `labor-force-participation` | `LBSSA{fips}` | monthly | % | BLS |
| `real-gdp` | `{geo}RGSP` | annual | млн долл. 2017 | BEA |
| `nominal-gdp` | `{geo}NGSP` | annual | млн долл. | BEA |
| `personal-income-per-capita` | `{geo}PCPI` | annual | долл. | BEA |
| `median-household-income` | `MEHOINUS{geo}A672N` | annual | долл. 2025 C-CPI-U; год базы сверяется с FRED Units при каждом ingest | Census |
| `population` | `{geo}POP` | annual | тыс. чел. | Census |
| `house-price-index` | `{geo}STHPI` | quarterly | индекс 1980Q1=100 | FHFA |
| `building-permits` | `{geo}BPPRIV` | monthly | единиц (поток, sum) | Census |
| `homeownership-rate` | `{geo}HOWN` | annual | % | Census |
| `minimum-wage` | `STTMINWG{geo}` | annual | долл./час | DOL |
| `civilian-labor-force` | `{geo}LF` | monthly | тыс. чел. (источник: человек ×0,001) | BLS LAUS |
| `civilian-employment` | `LASST{fips}0000000000005` | monthly | тыс. чел. (источник: человек ×0,001) | BLS LAUS |
| `unemployed-persons` | `LASST{fips}0000000000004` | monthly | тыс. чел. (источник: человек ×0,001) | BLS LAUS |
| `government-employment` | `{geo}GOVT` | monthly | тыс. чел. | BLS CES |

Новые сопоставимые национальные ряды: `us-civilian-labor-force` (`CLF16OV`),
`us-civilian-employment` (`CE16OV`), `us-government-employment` (`USGOVT`).
Штатные LAUS-ряды начинаются в январе 1976 года; занятость госсектора CES —
с января 1990 года. Загрузчик берёт всю доступную историю, затем ежедневный job заново сверяет опубликованные значения и пересмотры. Первоисточник — BLS;
транспорт полного ряда — CSV Федерального резервного банка Сент-Луиса (FRED).
Последние шесть календарных лет для трёх рядов численности LAUS сверяются напрямую
с API BLS: его значения имеют приоритет для совпадающих дат и могут опережать FRED.
Пакеты по 20 серий укладываются в публичную квоту API; ключ необязателен.
Прямой сервер `download.bls.gov` может отвечать 403; API BLS без ключа ограничивает
глубину истории, поэтому транспорт FRED сохраняет полный ряд без секретов.

### Массовый каталог BEA: вся доступная история США и штатов

Официальный первоисточник и транспорт — [региональные ZIP-архивы BEA](https://apps.bea.gov/regional/downloadzip.htm),
`https://apps.bea.gov/regional/zip/{SAGDP,SAINC,SQGDP,SQINC,SAPCE,SARPP,SASUMMARY}.zip`.
Каталог `backend/app/data/world_bea_regional/us.json` построен скриптом
`scripts/build-us-bea-catalog.py` из таблиц текущей классификации. Срез на
2026-09-24: 1 866 уникальных ненулевых рядов с общенациональной историей и покрытием
минимум 45 из 51 штата/округа; один и тот же показатель в разных таблицах
отсечён по совпадению полной истории США, Калифорнии и Нью-Йорка; полностью
нулевые линии не публикуются. Это снимок
каталога, а не обещание неизменного количества. Словарь русских названий —
`description_ru.json`; новые формулировки BEA требуют редакторского обновления
каталога. Исторические классификации отраслей не склеиваются с текущей.

Охвачены годовые и квартальные ВВП по отраслям, доходы населения, заработная
плата, оплата труда, потребительские расходы, их компоненты изменения и
региональные паритеты цен. Названия тем сверены с `Name` в официальных
`<table>__definition.xml` внутри архивов; единица каждой линии берётся из CSV.
Для каждого ряда опубликованы карточка США `us-bea-<table>-<line>` и карточки
штатов `bea-<table>-<line>`, источник, частота, единица и методология.
Наиболее ранние доступные наблюдения различаются по таблицам: доходы — вплоть
до 1929 г., квартальные доходы — с 1948 г., ВВП и потребление — преимущественно
с 1997 г., квартальный ВВП — с 2005 г., паритеты цен — с 2008 г. Фактический
старт отдельного ряда хранится в каталоге и проверяется при загрузке.

`backend/scripts/load-world-bea-regional.py --all` загружает полную историю.
Еженедельный `world_bea_regional_job` (вторник 04:20 МСК, флаг
`RUSTATS_WORLD_BEA_REGIONAL_INGEST_ENABLED`) проверяет все семь архивов и
перезагружает изменившиеся архивы целиком, включая пересмотры; SHA архива и
каталога записан в `world_dataset_state`. Неверный формат, сокращение
истории и покрытие менее 45 штатов прерывают публикацию архива с ошибкой.
Недоступные или засекреченные BEA значения не превращаются в нули.

Отброшены: бедность (нестабильный id SAIPE), налоговые поступления штата (нет ряда DC), недельные первичные заявки (шум). Территории (PR и др.) не включены — нет полной геометрии в `geoAlbersUsa` и полного набора серий.

Геометрия карты: U.S. Census Bureau cartographic boundary files, пакет `us-atlas` (`states-10m.json`, public domain / ISC). Генератор `scripts/regional/build_us_states_map_paths.mjs`, проекция `geoAlbersUsa`, результат `frontend/src/lib/usStatesMap.json`.

---

## Календарь публикаций — официальные графики (не ряды)

Календарь (`backend/app/services/calendar_sources/`, [ADR-0005](adr/0005-official-calendar-source-bound.md)) читает не данные, а **даты выхода**. Каждую ночь в 03:00 МСК (`calendar_refresh`), сверено 14.11.2026:

| Источник | Адрес | Что даёт | Модуль |
|---|---|---|---|
| Банк России, календарь решений по ключевой ставке | `https://cbr.ru/dkp/cal_mp/` (HTML, блоки `main-events_day`) | Заседания (опорные — с «Среднесрочным прогнозом»), резюме обсуждения; все опубликованные годы, 14.11 — по 2027 включительно | `cbr_key_rate.py` (запасной список `FALLBACK_MEETINGS` = страница на 14.11) |
| Банк России, календарь статистики | `https://www.cbr.ru/Queries/FileSource/105732/vCalendar.ics` (ссылка со страницы `statistics/indcalendar/`) | Резервы, денежная масса, кредиты и вклады, ставки, ипотека, внешний сектор (месячные выпуски торговли — на месячные ряды), оценка платёжного баланса (без ряда); время в **UTC** (`Z`) — переводится в МСК | `official_calendar.parse_cbr_ics` |
| Банк России, ежедневные публикации | правило «каждый рабочий день» + производственный календарь | Курсы доллара, евро, юаня, золото, RUONIA | `official_calendar.build_cbr_daily_rule_candidates` |
| Росстат, график срочных информаций | `rosstat.gov.ru/publications-plans/getPage?type=50` → `Grafik_srochn_YYYY.docx` (все годы на странице) | ИПЦ и срезы, ИЦП, ИПП, ВВП (две оценки и предварительная) | `rosstat_plan.py` |
| Росстат, график оперативных публикаций | `getPage?type=52` → `Grafic_oper_public_YYYY.doc` (Word 97, текст UTF-16LE, ячейки через `\x07`) | Доклад «Социально-экономическое положение России»: безработица, зарплата (с лагом месяц); «Краткосрочные экономические показатели»: розница, ввод жилья, строительство | `rosstat_oper_plan.py` |
| Производственный календарь | 2026: `publication.pravo.gov.ru/document/0001202509240023`; 2027: постановление № 1187 от 17.09.2026 (`government.ru/docs/59913/`) | Рабочие дни и рабочие субботы (20.02.2027) | `working_calendar.py` |
| Минфин | `minfin.gov.ru/ru/statistics/schedule` | Правило «14-й рабочий день месяца, следующего за отчётным» — срок «не позднее» (`official_deadline`, второй заход 14.11): выход часто раньше, подтверждается загрузкой | `official_calendar.build_minfin_rule_candidates` |
| ФРС США | `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` (блоки `fomc-meeting` по годам) | Решения FOMC 2026–2027, «*» — с прогнозами | `world_calendar.parse_fomc_calendar` |
| BEA (США) | `https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics` | ВВП (три оценки), личные доходы и PCE, внешняя торговля; время UTC | `world_calendar.parse_bea_ics` |
| Eurostat | `https://ec.europa.eu/eurostat/o/calendars/eventsJson?start=…Z&end=…Z&theme=&category=&keywords=&isEuroindicator=true&authorInclude=&authorExclude=` (без пустых параметров отвечает пустым телом) | Евроиндикаторы с отчётным периодом | `world_calendar.parse_eurostat_events` |
| BLS, ЕЦБ, FRED | `bls.gov/schedule` — 403 с боевого; `ecb.europa.eu` — не отвечает; FRED-календарь — разрыв соединений, ключа API нет | **не подключены** (14.11.2026) | — |

Доступ с боевого сервера 14.11.2026: `cbr.ru/dkp/cal_mp/` — 200; Росстат — читался в ночь на 14.11 (`last_seen_at`); Минфин режет сети Timeweb (на календарь не влияет, он скрыт). Ежегодно в декабре: проверить, что на страницах Росстата появились `Grafik_srochn_{год+1}.docx` и `Grafic_oper_public_{год+1}.doc`, и внести производственный календарь следующего года в `working_calendar.py` (без него правила следующего года не строятся).

## Соглашения о публикационных задержках

| Источник | Публикационная конвенция |
|----------|--------------------------|
| ЦБ DataService (`int_rat`, `mortgage`, `auto`) | publication date = M+1, фактическая дата данных = publication − 1 месяц (`date_offset_months=-1`) |
| ЦБ DataService (`m0/m1/m2`, deposits, credits) | дата = реальный месяц данных (`date_offset_months=0`) |
| Росстат `osn-MM-YYYY.pdf` (СЭП) | публикуется в месяце MM, содержит данные за **предыдущий** месяц (T+1 lag); reference month = `MM − 1` |
| Росстат `ipc_mes_MM-YYYY.xlsx` (CPI) | публикуется ~5 числа MM, данные за месяц `MM − 1` |
| Росстат `Nedel_ipc.xlsx` | актуализируется ежесреду; HTML-бюллетени публикуются в среду за прошедшую неделю |
| Минфин CSV | публикуется ~25 числа MM, данные за месяц `MM − 1` |

---

## Версионирование и архивы

- **Asset-hash trap**: при правке этого файла **не нужно** пересобирать backend/frontend — это документация, не код.
- **Schema drift**: если Росстат меняет имя файла (например, `ind_baza_2023_*.xlsx` → `ind_baza_2028_*.xlsx`) — парсер падает с понятной ошибкой, **обновить и здесь, и в `rosstat_sdds_fetcher.py`** одновременно.
- **SDDS deprecated** (ADR-0004): любые упоминания `*_GR.xlsx`, `Population_RUS.xlsx`, `Indprod_RUS.xlsx`, `Labor_RUS.xlsx`, `PPI_RUS.xlsx`, `HousePrices_RUS.xlsx` — это историческая SDDS-схема. **Не использовать**, удалена 2026-05-10.

---

## Когда обновлять этот файл

**Обязательно обновить**, если:

- Меняется URL/имя файла источника (Росстат сменил slug, ЦБ перенёс endpoint).
- Добавляется новый source-индикатор (новая строка в соответствующей таблице).
- Удаляется/депрекается индикатор (вычеркнуть из таблицы).
- Меняется `dataservice` блок (`publicationId`, `datasetId`, `element_id`, `measureId`).
- Меняется `gdp_sheet`/`gdp_history_sheet`/`ind_sheet`/`demo_file` в `model_config_json`.
- Меняется publication convention (lag, offset).

**После обновления:**
1. `Last updated` сверху → актуальная дата.
2. Синхронно обновить docstring соответствующего парсера в `backend/app/services/*_parser.py` (parser internals: source URL, лист, row/col, model_config schema, traps).
3. Если правка архитектурная (новый паттерн merge/chain) — добавить в ADR-0004 «Subsequent additions» или создать новый ADR.

### ЕМИСС — федеральные разрезы рынка труда (03.11.2026)

Коды и подписи определены в [реестре федеральных рядов](../backend/app/data/emiss_labor.py).
[Парсер](../backend/app/services/emiss_labor_parser.py) использует транспорт регионального
ЕМИСС с ETL-прокси. Каждый запрос фиксирует год, территорию и, где применимо, пол
и возраст. Периоды расположены в колонках, месяц, квартал и год записываются
в разные индикаторы. Штатный ежедневный ETL запускает активные коды
`rosstat_emiss_labor`. При пустой БД запрашивается вся утверждённая история.
При последующих прогонах запрашиваются год последней точки, предыдущий и
следующие годы до текущего. Точки сохраняются через BaseParser в
`indicator_data` по ключу «индикатор, дата», затем обновляется поколение кэша.

- [59301](https://www.fedstat.ru/indicator/59301) — уровень безработицы по
  возрасту и полу, с 2022 года. Более ранние месяцы возрастных разрезов требуют
  сверки с бюллетенями. В строках мужчин и женщин 15+ ранние месяцы отсутствуют.
- [59194](https://www.fedstat.ru/indicator/59194) и [59191](https://www.fedstat.ru/indicator/59191)
  — уровень занятости и численность рабочей силы для трёх возрастов, с 2022 года.
- [59303](https://www.fedstat.ru/indicator/59303) и [59302](https://www.fedstat.ru/indicator/59302)
  — численность долгосрочных и краткосрочных безработных, с 2019 года.
- [59197](https://www.fedstat.ru/indicator/59197) — численность занятых в
  условиях неполной занятости, с 2019 года.
- [43913](https://www.fedstat.ru/indicator/43913) — доля зарегистрированных
  среди безработных, год и квартал с 2013 года. В 2023 году выбирается
  «Российская Федерация», с 2024 года — строка без учёта новых субъектов.
- [62298](https://www.fedstat.ru/indicator/62298) — доля безработных с высшим
  образованием, год с 2022-го и квартал с 2023-го. Числитель и знаменатель
  относятся к безработным 15+.

В паспортах 59302, 59303 и 59197 указан возрастной охват 15–72 года до
2021-го и 15+ с 2021-го. Для 59302 и 59303 граница длительности составляет
12 месяцев. Паспорт 59197 раскрывает критерий занятости и возрастной охват,
но не уточняет критерий неполной занятости. Приказ Росстата № 707 определяет
неполную занятость по продолжительности рабочего времени через часы, желание
и готовность работать больше. Привязка именно этого определения к 59197
остаётся неподтверждённой.

Для остальных рядов строка страны меняется с января 2023 года. Значения за
отсутствующие периоды сохраняют пропуск. В срезе 03.11.2026 ЕМИСС не отдал
сентябрь 2022 для уровня занятости 15–24, июнь 2026 для неполной занятости и
IV квартал 2025 для доли зарегистрированных. Ранние ряды 59301 и новые
ряды 59194/59191 за 2019–2021 требуют отдельной сверки сопоставимости.
Национальный ряд общего уровня безработицы по-прежнему загружается из
ежемесячного бюллетеня Росстата.

Полная структура по образованию доступна в сборнике
[«Труд и занятость в России 2025»](https://rosstat.gov.ru/storage/mediabank/Trud_2025.pdf)
(таблицы 1.76 и 1.77, 2020–2024, всего и отдельно по полу). Значения высшего
образования 22,9%, 21,3%, 21,8% за 2022–2024 совпали с 62298. Подключение
всех уровней образования, архивных выпусков и региональных рядов остаётся
отдельной частью работы. Региональный фильтр 59301 есть в карточке, пробный
запрос по трём регионам за IV квартал 2025 вернул пустую выдачу.

До подключения этого контура федеральный парсер рынка труда извлекал четыре
ряда из ежемесячного бюллетеня, а региональный ЕМИСС обслуживал топливо.
В живом федеральном каталоге среди рядов безработицы на 03.11.2026 был только
общий показатель (сентябрь 2026). Это граница прежней реализации по коду;
отдельного решения исключить разрезы в истории не найдено.

Региональная сверка [43062](https://www.fedstat.ru/indicator/43062) дала
26,4%, 11,2% и 8,7% в Ингушетии, Дагестане и Чечне за 2024 год.
За 2025 год — 25,4%, 10,9%, 6,7%, в Москве — 0,8%, по России — 2,2%.
За II квартал 2026 есть отдельные наблюдения. Данные
[33414](https://www.fedstat.ru/indicator/33414) за 2025 год дают 1 681,3 тыс.
безработных по стране и 281,5 тыс. суммарно по трём республикам (16,7%).
Этот результат относится к годовым значениям за 2025 год.

[Eurostat, Key figures on Europe 2026](https://ec.europa.eu/eurostat/documents/15216629/23964567/KS-01-26-035-EN-N.pdf/f922271a-da8c-3d8e-30a0-daa5843b6a75)
публикует для ЕС в 2024 году 14,8% у 15–24 и 5,9% у 15–74 (примерно 2,5 раза).
Показатель «2,7 раза» требует указания отдельной выборки стран и весов.

### ЕМИСС — распределение доходов населения и заработных плат (18.11.2026)

Пустые поиски Пульса за 17.11.2026 («распределение зарплат», «распределение дохода россия», «джини», «доля доходов
10% самых богатых») указали на пробел каталога: в России не было ни одного ряда распределения. Коды и подписи —
[реестр](../backend/app/data/emiss_income.py), [парсер](../backend/app/services/emiss_income_parser.py),
`parser_type = rosstat_emiss_income`, категория «Рынок труда» (на странице раздела — темы «Распределение зарплат» и
«Неравенство доходов»). Транспорт — тот же `_post_grid`, что у регионального и трудового ЕМИСС (на проде fedstat
отвечает адресу сервера 403, запрос идёт через ETL-прокси). Один запрос на ряд: строки — территория и год, столбец —
период; при пустой базе запрашивается вся история, дальше — последний сохранённый год (у зарплат по группам — два
года) и новые годы. Россия до 2022 года — строка «Российская Федерация», с 2023 года — «без учета новых субъектов».
Все ряды годовые, точка — 1 января года; прогноза нет (`forecast_steps: 0`).

| Код | ЕМИСС | Что | Единица | История (живой запрос с Mac 18.11.2026) |
|---|---|---|---|---|
| `income-gini` | [31165](https://www.fedstat.ru/indicator/31165) | Коэффициент Джини (индекс концентрации доходов) | коэффициент 0–1 | 1992–2025, 34 года; 2025 — 0,422 |
| `income-funds-ratio` | [31170](https://www.fedstat.ru/indicator/31170) | Коэффициент фондов: доходы 10 % самых и наименее обеспеченных | раз | 1992–2025; 2025 — 16,0 |
| `income-share-quintile-1…5` | [31400](https://www.fedstat.ru/indicator/31400) | Доли пяти 20-процентных групп в общем объёме денежных доходов (измерение 58814) | % | 1992–2025, 34 года (2011–2022 ЕМИСС отдаёт только строкой «без учета новых субъектов» — это та же страна, парсер берёт её, если строки «Российская Федерация» нет); сумма пяти долей — 100 в каждом году; 2025 — 5,2 / 9,7 / 14,8 / 22,5 / 47,8 |
| `income-share-top10`, `income-share-bottom10` | [60756](https://www.fedstat.ru/indicator/60756) | Доли 10 % самых и наименее обеспеченных (измерение 58823) | % | 2013–2025; 2025 — 31,0 и 1,9 |
| `wages-median` | [61773](https://www.fedstat.ru/indicator/61773) | Медианная заработная плата | руб. | 2019–2025; 2025 — 65 307 |
| `wages-decile-1…10` | [58031](https://www.fedstat.ru/indicator/58031) | Средняя зарплата десяти 10-процентных групп работников, «Всего по обследуемым видам деятельности» (57940 = 1692933), период «апрель» (1540229) | руб. | 2017, 2019, 2021, 2023, 2025 — обследование раз в два года; 2025 — от 24 786 до 315 835 |

Не подключены: распределение населения по интервалам среднедушевого дохода ([31399](https://www.fedstat.ru/indicator/31399))
и работников по интервалам зарплаты ([58033](https://www.fedstat.ru/indicator/58033)) — границы интервалов меняются
почти каждый год (88 и 128 разных интервалов в справочниках), и ряд «доля с доходом в интервале» не сопоставим во времени.
Региональные значения 31165/31170/31400 в ЕМИСС есть (95–100 территорий) — региональный контур не подключался.
Загрузка в боевую базу не выполнялась: ряды появятся после выпуска и стартового догона пустых индикаторов
(`_catch_up_empty_indicators`).

### ЕМИСС — цены производителей стали (19.11.2026)

Мировая цена стали (`steel`) снята 16.08.2026 — свободного официального ряда котировок нет. Вместо неё — помесячные
«Средние цены производителей промышленных товаров» Росстата ([57606](https://www.fedstat.ru/indicator/57606)) по трём
позициям ОКПД2. Коды и подписи — [реестр](../backend/app/data/emiss_steel.py), [парсер](../backend/app/services/emiss_steel_parser.py),
`parser_type = rosstat_emiss_steel`, категория «Товарные рынки» (раздел `/russia/category/commodities`, где был `steel`).
Транспорт — тот же `_post_grid`, что у регионального, трудового и доходного ЕМИСС (на проде запрос идёт через ETL-прокси).
Один запрос на ряд: строки — продукция (57939), территория (57831) и год, столбцы — месяцы (33560); фильтры — рубль
(30611 = 950351), тонна (ОКЕИ 57956 = 1694829), канал «Внутренний рынок» (58601 = 1744136). Россия до 2022 года —
строка «Российская Федерация», с 2023 года — «без учета новых субъектов» (ЕМИСС отдаёт каждую строку только за свои годы).
Пустая база — вся история с 2017 года (≈13 с на три ряда с Mac), дальше — год последней точки, предыдущий и новые.
Обновление — ежедневный `daily_update_job`, как у соседних рядов ЕМИСС; Росстат публикует месяц на 12–16-й рабочий
день после его окончания (паспорт показателя; последнее обновление на 19.11.2026 — 29.10.2026, данные по сентябрь).
Цена — без НДС и акцизов, средняя взвешенная по объёму выпуска (методика Росстата, приказ № 729 от 17.11.2016).
Прогноза нет (`forecast_steps: 0`). Граница значения 3 000–500 000 ₽/т ловит сбой единицы или позиции.

| Код | ОКПД2 (oid) | Что | История (живой запрос с Mac 19.11.2026) |
|---|---|---|---|
| `steel-hot-rolled` | 1694672 | Прокат листовой горячекатаный стальной, без дополнительной обработки — та же продукция, что у прежнего `steel` | 2017-01 — 2026-09, 117 месяцев; 2017-01 — 34 380,35, 2026-09 — 54 556,33 ₽/т |
| `steel-rebar` | 1694665 | Прокат сортовой и катанка из нелегированных сталей — арматура, круг, катанка | 2017-01 — 2026-09; 2017-01 — 27 256,16, 2026-09 — 52 167,91 ₽/т |
| `steel-pipes` | 1694350 | Трубы стальные электросварные | 2017-01 — 2026-09; 2017-01 — 34 353,28, 2026-09 — 57 548,74 ₽/т |

Контрольные точки совпали во втором живом запросе с каналами в строках (тот же источник, другая раскладка таблицы).
Не взяты: агрегаты «Прокат сортовой и катанка горячекатаные стальные» (1693266) и «Трубы, профили пустотелые и их фитинги
стальные» (1700490) — значений нет; «Трубы круглого сечения прочие стальные» (1795425) — 0,4–1,2 млн ₽/т со скачками в
разы; «Сталь нелегированная в слитках» (1693561) на внутреннем рынке — 13–75 тыс. ₽/т с перепадами в полтора раза за
месяц (тонкий рынок). Канал «Всего» не взят: в нём экспорт (у полуфабрикатов он и задаёт цену).
Поиск: название ряда держит «стали» и не держит «стальн…» — правило `MEASURE_RULES["steel"]` отделяет цену стали от
посуды из стали; фразы «цена стали», «цены на сталь», «стоимость стали» — псевдонимы `steel` в `search_intent.py`
(«стали» само по себе — глагол). Загрузка в боевую базу не выполнялась: ряды появятся после выпуска и стартового
догона пустых индикаторов.

### ЕМИСС — зарплата, пенсия и рождаемость по регионам помесячно (19.11.2026)

До 19.11.2026 у регионов эти темы были только годовыми (сборник «Регионы России», последний год 2024). Заведены
помесячные ряды в слой `region_monthly_data` (тот же, что у цен 31448). Реестр — [`emiss_regional_social.py`](../backend/app/data/emiss_regional_social.py),
загрузчик — [`services/emiss_regional_social.py`](../backend/app/services/emiss_regional_social.py), job `emiss_social`
(12, 22 и 27-е число, 08:10 МСК; вне дней цен 15/20/25/28 и вне окон ETL). Метаданные — строки в конце
`app/data/regional/indicators.json` (приходят в базу при старте через `seed_regional`), английские названия — в
`region_indicators_en.py` из реестра. Транспорт, запись и границы истории — общие с `emiss_regional_parser`
(`_post_grid`, `_upsert_monthly_points`, advisory-блокировка, `update_regional_year_bounds`).

Один запрос на ряд: строки — территория и год, столбцы — 12 месяцев (33560); территории перечисляются явно — oid в
`app/data/regional/emiss_social_territories.json` (со страниц показателей 08–09.11.2026). Название территории из ответа
→ slug: `emiss_dimnames.json` + `TERRITORY_ALIASES` (межведомственный ОКАТО Соцфонда пишет «г. Москва », «Республика
Северная Осетия - Алания»; Краснодарский край с 2026 года — «с учетом ФТ «Сириус»»). Пропускаются Байконур и округа в
границах до 03.11.2018. Пустая база — вся история набора, дальше — год последней точки, предыдущий и новые. Ячейка вне
границ здравого смысла пропускается и считается, незнакомая территория считается — ряд не падает; ответ без единой
точки — смена формата (алерт раз в трое суток).

| Набор | Что | Ряды (коды) | Территория, Россия | История и последний период (живой запрос с Mac 19.11.2026) |
|---|---|---|---|---|
| [57824](https://www.fedstat.ru/indicator/57824) | Среднемесячная начисленная зарплата | `zarplata-mesyachnaya` (всего, ОКВЭД2 1692933) и 19 разделов ОКВЭД2 `zarplata-mesyachnaya-<раздел>` | 57831; Россия до 2022 — «Российская Федерация», с 2023 — «без учета новых субъектов» | 2017-01 — 2026-08 по субъектам, по России 2026-07; Россия 2026-07 — 109 523,5 ₽; 11 083 точки у «всего» |
| [61699](https://www.fedstat.ru/indicator/61699) | Средний размер назначенной пенсии (данные Соцфонда), на 1-е число | `pensiya-srednyaya-mesyachnaya`, `-rabotayuschih`, `-nerabotayuschih` (61609) | 30628 (межведомственный), Россия — одна строка, все субъекты | 2021 — на 1 сентября 2026; Россия — 25 469,39 ₽; 5 854 точки на ряд |
| [61698](https://www.fedstat.ru/indicator/61698) | Численность пенсионеров на 1-е число | `chislennost-pensionerov-mesyachnaya`, `chislennost-rabotayuschih-pensionerov`; человек → тысяч человек | 30628 | 2021 — на 1 сентября 2026; Россия — 40 519,3 тыс. |
| [62852](https://www.fedstat.ru/indicator/62852), [62853](https://www.fedstat.ru/indicator/62853) | Суммарный коэффициент рождаемости (Я1) и третьих и последующих детей (Я2) | `summarnyy-koeffitsient-rozhdaemosti-mesyachnyy`, `…-tretih-detey` | 57831, Россия — «без учета новых субъектов» | 2025-01 — 2026-09; Россия 2026-09 — 1,336 и 0,348; значение «за год» (1558883) не берётся |

Дата хранения: зарплата и рождаемость — отчётный месяц; пенсия и число пенсионеров «на 1 сентября» хранятся как
сентябрь (пометка в примечании ряда). Значение СКР за месяц — помесячная оценка Росстата; по данным она ведёт себя
как оценка за последние двенадцать месяцев (январь 2026 — 1,362 при годовом значении 2025 — 1,361), паспорт ЕМИСС
смысл месяца не описывает — проверить у Росстата. Контрольные точки совпали с ответами, скачанными 08–11.11.2026.
Объём на всю историю — ~255 тыс. точек (боевая `region_monthly_data` — ~175 байт на строку с индексами, ~45 МБ).
Не взяты: 62164 (пенсия по видам — по старости, по инвалидности) — квартальная, месячный график рвёт её на точки,
нужен квартальный слой; 348 подробных видов деятельности 57824 — нужен экран выбора; строки «январь–…» 57824.
Страница месячного ряда: SSR-тексты зарплаты, пенсии и рождаемости — свои (`MONTHLY_TEXT_RU/EN`), без ценовых фраз;
пересчёт «в ценах последнего месяца» API отдаёт только рублёвым рядам. Поиск: «средняя пенсия» (r6a), «зарплата
учителей/врачей/программистов/строителей/полицейских» → раздел ОКВЭД2 (`SEARCH_CONCEPTS` реестра).
Загрузка в боевую базу не выполнялась: ряды появятся после выпуска в ближайший плановый прогон.
### ЕМИСС — помесячные ряды регионов: сельхозцены, ввод жилья, промышленность, грузоперевозки (19.11.2026)

До 19.11.2026 эти темы по субъектам были только годовыми и кончались 2024 годом («Регионы России»). Теперь — свежие
помесячные ряды Росстата по субъектам и России в целом в слое `region_monthly_data`, как цены 31448.
Коды, названия, единицы — [реестр](../backend/app/data/emiss_regional_sets.py), разбор и запись —
[парсер](../backend/app/services/emiss_regional_sets_parser.py), задача `emiss_regional_sets` (15, 20, 25 и 28-е число,
08:10 МСК, на 30 минут позже цен 31448). Метаданные рядов дописывает `seed_regional.load_meta()` из реестра,
в `indicators.json` их нет. Транспорт — тот же `_post_grid` (на проде через ETL-прокси), один запрос — один год
набора: строки — позиция × территория, столбцы — 12 месяцев. Территории — справочник ОКАТО витрины 31448 плюс
«Краснодарский край (с учетом ФТ «Сириус»)» (1856621): эта строка берётся только за месяцы, где обычной строки края
нет (ввод жилья с мая 2026). Россия: до 2022 года — «Российская Федерация», с 2023-го — «без учета новых субъектов».
Пустая база — вся история набора (~60 запросов, с Mac ~3 минуты), дальше — год самой ранней последней точки − 1
и новые. Значение «0» у цены или индекса — месяц без продаж, пропуск; значение вне границ набора — пропуск и счёт
`rejected` в статистике прогона. Прогноза нет.

| Набор | Раздел регионов | Ряды (код) | История | Россия, сентябрь 2026 |
|---|---|---|---|---|
| [57693](https://www.fedstat.ru/indicator/57693) средние цены производителей сельхозпродукции, руб./т (яйца — руб. за 1000 шт.), без НДС | 13 «Сельское хозяйство» | `selhoz-cena-` + `pshenica`, `pshenica-3/-4/-5` (мягкая 3–5 класса), `yachmen`, `kukuruza`, `rozh`, `oves`, `grechiha`, `podsolnechnik`, `soya`, `raps`, `kartofel`, `svekla`, `moloko`, `krs`, `svinyi`, `ptica`, `yayca` | 2017-01 (классы пшеницы — 2019-01) | пшеница 10 185,32; подсолнечник 31 784,74; молоко 36 742,03 |
| [34118](https://www.fedstat.ru/indicator/34118) ввод жилья, тыс. м² за месяц, оперативные данные | 14 «Строительство» | `vvod-zhilya-mes` (всего), `vvod-zhilya-mkd-mes` (многоквартирные), `vvod-zhilya-izhs-mes` (построено населением) | 2012-01 (всего), 2015 (МКД, население) | 8 243,8; 2 848,5; 5 271,7 |
| [57806](https://www.fedstat.ru/indicator/57806) индекс производства, % к тому же месяцу прошлого года | 12 «Промышленное производство» | `ipp-dobycha-mes`, `ipp-obrabotka-mes`, `ipp-energetika-mes`, `ipp-vodosnabzhenie-mes` | 2015-01 | 95,9; 105,6; 96,8; 100,9 |
| [31076](https://www.fedstat.ru/indicator/31076) индексы тарифов на грузовые перевозки, % к тому же месяцу прошлого года | 16 «Транспорт» | `tarif-gruz-vse-mes`, `tarif-gruz-avto-mes`, `tarif-gruz-zhd-mes` | 2006-01 (этот вид индекса раньше не публиковался) | 108,48; 107,8; 114,68 |

Объём (живой проход всей истории с Mac 19.11.2026): 57693 — 82,9 тыс. точек, 34118 — 40,1 тыс., 57806 — 52,8 тыс.,
31076 — 50,1 тыс.; всего ≈226 тыс. строк (≈20 МБ с индексами). Особенности источника: у молока, яиц и кукурузы с 2024
года новый oid позиции под тем же названием — ряд берёт оба; строки «Всего по обследуемым видам» в 57806 нет ни за один
год, поэтому промышленность по регионам — четыре раздела; наборы 59262/59993 (те же МКД и ИЖС в млн м²) не взяты —
история короче, значения те же. Не заведены (19.11.2026): 57740 (индексы тех же сельхозцен), ход сева и уборки
34165/34158/40545/33784 (значения «на 1-е число», с 2023 года, без сои и ячменя), турпоездки 62900 (с 2025 года,
своё измерение территорий 3301), платные услуги 57788 — 34165/34158, 62900 и 57788 позже 19.11.2026 завела зона F
(раздел «пенсии по видам, итоги сева и уборки…» ниже). Загрузка в боевую базу не выполнялась: ряды появятся после
выпуска при первом прогоне задачи.
### ЦБ — кредиты физлицам и ипотека по России и регионам помесячно (DataService, 19.11.2026)

До 19.11.2026 из этих публикаций был только остаток кредитов физлицам (`consumer-credit`); по регионам — годовая
задолженность из «Регионов России» (раздел 19, на 1 января, до 2025 года). Пустые поиски людей: «задолженность
домохозяйств», «закредитованность», «сведения о задолженности по кредитам физическим лицам». Реестр —
[cbr_household_credit.py](../backend/app/data/cbr_household_credit.py): карточки России идут через действующий
`cbr_dataservice_json` (строки таблицы выше, раздел каталога «Деньги и бюджет»), ряды регионов —
[cbr_regional_credit_parser.py](../backend/app/services/cbr_regional_credit_parser.py) в `region_monthly_data`,
раздел регионов 19 «Финансы», `table_code` `19.k1`–`19.k8`, мост к карточке России — `MACRO_BY_TABLE`. Метаданные
рядов дописывает `seed_regional.load_meta()`. Задача `cbr_regional_credit` — 3, 6, 10 и 20-го числа в 07:45 МСК.

Регион в DataService — `measureId` (96 позиций: Россия 22, 8 округов, субъекты, «в том числе» автономные округа:
46 — НАО, 47 — Архангельская обл. без НАО, 91 — ХМАО, 92 — ЯНАО, 93 — Тюменская обл. без АО; сумма 91+92+93 = 90).
Несколько регионов одним запросом API не отдаёт (проверено 19.11.2026), поэтому прогон сначала спрашивает Россию:
нет нового месяца — ряд пропускается (1 запрос); есть — все 96 позиций с года последней точки − 1. Пустая база —
с 2019 года, ~96 запросов на ряд, 8 рядов, с паузой 0,25 с — несколько минут. Сервер Timeweb DataService отвечает
(200), обход не нужен. Единицы регионов — как у источника: млн руб., кредиты (штук), месяцы. Срок «0» — месяц без
рублёвых ипотек в регионе, пропуск. Разреза «новостройки / вторичка» у DataService нет (столбцы наборов 44–48 —
только всего / рубли / валюта); сезонно скорректированный долг (55, 56) не взят.

| Набор | Россия (карточка) | Регионы (код) | Россия, сентябрь 2026 (живой ответ 19.11.2026) |
|---|---|---|---|
| 41 выдано кредитов физлицам | `consumer-loans-issued`, млрд руб. | `kredity-fizlicam-vydano-mes` | 2 492,4 |
| 42 задолженность физлиц | `consumer-credit` (была), трлн руб. | `kredity-fizlicam-dolg-mes` | 37,67 |
| 43 просроченная задолженность физлиц | `consumer-credit-overdue`, млрд руб. | `kredity-fizlicam-prosrochka-mes` | 1 806,7 |
| 44 число ипотек | `mortgage-issued-count`, тыс. | `ipoteka-chislo-mes` | 125,2 |
| 45 выдано ипотеки | `mortgage-issued`, млрд руб. | `ipoteka-vydano-mes` | 617,1 |
| 46 задолженность по ипотеке | `mortgage-debt`, трлн руб. | `ipoteka-dolg-mes` | 21,97 |
| 47 просрочка по ипотеке | `mortgage-overdue`, млрд руб. | `ipoteka-prosrochka-mes` | 268,8 |
| 48 средний срок ипотеки | `mortgage-term`, мес. | `ipoteka-srok-mes` | 304,8 |

Объём: 8 рядов × 96 позиций × 93 месяца ≈ 71 тыс. строк (≈7–10 МБ с индексами), дальше ≈ 770 строк в месяц; карточки
России — 7 × 93 точки. Загрузка в боевую базу не выполнялась: карточки России заполнит ежедневный ETL, регионы —
первый прогон `cbr_regional_credit` после выпуска. Условия ЦБ: использование с указанием источника.

### ЕМИСС — цены производителей по отраслям и товарам, цены в строительстве (19.11.2026)

До 19.11.2026 из цен производителей на сайте был только общий индекс (`ppi`). Заведены 50 помесячных рядов Росстата по
России целиком из пяти витрин ЕМИСС: [57609](https://www.fedstat.ru/indicator/57609) (ИЦП по видам деятельности, 14 из
250), [57608](https://www.fedstat.ru/indicator/57608) (ИЦП по товарам, 18 из 1672; сталь — 57606 выше),
[57724](https://www.fedstat.ru/indicator/57724) (средние цены покупки стройматериалов строительными организациями, 10 из
163), [57796](https://www.fedstat.ru/indicator/57796) (ИЦП на строительную продукцию, 4 из 372),
[63349](https://www.fedstat.ru/indicator/63349) (индексы цен по группам объектов капитального строительства, все 4, с
2025 года). Коды, oid и подписи — [реестр](../backend/app/data/emiss_producer_prices.py),
[парсер](../backend/app/services/emiss_producer_prices_parser.py), `parser_type = rosstat_emiss_producer_prices`,
категория «Цены» (раздел `/russia/category/prices`). Регионы в витринах есть (96–100 территорий) — региональный слой не
подключался.

Индексы — вид показателя «Отчетный месяц к соответствующему месяцу предыдущего года» (57937 = 1704141), канал «Внутренний
рынок» (58601 = 1744136) у 57609/57608, единица «процент» (30611 = 950473); хранится изменение в процентах (104,5 → 4,5).
Средние цены 57724 — рубль (30611 = 950351), единица ОКЕИ (57956) — строка ответа, ряд берёт только свою. Транспорт — тот
же `_post_grid`, один запрос на витрину за прогон (ответ держится в памяти процесса 15 минут, ряды витрины делят его).
Россия до 2022 года — строка «Российская Федерация», с 2023 года — «без учета новых субъектов». Пустая база — вся история
витрины; дальше — год последней точки, предыдущий и новые. Обновление — ежедневный `daily_update_job`, как у соседних
рядов ЕМИСС. Прогноза нет (`forecast_steps: 0`). Границы: индекс 10–1000 (у нефти в мае 2021 года 552,92 — база весны
2020-го), цена 50–1 000 000 ₽. Всего 5 262 точки на всю историю (≈1 МБ в `indicator_data` с индексами).

Пропуски источника: у товаров 57608 в 2021 году по 2–6 месяцев не опубликовано (смена классификатора), нефть — с 2021
года, каменный уголь и «жилые и нежилые здания» 57796 — с 2018 года, линии электропередачи 63349 — с июля 2025 года.
Цемент 57724 — с 2022 года (до 2022 года другая позиция «Цементы общестроительные»); бетон сшит из двух oid с одним
названием (1693127 до 2021 года, 1793407 с 2022 года — ОКПД2 обновлён без смены описания).
Не взяты: 57709 (индексы цен на те же стройматериалы — рубли понятнее индекса); «Всего по обследуемым видам» 57609 на
внутреннем рынке не публикуется (общий индекс уже есть — `ppi`); электроэнергия 57608 — десятки строк по категориям
потребителей и тарифам; минеральные удобрения 57608 по России не опубликованы; песок и гравий 57724 — средняя цена
прыгает в 2–3 раза за месяц (песок 889 → 292 → 976 ₽/м³ в мае–июле 2026). У кирпича (2019–2020), плит перекрытий (2023)
и пиломатериалов (2023) единичные скачки средней цены на 40–60 % — так в источнике, ряды оставлены.

Сверка: последние точки совпали с независимыми запросами 19.11.2026 (другая раскладка таблицы — все позиции витрины за
2025–2026) и со скачанными 08.11 ответами (57724, 63349): добыча 118,51, бензин 97,59, ДТ 128,13 (2026-09), строительная
продукция всего 107,19 (2026-08), жилищно-гражданские объекты 113,42, бетон 8 199,05 ₽/м³, щебень 2 698,49 ₽/м³.
Поиск: псевдоним «бетон/бетона» в `search_intent.py` («бетона» исправлялось в «батона» → хлеб), фразы из Яндекса — в
ключевых словах рядов. Загрузка в боевую базу не выполнялась: ряды появятся после выпуска и стартового догона пустых
индикаторов.

| Код | Витрина | oid | Название | История (живой запрос 19.11.2026), месяцев | Последнее значение |
|---|---|---|---|---|---|
| `ppi-mining` | 57609 | 1692320 | Цены производителей за год: добыча полезных ископаемых | 2017-01 — 2026-09, 117 | 18,51 % |
| `ppi-manufacturing` | 57609 | 1692321 | Цены производителей за год: обрабатывающие производства | 2017-01 — 2026-09, 117 | 7,71 % |
| `ppi-energy` | 57609 | 1692750 | Цены производителей за год: электроэнергия, газ и тепло | 2017-01 — 2026-09, 117 | -1,47 % |
| `ppi-water` | 57609 | 1692748 | Цены производителей за год: водоснабжение и отходы | 2017-01 — 2026-09, 117 | 2,85 % |
| `ppi-oil-gas` | 57609 | 1692336 | Цены производителей за год: добыча нефти и газа | 2017-01 — 2026-09, 117 | 20,83 % |
| `ppi-coal-mining` | 57609 | 1692335 | Цены производителей за год: добыча угля | 2017-01 — 2026-09, 117 | 24,85 % |
| `ppi-food-industry` | 57609 | 1692340 | Цены производителей за год: пищевая промышленность | 2017-01 — 2026-09, 117 | 0,34 % |
| `ppi-petroleum-products` | 57609 | 1692348 | Цены производителей за год: нефтепереработка | 2017-01 — 2026-09, 117 | 26,55 % |
| `ppi-chemicals` | 57609 | 1692349 | Цены производителей за год: химия | 2017-01 — 2026-09, 117 | 12,25 % |
| `ppi-pharma` | 57609 | 1692309 | Цены производителей за год: лекарства | 2017-01 — 2026-09, 117 | 1,07 % |
| `ppi-building-materials` | 57609 | 1692351 | Цены производителей за год: цемент, стекло, кирпич | 2017-01 — 2026-09, 117 | 2,76 % |
| `ppi-metallurgy` | 57609 | 1692352 | Цены производителей за год: металлургия | 2017-01 — 2026-09, 117 | 9,64 % |
| `ppi-wood` | 57609 | 1692796 | Цены производителей за год: древесина и пиломатериалы | 2017-01 — 2026-09, 117 | 4,12 % |
| `ppi-vehicles` | 57609 | 1692819 | Цены производителей за год: автомобили | 2017-01 — 2026-09, 117 | 0,77 % |
| `ppi-crude-oil` | 57608 | 1831798 | Цена производителей за год: нефть | 2021-01 — 2026-09, 67 | 26,33 % |
| `ppi-natural-gas` | 57608 | 1693328 | Цена производителей за год: природный газ | 2017-01 — 2026-09, 115 | 9,49 % |
| `ppi-hard-coal` | 57608 | 1694797 | Цена производителей за год: каменный уголь | 2018-01 — 2026-09, 99 | 28,37 % |
| `ppi-gasoline` | 57608 | 1694068 | Цена производителей за год: автомобильный бензин | 2017-01 — 2026-09, 113 | -2,41 % |
| `ppi-diesel` | 57608 | 1694081 | Цена производителей за год: дизельное топливо | 2017-01 — 2026-09, 113 | 28,13 % |
| `ppi-cement` | 57608 | 1693124 | Цена производителей за год: цемент | 2017-01 — 2026-09, 113 | -2,42 % |
| `ppi-copper` | 57608 | 1757782 | Цена производителей за год: медь | 2017-01 — 2026-09, 113 | 49,34 % |
| `ppi-aluminium` | 57608 | 1709082 | Цена производителей за год: алюминий | 2017-01 — 2026-09, 113 | 41,27 % |
| `ppi-beef` | 57608 | 1694621 | Цена производителей за год: говядина | 2017-01 — 2026-09, 113 | 3,89 % |
| `ppi-pork` | 57608 | 1694620 | Цена производителей за год: свинина | 2017-01 — 2026-09, 113 | -8,76 % |
| `ppi-poultry` | 57608 | 1757893 | Цена производителей за год: мясо птицы | 2017-01 — 2026-09, 113 | 15,70 % |
| `ppi-milk` | 57608 | 1757631 | Цена производителей за год: пастеризованное молоко | 2017-01 — 2026-09, 115 | -0,39 % |
| `ppi-butter` | 57608 | 1757634 | Цена производителей за год: сливочное масло | 2017-01 — 2026-09, 115 | -9,47 % |
| `ppi-sugar` | 57608 | 1693843 | Цена производителей за год: сахар | 2017-01 — 2026-09, 115 | 7,70 % |
| `ppi-sunflower-oil` | 57608 | 1693003 | Цена производителей за год: подсолнечное масло | 2017-01 — 2026-09, 115 | 7,52 % |
| `ppi-flour` | 57608 | 1757645 | Цена производителей за год: пшеничная мука | 2017-01 — 2026-09, 113 | -4,01 % |
| `ppi-bread` | 57608 | 1693828 | Цена производителей за год: хлеб | 2017-01 — 2026-09, 113 | 5,94 % |
| `ppi-cars` | 57608 | 1693287 | Цена производителей за год: легковые автомобили | 2017-01 — 2026-09, 113 | 1,57 % |
| `build-cement` | 57724 | 1693124 | Цена стройматериалов: цемент | 2022-01 — 2026-09, 57 | 9 730,20 руб./т |
| `build-crushed-stone` | 57724 | 1693348 | Цена стройматериалов: щебень | 2017-01 — 2026-09, 117 | 2 698,49 руб./м³ |
| `build-concrete` | 57724 | 1693127/1793407 | Цена стройматериалов: товарный бетон | 2017-01 — 2026-09, 117 | 8 199,05 руб./м³ |
| `build-mortar` | 57724 | 1694306 | Цена стройматериалов: строительный раствор | 2017-01 — 2026-09, 117 | 6 829,45 руб./м³ |
| `build-brick` | 57724 | 1694273 | Цена стройматериалов: керамический кирпич | 2017-01 — 2026-09, 117 | 21 786,74 руб./тыс. шт. |
| `build-silicate-brick` | 57724 | 1757755 | Цена стройматериалов: силикатный кирпич | 2017-01 — 2026-09, 117 | 18 275,24 руб./тыс. шт. |
| `build-floor-slabs` | 57724 | 1758236 | Цена стройматериалов: плиты перекрытий | 2017-01 — 2026-09, 117 | 28 903,43 руб./м³ |
| `build-timber` | 57724 | 1694031 | Цена стройматериалов: хвойные пиломатериалы | 2017-01 — 2026-09, 117 | 21 541,15 руб./м³ |
| `build-insulation` | 57724 | 1757763 | Цена стройматериалов: минеральный утеплитель | 2017-01 — 2026-09, 117 | 6 228,66 руб./м³ |
| `build-bitumen` | 57724 | 1694134 | Цена стройматериалов: битум | 2017-01 — 2026-09, 117 | 46 392,98 руб./т |
| `ppi-construction` | 57796 | 1692933 | Цены в строительстве за год: всего | 2017-01 — 2026-08, 116 | 7,19 % |
| `ppi-construction-buildings` | 57796 | 1692441 | Цены в строительстве за год: жилые и нежилые здания | 2018-01 — 2026-08, 104 | 8,25 % |
| `ppi-construction-civil` | 57796 | 1692359 | Цены в строительстве за год: дороги, мосты и сети | 2017-01 — 2026-08, 116 | 6,34 % |
| `ppi-construction-specialised` | 57796 | 1692360 | Цены в строительстве за год: отделка и монтаж | 2017-01 — 2026-08, 116 | 1,55 % |
| `build-cost-housing` | 63349 | 1856450 | Стоимость стройки за год: жильё и общественные здания | 2025-01 — 2026-09, 21 | 13,42 % |
| `build-cost-industrial` | 63349 | 1856451 | Стоимость стройки за год: заводы и склады | 2025-01 — 2026-09, 21 | 17,04 % |
| `build-cost-roads` | 63349 | 1856452 | Стоимость стройки за год: дороги | 2025-01 — 2026-09, 21 | 10,63 % |
| `build-cost-power-lines` | 63349 | 1856469 | Стоимость стройки за год: линии электропередачи и сети | 2025-07 — 2026-09, 15 | 7,96 % |

### ЕМИСС — пенсии по видам, итоги сева и уборки, платные услуги, турпоездки по регионам (19.11.2026, зона F)

Что осталось после зон A–E. Реестры те же: квартальный и годовой слой — [`app.data.emiss_quarterly`](../backend/app/data/emiss_quarterly.py)
(задача `emiss_quarterly`, 5/15/25-го в 07:55 МСК), помесячный — [`app.data.emiss_regional_sets`](../backend/app/data/emiss_regional_sets.py)
(задача `emiss_regional_sets`, 15/20/25/28-го в 08:10 МСК). Новых задач и расписаний нет. Живой проход всей истории с Mac
19.11.2026, без базы: 15 запросов, ошибок нет.

| Набор | Ряды сайта | Слой | История | Последний период | Россия | Точек |
|---|---|---|---|---|---|---|
| [62164](https://www.fedstat.ru/indicator/62164) средняя пенсия по видам (Соцфонд), ₽ | `pensiya-po-starosti`, `pensiya-po-starosti-nerabotayuschih`, `pensiya-po-invalidnosti`, `pensiya-po-potere-kormiltsa`, `pensiya-socialnaya` (раздел 3) | квартал, «на 1-е число» квартала | IV 2021 (на 1.10.2021) | IV 2026 (на 1.10.2026) | по старости 27 322,54; неработающим 27 882,08 | 10 080 |
| [34165](https://www.fedstat.ru/indicator/34165) собрано урожая, тыс. т, хозяйства всех категорий | `urozhay-{zerno,podsolnechnik,svekla,kartofel}-1-noyabrya` (раздел 13) | год, дата 1 ноября | 2023 | 2025 (на 1.11.2026 ещё нет) | зерно 2025 — 134 535,21 | 773 |
| [34158](https://www.fedstat.ru/indicator/34158) посеяно яровых, тыс. га, хозяйства всех категорий | `yarovoy-sev-{vsego,zernovye,pshenica,kukuruza,podsolnechnik}-1-iyunya` (раздел 13) | год, дата 1 июня | 2023 | 2026 | все яровые 2026 — 41 947,29 | 1 389 |
| [57788](https://www.fedstat.ru/indicator/57788) платные услуги населению, млн ₽ за месяц (в источнике тыс. ₽) | `platnye-uslugi-mes` и 11 видов `platnye-uslugi-<вид>-mes` (раздел 15) | месяц | 2017-01 | 2026-09 | 1 891 143,29 | 130 751 |
| [62900](https://www.fedstat.ru/indicator/62900) туристические поездки, тыс. с начала года (в источнике млн) | `turpoezdki-s-nachala-goda` (раздел 6) | месяц | 2025-01 | 2026-10 | сентябрь 2026 — 74 446,4 | 1 774 |

Всего ≈145 тыс. строк (≈25 МБ с индексами при ~175 байт на строку `region_monthly_data`).

Особенности источника:
- 62164: измерение территорий — межведомственный ОКАТО 30628 (как у 61699): oid берутся из
  `emiss_social_territories.json` (ключ 61699), названия — общий справочник плюс `TERRITORY_ALIASES` зоны B; Байконур
  пропускается. Вид «Всего» не взят — средняя пенсия всех видов идёт помесячно (61699). «За выслугу лет» не взят: по
  регионам 4 территории, у строки России значения около 950 тыс. — не размер пенсии.
- 34165/34158: оперативные данные «на 1-е число» месяца сезона. В ряд идёт одна дата — последняя в сезоне; урожай 2026
  года появится, когда Росстат опубликует 1 ноября. Вес урожая — при первом учёте, до сушки и очистки, поэтому
  отличается от окончательного валового сбора сборника. У 34158 на 1 апреля встречается заглушка 1 000 000 — отсекается
  `max_value`. Сои и ячменя в оперативных наборах нет (их искал один человек). 40545 (озимые, только
  сельхозорганизации) и 33784 (убранная площадь) не взяты.
- 57788: месяцы и «январь–N» — разные oid периода, берутся только месяцы. Гостиницы не взяты: у позиции два названия
  в разные годы.
- 62900: своё измерение территорий 3301 (oid — `regional/emiss_3301_territories.json`, снято со страницы 09.11.2026;
  три автономных округа названы без области — `aliases`). Значения — с начала года. Месяц разностью не выводится:
  в 2025 году у 34 регионов декабрь меньше ноября, всего 96 отрицательных разностей.

### Туризм по регионам: гостиницы, санатории, турфирмы, турпоток, «Поездки» ЦБ, турналог, реестры (20.11.2026, зона t2)

Реестр — [`app.data.tourism_regional`](../backend/app/data/tourism_regional.py), загрузчик —
[`app.services.tourism_regional_loader`](../backend/app/services/tourism_regional_loader.py), job `tourism_regional`
ежедневно в 08:25 МСК. Слои: `region_data` (год), `region_quarterly_data` (YYYYQ), `region_monthly_data` (YYYYMM).
Раздел 6 «Культура, отдых и туризм»; ИПЦ туристских позиций — раздел 20, автобусы и итог речных перевозок — 16.
Коды новых рядов `tour-*` (72 ряда), продлены с 2025 года три ряда сборника: 6.7.1, 6.7.2, 6.8.1.

| Источник | Ряды | Период | Как берётся |
|---|---|---|---|
| ЕМИСС 31579/31560/31583/31586/31587/31003/31040 | гостиницы и прочие КСР: число, размещённые, места, номера, ночёвки, доходы, затраты | год, 2002–2025 | названиями со страницы набора; снимок 20.11 |
| ЕМИСС 42101/42102/42103/42105 | санатории: доходы, отдыхающие, ночёвки, номера | год, 2002/2003/2005–2025 | то же |
| ЕМИСС 31615, 31591, 31598 | турфирмы по видам; туристы турфирм всего / по России / за рубеж и по 36 странам (≥10 тыс. в 2023–2025 или ≥50 тыс. в любой год с 2004); иностранцы всего и из 7 стран (≥50 тыс. в любой год) | год, 2004–2025 | то же |
| ЕМИСС 62301 | ночёвки в КСР за месяц | 2023-01 — 2026-07 | нарастающий итог → разность |
| ЕМИСС 57788 | платные услуги: гостиницы (две подписи позиции), специализированные КСР | месяц с 2017 | снимок |
| ЕМИСС 62999/63001, 57714 | речные пассажиры (туристские, экскурсионные, все), морские; автобусы | месяц с 2025 / с 2017 | снимок (сетка a3) |
| ЕМИСС 62073/62299/62300/62279/62074/62302/62280, 44040/44042/44041/57731/62159/42106/42104/62199/60944, ИПЦ 31074 (7 позиций) | оперативные КСР и санатории, россияне/иностранцы в КСР, площадь и категории номеров, число и места санаториев, ВДС туриндустрии (62199, млн руб.) и её доля в ВРП (62197), дети в турпоездках, ИПЦ гостиниц/санаториев/экскурсий/поездок | — | **не скачаны** (fedstat 403 с ~16:50 20.11); загрузчик возьмёт сам при доступе: oid ищет по названиям на странице набора, единица страницы сверяется с реестром (другая — набор пропускается) |
| Росстат, `Turpotok_2kv-2026.xlsx` | оценка турпотока: поездки и ночёвки за год (2022–2025) и за квартал (разность «январь–…», до II кв. 2026) | | живой: ссылка `Turpotok_*.xlsx` со страницы rosstat.gov.ru/statistics/turizm (цепочка Минцифры, проверено 20.11); снимок; помесячный лист не берётся (третий «турпоток» рядом с 62900 путал бы) |
| Банк России, `exp/imp_services_reg_YY.xlsx` | «Поездки» по субъектам: экспорт и импорт всего, деловые, личные, туристские услуги | квартал, 2019 — II кв. 2026 | живой: файлы прошлого и текущего года; 2018 — без «Поездок»; колонки года и «январь–июнь» не берутся; ряд из одних нулей не пишется |
| ФНС, 1-НМ (архивы `1nm…reg.zip`, файл 11О, графа 1434.3) | турналог: поступило с начала года; за год | месяц с 2025-01 | живой: три последних архива со страницы отчёта (проверено 20.11 с Mac); снимок; разность месяцев ложная (платят раз в квартал), поэтому ряд «с начала года» |
| Росаккредитация, API реестра | действующие средства размещения (снимок месяца), новые записи за год | с 2023 | живой, ~104 запроса по 500 |
| Минэкономразвития, ЕФРТ (`ev.economy.gov.ru/lk_exp/registry/integ/public/subjects/touroperators` и `/export`) | туроператоры (регион по ОГРН), турагенты (по ИНН) на конец месяца | снимок 2026-11, дальше копится | живой: POST `{}` с браузерным User-Agent; с Mac отвечает только через en0, с боевого не проверено — сбой без алерта, остаётся снимок |
| ЕМИСС 59153, 31258 | число организаций отдыха детей; оборот общепита за месяц | — | не скачаны; 31258 принимает единицу «тысяча/миллион/миллиард рублей» с пересчётом |
| СберИндекс | внутренние туристы, % г/г (приближённо, подписано) | 2019-01 — 2022-04 | снимок; ряд остановлен источником |

Снимок `backend/app/data/regional/tourism_seed.csv.gz` (~112 тыс. точек) собирает
`backend/scripts/build_tourism_regional_seed.py` из `.artifacts/tourism-2026-11-20` и файлов ЦБ; job пишет его
«только недостающее» (ON CONFLICT DO NOTHING), живой ответ — upsert с охраной значения. Территории — по названию
(нормализация «г.Санкт-Петербург», «Централный ФО», «город Москва », «Марий-Эл», ОКАТО-номер в начале строки ЦБ;
«…ФТ «Сириус»» — запасная строка края). Россия: «РФ» до 2022, «без учета новых субъектов» с 2023.

**Доработка 20.11.2026 (сборщик c4, `.artifacts/tourism-2026-11-20/c4`).** Тот же реестр и снимок (264 тыс. точек):

- курортный сбор 2018–2024 (`tour-kurortnyy-sbor`) — Казначейство, ф. 0503317, КБК 1 15 08000 02; поступления 2025
  года (недоимка) не берутся; «Сириус» — не субъект, в ряды не входит;
- «Туризм в России» 2024, R5t1–R5t4 по субъектам 2018–2023: гостиницы (число, номера, номера высшей категории —
  закрывает 57731, места), хостелы, санаторно-курортные организации (число и места — закрывает 42106/42104),
  организации отдыха;
- сборники Росстата через tochno.st (CC BY 4.0, источник в карточке — Росстат): платные услуги гостиниц, санаториев,
  баз отдыха, туристские (объём и индекс физобъёма), ИПЦ гостиниц/санаториев/внутреннего и зарубежного туризма
  (декабрь к декабрю), число санаториев/детских санаториев/профилакториев и организаций отдыха (2010–2024), рестораны
  и столовые, прибыль ресторанов, инвестиции «гостиницы и рестораны»;
- средние цены туруслуг `sred_potreb_cen_*.xlsx` (2022-01 — 2026-09, по России, округам и субъектам): продлевают ряды
  `ceni-*` реестра цен ЕМИСС 31448 только недостающими месяцами; живой файл — ежедневно; города (~280) не берутся —
  страниц городов на сайте нет; новые позиции — купе и плацкарт нефирменных поездов (`tour-cena-*`);
- загрузка мест (`tour-ksr-zagruzka-mest`) — **расчёт сайта** по данным Росстата (ночёвки / (места × 365)),
  источник подписан «расчёт по данным Росстата»;
- не взяты: турпоток 14 регионов из СМИ (несопоставимо), «Регионы России» 2023–2025 (ряды на сайте уже до 2024 года),
  работники КСР 61968 (в сборнике только по России).

**Добор g2 (20.11.2026).** `tour-turpotok-ocenka-regiona` — турпоток **по оценке самого региона** (18 регионов,
2010–2025; Москва — открытые данные Комитета по туризму 62056, 26,5 млн в 2025). У региона одна мера (та, которой
больше лет; Ставрополье без «9 млн по операторам связи»), из двух цифр за год — не из пересказа СМИ; годы перехода на
оценку Росстата и обратно — «разрывы» (Ставрополье 2023, Карелия 2024/2025). Методика каждого региона —
`app/data/regional/tourism_region_methods.json` — публичный текст ru/en, написан вручную по `g2/regions/methods.csv` одной схемой «кого считают / как считают / оговорка / годы разрыва»; сборщик снимка только сверяет, что найденные по данным разрывы отмечены. Выводится в «Откуда данные» карточки.
Рейтинга регионов и места среди регионов у ряда нет (`NOT_RANKED`): методики несопоставимы, с рядом Росстата не
смешивается. Реестр размещения Москвы 2018–2025 — `tour-moskva-reestr-*` (последняя дата обновления в году).
Петербург не взят: реестр гостиниц застыл на 2021 году, динамики нет.

**Круг наблюдателей (20.11.2026).** Коды `tour-avtobusy-passazhiry` → `avtobusy-passazhiry-mes`, `tour-obshchepit-*` →
`obshchepit-*` (раздел 15): не туризм; миграция `20261120_region_data_updated` переименовывает на месте и добавляет
`region_indicators.data_updated_at` (дата последнего изменения данных ряда, пишет загрузчик туризма). API регионов
(`/api/v1/regions/{slug}/i/{code}`, `…/monthly`, квартальный ответ того же адреса): `indicator.source`
{name, url, about, dataset, calculated, approximate, ranked, region_method}, `indicator.ranked`,
`indicator.data_updated_at`. Рейтинг (`/api/v1/regions/heatmap/{code}`): `indicator.source`, `indicator.ranked`;
у налога и курортного сбора `values[].status` = `not_introduced` | `zero_year` | `no_receipts_yet`, `missing[].status` =
`not_introduced` | `no_data`; у нулей и от нуля `prev` не отдаётся (нет «−100 %»). Загрузка мест и оценки регионов —
без места среди регионов (`NOT_RANKED`). Адреса источников — набор ЕМИСС или файл/публикация (`source_url`).

**Добор 21.11.2026 (a1 докачала ЕМИСС, g1 через стенд).** Снимок: 362 тыс. точек. В него вошли наборы, которые ждали
fedstat: 44040/44042/44041, 57731 (ЕМИСС главнее сборника), 42106/42104, 62197/62199, 59153 (2018–2019), месячные
62073/62074/62279/62280/62299/62300/62302; 31258 по субъектам — только год, продлевает 15.7 на 2025 (`periods="dec"`).
Сняты (в наборе только Россия; на стенде скрываются `RETIRED`): 60944, 62159, 31258 помесячно. Новое из g1 (длинные
выгрузки, `g1_points`): оборот гостиниц, турагентств, общепита (57710, месяц с 2017), работники гостиниц и
турагентств (57848), инвестиции в гостиницы и санатории (59084, год); реестр МСП ФНС (`msp_points`, ОКВЭД 55/56/79 по
основному виду, последний снимок года, регион по коду ФНС, старые коды округов прибавляются к краю). ИПЦ 31074 — 35
позиций с точными подписями из выгрузки; снимка нет: историю с 2002 года берёт живая загрузка (снимок остановил бы её
на годе снимка). Средние цены 31448 продлевает существующий загрузчик цен (`ceni-*`). Общепит и обеды в ресторанах —
коды без `tour-`, раздел 15/20.
