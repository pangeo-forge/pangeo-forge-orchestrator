"""add_bakery_and_feedstock

Revision ID: 6197f9c7aff6
Revises: 81c7d27bde71
Create Date: 2022-01-21 15:20:32.472135

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "6197f9c7aff6"
down_revision = "81c7d27bde71"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "bakery",
        sa.Column("region", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "feedstock",
        sa.Column("spec", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(None, "reciperun", "bakery", ["bakery_id"], ["id"])
    op.create_foreign_key(None, "reciperun", "feedstock", ["feedstock_id"], ["id"])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "reciperun", type_="foreignkey")
    op.drop_constraint(None, "reciperun", type_="foreignkey")
    op.drop_table("feedstock")
    op.drop_table("bakery")
    # ### end Alembic commands ###
