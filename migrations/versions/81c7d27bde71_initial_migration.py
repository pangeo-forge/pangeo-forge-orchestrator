"""initial migration

Revision ID: 81c7d27bde71
Revises:
Create Date: 2022-01-19 12:52:39.059776

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "81c7d27bde71"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "reciperun",
        sa.Column("recipe_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("bakery_id", sa.Integer(), nullable=False),
        sa.Column("feedstock_id", sa.Integer(), nullable=False),
        sa.Column("head_sha", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("version", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("conclusion", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("reciperun")
    # ### end Alembic commands ###
