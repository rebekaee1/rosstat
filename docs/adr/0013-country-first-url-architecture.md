# ADR-0013 — Страна как первый сегмент URL (path-cut, затем языковой сплит `ru.` + apex)

- **Status:** Proposed (проектирование 2026-08-16; реализация отдельным заходом)
- **Date:** 2026-08-16
- **Last verified:** 2026-09-03 (apex = EN, `ru.` = RU; geo людям из РФ, ботов не редиректим)
- **Part of:** [`AGENTS.md`](../../AGENTS.md), [`CONTEXT.md`](../../CONTEXT.md), [`ADR-0003`](0003-seo-single-source-server-rendered.md), [`ADR-0008`](0008-regional-bounded-context.md), [`ADR-0011`](0011-world-eurostat-data-plane.md)
- **Backlog:** [`docs/backlog.md`](../backlog.md) — раздел «Карта миграции URL (ADR-0013)» + решения звонка 14 (Р-1…Р-3)

---

## Контекст

Публичная адресация платформы сейчас смешивает три модели:

1. **Россия без карточки страны** — макроразмазано по `/`, `/category/*`, `/indicator/*`, `/today/*`, `/calendar/*`.
2. **Регионы как верхнеуровневый раздел** — `/regions`, `/region/*`, `/region-rating/*`, `/region-vs/*` (ADR-0008, ~40k URL).
3. **Мир как префиксный раздел** — `/world`, `/world/{slug}`, `/world/{slug}/{code}`, `/world/rating/{concept}`.

Владелец (звонок 14 + уточнения 2026-08-16) зафиксировал:

- страна = **первый** сегмент для всех стран (`/russia/...`, `/germany/...`);
- регионы России живут **внутри** карточки России, не отдельным верхним разделом;
- сначала path-cut на текущем `forecasteconomy.com`, затем языковой сплит на
  **поддоменах того же gTLD** (не смена ccTLD):
  `ru.forecasteconomy.com` = русский UI/тексты,
  `forecasteconomy.com` (apex) = английский UI/тексты,
  пути path-identical;
- покупка `forecasteconomy.ru` / host-wide 301 `.com`→`.ru` **не** являются
  целевой схемой (см. Subsequent additions 2026-08-16 вечер).

Смену путей и языковых хостов нельзя совмещать в один день: при просадке
индексации невозможно атрибутировать причину. Языковой сплит — это **не**
«Переезд сайта» (оба хоста остаются живыми с разным языком + hreflang).

## Решение

### 1. Единое правило адресации

```
/{country}                         карточка страны
/{country}/…                       разделы этой страны (если есть)
/world                             хаб карты и межстрановых рейтингов
/                                  витрина платформы (не карточка России)
```

`{country}` — латинский slug в стиле уже существующих `world_countries.slug`
(`germany`, `united-states`, `czechia`). Для России канон — **`russia`**, не `rossiya`
(единообразие с англоязычными слагами; коллизии с корневыми путями нет —
`russia` отсутствует в `world_countries`, пересечение 47 слагов с `STATIC_PAGES`
и зарезервированными корнями пусто).

### 2. Россия: карточка + префикс всех российских семейств

| Смысл | Новый шаблон |
|-------|----------------|
| Карточка страны | `/russia` |
| Категории | `/russia/category/{slug}` |
| Макроиндикатор | `/russia/indicator/{code}` |
| Годовой лендинг | `/russia/indicator/{code}/{year}` |
| «Сегодня» | `/russia/today`, `/russia/today/{code}` |
| Календарь | `/russia/calendar`, `/russia/calendar/{yyyy}/{mm}` |
| Демография (хаб) | `/russia/demographics` |
| Регионы — хаб / карта | `/russia/regions`, `/russia/regions/map/{code}` |
| Профиль региона | `/russia/region/{slug}` |
| Показатель региона | `/russia/region/{slug}/{code}` |
| Рейтинг регионов | `/russia/region-rating/{code}` |
| Пара регионов | `/russia/region-vs/{a}-vs-{b}` |

Осознанный выбор **префиксной** схемы (`/russia/region/…`), а не глубокой
перекладки в `/russia/regions/{slug}`: один регулярный слой 301, меньше риска
ошибиться в OG/хлебных крошках, регионы всё равно иерархически под `/russia`.
Глубокий rename «region → regions/{slug}» — отдельный проход **после** стабилизации,
не в том же релизе.

### 3. Другие страны (мир)

| Смысл | Новый шаблон |
|-------|----------------|
| Карточка | `/{slug}` (было `/world/{slug}`) |
| Показатель | `/{slug}/{code}` (было `/world/{slug}/{code}`) |
| Рейтинг стран (кросс) | `/world/rating/{concept}` — **остаётся** под `/world` |
| Хаб | `/world` |

