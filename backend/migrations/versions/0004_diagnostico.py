"""renda mensal, importações com período coberto e confiança da categorização

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REGRAS_DE_TRANSFERENCIA = ["PAGTO FATURA", "PAGAMENTO FATURA", "PAG FATURA", "PAGAMENTO RECEBIDO"]

UPGRADE = [
    """
    CREATE TABLE perfil_financeiro (
        id SMALLINT PRIMARY KEY DEFAULT 1,
        renda_mensal_centavos BIGINT NOT NULL,
        renda_variavel BOOLEAN NOT NULL DEFAULT false,
        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT ck_perfil_unico CHECK (id = 1),
        CONSTRAINT ck_renda_nao_negativa CHECK (renda_mensal_centavos >= 0)
    )
    """,
    """
    CREATE TABLE importacoes (
        id SERIAL PRIMARY KEY,
        conta_id INTEGER NOT NULL REFERENCES contas(id),
        arquivo VARCHAR(200),
        inicio DATE,
        fim DATE,
        novas INTEGER NOT NULL,
        duplicadas INTEGER NOT NULL,
        criada_em TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT ck_importacao_periodo CHECK (inicio IS NULL OR fim IS NULL OR inicio <= fim)
    )
    """,
    "CREATE INDEX ix_importacoes_conta_id ON importacoes (conta_id)",
    """
    ALTER TABLE transacoes
        ADD COLUMN importacao_id INTEGER REFERENCES importacoes(id) ON DELETE SET NULL,
        ADD COLUMN confianca_categoria VARCHAR(5),
        ADD CONSTRAINT ck_confianca_categoria
            CHECK (confianca_categoria IN ('alta', 'media', 'baixa'))
    """,
    "CREATE INDEX ix_transacoes_importacao_id ON transacoes (importacao_id)",
    """
    INSERT INTO importacoes (conta_id, arquivo, inicio, fim, novas, duplicadas)
    SELECT l.conta_id, 'importado antes do diagnóstico', min(t.data), max(t.data), count(*), 0
    FROM transacoes t
    JOIN lancamentos l ON l.transacao_id = t.id
    JOIN contas c ON c.id = l.conta_id
    WHERE t.origem = 'ofx' AND c.tipo IN ('ativo', 'passivo')
    GROUP BY l.conta_id
    """,
    """
    UPDATE transacoes t
    SET importacao_id = i.id
    FROM lancamentos l
    JOIN importacoes i ON i.conta_id = l.conta_id
    WHERE l.transacao_id = t.id AND t.origem = 'ofx'
    """,
    "INSERT INTO regras_categoria (padrao, categoria) VALUES "
    + ", ".join(f"('{padrao}', 'Transferência interna')" for padrao in REGRAS_DE_TRANSFERENCIA)
    + " ON CONFLICT (padrao) DO NOTHING",
]

DOWNGRADE = [
    "DELETE FROM regras_categoria WHERE padrao IN ("
    + ", ".join(f"'{padrao}'" for padrao in REGRAS_DE_TRANSFERENCIA)
    + ")",
    "ALTER TABLE transacoes DROP COLUMN confianca_categoria, DROP COLUMN importacao_id",
    "DROP TABLE importacoes",
    "DROP TABLE perfil_financeiro",
]


def upgrade() -> None:
    for comando in UPGRADE:
        op.execute(comando)


def downgrade() -> None:
    for comando in DOWNGRADE:
        op.execute(comando)
