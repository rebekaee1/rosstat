"""Private semantic/type/pre-LIMIT controls for generic official native facets."""
import pytest
from sqlalchemy import create_engine,MetaData,Table,Column,Integer,String,JSON,insert,select
from sqlalchemy.dialects import postgresql
from app.services import search_dimensions as D

@pytest.fixture
def table():
 engine=create_engine('sqlite:///:memory:');m=MetaData();t=Table('native_facets',m,Column('id',Integer,primary_key=True),Column('provider',String),Column('slice',JSON));m.create_all(engine)
 with engine.begin() as c:yield c,t
 engine.dispose()
@pytest.mark.parametrize('key,axis,member,wrong_axis,wrong_member',[
 ('search-dim-education-levels-total','isced11','TOTAL','iscedf13','ED0-2'),
 ('search-dim-education-fields-total','iscedf13','TOTAL','isced11','F01'),
 ('search-dim-birth-countries-total','c_birth','TOTAL','citizen','NAT'),
 ('search-dim-migration-statuses-total','mgstatus','TOTAL','c_birth','NAT'),
 ('search-dim-worktime-total','worktime','TOTAL','duration','TOT_FTE'),
 ('search-dim-institution-sectors-total','sector','TOT_SEC','nace_r2','S13'),
 ('search-dim-age-total','age','TOTAL','sex','Y15-74'),
 ('search-dim-education-pre-primary','isced11','ED02','iscedf13','ED01'),
 ('search-dim-education-tertiary','isced11','ED5-8','iscedf13','ED0-2'),
 ('search-dim-education-vocational-secondary-post-secondary','isced11','ED35_45','iscedf13','ED3'),
 ('search-dim-statistic-mean-equivalised-income','statinfo','MEAN_EI','indic_em','MED_EI'),
 ('search-dim-statistic-average','statinfo','AVG','duration','MED'),
 ('search-dim-contract-duration-under-one-month','duration','M_LT1','worktime','M1-3'),
 ('search-dim-adjustment-seasonal-calendar','s_adj','SCA','statinfo','SA'),
 ('search-dim-adjustment-seasonal-without-calendar','s_adj','SA','statinfo','SCA'),
 ('search-dim-reason-too-expensive','reason','TXP','lev_limit','TOTAL'),
 ('search-dim-activity-limitation-some','lev_limit','SOME','reason','SEV'),
 ('search-dim-activities-professional-sts','nace_r2','M_STS','nace_r1','M'),
])
def test_exact_role_has_SQL_Python_parity(table,key,axis,member,wrong_axis,wrong_member):
 c,t=table;slices=[{axis:member},{axis:wrong_member},{wrong_axis:member},{},{axis:None},{axis:True},{axis:[member]},{axis:{'code':member}}];providers=['Eurostat']*len(slices)+['not-Eurostat',' Eurostat '];slices += [{axis:member},{axis:' '+member.lower()+' '}]
 c.execute(insert(t),[{'id':i,'provider':p,'slice':s} for i,(p,s) in enumerate(zip(providers,slices),1)])
 clauses=D.dimension_constraints(((key,),),t.c.provider,t.c.slice);got=c.execute(select(t.c.id).where(*clauses).order_by(t.c.id)).scalars().all()
 expected=[i for i,(p,s) in enumerate(zip(providers,slices),1) if key in D.dimension_metadata(p,s).split()]
 assert got==expected==[1,10]

def test_type_guard_numeric_strings_remain_distinct_from_numbers(table):
 c,t=table;values=[{'sector':'0'},{'sector':0},{'sector':False},{'sector':['0']},{'sector':{'value':'0'}},{'na_item':'0'},{}]
 c.execute(insert(t),[{'id':i,'provider':'Eurostat','slice':s} for i,s in enumerate(values,1)])
 got=c.execute(select(t.c.id).where(D._member_column(t.c.slice,'sector')=='0')).scalars().all()
 assert got==[1]
 assert D._members('Eurostat',values[0])['sector']=='0'
 assert 'sector' not in D._members('Eurostat',values[1])
 assert not D.native_dimension_labels('Eurostat',values[0])  # Unregistered numeric member has no semantic label.

@pytest.mark.parametrize('key,axis,member',[
 ('search-dim-education-levels-total','isced11','TOTAL'),
 ('search-dim-birth-countries-total','c_birth','TOTAL'),
 ('search-dim-contract-duration-under-one-month','duration','M_LT1'),
])
def test_named_facet_filters_before_LIMIT(table,key,axis,member):
 c,t=table;c.execute(insert(t),[{'id':i,'provider':'Eurostat','slice':{'citizen':'TOTAL','age':'Y15-74','worktime':'TOT_FTE'}} for i in range(1,136)]+[{'id':136,'provider':'Eurostat','slice':{axis:member}}])
 got=c.execute(select(t.c.id).where(*D.dimension_constraints(((key,),),t.c.provider,t.c.slice)).order_by(t.c.id).limit(1)).scalars().all()
 assert got==[136]

