#!/usr/bin/env bash
# F13: создать/обновить роль приложения `rustats_app` (scripts/db-roles.sql) в контейнере postgres.
# Секреты не печатаются. Использование (на сервере, из /opt/rosstat):
#   scripts/db-roles.sh                # пароль берётся из RUSTATS_APP_DB_PASSWORD (.env) или генерируется и дописывается в .env
#   scripts/db-roles.sh --verify       # только проверки (роль не суперпользователь, права, подключение)
# После первого запуска перезапустить backend и scheduler: в .env появятся RUSTATS_APP_DB_USER/RUSTATS_APP_DB_PASSWORD.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE="${ENV_FILE:-.env}"
dc() { docker compose "$@"; }
pg() { dc exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d rustats -v ON_ERROR_STOP=1 -At "$@"' sh "$@"; }

verify() {
  local pw
  pw="$(grep -E '^RUSTATS_APP_DB_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
  [[ -n "$pw" ]] || { echo "RUSTATS_APP_DB_PASSWORD не задан в $ENV_FILE" >&2; return 1; }
  echo "== роль"
  pg -c "select rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls from pg_roles where rolname in ('rustats','rustats_app') order by 1"
  echo "== подключение под rustats_app и права"
  dc exec -T -e PGPASSWORD="$pw" postgres psql -h 127.0.0.1 -U rustats_app -d rustats -At -v ON_ERROR_STOP=1 <<'SQL'
select 'whoami', current_user, (select rolsuper from pg_roles where rolname = current_user);
select 'can_select_alembic_version', count(*) from alembic_version;
create temp table _t(x int); insert into _t values (1); select 'temp_table_ok', count(*) from _t;
select 'has_create_on_public', has_schema_privilege('rustats_app', 'public', 'CREATE');
select 'can_read_other_db_list', count(*) from pg_database;
SQL
  echo "== запрещённое должно падать"
  if dc exec -T -e PGPASSWORD="$pw" postgres psql -h 127.0.0.1 -U rustats_app -d rustats -At -c "create table _must_fail(x int)" 2>&1 | grep -q "permission denied"; then
    echo "CREATE TABLE: permission denied (ожидаемо)"
  else
    echo "ОШИБКА: rustats_app смог создать таблицу" >&2; return 1
  fi
}

if [[ "${1:-}" == "--verify" ]]; then verify; exit $?; fi

pw="$(grep -E '^RUSTATS_APP_DB_PASSWORD=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)"
if [[ -z "$pw" ]]; then
  pw="$(openssl rand -hex 24)"
  { echo; echo "# F13: роль приложения (scripts/db-roles.sh, $(date +%F))"; echo "RUSTATS_APP_DB_USER=rustats_app"; echo "RUSTATS_APP_DB_PASSWORD=$pw"; } >> "$ENV_FILE"
  echo "Пароль rustats_app сгенерирован и дописан в $ENV_FILE (не печатается)."
fi
dc exec -T -e APP_PASSWORD="$pw" postgres sh -c 'psql -U "$POSTGRES_USER" -d rustats -v ON_ERROR_STOP=1 -q -v app_password="$APP_PASSWORD" -f -' < scripts/db-roles.sql
echo "Роль rustats_app создана/обновлена. Дальше: перезапустить backend и scheduler, затем scripts/db-roles.sh --verify"