У страны без регионов просто нет поддерева `regions` / `region` / `region-rating` /
`region-vs` — 404, без спец-веток в роутере. Наличие регионального контура —
флаг возможностей страны (`has_regions`), сейчас только у `russia`.

Асимметрия ` /russia/indicator/{code}` vs `/{slug}/{code}` осознанна: у России
курируемый каталог с категориями и view-mode; у мира — плоский список кодов
провайдера (в т.ч. с точками). Унификация в TE-стиль `/russia/cpi` возможна
позже, не блокирует этап 1.

### 4. Главная `/`

**Решение: `/` остаётся витриной платформы.** Карточка России — `/russia`.

| Вариант | Плюсы | Минусы |
|---------|-------|--------|
| A. `/` = платформа, `/russia` = страна (**принято**) | Сохраняет бренд и вход в мир; совпадает с H-1/H-2 звонка 14; не сжигает вес главной на «только РФ» | Нужна новая страница `/russia` и перенос «Показатели России» с главной |
| B. `/` = карточка России | Короткий URL ядра | Ломает позиционирование «страны и мир»; главный интент Яндекса размажется; откат болезненнее |

### 5. Этапы миграции (жёстко)

1. **Path-cut на `forecasteconomy.com`** — все 301 внутри домена, новые canonical /
   sitemap / IndexNow / переобход. Мир можно выкатить в том же или следующем
   микрорелизе (URL мира на проде ещё не проиндексированы — звонок 14).
2. **Стабилизация 3–4 недели** — только мониторинг индексации; не трогать
   языковые хосты.
3. **Языковой сплит (после появления EN-волны):** `ru.forecasteconomy.com` =
   ru, apex `.com` = en; path-identical; взаимный hreflang; canonical на своём
   хосте. Пока EN нет — geo «иностранцы → apex» **не** включать (иначе два
   русских канона). Детали — Subsequent additions + `docs/backlog.md` §F.

### 6. Редиректы — один hop, переиспользовать `legacy_redirects.py`

- **Массовые префиксы** — `rewrite … permanent` / `return 301` в nginx
  (или тонкий префиксный слой перед SSR), шаблоны вида
  `^/indicator/(.*) → /russia/indicator/$1`.
- **Семантические** (легаси-коды, unlisted siblings, старые слаги регионов,
  world frequency siblings) — по-прежнему `backend/app/data/legacy_redirects.py`
  + `_permanent_redirect` в `seo_pages.py`.
- **Инвариант:** любой резолвер обязан возвращать **уже финальный** путь
  (`/russia/indicator/cpi`, не `/indicator/cpi`). Иначе цепочка
  legacy → старый канон → новый канон = потеря веса.
  При path-cut обновить строки в `LEGACY_INDICATOR_REDIRECTS`,
  `_BESPOKE_UNLISTED_CANONICAL`, `_generic_sibling_index`,
  `resolve_world_frequency_sibling`, `resolve_world_unlisted_indicator`.

### 7. Синхронный контур (иначе робот видит противоречие)

В одном релизе path-cut: React Router, nginx SSR locations, `site_urls.py`,
все `seo_*.py` canonical/OG/JSON-LD/хлебные крошки, `PAGE_META` links,
внутренняя перелинковка (navbar/footer/home), IndexNow full ping,
сброс очереди `webmaster_recrawl` на новые пути, RSS `feed.xml`.

OG public paths предпочтительно зеркалят иерархию
(`/og/russia/{code}.png`, `/og/{slug}/{code}.png`); старые `/og/…` —
301 на новые.

## Последствия

- Появляется first-class карточка `/russia` и единый country-router.
- ~44,7k российских URL и ~34,8k мировых меняют путь (цифры — backlog).
- Data planes (макро / регионы ADR-0008 / world ADR-0011) **не** сливаются:
  меняется только публичная адресация и навигация.
- Guard-тест: `world_countries.slug ∪ {russia}` ∩ reserved roots = ∅.

## Subsequent additions (after acceptance)

### 2026-08-16 — решения владельца при реализации path-cut

1. **Главная `/` остаётся витриной платформы.** Карточка России — `/russia`.
   Ничего в смысле «главная = Россия» не меняем.
2. **Единая схема для всех стран, включая мир:** тип сущности назван явно.
   Показатели мира тоже под `/{country}/indicator/{code}`, а не плоский
   `/{country}/{code}`. Оба path-cut (Россия + мир) — в одном релизе.
3. **Форма адреса (канон):**

