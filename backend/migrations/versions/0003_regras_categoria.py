"""regras de categoria definidas pela pessoa, aplicadas antes do Claude

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REGRAS_INICIAIS = [
    ("UBER EATS", "Restaurantes e delivery"),
    ("UBER", "Transporte"),
    ("IFD", "Restaurantes e delivery"),
    ("IFOOD", "Restaurantes e delivery"),
    ("RAPPI", "Restaurantes e delivery"),
    ("ZAFFARI", "Mercado"),
    ("CARREFOUR", "Mercado"),
    ("ASSAI", "Mercado"),
    ("ATACADAO", "Mercado"),
    ("NETFLIX", "Assinaturas"),
    ("SPOTIFY", "Assinaturas"),
    ("DISNEY", "Assinaturas"),
    ("DROGASIL", "Saúde"),
    ("PANVEL", "Saúde"),
    ("FARMACIA", "Saúde"),
    ("POSTO", "Transporte"),
    ("SALARIO", "Salário"),
    ("RENDIMENTO", "Rendimentos"),
    ("ESTORNO", "Reembolsos"),
]

UPGRADE = [
    """
    CREATE TABLE regras_categoria (
        id SERIAL PRIMARY KEY,
        padrao VARCHAR(120) NOT NULL UNIQUE,
        categoria VARCHAR(60) NOT NULL,
        criada_em TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    "INSERT INTO regras_categoria (padrao, categoria) VALUES "
    + ", ".join(f"('{padrao}', '{categoria}')" for padrao, categoria in REGRAS_INICIAIS),
]

DOWNGRADE = [
    "DROP TABLE regras_categoria",
]


def upgrade() -> None:
    for comando in UPGRADE:
        op.execute(comando)


def downgrade() -> None:
    for comando in DOWNGRADE:
        op.execute(comando)
