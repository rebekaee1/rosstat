# Embeddable Widgets — архитектурное исследование

**Проект:** Forecast Economy (forecasteconomy.com)
**Дата:** 2026-04-09
**Автор:** AI Research

---

## 1. Конкурентный анализ: как встраиваются экономические данные

### 1.1 TradingEconomics

**URL:** `tradingeconomics.com/embed/?s=russiagdpgro`

**Механизм:** iframe на статичный PNG-чарт (Cloudfront CDN: `d3fy651gv2fhd3.cloudfront.net/charts/embed.png?s=russiagdpgro`). Кликабельная картинка ведёт на основной сайт. Нет интерактивности.

**Виджеты (tradingeconomics.com/api/widgets.aspx):**
- Markets Overview — таблица индексов
- Market Charts — интерактивный iframe
- Economic Charts — iframe с JS
- Calendar — таблица событий
- Tree Map — heatmap
- News — лента

**Модель:** платный API; embed бесплатен с attribution «Trading Economics».

**Код вставки:** `<iframe src="//tradingeconomics.com/embed/..." width="600" height="400"></iframe>` + `<a>` attribution.

**Вывод:** простейшая реализация — серверный PNG + ссылка. Интерактивные виджеты только через API-подписку.

---

### 1.2 TradingView — индустриальный стандарт

**URL:** `tradingview.com/widget-docs/`

**Два формата (2025+):**

**A. Web Components (рекомендуемый):**
```html
<script type="module" src="https://www.tradingview-widget.com/w/en/tv-widget.js"></script>
<tv-mini-chart symbol="MOEX:USDRUB" width="100%" height="300"></tv-mini-chart>
```
- Shadow DOM — изоляция стилей
- Shared loader — один `<script>` на страницу, все виджеты переиспользуют бандл
- CSS-токены для кастомизации (`--tv-color-*`)
- Поддержка dynamic attributes (реактивные обновления)

**B. iframe (legacy):**
```html
<div class="tradingview-widget-container">
  <script src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js">
    { "symbol": "MOEX:USDRUB", "width": "100%", "height": 300 }
  </script>
</div>
```
Script создаёт iframe программно. JSON-конфигурация в теле `<script>`.

**Конструктор виджетов:** `tradingview.com/widget/` — best-in-class UX:
1. Выбор типа виджета (mini chart, overview, ticker tape, calendar, heatmap)
2. Live preview справа
3. Кнопка «Copy embed code»
4. Настройки: символ, тема (light/dark), цвета, размер, locale

**Бандл:** ~50-80 KB gzip для mini-chart (Web Component), остальное подгружается по требованию.

**Вывод:** эталон. Web Component подход — будущее. Но для нашего масштаба (MVP) это overengineering.

---

### 1.3 FRED (Federal Reserve Economic Data)

**URL:** `fred.stlouisfed.org`

**Механизм:** чистый iframe.
```html
<iframe src="//fred.stlouisfed.org/graph/graph-landing.php?g=j37b&width=670&height=475"
  scrolling="no" frameborder="0"
  style="overflow:hidden; width:670px; height:525px;"
  allowTransparency="true" loading="lazy">
</iframe>
```
Плюс обязательный JS для responsive:
```html
<script src="https://fred.stlouisfed.org/graph/js/embed.js"></script>
```

**Виджеты:**
- Полный интерактивный график (zoom, hover, tooltips)
- «At a Glance» виджет — до 10 серий в компактном формате
- Конфигуратор: `fred.stlouisfed.org/fred-glance-widget/configure.html`

**Responsive:** обёртка `<div class="embed-container">` + width/height в src URL.

**Вывод:** самый близкий аналог к нашему случаю. Государственные экономические данные, бесплатно, iframe-подход, минимальная сложность.

---

### 1.4 World Bank

**Механизм:** iframe с интерактивным графиком. Кнопка «Share» на каждой странице данных. Автообновление при появлении новых данных.

Дополнительно: открытый API `api.worldbank.org/v2/` позволяет строить графики любой библиотекой.

---

