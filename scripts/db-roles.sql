-- F13 (2026-10-04): роль приложения без прав суперпользователя.
--
-- Запускать под bootstrap-ролью (`rustats`, суперпользователь контейнера postgres) через scripts/db-roles.sh.
-- Идемпотентно: можно повторять. Владелец объектов и роль миграций остаются `rustats` — данные и
-- владение не переносятся (нулевой риск для содержимого). Приложение (`rustats_app`) получает только
-- DML, использование последовательностей и временные таблицы; не может создавать/менять/удалять
-- объекты, читать чужие БД, выполнять COPY PROGRAM/файловые операции и занимать reserved-соединения.
--
-- Параметры psql: -v app_password='…' (обязателен, ≥ 24 символов).
\set ON_ERROR_STOP on

SELECT length(:'app_password') >= 24 AS password_ok \gset
\if :password_ok
\else
  \echo 'app_password must be at least 24 characters'
  SELECT 1/0;
\endif

SELECT 'CREATE ROLE rustats_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 80'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rustats_app') \gexec
ALTER ROLE rustats_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'app_password';

GRANT CONNECT, TEMPORARY ON DATABASE rustats TO rustats_app;

GRANT USAGE ON SCHEMA public TO rustats_app;
-- rustats_app не получает CREATE на схеме; PUBLIC не трогаем (его могут использовать другие роли хоста).
REVOKE CREATE ON SCHEMA public FROM rustats_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rustats_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO rustats_app;
-- Статистика PostgreSQL для BI/диагностики (pg_stat_*, pg_stat_statements), без права читать данные чужих таблиц.
GRANT pg_read_all_stats TO rustats_app;

-- Объекты, которые создаст владелец позже (миграции), сразу доступны приложению.
ALTER DEFAULT PRIVILEGES FOR ROLE rustats IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rustats_app;
ALTER DEFAULT PRIVILEGES FOR ROLE rustats IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO rustats_app;
