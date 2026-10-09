-- Scoped PostgreSQL maintenance for the country catalogue, 2026-10-09.
-- Apply as the database owner with psql -v ON_ERROR_STOP=1.
-- Repeated runs preserve rows and schema. This is operator maintenance,
-- not an Alembic revision or an application-startup task.
SET statement_timeout = '5min';
SET lock_timeout = '5s';

-- Metadata updates mark heap pages not all-visible. The default 20% vacuum
-- threshold left 63k dead tuples for weeks and made covering scans read heap.
-- Trigger smaller regular cleanups (~4.5k changes at the observed 357k rows).
ALTER TABLE world_indicators SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_threshold = 1000
);

-- The sampled distinct-key estimate was 61k vs 341k actual nonzero keys.
ALTER TABLE world_data_points ALTER COLUMN indicator_id SET STATISTICS 1000;
VACUUM (ANALYZE) world_indicators;
ANALYZE world_data_points (indicator_id);