### 1.5 Google Finance

**Статус:** embed функциональность **deprecated с ~2012**. Redirects на google.com/finance, виджеты не работают. Не рассматриваем.

---

## 2. Три архитектурных подхода

### 2.A. iframe-подход (наш React рендерит страницу `/embed/:code`)

**Как работает:**
1. Новый маршрут: `https://forecasteconomy.com/embed/cpi?theme=light&height=400&period=5y`
2. React рендерит **только график** — без Navbar, Footer, NoiseOverlay
3. Внешний сайт вставляет `<iframe src="...">`
4. Никакого нового бандла — тот же SPA

**Параметры query string:**
| Параметр | Значения | Default |
|----------|---------|---------|
| `theme` | `light`, `dark` | `light` |
| `height` | число (px) | `400` |
| `period` | `1y`, `3y`, `5y`, `10y`, `all` | `5y` |
| `showTitle` | `true`, `false` | `true` |
| `showForecast` | `true`, `false` | `false` |
| `showAttribution` | `true`, `false` | `true` |
| `interactive` | `true`, `false` | `true` |

**Текущий стек загружает:**
| Чанк | gzip |
|-------|------|
| `charts` (Recharts) | 105.58 KB |
| `vendor` (React+Router) | 14.34 KB |
| `query` (React Query+Axios) | 27.38 KB |
| `animation` (GSAP) | 27.41 KB |
| `index` (app code) | 68.27 KB |
| CSS | 7.80 KB |
| **Итого** | **~250 KB gzip** |

**Оптимизация:** для embed-маршрута не нужны Router, GSAP-анимации, xlsx, большая часть app code. Но при текущем SPA-подходе загрузится весь бандл.

**CORS/Security — КРИТИЧНО:**
- Текущий `X-Frame-Options: SAMEORIGIN` (и в Caddy, и в nginx) **блокирует** iframe на чужих сайтах
- CSP `frame-ancestors 'self'` аналогично блокирует
- **Решение:** для маршрутов `/embed/*` — убрать `X-Frame-Options`, установить `Content-Security-Policy: frame-ancestors *`
- Основной сайт остаётся с `SAMEORIGIN`

**Плюсы:**
- Минимум работы: новый React-компонент + маршрут в nginx
- Полная интерактивность (zoom, pan, tooltips)
- Тот же код, те же данные
- SSR не нужен — iframe = отдельный документ

**Минусы:**
- 250 KB — тяжело для embed
- Загружает весь SPA, а показывает 5% UI
- Время загрузки: ~1-2 сек на быстром соединении
- Каждый embed = полная React-гидрация

**Трудозатраты: 1-2 дня.**

---

### 2.B. Отдельный lightweight бандл (embed.js)

**Как работает:**
1. Отдельный Vite entry point: `frontend/embed.html` + `frontend/src/embed/main.jsx`
2. Минимальный бандл: **только** Recharts (или Chart.ts) + компонент графика
3. Без React Router, без GSAP, без React Query (прямой fetch)
4. Два варианта использования:

**Вариант A — script tag:**
```html
<div id="fe-embed-cpi" data-code="cpi" data-height="300" data-theme="light"></div>
<script src="https://forecasteconomy.com/embed.js" async></script>
```
Script находит все `[id^=fe-embed]`, создаёт React root в каждом.

**Вариант B — iframe на embed.html:**
```html
<iframe src="https://forecasteconomy.com/embed.html?code=cpi&height=300"></iframe>
```

**Оценка размера бандла:**

| Библиотека | gzip | Интерактивность |
|------------|------|-----------------|
| Recharts (только Area+XAxis+YAxis+Tooltip) | ~80-100 KB | Полная |
| Chart.ts | ~15 KB | Хорошая |
| Vanilla SVG (sparkline) | ~3-5 KB | Минимальная |

С tree-shaking Recharts v3 можно получить ~80 KB. С Chart.ts — ~15 KB. Для sparkline-виджетов — vanilla SVG за 3 KB.

