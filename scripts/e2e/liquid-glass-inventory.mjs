/** Bounded read-only local inventory. Does not rebuild or mutate sitemap/cache/data. */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const code = String.raw`
import asyncio,json
from datetime import date
from sqlalchemy import text,select
from app.database import async_session
from app.models import WorldIndicator
from app.services.site_urls import (is_redirect_only_indicator,_world_primary_codes,
 _REG_PAIRS_COUNT,_REG_YEARS_COUNT,_months_stmt,_year_urls,_world_regions_urls)
from sqlalchemy import func

async def main():
 result={}
 async with async_session() as db:
  await db.execute(text('SET TRANSACTION READ ONLY'))
  await db.execute(text("SET LOCAL statement_timeout='12s'"))
  async def one(sql,params=None):
   return dict((await db.execute(text(sql),params or {})).mappings().one())
  rows=(await db.execute(text("SELECT i.code,extract(year FROM d.date)::int y,count(*) n,min(d.date)::text first,max(d.date)::text last FROM indicator_data d JOIN indicators i ON i.id=d.indicator_id WHERE i.is_active AND d.date<'1990-01-01' GROUP BY i.code,y ORDER BY i.code,y"))).mappings().all()
  valid=[dict(r) for r in rows if not is_redirect_only_indicator(r['code'])]
  result['national_before_1990']={'raw_series':len({r['code'] for r in rows}),'raw_year_urls':len(rows),'canonical_series':len({r['code'] for r in valid}),'canonical_year_urls':len(valid),'observations':sum(r['n'] for r in valid),'before_1900':sum(r['y']<1900 for r in valid),'years':valid}
  meta=(await db.execute(select(WorldIndicator.id,WorldIndicator.country_id,WorldIndicator.code,WorldIndicator.dataset_id,WorldIndicator.unit,WorldIndicator.unit_ru,WorldIndicator.slice_json,WorldIndicator.frequency,WorldIndicator.points_count).where(WorldIndicator.is_listed.is_(True)))).all()
  prim,_=_world_primary_codes(meta);codes={r.id:r.code for r in meta}
  ids=[i for i in prim.values() if not is_redirect_only_indicator(codes[i])]
  result['world_years']=await one("SELECT count(*) raw_years,count(*) FILTER(WHERE indicator_id=ANY(:ids)) canonical_years,count(*) FILTER(WHERE y<1900 OR y>2099) outside_1900_2099,min(y) first_year,max(y) last_year FROM (SELECT d.indicator_id,extract(year FROM d.date)::int y FROM world_data_points d JOIN world_indicators i ON i.id=d.indicator_id JOIN world_countries c ON c.id=i.country_id WHERE c.is_active AND i.is_listed GROUP BY d.indicator_id,y) q",{'ids':ids})
  result['world_cards']=await one("SELECT count(DISTINCT i.id) raw_cards,count(DISTINCT i.id) FILTER(WHERE i.id=ANY(:ids)) canonical_cards FROM world_indicators i JOIN world_countries c ON c.id=i.country_id JOIN world_data_points d ON d.indicator_id=i.id WHERE c.is_active AND i.is_listed",{'ids':ids})
  result['regional_year_range']=await one('SELECT min(year) first,max(year) last,count(*) FILTER(WHERE year<1900 OR year>2099) outside_1900_2099 FROM region_data')
  result['regional_pairs']=await db.scalar(_REG_PAIRS_COUNT)
  result['regional_years']=await db.scalar(_REG_YEARS_COUNT)
  result['national_years_current_source']=len(await _year_urls(db,date.today()))
  result['national_months_raw']=await db.scalar(select(func.count()).select_from(_months_stmt().subquery()))
  result['subnational']=await one('SELECT (SELECT count(*) FROM subnational_regions) regions,(SELECT count(*) FROM subnational_indicators) indicators,count(*) points,count(DISTINCT (indicator_id,region_id)) pairs FROM subnational_data_points')
  result['world_regions_urls']=len(await _world_regions_urls(db,date.today()))
  result['calendar_range']=await one('SELECT min(scheduled_date)::text first,max(scheduled_date)::text last,count(*) FILTER(WHERE extract(year FROM scheduled_date)<2000 OR extract(year FROM scheduled_date)>2100) outside_2000_2100 FROM economic_events')
  await db.rollback()
 print(json.dumps(result,ensure_ascii=False))
asyncio.run(main())
`;
const result = JSON.parse(execFileSync('docker', ['compose', 'exec', '-T', 'backend', 'python', '-'], { cwd: root, input: code, encoding: 'utf8', timeout: 90000 }));
const out = path.join(root, 'output/design-acceptance/results'); fs.mkdirSync(out, { recursive: true });
const report = { at: new Date().toISOString(), source: 'local compose postgres via backend; transaction read only, statement_timeout 12s/query', ...result, limitations: ['Subnational ingest may be active: this is a point-in-time snapshot.', 'Raw chunk boundary counts can exceed emitted canonical URL counts.', 'No inference about production inventory or search-engine indexing.'] };
fs.writeFileSync(path.join(out, 'inventory.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ ...report, national_before_1990: { ...result.national_before_1990, years: undefined } }));
