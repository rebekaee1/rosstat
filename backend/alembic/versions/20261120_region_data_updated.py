"""Дата последнего изменения данных регионального ряда; переименование нетуристических рядов (20.11.2026).

Revision ID: 20261120_region_data_updated
Revises: 20261120_world_tourism_cat

Только добавление: `region_indicators.data_updated_at` (дата, когда загрузчик последний раз добавил или изменил точку
ряда; пусто — загрузчик дату не ведёт). Нужна странице показателя по региону для строки «как цитировать» (круг
наблюдателей 20.11.2026, №2/№5). Пишет пока загрузчик туризма по регионам (`tourism_regional_loader`).

Данные: городские автобусы и общепит выведены из туризма (№37) — коды `tour-…` переименованы на месте, точки
сохраняются (если новый код уже есть, старый не трогается). Откат: колонка удаляется, коды возвращаются.
"""
import sqlalchemy as sa
from alembic import op

revision = "20261120_region_data_updated"
down_revision = "20261120_world_tourism_cat"
branch_labels = None
depends_on = None

RENAMED = {
    "tour-avtobusy-passazhiry": "avtobusy-passazhiry-mes",
    "tour-obshchepit-oborot-mes": "obshchepit-oborot-mes",
    "tour-obshchepit-restorany": "obshchepit-restorany",
    "tour-obshchepit-stolovye": "obshchepit-stolovye",
    "tour-obshchepit-rezultat-restorany": "obshchepit-rezultat-restorany",
}


def _rename(pairs: dict[str, str]) -> None:
    for old, new in pairs.items():
        op.execute(sa.text(
            "UPDATE region_indicators SET code = :new WHERE code = :old "
            "AND NOT EXISTS (SELECT 1 FROM region_indicators WHERE code = :new)"
        ).bindparams(old=old, new=new))


def upgrade() -> None:
    op.add_column("region_indicators", sa.Column("data_updated_at", sa.Date(), nullable=True))
    _rename(RENAMED)


def downgrade() -> None:
    _rename({new: old for old, new in RENAMED.items()})
    op.drop_column("region_indicators", "data_updated_at")