**Плюсы:**
- Контролируемый размер бандла
- Нет лишнего кода
- Script-tag вставка проще для пользователя, чем iframe
- CDN + immutable hash = агрессивное кэширование

**Минусы:**
- Два entry point в Vite (поддержка)
- CSP на хост-сайтах может блокировать внешние скрипты
- Shadow DOM не из коробки — конфликты стилей
- Сложнее, чем iframe

**Трудозатраты: 3-5 дней.**

---

### 2.C. Серверный SVG/PNG snapshot

**Как работает:**
1. Backend эндпоинт: `GET /api/v1/chart/cpi.svg?period=5y&width=800&height=400`
2. Python генерирует SVG через matplotlib (или plotly, или hand-crafted SVG)
3. Внешний сайт: `<img src="https://forecasteconomy.com/api/v1/chart/cpi.svg">`

**Варианты генерации:**

| Инструмент | Качество | Размер SVG | Зависимости |
|------------|----------|------------|-------------|
| matplotlib | Среднее (академический стиль) | 50-200 KB | matplotlib ~30MB |
| plotly (kaleido) | Хорошее | 80-300 KB | kaleido ~80MB |
| Hand-crafted SVG (Jinja2 template) | Контролируемое | 5-20 KB | 0 |

**Рекомендация:** hand-crafted SVG через Jinja2 template. Полный контроль над стилем, минимальные зависимости, результат 5-20 KB.

```python
@router.get("/chart/{code}.svg")
async def chart_svg(
    code: str,
    period: str = "5y",
    width: int = 800,
    height: int = 400,
    theme: str = "light",
    db: AsyncSession = Depends(get_db),
):
    # Получить данные
    data = await get_data_points(code, period, db)
    # Рендерить SVG из Jinja2 шаблона
    svg = render_chart_svg(data, width, height, theme)
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})
```

**Плюсы:**
- 0 JS на стороне клиента
- Работает в email, Notion, Markdown, Wikipedia
- Мгновенная загрузка (SVG кэшируется CDN)
- Нет проблем с CSP, X-Frame-Options, CORS
- SEO: поисковики индексируют `<img>` тег

**Минусы:**
- Нет интерактивности (нет зума, панорамы, тултипов)
- Нужно поддерживать SVG-шаблон отдельно от React-графика
- Нагрузка на backend при генерации
- Кэширование обязательно (TTL 1-6 часов)

**Трудозатраты: 2-3 дня.**

---

## 3. Каталог виджетов

### 3.1 Полный интерактивный график
- Zoom, pan, tooltips
- Прогноз (опционально)
- Attribution внизу
- **Подход:** iframe (2.A) или lightweight бандл (2.B)
- **Приоритет:** P0 (MVP)

### 3.2 Sparkline (мини-линия)
- Без осей, без тултипов
- Только тренд за последние 12 мес / 5 лет
- Размер: 200×50 px
- **Подход:** SVG (2.C) — идеально
- **Код:** `<img src="https://forecasteconomy.com/api/v1/spark/cpi.svg?period=1y" width="200" height="50">`
- **Приоритет:** P0 (wow-фактор, 0 JS, работает везде)

### 3.3 Карточка (tile)
- Название + текущее значение + изменение (↑/↓) + sparkline
- Размер: 300×120 px
- **Подход:** SVG (2.C) или iframe (2.A)
- **Приоритет:** P1

### 3.4 Таблица последних N значений
- 5-20 строк: дата + значение
- **Подход:** iframe (2.A) — отдельный компонент `/embed/table/:code`
- **Приоритет:** P2

### 3.5 Сравнение двух индикаторов
- Два индикатора на одном графике (dual Y-axis)
- **Подход:** iframe → `/embed/compare?a=cpi&b=usd-rub`
- **Приоритет:** P2

### 3.6 Калькулятор инфляции
- Встраиваемый: «сколько стоили 1000 руб. в 2010 в 2025?»
- **Подход:** lightweight бандл (2.B) — нужна интерактивность
- **Приоритет:** P3 (wow-фактор, но сложно)

---

## 4. Конструктор виджетов (Embed Builder)

