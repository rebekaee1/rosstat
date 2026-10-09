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
Остались24 logical groups без подтверждённой доставки по получателям (25 failed rows):
5 analytics_anomaly,6 http_5xx_spike,2 scheduler_alert,2 zero_parse;
2 digest (вчера),2 pulse_digest parts (вчера),2 new_user,
2 world_ingest_summary,1 etl_summary. Это сообщения/части по чатам,
не24 уникальных событий сайта. У одной группы ответ отправки не записан после
прерывания процесса; фактическая доставка этой группы неизвестна. Сегодняшние digest2 и Pulse4 parts
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

Полный check-all: 4585 backend tests passed,170 skipped;3168 frontend tests
passed, lint/build/knowledge checks зелёные. bash -n backup script passed.
16 новых регрессий падали до исправления и проходят после.

## Состояние и границы

Код закоммичен 9bc0c014 и pushed; approval wrapper 0a4d0966.
Production выпущен: runtime target9bc0c0145f8eb8a019fd8fc60cdddf64ecc55aae,
Git/image wrapper0a4d0966b9bb952d5b8a39b1f927821178ad124d.
Приёмка завершена 2026-10-09 17:48 МСК. В post-release docs commit код не меняется. Историческая досылка
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


## Production acceptance

Все15 минут штатного deploy watch: ready=1, backend/scheduler OOM=false;
34 RU/EN representative pages passed. Main-page bot TTFB 0.034113–1.341573 s; это не p95/LTE пользовательской загрузки.
На минуте10 первая HTTPS home probe дала curl28/http000 (8s timeout); повтор200/1.342s, ready200/0.019s, следующая минута200/0.039s. Точка транзиентного отказа не установлена; это окно не доказывает отсутствие всех деградаций.
Четыре фактических telegram_bot._api getMe:4/4 ok=true, 0.439–1.037 s.
Owner-only alerting receipt: outbox3303,ok=true,message_id4744;
host pg-backup tg_notify receipt:ok=true,message_id4743.
Runtime SHA256 четырёх application source files и pg-backup.sh совпадают
с проверенной локальной версией. Alembic20261009c_session_perf. Dedicated
route включён, digest/realtime/poller/resend=true; retry bounds6h/10min/10per-run/3tries.
За последнюю часть наблюдения scheduler: {"log_lines": 493, "getUpdates_http_200": 0, "getUpdates_http_non200": 0, "telegram_getUpdates_failures": 1, "telegram_sendMessage_failures": 0, "connect_timeout_mentions": 0, "resend_job_success": 3, "poller_job_success": 35}.
Успешное завершение poller job и отсутствие ошибок не являются проверкой
конкретной входящей пользовательской команды; кнопку владелец ещё не проверял.
Исторические24 группы не воспроизводились: выбор способа восстановления
ожидается в вопросе владельцу. Одна pending-interrupted группа имеет
неизвестный фактический результат; остальные провалы имеют ошибки доставки.
Перед первым preflight созданная нами protected .env backup попала
под git dirty guard. Выпуск остановлен до fetch/cutover. Backup перенесён
за пределы repo, повторный штатный выпуск завершён; проверки не обходились.

В17:44:21 MSK один getUpdates завершился ReadTimeout (long poll),
без ConnectTimeout и без ошибки отправки уведомлений. Затем8 циклов
poller завершились без новых getUpdates errors; дополнительный реальный
getMe после этого:True/0.494s. Offset продвигается
только после обработки ответа; ReadTimeout его не подтверждает.
Количество executed-successfully — завершения job, а не отдельные
HTTP receipts. Конкретное нажатие кнопки человеком не проверялось.