```
/{country}
/{country}/indicator/{code}[/{year}]
/{country}/category/{slug}
/russia/region[/{slug}[/{code}]]
/russia/region/map/{code}
/russia/region-rating/{code}
/russia/region-vs/{a}-vs-{b}
/russia/today[/{code}]  /russia/calendar…  /russia/demographics
/world  /world/rating/{concept}
/compare  /calculator*
```

Почему явный `/indicator/` и `/region/`: показатели и регионы не делят
пространство имён (коллизия кода показателя со слагом региона при 489
региональных слагах — вопрос времени). У Германии те же сегменты, просто
нет регионального поддерева.

**Реализация:** `app.services.site_paths` + `frontend/src/lib/sitePaths.js`;
guard `test_site_path_collisions.py`; `legacy_redirects` целит финальные пути;
nginx mass-301 + новые SSR locations; sitemap через `site_urls`.
Языковой сплит `ru.` ↔ apex — отдельный этап после стабилизации path-cut
и появления EN-волны (`docs/backlog.md` §F).

### 2026-08-16 (день) — черновик «ccTLD `.ru`» (снят вечером)

Дневной черновик предполагал покупку `forecasteconomy.ru`, host-wide 301
`.com`→`.ru` и «Переезд сайта». **Снят** уточнением владельца тем же вечером:
целевая схема — языковой сплит на поддомене, не смена ccTLD. Текст ниже
заменяет дневной чеклист.

### 2026-08-16 (вечер) — `ru.forecasteconomy.com` + apex, geo, i18n

Уточнение владельца к п. 5 и к Р-2/Р-3 звонка 14. Полный чеклист —
`docs/backlog.md` §F «Поддомен `ru.` + geo + i18n».