### Страница `/embed`

**Референс:** TradingView widget builder — лучший UX в индустрии.

**UI:**
```
┌─────────────────────────────────────────────────────────────┐
│  Конструктор виджетов                                       │
├────────────────────────┬────────────────────────────────────┤
│                        │                                    │
│  Тип виджета:          │    LIVE PREVIEW                    │
│  ○ График              │    ┌──────────────────────────┐    │
│  ○ Sparkline           │    │  ██████████████████████   │    │
│  ○ Карточка            │    │  ████████████ ·····       │    │
│  ○ Таблица             │    │                          │    │
│                        │    │  Данные: Forecast Economy │    │
│  Индикатор:            │    └──────────────────────────┘    │
│  [▼ ИПЦ              ] │                                    │
│                        │                                    │
│  Период:               │    Код для вставки:                │
│  ○ 1 год  ○ 3 года    │    ┌──────────────────────────┐    │
│  ○ 5 лет  ● 10 лет    │    │ <iframe src="https://    │    │
│                        │    │  forecasteconomy.com/     │    │
│  Размер:               │    │  embed/cpi?period=10y    │    │
│  Ширина: [600] px      │    │  &height=400"            │    │
│  Высота: [400] px      │    │  width="600"             │    │
│                        │    │  height="400"></iframe>   │    │
│  Тема: ○ Светлая      │    └──────────────────────────┘    │
│         ● Тёмная       │    [📋 Копировать код]             │
│                        │                                    │
│  ☑ Показать заголовок  │                                    │
│  ☐ Показать прогноз    │                                    │
│                        │                                    │
├────────────────────────┴────────────────────────────────────┤
│  Условия: бесплатно с обязательной ссылкой на              │
│  forecasteconomy.com. Подробнее: /terms                     │
└─────────────────────────────────────────────────────────────┘
```

**Реализация:**
- React-страница в основном SPA
- Live preview: iframe с текущими параметрами (realtime обновление)
- Код для вставки: textarea с автоматической генерацией
- Кнопка копирования (Clipboard API)
- Dropdown из всех 80 индикаторов (с поиском)

**Трудозатраты:** 2-3 дня (при готовом embed-маршруте).

---

## 5. Security: CORS / CSP / X-Frame-Options

### Текущее состояние (блокирующее)

**Caddy:**
```
X-Frame-Options "SAMEORIGIN"
Content-Security-Policy "... frame-src 'none'"
```

**Nginx:**
```
add_header X-Frame-Options "SAMEORIGIN" always;
add_header Content-Security-Policy "... frame-src 'none'" always;
```

### Что нужно изменить

**Подход:** дифференцированные заголовки по маршруту.

**Nginx:**
```nginx
# Embed-маршруты: разрешить встраивание
location ~ ^/embed/ {
    try_files /index.html =404;
    add_header Content-Security-Policy "frame-ancestors *" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    # НЕ ставим X-Frame-Options (deprecated, CSP приоритетнее)
    # НЕ ставим frame-ancestors 'self' — разрешаем всем
    add_header Cache-Control "no-cache";
}

# Основной сайт: запретить встраивание (как сейчас)
# X-Frame-Options: SAMEORIGIN остаётся в server {} block
```

**Caddy:**
```
@embed path /embed/*
header @embed X-Frame-Options ""
header @embed Content-Security-Policy "frame-ancestors *"
```

**Rate limiting для embed API:**
- Текущий лимит: 120 req/min per IP
- Для embed: данные кэшируются (Redis, 5 мин TTL) — нагрузка минимальна
- Рекомендация: дополнительный лимит `Referer`-based — если один домен делает >1000 req/hour, блокировать

**Referrer tracking:**
- Логировать `Referer` header при запросах к `/embed/*`
- Считать impressions: `embed_views` таблица (indicator_code, referrer_domain, date, count)
- Не блокировать при отсутствии Referer (многие браузеры его обрезают)

---

## 6. Attribution и юридическое

