"""Идентификаторы ревизий Alembic и цепочка миграций.

`alembic_version.version_num` в PostgreSQL имеет тип varchar(32): ревизия длиннее 32 символов проходит на SQLite и падает
при записи версии на боевой базе («value too long for type character varying(32)»). Так сорвался первый боевой
выпуск круга 12 (12.10.2026): бэкенд не стартовал. Тест ловит такую ревизию до выпуска.
"""
import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
_REV = re.compile(r'^revision\s*(?::[^=\n]+)?=\s*["\']([^"\']+)["\']', re.M)
_DOWN = re.compile(r'^down_revision\s*(?::[^=\n]+)?=\s*(None|["\']([^"\']+)["\'])', re.M)


def _revisions():
    rows = {}
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf8")
        rev = _REV.search(text)
        if not rev:
            continue
        down = _DOWN.search(text)
        rows[rev.group(1)] = (path.name, down.group(2) if down and down.group(2) else None)
    return rows


def test_revision_ids_fit_version_num_column():
    too_long = {rev: name for rev, (name, _) in _revisions().items() if len(rev) > 32}
    assert not too_long, f"ревизии длиннее 32 символов (колонка alembic_version.version_num): {too_long}"


def test_single_head_and_known_parents():
    rows = _revisions()
    parents = {down for _, down in rows.values() if down}
    unknown = parents - set(rows)
    assert not unknown, f"down_revision указывает на несуществующую ревизию: {unknown}"
    heads = [rev for rev in rows if rev not in parents]
    assert len(heads) == 1, f"ожидалась одна голова миграций, найдено: {heads}"
