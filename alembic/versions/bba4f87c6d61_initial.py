import sqlalchemy as sa

from alembic import op

revision = "bba4f87c6d61"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urt30t_players",
        sa.Column("pid", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("auth", sa.String(length=32), nullable=False),
        sa.Column("guid", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("group", sa.Integer(), nullable=False),
        sa.Column("xp", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("pid"),
    )
    op.create_index(
        op.f("ix_urt30t_players_auth"), "urt30t_players", ["auth"], unique=True
    )
    op.create_index(
        op.f("ix_urt30t_players_guid"), "urt30t_players", ["guid"], unique=True
    )
    op.create_table(
        "urt30t_aliases",
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=32), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pid"],
            ["urt30t_players.pid"],
        ),
        sa.PrimaryKeyConstraint("pid", "alias"),
    )
    op.create_table(
        "urt30t_connections",
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pid"],
            ["urt30t_players.pid"],
        ),
        sa.PrimaryKeyConstraint("pid", "created_at"),
    )
    op.create_table(
        "urt30t_guids",
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("guid", sa.String(length=32), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pid"],
            ["urt30t_players.pid"],
        ),
        sa.PrimaryKeyConstraint("pid", "guid"),
    )
    op.create_table(
        "urt30t_ip_addresses",
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column("address", sa.String(length=64), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pid"],
            ["urt30t_players.pid"],
        ),
        sa.PrimaryKeyConstraint("pid", "address"),
    )
    op.create_table(
        "urt30t_penalties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pid", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("kick", "tempban", "permban", name="penalty", length=20),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pid"],
            ["urt30t_players.pid"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("urt30t_penalties")
    op.drop_table("urt30t_ip_addresses")
    op.drop_table("urt30t_guids")
    op.drop_table("urt30t_connections")
    op.drop_table("urt30t_aliases")
    op.drop_index(op.f("ix_urt30t_players_guid"), table_name="urt30t_players")
    op.drop_index(op.f("ix_urt30t_players_auth"), table_name="urt30t_players")
    op.drop_table("urt30t_players")
