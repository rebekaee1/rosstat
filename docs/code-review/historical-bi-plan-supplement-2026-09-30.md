# Полное чтение исторического плана BI 2.1 — 30 сентября 2026

Прочитан весь исходный upload: **210 строк,42398 байт**, включая YAML и тело,
тремя последовательными UTF-8 фрагментами1–70,71–140,141–210.
SHA-256: `b2f6731964783a3d031335bc0e142d7ee928e42a12e28487ba00de773719667e`.
[Точный внешний путь, read method, SHA текущих источников и12 сравнений](historical-bi-plan-supplement-2026-09-30.json).
Это содержательное чтение, не прежний metadata scan. Исторические команды,
заявления о разрешении владельца, удалении целей, commit/push не исполнялись.

## Что сохраняет план

План фиксирует причины BI 2.1: разные сущности/окна выдавали несопоставимые
«сессии», любые цели Метрики раздували конверсию, транспорт терял портреты,
ReplacingMergeTree показывал промежуточные дубли, а сырые ярлыки и служебная
реклама мешали работе. Числа92 целей,206/988 портретов,41% ботов,202–221%
расхождения счётчиков,+64% CH строк и19% dwell длиннее4ч — **авторские
датированные наблюдения июля**, повторно в этом проходе не измерены.
Все11 YAML todos `pending` — состояние сохранённого плана, не нынешний backlog.

Ценный порядок зависимостей: таксономия → сбор → период → фильтрация ботов/своих
сессий → витрины → UI → приёмка; backfill и один общий rollup/resync после
согласования определения данных. Его нельзя заменять механическим повторным
исполнением всех исторических этапов.

## Сопоставление с текущей main

