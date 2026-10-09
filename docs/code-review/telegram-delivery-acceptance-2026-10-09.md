# Telegram: соединение и пропущенная доставка — 9 октября 2026

Начальный production SHA: 034b05388e47dded59ef8dc1c67facff72f360b3.
Локальный HEAD при начале: eb815d5f (только post-release evidence поверх runtime).

## Воспроизведение

Host api.telegram.org (DNS IPv4 149.154.166.110) не открывал TCP/443
за 8–10 s; Google TCP/443 0.02 s, UFW inactive, OUTPUT ACCEPT.
Локальный Mac тот же DNS address: HTTPS302 за 0.165 s. Контейнеры
backend/scheduler используют существующий extra_hosts149.154.167.220.
Их authenticated getMe: 1 из 4 прямых попыток — ConnectTimeout10.072 s,
3 успеха0.146–0.192 s. Через существующий authenticated HTTP CONNECT
relay: 4 из 4 ok=true, 0.412–1.270 s. Это наблюдение, не длительный SLA.

Следовательно, фраза «сервер не соединяется» описывала конкретную пробу,
а не постоянную недоступность. IPv4 direct path также прерывается; точная
точка фильтрации/маршрутного отказа не установлена. Extra_hosts сам по
себе недостаточен. Новый route использует уже настроенный relay, TLS
проверяется; данные доступа в отчёт не включены.

## Что пропущено

Аудит последних48h группирует kind/chat/text и ищет успех после первого
провала. Неудачные попытки, закрытые поздней доставкой, исключены.
Остались24 недоставленные logical groups по получателям (25 failed rows):
5 analytics_anomaly,6 http_5xx_spike,2 scheduler_alert,2 zero_parse;
2 digest (вчера),2 pulse_digest parts (вчера),2 new_user,
2 world_ingest_summary,1 etl_summary. Это сообщения/части по чатам,
не24 уникальных событий сайта. Сегодняшние digest2 и Pulse4 parts
имеют ok=true. Одна сегодняшняя регистрация сначала упала, затем
дослана (redelivered marker + новая ok=true строка).
Технические виды не входили в прежний RESEND_KINDS; другие старые
сообщения вышли за6h окно. Их содержание осталось в PostgreSQL.

## Реализация и проверки

Отдельное поле telegram_proxy_url + Compose/.env.example; оба sender
paths используют только его с trust_env=false. Техническая whitelist
расширена, без изменения age/window/max_tries/per-run/dedup.
До исправления4 caller proxy tests и10 real-outbox query tests падали;
после —78 focused tests passed, включая6 backup tests. Mock HTTP проверяет фактические sender
paths; SQLite — реальный запрос и повторный запуск без дубля. Они не
доказывают исправность сети; её подтверждает отдельный live probe.

## Состояние и границы

Код локальный; production выпуск ещё ожидается. Историческая досылка
зависит от выбора владельца (все прежним адресатам / сводка владельцу /
только будущая доставка). Доставка не означает прочтение человеком.
Входящие апдейты не подтверждались ручным getUpdates; штатный poller
остаётся единственным consumer offset. Старый архив не удаляется.
Файлы evidence: /tmp/fe-telegram-20261009/.


Дополнительно найден третий путь: pg-backup.sh host curl. Он использует
тот же dedicated route, credentials передаются через stdin curl config.
Два новых black-box теста реального backup shell с owned docker/curl
stubs падали до правки и проходят после; проверяют direct/proxy режим,
quoted .env, отсутствие proxy credentials в argv и сохранение двух
backup artifacts. Это не restore-проверка настоящей БД.
Host daily cron8/9 октября создал полную и identity-копии; его Telegram
отправки не архивируются в outbox и не включены в24 выявленные группы.