def test_unknown_typed_facets_fail_closed(table):
 c,t=table;c.execute(insert(t),{'id':1,'provider':'Eurostat','slice':{'isced11':'TOTAL'}})
 assert not c.execute(select(t.c.id).where(*D.dimension_constraints((('search-dim-unknown-total',),),t.c.provider,t.c.slice))).all()

def test_official_corrections_exclude_wrong_local_members(table):
 assert 'primary education' not in ' '.join(D.native_dimension_labels('Eurostat',{'isced11':'ED02'})).lower().replace('pre-primary education','')
 assert 'начальное' not in ' '.join(D.native_dimension_labels('Eurostat',{'isced11':'ED02'})).lower()
 texts=' '.join(D.native_dimension_labels('Eurostat',{'nace_r2':'M_STS'}))
 assert 'required by STS regulation' in texts and 'прочие услуги' not in texts
 assert not D.native_dimension_labels('other',{'nace_r2':'M_STS'})
 assert not D.native_dimension_labels('Eurostat',{'isced11':'ZZ_UNKNOWN'})

def test_relevant_official_labels_have_SQL_Python_witness_parity(table):
 c,t=table;values=[{'na_item':'P34'},{'na_item':'P31'},{'indic_em':'P34'},{}]
 c.execute(insert(t),[{'id':i,'provider':'Eurostat','slice':s} for i,s in enumerate(values,1)])
 exp=D.native_dimension_text(t.c.provider,t.c.slice,(('non-resident',),('households',)))
 rows=c.execute(select(t.c.id,exp).order_by(t.c.id)).all()
 assert 'non-resident' in rows[0][1] and 'нерезидентных' in rows[0][1]
 assert not rows[2][1] and not rows[3][1]
 assert 'non-resident' in ' '.join(D.native_dimension_labels('Eurostat',values[0]))

def test_contract_role_is_masked_before_month_calendar():
 text=D.prepare_dimensions('employment contract less than 1 month in 2025 monthly data')
 assert 'less than 1 month' not in text and '2025 monthly data' in text
 assert 'native facet contract duration under one month' in text
 assert D.prepare_dimensions('month 1 in 2025')=='month 1 in 2025'

def test_ge_age_long_span_prevents_exact_age_partial_match():
 text=D.prepare_dimensions('people aged 18 or over in 2025')
 assert 'aged 18' not in text and '2025' in text
 aliases={key:als for als,(key,) in D.DIMENSION_CONCEPTS}
 assert aliases['search-dim-age-y-ge18'][0] in text
 assert aliases['search-dim-age-y18'][0] not in text

def test_verified_age_bands_are_available_without_inventing_unknown_bands():
 assert D.dimension_metadata('Eurostat',{'age':'Y40-64'}).startswith('search-dim-age-y40-64')
 assert D.dimension_metadata('Eurostat',{'age':'Y15-59'}).startswith('search-dim-age-y15-59')
 assert D.prepare_dimensions('aged 40 64 in 2025')!='aged 40 64 in 2025'
 assert D.prepare_dimensions('aged 43 67 in 2025')=='aged 43 67 in 2025'

def test_named_total_is_not_a_free_label_or_any_other_total():
 assert not D.native_dimension_labels('Eurostat',{'isced11':'TOTAL','iscedf13':'TOTAL','c_birth':'TOTAL','worktime':'TOTAL'})
 assert D.prepare_dimensions('all total everyone all categories')=='all total everyone all categories'
 assert 'native facet education levels total' in D.prepare_dimensions('all education levels')
 assert 'native facet education fields total' in D.prepare_dimensions('all fields of study')

def test_postgresql_type_proof_and_query_expression_are_bounded(table):
 _c,t=table;expr=D.native_dimension_text(t.c.provider,t.c.slice,(('non-resident',),('households',)));sql=str(select(expr).compile(dialect=postgresql.dialect(),compile_kwargs={'literal_binds':True}))
 assert 'jsonb_typeof' in sql and "= 'string'" in sql
 assert len(sql)<15000
 empty=D.native_dimension_text(t.c.provider,t.c.slice,(('zzzz_unknown_token',),));q=str(select(empty).compile(dialect=postgresql.dialect(),compile_kwargs={'literal_binds':True}))
 assert 'jsonb_typeof' not in q