### Watermark в виджете
```
┌────────────────────────────────────────────┐
│  ИПЦ России (к предыдущему месяцу)        │
│                                            │
│  ██████████████████████████████████         │
│  ████████████████████ ·······              │
│                                            │
│  ───────────────────────────────────────── │
│  📊 Данные: Forecast Economy               │
│     forecasteconomy.com                    │
└────────────────────────────────────────────┘
```

- Ссылка `forecasteconomy.com/indicator/{code}` — **главная SEO-ценность**
- `target="_blank" rel="noopener"` — открывается в новом окне
- Нельзя убрать (CSS: `pointer-events: auto`, `position: absolute`, `z-index`)
- Размер: 11-12px, мягкий серый цвет — не мешает, но видим

### Terms of Use
- Бесплатно для некоммерческого использования с attribution
- Коммерческое: бесплатно до 100K показов/мес, далее — по запросу
- Attribution обязателен (ссылка на forecasteconomy.com)
- Запрещено: удаление watermark, перепродажа данных
- Отдельная страница `/terms-embed`

### Backlink-стратегия (SEO)
- Каждый встроенный виджет = dofollow-ссылка на forecasteconomy.com
- При 100 сайтах × 5 виджетов = 500 уникальных backlinks
- Ссылка ведёт на конкретный `/indicator/{code}` — прокачивает deep pages
- **Это основная бизнес-ценность embed-виджетов**

---

## 7. Архитектурная рекомендация: MVP

### Фаза 1 — MVP (3-4 дня)

**Подход: iframe (2.A) + SVG sparkline (2.C)**

Почему: максимальная отдача при минимальных затратах.

#### Шаг 1: Embed-страница React (1 день)

Новый компонент `EmbedChart.jsx`:
```jsx
// frontend/src/pages/EmbedChart.jsx
import { useParams, useSearchParams } from 'react-router-dom';
import { useIndicator, useIndicatorData, useForecast } from '../lib/hooks';
import IndicatorChart from '../components/IndicatorChart';
import { formatValueWithUnit, formatDate, formatChange } from '../lib/format';

export default function EmbedChart() {
  const { code } = useParams();
  const [params] = useSearchParams();

  const theme = params.get('theme') || 'light';
  const height = parseInt(params.get('height')) || 400;
  const showTitle = params.get('showTitle') !== 'false';
  const showForecast = params.get('showForecast') === 'true';
  const period = params.get('period') || '5y';

  const { data: meta } = useIndicator(code);
  const { data: dataResp } = useIndicatorData(code);
  const { data: forecast } = useForecast(code);

  const points = dataResp?.data || [];

  return (
    <div className={`embed-root ${theme}`}
         style={{ height, overflow: 'hidden', fontFamily: 'DM Sans, sans-serif' }}>
      {showTitle && meta && (
        <div className="embed-header">
          <span className="embed-title">{meta.name}</span>
          <span className="embed-value">
            {formatValueWithUnit(meta.current_value, meta.unit)}
          </span>
          {meta.change != null && (
            <span className={`embed-change ${meta.change >= 0 ? 'positive' : 'negative'}`}>
              {formatChange(meta.change)}
            </span>
          )}
        </div>
      )}

      <IndicatorChart
        cpiData={points}
        mode="cpi"
        showForecast={showForecast}
        forecastData={forecast}
        unit={meta?.unit || '%'}
        dateFormat="short"
      />

      <a href={`https://forecasteconomy.com/indicator/${code}`}
         target="_blank" rel="noopener"
         className="embed-attribution">
        📊 Данные: Forecast Economy
      </a>
    </div>
  );
}
```

Маршрут в App.jsx — **отдельный layout без Navbar/Footer:**
```jsx
// В App.jsx: embed-маршруты рендерят без shell
<Route path="/embed/:code" element={<EmbedChartKeyed />} />
```

Или, архитектурно чище, **отдельный entry point в Router:**
```jsx
function EmbedLayout() {
  return (
    <Suspense fallback={<div>...</div>}>
      <Routes>
        <Route path="/embed/:code" element={<EmbedChart />} />
      </Routes>
    </Suspense>
  );
}

