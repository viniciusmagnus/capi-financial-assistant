"""banco e número nas contas, para reconhecer conta e cartão sem apelido

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REGRAS_DE_TRANSFERENCIA = ["PAGAMENTO EM", "PAGAMENTO DE FATURA"]

UPGRADE = [
    "ALTER TABLE contas ADD COLUMN banco VARCHAR(40), ADD COLUMN numero VARCHAR(60)",
    """
    UPDATE contas c
    SET numero = origem.numero
    FROM (
        SELECT DISTINCT ON (l.conta_id) l.conta_id, split_part(t.id_externo, ':', 1) AS numero
        FROM transacoes t
        JOIN lancamentos l ON l.transacao_id = t.id
        JOIN contas c2 ON c2.id = l.conta_id
        WHERE t.origem = 'ofx' AND c2.tipo IN ('ativo', 'passivo')
        ORDER BY l.conta_id, t.id DESC
    ) AS origem
    WHERE c.id = origem.conta_id
    """,
    "INSERT INTO regras_categoria (padrao, categoria) VALUES "
    + ", ".join(f"('{padrao}', 'Transferência interna')" for padrao in REGRAS_DE_TRANSFERENCIA)
    + " ON CONFLICT (padrao) DO NOTHING",
]

DOWNGRADE = [
    "DELETE FROM regras_categoria WHERE padrao IN ("
    + ", ".join(f"'{padrao}'" for padrao in REGRAS_DE_TRANSFERENCIA)
    + ")",
    "ALTER TABLE contas DROP COLUMN numero, DROP COLUMN banco",
]


def upgrade() -> None:
    for comando in UPGRADE:
        op.execute(comando)


def downgrade() -> None:
    for comando in DOWNGRADE:
        op.execute(comando)
