-- Охват публичных прогнозов world_* (круг 13, R-FCST). Только чтение.
-- Публичный прогноз = последняя актуальная запись world_forecasts (is_current) со статусом passed
-- (то, что отдаёт API /world/.../data). Показатели: is_listed, частоты monthly/quarterly/annual.
-- Запуск (боевая база: только чтение, одна короткая выборка):
--   docker compose exec -T postgres psql -U rustats -d rustats -f - < backend/scripts/world-forecast-coverage.sql
\pset format aligned
\echo '=== 1. По странам первой линии'
with pub as (
  select distinct on (f.world_indicator_id) f.world_indicator_id, f.strategy, f.mase, f.baseline_mase
  from world_forecasts f
  where f.is_current and f.gate_status = 'passed'
  order by f.world_indicator_id, f.id desc
)
select c.slug as country,
       count(*) as indicators_maq,
       count(p.world_indicator_id) as public_forecasts,
       count(*) filter (where p.strategy = 'imf_weo') as imf_official,
       round(100.0 * count(p.world_indicator_id) / nullif(count(*), 0), 1) as pct_public
from world_indicators i
join world_countries c on c.id = i.country_id
left join pub p on p.world_indicator_id = i.id
where i.is_listed and i.frequency in ('monthly', 'quarterly', 'annual')
  and c.slug in ('united-states', 'china', 'japan', 'india', 'brazil', 'turkey',
                 'germany', 'france', 'united-kingdom')
group by c.slug
order by case c.slug when 'united-states' then 1 when 'china' then 2 when 'japan' then 3
                     when 'india' then 4 when 'brazil' then 5 when 'turkey' then 6
                     when 'germany' then 7 when 'france' then 8 else 9 end;

\echo '=== 2. Весь мир: по группам'
with pub as (
  select distinct on (f.world_indicator_id) f.world_indicator_id, f.strategy
  from world_forecasts f where f.is_current and f.gate_status = 'passed'
  order by f.world_indicator_id, f.id desc
)
select case when c.slug = 'united-states' then 'US'
            when c.region_ru = 'Европа' then 'Europe'
            else 'Rest' end as grp,
       count(*) as indicators_maq,
       count(p.world_indicator_id) as public_forecasts,
       count(*) filter (where p.strategy = 'imf_weo') as imf_official
from world_indicators i
join world_countries c on c.id = i.country_id
left join pub p on p.world_indicator_id = i.id
where i.is_listed and i.frequency in ('monthly', 'quarterly', 'annual')
group by 1 order by 1;

\echo '=== 3. По классам (категория), США + Китай + Япония + Индия + Бразилия + Турция + Германия + Франция + Великобритания'
with pub as (
  select distinct on (f.world_indicator_id) f.world_indicator_id, f.strategy
  from world_forecasts f where f.is_current and f.gate_status = 'passed'
  order by f.world_indicator_id, f.id desc
)
select i.category_ru as class,
       count(*) as indicators_maq,
       count(p.world_indicator_id) as public_forecasts,
       count(*) filter (where p.strategy = 'imf_weo') as imf_official
from world_indicators i
join world_countries c on c.id = i.country_id
left join pub p on p.world_indicator_id = i.id
where i.is_listed and i.frequency in ('monthly', 'quarterly', 'annual')
  and c.slug in ('united-states', 'china', 'japan', 'india', 'brazil', 'turkey',
                 'germany', 'france', 'united-kingdom')
group by 1 order by 3 desc, 1 limit 20;

\echo '=== 4. Качество опубликованных (без официальных МВФ: у них нет MASE)'
select count(*) as published,
       round(avg(mase)::numeric, 3) as mase_mean,
       round((percentile_cont(0.5) within group (order by mase))::numeric, 3) as mase_median,
       round((percentile_cont(0.25) within group (order by mase))::numeric, 3) as mase_p25,
       round((percentile_cont(0.75) within group (order by mase))::numeric, 3) as mase_p75,
       round(100.0 * count(*) filter (where mase < 1) / nullif(count(*), 0), 1) as pct_mase_lt1,
       round(100.0 * count(*) filter (where baseline_mase is not null and mase < baseline_mase) / nullif(count(*) filter (where baseline_mase is not null), 0), 1) as pct_better_than_naive
from world_forecasts
where is_current and gate_status = 'passed' and strategy <> 'imf_weo' and mase is not null;

\echo '=== 5. Ключевые ряды США/Китая/Японии/Индии/Бразилии: есть ли публичный прогноз'
select i.code, left(i.name_en, 44) as name,
       case when exists (select 1 from world_forecasts f where f.world_indicator_id = i.id and f.is_current and f.gate_status = 'passed') then 'YES' else '-' end as public
from world_indicators i
where i.code in ('us-cpi-all', 'us-cpi-core', 'us-unemployment-rate', 'us-civilian-labor-force',
                 'us-employment-population', 'us-rent', 'us-gdp-real', 'us-nonfarm-payrolls',
                 'cn-cpi-all', 'cn-gdp-real', 'jp-m2', 'jp-monetary-base', 'br-cpi-ipca', 'br-retail-sales',
                 'uk-cpi-all', 'uk-unemployment-rate')
order by i.code;
