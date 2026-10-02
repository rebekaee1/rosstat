"""Typed SQL guards retain their subject semantics before retrieval LIMIT."""
import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, select
from sqlalchemy.dialects import postgresql

from app.services.search_language_sql import _pattern_clause, measure_constraints


def test_typed_capital_guards_filter_before_limit():
    engine = create_engine('sqlite://')
    metadata = MetaData()
    rows = Table('rows', metadata, Column('code', String), Column('name', String))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(rows.insert(), [
            dict(code='aaa', name='Gross fixed capital formation'),
            dict(code='bbb', name='Gross capital formation'),
        ])
        query = select(rows.c.code).where(*measure_constraints((('capital-formation',),), rows.c.code, (rows.c.name,), postgres=False)).order_by(rows.c.code).limit(1)
        assert connection.execute(query).scalar_one() == 'bbb'


def test_multiple_required_patterns_and_null_exclusions():
    engine = create_engine('sqlite://')
    metadata = MetaData()
    rows = Table('rows', metadata, Column('code', String), Column('name', String))
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(rows.insert(), [
            dict(code='mortgage-rate', name=None),
            dict(code='deposit-rate', name='Deposit mortgage interest rate'),
            dict(code='credit-rate', name='Lending interest rate'),
        ])
        query = select(rows.c.code).where(*measure_constraints((('credit-rate',),), rows.c.code, (rows.c.name,), postgres=False))
        assert connection.execute(query).scalars().all() == ['credit-rate']


def test_postgres_guard_uses_native_regex_without_seo_fields():
    rows = Table('rows', MetaData(), Column('code', String), Column('name', String))
    query = select(rows.c.code).where(*measure_constraints((('labour-productivity',),), rows.c.code, (rows.c.name,), postgres=True))
    compiled = str(query.compile(dialect=postgresql.dialect()))
    assert '~' in compiled
    assert 'lower' in compiled and 'coalesce' in compiled
    assert 'seo' not in compiled


def test_unknown_measure_adds_no_invented_constraint():
    rows = Table('rows', MetaData(), Column('code', String), Column('name', String))
    assert measure_constraints((('unknown-measure',),), rows.c.code, (rows.c.name,), postgres=False) == []


def test_sqlite_rejects_unimplemented_regex_syntax():
    rows = Table('rows', MetaData(), Column('code', String))
    with pytest.raises(ValueError, match='unsupported SQLite search measure pattern'):
        _pattern_clause(rows.c.code, r'price[0-9]+', postgres=False)
