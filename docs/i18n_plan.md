# План мультиязычности (i18n) — `/ru` префикс и подготовка к `/en`

**Источник:** правка `missed_004` (видео НА правки 3). Архитектурная задача, не реализована в текущей итерации.

## Цель

Сделать сайт пригодным для добавления англоязычной версии (`/en/...`) с минимальными последствиями для существующих SEO-сигналов и canonical-URL.

## Решения

1. **Prefix-based роутинг.** Все маршруты переводятся под префикс языка:
   - `/` → `/ru/`
   - `/category/prices` → `/ru/category/prices`
   - `/indicator/cpi` → `/ru/indicator/cpi`
   - `/about` → `/ru/about`
   - и т.д.
2. **301-редирект `/` → `/ru/`** на уровне Caddy/nginx или React Router (`Navigate to="/ru/" replace`).
3. **Canonical** для `/ru/*` остаётся в backend OG endpoint (`/api/v1/og/...`) — добавить параметр lang.
4. **Sitemap** делится на 2 секции: `https://forecasteconomy.com/sitemap-ru.xml` и `sitemap-en.xml`.
5. **Hreflang.** В `<head>` каждой страницы:
   ```html
   <link rel="alternate" hreflang="ru" href="https://forecasteconomy.com/ru/indicator/cpi" />
   <link rel="alternate" hreflang="en" href="https://forecasteconomy.com/en/indicator/cpi" />
   <link rel="alternate" hreflang="x-default" href="https://forecasteconomy.com/" />
   ```
6. **Контент.**
   - Тексты в `frontend/src/lib/categories.js`, `useMeta.js`, `track.js` (event labels), компоненты — через i18n библиотеку (`react-i18next`).
   - Имена индикаторов: `Indicator.name_en` (уже есть в БД); description_en/methodology_en — добавить.
   - Все `*-yoy/qoq` подписи — переводимы.
7. **Yandex Metrika.** Параметр `lang` добавляется в каждое событие (через `track.js withCategory`-style helper).

## Этапы

### Этап 0 — подготовка (текущая итерация — ЭТО доку.)
- [x] Документ заведён.
- [ ] Решено, какой набор страниц мигрирует первым: главная, About, 1 категория, 3 топ-индикатора (cpi, usd-rub, unemployment).

### Этап 1 — инфраструктура (отдельная задача)
- [ ] `react-i18next` + `i18next-browser-languagedetector` установлены, конфиг.
- [ ] `frontend/src/locales/ru/*.json`, `frontend/src/locales/en/*.json` структура.
- [ ] `LangProvider` оборачивает App, по умолчанию `ru`.
- [ ] React Router добавляет `:lang` сегмент: `/:lang/category/:slug`, `/:lang/indicator/:code`.
- [ ] Все hardcoded русские строки → `t('key')`.

### Этап 2 — backend поддержка
- [ ] `Indicator.description_en`, `Indicator.methodology_en` колонки.
- [ ] Миграция Alembic.
- [ ] Заполнение для топ-30 индикаторов.
- [ ] OG endpoint принимает `?lang=en`.

### Этап 3 — SEO-сигналы
- [ ] Sitemap делится.
- [ ] Hreflang в `index.html` (через React Helmet или прямой инжект).
- [ ] Yandex Webmaster подтверждение английского сегмента.
- [ ] robots.txt не блокирует `/en/`.

### Этап 4 — публикация
- [ ] 301 `/` → `/ru/` при условии Accept-Language: ru-* остаётся `/ru/`, иначе `/en/`.
- [ ] LocaleSwitcher в Navbar (флаг + дропдаун).

## Не делаем сейчас

- Перевод значений индикаторов в долларах/евро (это отдельный feature — currency switcher).
- Локализация дат/чисел через Intl.NumberFormat / Intl.DateTimeFormat — оценить отдельно.

## Open questions

- **URL для главной:** `/` или `/ru/` для русскоязычного контента? Рекомендация: `/` редиректит на `/ru/`, `/ru/` — каноничный.
- **Мобильное приложение и embeds:** embed-виджеты (`/widgets`) тоже под язык?

---

## История правок документа

- 2026-04-27 — создан как ответ на правку `missed_004` НА правки 3.