1. **Целевая схема (не ccTLD):**
   - `ru.forecasteconomy.com` — русский UI и русские тексты (то, что сейчас).
   - `forecasteconomy.com` (apex) — английский UI и английские тексты.
   - Пути path-identical после path-cut (`/russia/indicator/cpi`, `/germany`, …).
   - Canonical — на **своём** хосте (не кросс-канон всех страниц на один хост).
   - hreflang: `ru` ↔ `en`; **`x-default` → apex** (международный/нецелевой
     вход; Google/Яндекс: x-default для версии без жёсткой локали /
     автовыбора — [Yandex locale-pages](https://yandex.ru/support/webmaster/ru/yandex-indexing/locale-pages),
     [Google localized versions](https://developers.google.com/search/docs/specialty/international/localized-versions)).

2. **Порядок фаз (жёстко):**
   (a) path-cut на текущем apex `.com` (русский, как сейчас);
   (b) DNS+Caddy для `ru.` (TLS), пока контент тот же — **не** объявлять оба
   хоста конкурирующими канонами в поиске (см. §F: парковка / один канон);
   (c) английский на apex — только когда есть что отдавать (первая волна —
   хабы/навбар/страны/рейтинги/compare/about/калькуляторы/топ РФ-карточек;
   ~40k регионов EN — не в первой волне);
   (d) geo для людей + hreflang — когда обе языковые версии живые.
   **Пока EN нет — geo «иностранцы → apex» не включать** (два русских канона).

3. **Geo для людей, не для ботов.** Страна по IP на краю (переиспользовать
   DB-IP Lite / `services/geoip.py`, ADR-0010; не MaxMind). Accept-Language
   один не использовать. Россия → `ru.`; остальные → apex. Поисковые UA
   (YandexBot, Googlebot, Bingbot) и свои служебные (IndexNow и т.п.) —
   **всегда** запрошенный хост, без geo-редиректа. Cookie/query «остаться
   на этой версии»; прямой заход на `ru.` из-за рубежа не уводить силой.
   Не редиректить `/api/*`, `/assets/*`, `/og/*`, `/sitemap*`, `/feed.xml`,
   `/embed/*`. Яндекс: IP-редирект языковых версий путает выдачу —
   предпочтительны переключатель + обе версии `200 OK`
   ([managing-redirects §region](https://yandex.ru/support/webmaster/ru/robot-workings/managing-redirects)).
   Google: отдельные URL + hreflang лучше locale-adaptive only по IP
   ([locale-adaptive](https://developers.google.com/search/docs/specialty/international/locale-adaptive-pages));
   разный контент боту и человеку = риск cloaking
   ([spam policies](https://developers.google.com/search/docs/essentials/spam-policies#cloaking)).

4. **DNS:** не покупать `.ru` для этой цели. В панели `forecasteconomy.com`:
   A-имя `ru` → `201.51.11.170`; Caddy — второй host (или тот же блок с двумя
   именами) + TLS; `www` как сейчас → apex. Это **не** «Переезд сайта» /
   Change of Address на весь домен.

5. **i18n:** один фронт, словари, переключатель языка; серверные тексты
   (`seo_content`, `indicator_seo`, SSR) — en-слой. Не автопереводить 40k
   региональных. Поддомен vs `/en/` — выбран поддомен (владелец).

6. **ccTLD позже (опционально):** `ru.forecasteconomy.com` слабее сигнала
   «Россия» для Яндекса, чем `forecasteconomy.ru` в зоне `.ru`. Позже можно
   повесить `.ru` как алиас русской витрины (тот же контент / 301 на `ru.`
   или зеркало с единым каноном), **без** отказа от `ru.` сейчас. Не
   блокирует текущий план.

7. **SEO / meta (правило одного языка):** страница на хосте говорит на одном
   языке. `ru.` — русские title/description/h1/`og:locale=ru_RU`; apex —
   английские. Self-canonical на своём хосте; hreflang не подменяет
   canonical (Google: при hreflang canonical в том же языке —
   [consolidate duplicate URLs](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)).
   Яндекс: HTML alternate / hreflang; Sitemap для языковых версий больше
   не поддерживается
   ([locale-pages](https://yandex.ru/support/webmaster/ru/yandex-indexing/locale-pages)).
   Страницы без EN-пары — без `hreflang="en"` на 404 и вне EN-sitemap.
   Вебмастер: `ru.` регион «Россия»; apex — не «Россия» (при необходимости —
   без региональной привязки). Полный чеклист — `docs/backlog.md` §F.8.

### 2026-09-03 — исходный сплит включён: apex EN, `ru.` RU, geo людям

Владелец подтвердил исходный план ADR-0013 §F, не инверсию Р-Б
(apex не остаётся русским, отдельный `en.` не нужен).

- `forecasteconomy.com` = английский канон (`x-default`).
- `ru.forecasteconomy.com` = русский канон; флажок «Русский» ведёт сюда
  (path-identical, cookie `fe_locale_pref=ru` на `.forecasteconomy.com`).
- Людей с IP России/СНГ с apex уводим на `ru.` (`RUSTATS_GEO_LOCALE_REDIRECT_ENABLED`).
  Явный cookie `en` / `stay-en` важнее гео. Accept-Language по-прежнему
  не редиректит (тот же VPN-баг 2026-08-31).
- Поисковые и ИИ-краулеры остаются на запрошенном хосте. Индексация:
  hreflang ru/en/x-default, sitemap на оба хоста, регион Вебмастера
  «Россия» на свойстве `ru.` (кабинет — снаружи репозитория).
- Cutover-флаги на проде: `RUSTATS_APEX_LOCALE_EN=true`, geo true.
  Р-Б (apex=RU, EN на `en.`) в код не принимается.

### 2026-08-31 — geo-редирект снят, язык = хост

Решение владельца: IP/VPN и `Accept-Language` не выбирают язык. Сценарий
«с VPN — английский, без VPN — русский, хотя язык браузера английский»
был прямым следствием `_geo_locale_redirect` в `main.py`. Функция стала
no-op; middleware её не вызывает. Cookie `fe_locale_pref` остаётся памятью
явного выбора переключателя (`locale_pref` query → Set-Cookie на
`.forecasteconomy.com`), но не источником редиректа на другой хост.
Флаги `RUSTATS_GEO_LOCALE_REDIRECT_ENABLED` /
`RUSTATS_BROWSER_LANG_REDIRECT_ENABLED` в env игнорируются (оставлены,
чтобы старые окружения не падали). Боты и служебные маршруты по-прежнему
отвечают на запрошенном хосте.

IndexNow после ETL — карточки + годовые landing текущего/прошлого года;
полная подача — очередь Redis (`enqueue_paths` / `indexnow_drain_job`)
по статическим секциям `site_urls`, отдельно на apex и `ru.` после cutover.
Google Search Console (Domain property, sitemap shards, Request Indexing
хабов) — руками владельца; Indexing API не строим.

### 2026-09-03 — один канон до cutover (Р-А) и Proposed инверсия сплита (Р-Б)

**Р-А (сделано в коде).** До `apex_locale_en` `ru.forecasteconomy.com` отдаёт
`<link rel=canonical>` на apex, пустой `<sitemapindex>`, robots без `Host:`.
Зеркало `ru.` не кормит Вебмастер sitemap'ом — иначе 22k холостых запросов
робота в день. При cutover переключается одним флагом.

**Р-Б (отклонено 2026-09-03).** Владелец подтвердил исходный сплит:
apex = EN, русский канон на `ru.forecasteconomy.com`. Инверсия
«apex остаётся RU, EN на `en.`» в код не входит.
