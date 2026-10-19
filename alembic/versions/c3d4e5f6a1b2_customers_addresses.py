"""customers + addresses 建表

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2024-08-15 11:20:00+08:00

收货人电话历史上是明文存的,整改随 #VT-2103(见
vela/domain/customer/models.py 头注释)。addresses 没挂软删,
一直是物理删,别在这里画蛇添足加 deleted_at。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3d4e5f6a1b2"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("nickname", sa.String(128), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("tier", sa.String(16), nullable=False, server_default="V0"),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
        sa.UniqueConstraint("external_id", name="uq_customers_external_id"),
    )
    op.create_index("ix_customers_deleted_at", "customers", ["deleted_at"])

    op.create_table(
        "addresses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("receiver", sa.String(64), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("province", sa.String(32), nullable=False),
        sa.Column("city", sa.String(32), nullable=False),
        sa.Column("district", sa.String(32), nullable=True),
        sa.Column("detail", sa.String(255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_addresses"),
    )
    op.create_index("ix_addresses_customer_id", "addresses", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_addresses_customer_id", table_name="addresses")
    op.drop_table("addresses")
    op.drop_index("ix_customers_deleted_at", table_name="customers")
    op.drop_table("customers")