// В App: если pathname.startsWith('/embed') → EmbedLayout, иначе → MainLayout
```

#### Шаг 2: nginx + Caddy для embed-маршрутов (0.5 дня)

```nginx
# nginx.conf — добавить ПЕРЕД основными location-блоками
location ~ ^/embed/[a-z0-9-]+/?$ {
    try_files /index.html =404;
    add_header Cache-Control "no-cache";
    # Разрешить iframe на любом домене
    add_header Content-Security-Policy "frame-ancestors *" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    # Явно НЕ ставим X-Frame-Options
}
```

```
# Caddyfile — conditional headers
@embed path /embed/*
header @embed X-Frame-Options ""
header @embed Content-Security-Policy "frame-ancestors *"
```

#### Шаг 3: SVG sparkline endpoint (1 день)

```python
# backend/app/api/charts.py
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

router = APIRouter(prefix="/chart", tags=["charts"])

SPARK_TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <polyline fill="none" stroke="{color}" stroke-width="{sw}"
    stroke-linecap="round" stroke-linejoin="round"
    points="{points}" />
  {gradient}
</svg>'''

GRADIENT_TEMPLATE = '''<defs>
  <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{color}" stop-opacity="0.15"/>
    <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
  </linearGradient>
</defs>
<polygon fill="url(#g)"
  points="0,{h} {points} {w},{h}" />'''

@router.get("/spark/{code}.svg")
async def sparkline_svg(
    code: str,
    w: int = Query(200, ge=50, le=1000),
    h: int = Query(60, ge=20, le=500),
    period: str = Query("1y"),
    color: str = Query("B8942F"),
    fill: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    # Получить данные (последние N точек)
    points = await _get_spark_data(code, period, db)
    if not points:
        return Response(content="<svg/>", media_type="image/svg+xml")

    # Нормализовать в координаты SVG
    values = [p.value for p in points]
    min_v, max_v = min(values), max(values)
    span = max_v - min_v or 1
    padding = 2

    svg_points = []
    for i, v in enumerate(values):
        x = round(padding + (w - 2 * padding) * i / (len(values) - 1), 1)
        y = round(padding + (h - 2 * padding) * (1 - (v - min_v) / span), 1)
        svg_points.append(f"{x},{y}")

    pts_str = " ".join(svg_points)
    gradient = ""
    if fill:
        gradient = GRADIENT_TEMPLATE.format(
            color=f"#{color}", h=h, points=pts_str, w=w
        )

    svg = SPARK_TEMPLATE.format(
        w=w, h=h, color=f"#{color}", sw=1.5,
        points=pts_str, gradient=gradient
    )

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )
```

**Использование:**
```html
<!-- Sparkline в статье -->
<img src="https://forecasteconomy.com/api/v1/chart/spark/cpi.svg?period=1y&w=200&h=50"
     alt="Тренд ИПЦ" width="200" height="50">

<!-- В email-рассылке -->
<img src="https://forecasteconomy.com/api/v1/chart/spark/usd-rub.svg?period=3m&w=300&h=80"
     alt="Курс доллара" width="300" height="80">
```

#### Шаг 4: Страница-конструктор `/embed` (1-1.5 дня)

React-страница в основном SPA:
- Dropdown: 80 индикаторов (с поиском, группировка по категориям)
- Тип: график / sparkline / карточка
- Настройки: размер, тема, период, прогноз
- Live preview: `<iframe>` с текущими параметрами
- Textarea с кодом для вставки + кнопка «Копировать»

---

### Фаза 2 — улучшения (после MVP, 3-5 дней)

1. **SVG карточка (tile):** серверный SVG с числом + sparkline + изменением
2. **Lightweight embed.js бандл:** отдельный Vite entry для тех, кому iframe не подходит
3. **Embed analytics:** таблица `embed_impressions` (code, referrer, date, count)
4. **Темы:** dark mode для embed (CSS variables)
5. **Responsive iframe:** postMessage API для авто-height

### Фаза 3 — advanced (5+ дней)

1. **Web Component** (как TradingView): `<fe-chart code="cpi">` с Shadow DOM
2. **Калькулятор инфляции:** встраиваемый интерактивный виджет
3. **API для сторонних разработчиков:** REST + embeddable JS SDK
4. **OG Image generation:** серверный PNG для social sharing (Twitter cards, Telegram preview)

---

## 8. Оценка трудозатрат

| Задача | Дни | Зависимости |
|--------|-----|-------------|
| EmbedChart.jsx + embed layout в Router | 0.5 | — |
| CSS для embed (light/dark, attribution) | 0.5 | — |
| nginx/Caddy: embed headers | 0.5 | — |
| SVG sparkline API endpoint | 1 | — |
| Embed builder page (`/embed`) | 1.5 | EmbedChart |
| Тесты (vitest + pytest) | 0.5 | Всё выше |
| **Итого MVP** | **4.5** | |
| SVG tile endpoint | 1 | SVG spark |
| embed.js lightweight бандл | 3 | EmbedChart |
| Embed analytics (impressions) | 1 | nginx/backend |
| Web Component | 5 | embed.js |

---

## 9. Итоговая рекомендация

**MVP = iframe + SVG sparkline + embed builder page.**

Обоснование:
1. **iframe** — наименьшая сложность при полной интерактивности. 250 KB — не идеально, но приемлемо для embed (TradingView iframe ~300 KB). Браузер кэширует бандл — при повторных визитах загрузка мгновенная.
2. **SVG sparkline** — wow-фактор при нулевом JS. Работает в email, Notion, Markdown, любой CMS. 5 KB на виджет. Генерируется за <10ms на backend. Это **уникальный** продукт — ни TradingEconomics, ни FRED такого не предлагают в чистом виде.
3. **Embed builder** — конвертирует посетителей в «распространителей». Каждый встроенный виджет = бесплатный backlink.

**Не начинать с:**
- Lightweight бандл (embed.js) — преждевременная оптимизация, пока нет трафика embed
- Web Components — overengineering для текущего масштаба
- matplotlib/plotly — тяжёлые зависимости ради серверного рендеринга; hand-crafted SVG лучше

**Порядок реализации:**
1. SVG sparkline endpoint (backend) — можно задеплоить и использовать немедленно
2. EmbedChart (frontend) + nginx/Caddy headers
3. Embed builder page
4. Metrics/analytics

---

## Приложение A: примерный embed-код для пользователя

### Интерактивный график
```html
<!-- Forecast Economy — ИПЦ России -->
<iframe src="https://forecasteconomy.com/embed/cpi?period=5y&theme=light&height=400"
  width="100%" height="420" frameborder="0"
  style="border: 1px solid #eee; border-radius: 12px;"
  loading="lazy" allowtransparency="true">
</iframe>
```

### Sparkline (для вставки в текст)
```html
<img src="https://forecasteconomy.com/api/v1/chart/spark/usd-rub.svg?period=1y&w=200&h=50"
  alt="Курс доллара к рублю — тренд за год" width="200" height="50"
  style="vertical-align: middle;">
```

### Карточка (tile)
```html
<iframe src="https://forecasteconomy.com/embed/tile/cpi?theme=light"
  width="320" height="140" frameborder="0"
  style="border-radius: 12px;"
  loading="lazy">
</iframe>
```

## Приложение B: чеклист перед выпуском

- [ ] `X-Frame-Options` убран для `/embed/*` маршрутов
- [ ] `Content-Security-Policy: frame-ancestors *` установлен для `/embed/*`
- [ ] SVG sparkline корректно кэшируется (Cache-Control: public)
- [ ] CORS `Access-Control-Allow-Origin: *` для SVG-эндпоинта
- [ ] Attribution ссылка не перекрывается, кликабельна
- [ ] Embed builder корректно генерирует код
- [ ] Тесты: embed route рендерит без Navbar/Footer
- [ ] Тесты: SVG валиден (xmlns, viewBox)
- [ ] Rate limiting работает для embed-запросов
- [ ] Sitemap: `/embed` страница добавлена
