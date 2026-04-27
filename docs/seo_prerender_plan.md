# SEO Prerender Plan — устранение дубликатов title/description

**Источник:** правка `v3/edit_005` (видео НА правки 3). Высокий приоритет.

## Проблема

Yandex Webmaster показывает дублирующиеся title/description для:
- `/indicator/unemployment`
- `/indicator/usd-rub`
- (и потенциально других страниц индикаторов)

**Причина.** Frontend — Vite SPA. Когда краулер запрашивает `/indicator/cpi`, nginx отдаёт **один и тот же** статичный `index.html` со стандартным title `Forecast Economy — данные и прогноз...`. JavaScript-хук `useDocumentMeta` обновляет `<title>` уже после монтирования React, но робот Яндекса не выполняет JS (или выполняет частично).

## Решения (в порядке приоритета)

### 1. Backend OG endpoint расширить до полного prerender (РЕКОМЕНДОВАНО)

Уже есть `/api/v1/og/{indicator|category|page}/{slug}` (см. snapshot истории — bots-detect через nginx UA). Расширить:
- Возвращать **полный HTML** для индикаторных URL (`/indicator/{code}`), а не только OG-теги.
- Тело страницы строится через шаблон Jinja: title из SEO_MAP, description из SEO_MAP, breadcrumbs, последняя точка ряда, ссылка на canonical.
- nginx перенаправляет `User-Agent: Yandex|Google|Bing|...` на этот endpoint.
- Реальные пользователи получают SPA как раньше.

**Плюсы:**
- Минимальная инвазивность.
- Уже есть инфраструктура (OG endpoint работает на `/api/v1/og/indicator/{slug}`).
- Контролируем точно, что отдаёт каждый URL.

**Минусы:**
- Дублирование шаблонов (Jinja в backend + JSX в frontend).
- Нужен список UA для bot-detect (уже частично есть в Caddy/nginx).

### 2. vite-plugin-prerender-spa-plugin (СТАТИЧЕСКИЙ)

Установка:
```bash
npm install --save-dev vite-plugin-prerender-spa
```

Конфиг `vite.config.js`:
```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import prerender from 'vite-plugin-prerender-spa';

export default defineConfig({
  plugins: [
    react(),
    prerender({
      staticDir: 'dist',
      routes: [
        '/',
        '/about',
        '/privacy',
        '/calculator',
        '/compare',
        '/demographics',
        '/calendar',
        '/widgets',
        '/category/prices',
        '/category/rates',
        '/category/finance',
        '/category/labor',
        '/category/gdp',
        '/category/population',
        '/category/trade',
        '/category/business',
        '/category/science',
        '/indicator/cpi',
        '/indicator/key-rate',
        '/indicator/usd-rub',
        '/indicator/unemployment',
        // + остальные топ-30 индикаторов
      ],
      renderer: '@prerenderer/renderer-puppeteer',
    }),
  ],
});
```

**Плюсы:**
- Чисто frontend-решение, бэкенд не трогаем.
- Реальный SPA-рендер через Puppeteer → точно совпадает с тем, что видит пользователь.

**Минусы:**
- При сборке: запускается headless Chrome, замедляет CI на 30-60s.
- Список routes нужно обновлять при добавлении индикатора (не из БД).
- При деплое — пересборка всего frontend.
- Динамические запросы (например, последние данные) не учитываются (на момент сборки).

### 3. Server-side rendering (SSR) — Next.js / Remix migration

Полная миграция с Vite SPA → Next.js. Долго, дорого, рискованно. **Не рекомендуется** без явной потребности.

## Решение этой итерации

Из-за сложности и рисков:
1. **Не пытаемся установить prerender автоматически** в этой итерации.
2. **Вариант 1 (backend OG endpoint расширенный)** — рекомендуется как следующий шаг. Реализация:
   - Расширить шаблон `og_template.html` в backend на полный HTML (title, meta, h1, p, og:tags, breadcrumbs).
   - Подключить детекцию UA в nginx или Caddy (уже частично есть).
   - Тестировать через `curl -A "Yandex" https://forecasteconomy.com/indicator/cpi` — должен вернуть уникальный HTML.

## TODO

- [ ] Прототип расширенного шаблона backend OG (один индикатор: cpi).
- [ ] Добавление UA-rewrite в nginx/Caddy: `if ($http_user_agent ~* (Yandex|Google|Bing)) { rewrite ^/indicator/(.+)$ /api/v1/og/indicator/$1 last; }` (если ещё нет).
- [ ] Проверить через Yandex Webmaster instrument «Просмотр глазами Яндекса» (https://webmaster.yandex.ru) — должен вернуть уникальный title для каждой страницы.
- [ ] Подождать переиндексации (3-7 дней), убедиться что дубли уходят.

## Эксперимент с vite-plugin-prerender (отложен)

В эту итерацию prerender-pluginы не устанавливаются: высокий риск сломать build, низкая ценность по сравнению с backend OG.

---

## История правок документа

- 2026-04-27 — создан как ответ на правку `v3/edit_005` НА правки 3.
