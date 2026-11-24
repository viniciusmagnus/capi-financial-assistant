"""teto de gastos do mês e conta da carteira para gastos anotados à mão

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = [
    """
    CREATE TABLE tetos_mensais (
        mes DATE PRIMARY KEY,
        valor_centavos BIGINT NOT NULL,
        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT ck_teto_positivo CHECK (valor_centavos > 0),
        CONSTRAINT ck_teto_primeiro_dia CHECK (extract(day FROM mes) = 1)
    )
    """,
    "INSERT INTO contas (nome, tipo) VALUES ('Ativo:Carteira', 'ativo') ON CONFLICT (nome) DO NOTHING",
]

DOWNGRADE = [
    "DROP TABLE tetos_mensais",
]


def upgrade() -> None:
    for comando in UPGRADE:
        op.execute(comando)


def downgrade() -> None:
    for comando in DOWNGRADE:
        op.execute(comando)
