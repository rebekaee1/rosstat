# ADR-0028: Раздел «Исследования» — PDF-отчёты к роликам и счётчик скачиваний

**Status:** Accepted 09.11.2026 по слову владельца («по каждому ролику сделать материалы в виде PDF-отчёта… загрузить эти материалы на сайт… чтобы можно было скачивать эти отчёты, поставить метки, сколько раз скачал кто отчёт… ссылку с Telegram-бота на группу и с группы на Telegram-бота»). Выпуск на боевой — по отдельной команде владельца.
**Date:** 2026-11-09.
**Part of:** [`../data-contracts.md`](../data-contracts.md#исследования-pdf-отчёты-к-роликам--2026-11-09).
**Related:** [ADR-0003](0003-ssr-seo-strategy.md) (SSR), [ADR-0010](0010-analytics-contour-identity-goals-marts-olap.md) (цели), [ADR-0027](0027-public-telegram-bot.md) (публичный бот).
**Code anchors:** `backend/app/api/research.py`, `backend/app/data/research_catalog.json`, `backend/app/services/seo_research.py`, `backend/app/models.py` (`ResearchDownload`), Alembic `20261109_research_downloads`, `frontend/src/pages/ResearchPage.jsx`, `frontend/src/styles/research.css`, `frontend/public/research/`, `frontend/nginx.conf` (`/research/files/`), `backend/app/services/public_bot.py` (`research_url`, `research_keyboard`, `/research`), `backend/tests/test_research.py`.

## Контекст

Контент-завод ForecastEconomy (`~/Desktop/content-factory`) выпускает короткие ролики-исследования. К каждому ролику собран PDF-отчёт: аннотация, главное в цифрах, история, графики, кадры, выводы, «что это значит для тебя», методика и источники, авторы. Владелец хочет раздел на сайте со скачиванием, счётчик скачиваний и связку с Telegram (бот ↔ группа с отчётами). Трафик сначала идёт в бота.

## Решение

1. **Каталог — файл, а не таблица.** `research_catalog.json` готовит скрипт контент-завода `материалы/выгрузить_на_сайт.py <repo>`: копирует PDF в `frontend/public/research/files/forecasteconomy-research-NN-<slug>.pdf`, обложку (1-я страница, webp 480×680) в `frontend/public/research/covers/`, пишет поля `slug, number, title, subtitle, annotation, figures[{value,label,tone}], conclusions, topics, file, download_name, cover, pages, size_mb, authors`, верхние `release` («ноябрь», без дат — слово владельца), `release_en`, `group_url` (группа Telegram, пусто — пока нет). Новый выпуск = перезапуск скрипта и коммит.
2. **Скачивание через счётчик.** `GET /api/v1/research/{slug}/download`: неизвестный slug → 404; боты по User-Agent не считаются; один адрес — не чаще раза в сутки на отчёт (Redis `fe:research:dl:<sha256(slug|ip|день)[:32]>`, `SET NX EX 86400`; без Redis считается каждое); +1 в `research_downloads(slug, date, count)` (уникальность slug+date, гонка → повтор обновлением); ответ 302 на статический PDF, `Cache-Control: no-store`, `X-Robots-Tag: noindex`. ПДн и IP не хранятся. Сбой счётчика не мешает скачиванию.
3. **Список.** `GET /api/v1/research` — каталог + `downloads` по отчёту и `total_downloads`, `Cache-Control: public, max-age=60`. Без таблицы (до миграции) — нули.
4. **Страница `/research`.** SPA `ResearchPage` (карточка: обложка, номер и темы, название, подзаголовок, 4 цифры с цветом направления, «Аннотация и выводы», «Скачать PDF», страницы/размер/скачивания) и SSR `seo_research.render_research_html` (тот же текст, JSON-LD `CollectionPage` с `Report`). RU/EN; отчёты на русском, EN-страница это говорит. Ссылки: меню телефона, подвал, sitemap (`STATIC_PAGES`), зарезервированный сегмент.
5. **Цель аналитики** `research_download` (микро) — клик по «Скачать» на фронте; серверный счётчик — источник правды для числа скачиваний.
6. **Telegram.** Бот (публичный режим ADR-0027): кнопка «📚 Исследования (PDF)» в меню, команда `/research` (и слова «исследования», «отчеты»), вход `?start=research…`; ведут в группу из `RUSTATS_PUBLIC_BOT_GROUP_URL`, а пока она пуста — на `/research`. Обратная ссылка группа → бот (`t.me/ForecastEconomyBot?start=group_research`) ставится в описании и закрепе группы. Группу создаёт владелец (бот не может создать группу), бота добавляет админом.

## Последствия

- PDF (~2 МБ × 21 ≈ 39 МБ) лежат в репозитории и образе фронта; кэш nginx неделя. При росте выпусков вынести в объектное хранилище — отдельное решение.
- Число скачиваний — «уникальные адреса в сутки», не люди.
- Проверено локально 09.11.2026: тесты `test_research.py`, `test_public_bot.py`, vitest; страница в браузере на 1280 и 375 px, RU/EN, с подменным API. Не проверено: боевой nginx, миграция на проде, живой бот.

## Дополнение 2026-11-09 — источник скачивания и выпуск

Владелец 09.11.2026: «нужно ещё трекерить, сколько с сайта загрузили». До первого выпуска таблица получила колонку
`source` (миграция поправлена на месте, на проде её не было; после слияния она идёт за `20261109_public_bot_dialog`).

- `site` — Referer с хоста `forecasteconomy.com` или его поддомена (браузер шлёт его при клике: политика сайта
  `strict-origin-when-cross-origin`). Метки `?src=site` нет нарочно: ссылку со страницы с такой меткой получил бы и
  обходчик.
- `bot`, `tg` — метки `?src=bot` / `?src=tg` у прямых ссылок из бота и канала (в HTML сайта их нет).
- `direct` — всё остальное. Ферма 05–09.11 ходила с десятков тысяч адресов браузерным UA и без Referer; `direct`
  не входит в `downloads` / `total_downloads`, утренний дайджест пишет его отдельно («без перехода с сайта — похоже
  на роботов»).
- Метка «раз в сутки с адреса» учитывает источник: заход без перехода не съедает учёт настоящего скачивания.
- Строка дайджеста: «📚 Скачали исследования вчера: N (с сайта …, из бота …, из канала …)».

PDF, выложенные в канал `@forecasteconomy` вложениями, счётчик не видит: Telegram не сообщает число скачиваний
вложений, видны только просмотры поста.
