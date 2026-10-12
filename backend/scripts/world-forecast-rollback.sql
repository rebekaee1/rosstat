-- Откат включения прогнозов world_* (круг 13, R-FCST): вернуть набор публичных прогнозов к моменту t0.
--
-- До включения первого флага снять «снимок актуальных»:
--   create table fcst_current_backup as select id from world_forecasts where is_current;
-- Откат (после выключения флагов в .env и пересоздания scheduler):
--   docker compose exec -T postgres psql -U rustats -d rustats \
--     -v t0="'2026-10-13 00:00'" -v apply=commit -f - < backend/scripts/world-forecast-rollback.sql
-- t0 — время (UTC, как created_at) за минуту до первого включения; apply=commit применяет, apply=rollback только показывает счётчики.
-- Строки world_forecasts и world_forecast_values не удаляются: снимается и возвращается только is_current, поэтому
-- откат обратим (повторный прогон партии вернёт всё, что нужно).
-- После отката: сбросить кэш мира (см. impl-r-fcst.md, раздел «Откат»).
\set ON_ERROR_STOP on
begin;
select count(*) as to_deactivate from world_forecasts where is_current and created_at >= :t0;
select count(*) as to_restore from world_forecasts f
  where not f.is_current and f.id in (select id from fcst_current_backup);
update world_forecasts set is_current = false where is_current and created_at >= :t0;
update world_forecasts set is_current = true where id in (select id from fcst_current_backup) and not is_current;
select count(*) as current_after, (select count(*) from fcst_current_backup) as current_before from world_forecasts where is_current;
select case when :'apply' = 'commit' then 'COMMIT' else 'ROLLBACK' end as action \gset
:action;