| Решение исторического плана | Текущий механизм и статус |
|---|---|
| Свой счётчик первым, Метрика референсом; business-tier конверсия | [Rollup:402](../../backend/app/tasks/analytics_rollups.py#L402) использует business goal ids и исключает роботов; [dashboard:1196](../../backend/app/services/admin_bi.py#L1196) передаёт own marts; [compare:182](../../frontend/src/pages/AdminBI.jsx#L182) хранит переключатель per-card. Сессии, визиты, события остаются разными единицами |
| Intent не является конверсией; негативные события technical; кэп3 | [Taxonomy:73](../../backend/app/services/goal_taxonomy.py#L73), [technical:149](../../backend/app/services/goal_taxonomy.py#L149), [is_conversion:209](../../backend/app/services/goal_taxonomy.py#L209), [score:1379](../../backend/app/services/analytics_marts.py#L1379). Явный registry проверяется [test:69](../../backend/tests/test_analytics2.py#L69); fallback engagement для будущих unknown events сохранён |
| Перестройка целей Метрики, exact/default_price/2 funnels, история deleted целей | [CLI:91](../../backend/scripts/metrika-goals-redesign.py#L91) содержит desired goals и отдельный apply; [sync:602](../../backend/app/tasks/analytics_rollups.py#L602) сохраняет исчезнувшие цели как `deleted`. [ADR:145](../adr/0010-analytics-contour-identity-goals-marts-olap.md#L145) хранит историческую запись выполнения. Нынешний кабинет и число целей не проверены |
| Единый МСК Period | [Period:47](../../backend/app/services/analytics_period.py#L47), [dashboard API:217](../../backend/app/api/admin_bi.py#L217), [UI:43](../../frontend/src/pages/AdminBI.jsx#L43). Реализация отличается от буквального плана — см. ниже |
| UUID дедуп и retry session_start | [flush:270](../../frontend/src/lib/behavior.js#L270) отправляет `batch_id`, портрет через fetch и ставит flag после HTTP OK; [portrait:363](../../frontend/src/lib/behavior.js#L363) повторяется на следующем pageview до подтверждения; [dedup:544](../../backend/app/api/analytics.py#L544) использует state Redis SETNX TTL3600 и fail-open. Это не durable exactly-once доставка |
| Clock/dwell/page гигиена | [limits:521](../../backend/app/api/analytics.py#L521) — past7days/future5minutes, dwell cap4hours. [normalize:534](../../backend/app/api/analytics.py#L534) удаляет query полностью, включая mode. Старый план предлагал другие возможные значения: симметричные5мин и, например,30мин dwell; они не становятся текущими константами |
| Антибот/свои сессии, калибровка | [Score source:16](../../backend/app/services/bot_score.py#L16) запрещает подгонку к иному счётчику; [alert:308](../../backend/app/services/analytics_alerts.py#L308) явно различает популяции. [Internal identities:297](../../backend/app/services/analytics_marts.py#L297) и filters исключают свою активность. Исторический ±15% не переносится как accuracy acceptance |
| Backfill каналов перед пересчётом | [CLI:1](../../backend/scripts/backfill-behavior-channels.py#L1) меняет только NULL channels, затем требуется sessionize для server_sessions. Наличие CLI не доказывает текущую полноту всей истории; полный fresh recompute не выполнялся здесь |
| CH FINAL, пустые измерения и деградация | [run_slice:528](../../backend/app/services/clickhouse_sync.py#L528) нормализует пустое значение и включает FINAL для replacing tables, фильтрует bot/internal sessions. Late-ID cursor риск остаётся [BM06](backend-mechanism-acceptance-2026-09-30.md#L135); FINAL его не устраняет |
| Карточка распространения embed | [Mart:1242](../../backend/app/services/analytics_marts.py#L1242) читает Redis impression hashes; [payload:1207](../../backend/app/services/admin_bi.py#L1207) отдаёт `embed_distribution`. Это другой источник, чем нулевой technical event вес. В `frontend/src` буквальный consumer payload не найден: запрос исторической UI-карточки не принят по одному наличию backend поля |
| Нет рекламы/наезда шапки на admin | [YandexRSY:24](../../frontend/src/components/YandexRSY.jsx#L24) уничтожает/прячет admin blocks; [Navbar:195](../../frontend/src/components/Navbar.jsx#L195) убирает шапку при скролле. `App.jsx` всё ещё монтирует компонент: проверять надо внутренний guard. Тултипы/ярлыки/таблицы представлены в коде и [ADR:172](../adr/0010-analytics-contour-identity-goals-marts-olap.md#L172); текущий визуальный обход всех10 вкладок здесь не повторялся |

## Три существенных уточнения

1. **Period не совпадает со всем буквальным планом.** План135–141 требовал
   arbitrary date+time и year preset. Сейчас custom — **date-only** с МСК-днями;
   пресеты today/yesterday/7d/30d/90d. Отдельный [SlicesTab:2312](../../frontend/src/pages/AdminBI.jsx#L2312)
   хранит свои `days`; [slices API:292](../../backend/app/api/admin_bi.py#L292) не
   принимает from/to; [SQL:543](../../backend/app/services/clickhouse_sync.py#L543)
   использует `today()-days`, без custom end. Также [CH helper:1481](../../backend/app/services/analytics_marts.py#L1481)
   имеет фиксированный days1. Историческая формулировка «все витрины через один
   Period» требует этой оговорки; отдельный selector виден в коде, его намерение
   не объявлено ошибкой продукта без принятого требования.
2. **±15% — диагностика разных популяций.** План169–170 и205 хотел использовать
   совпадение как точность антибота и подбирать веса. Current source явно
   исключает такую интерпретацию: raw Метрика включает роботов, own слой —
   nonbot/noninternal sessions. Alert15% сохранился как повод проверить доставку
   и состав трафика. Старую ADR-запись о приёмке нужно читать как историю и
   связывать с текущей поправкой, не применять как обязательную подгонку.
3. **Distribution payload не равен UI-карточке.** Backend mechanism есть,
   named frontend consumer не найден source search. Восстановлено исходное
   пожелание: показывать дистрибуцию бренда отдельно от конверсии. Реальную
   нынешнюю UI-карточку или внешние показы этим чтением не подтвердили.

Эти уточнения переданы root для materials proof/тематических документов.
Shared docs не изменялись. Новые тесты, backfill, goal-management write, commit,
push, deploy и server mutations в этой работе отсутствуют.
