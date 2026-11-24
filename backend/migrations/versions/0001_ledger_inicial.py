"""ledger inicial, notas fiscais e trechos para RAG

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPGRADE = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE TYPE tipo_conta AS ENUM ('ativo', 'passivo', 'patrimonio', 'receita', 'despesa')",
    "CREATE TYPE origem_categoria AS ENUM ('regra', 'claude', 'usuario')",
    """
    CREATE TABLE contas (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(120) NOT NULL UNIQUE,
        tipo tipo_conta NOT NULL,
        criada_em TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE transacoes (
        id SERIAL PRIMARY KEY,
        data DATE NOT NULL,
        descricao TEXT NOT NULL,
        origem VARCHAR(20) NOT NULL,
        id_externo VARCHAR(200),
        categorizada_por origem_categoria,
        criada_em TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_transacao_origem UNIQUE (origem, id_externo)
    )
    """,
    "CREATE INDEX ix_transacoes_data ON transacoes (data)",
    """
    CREATE TABLE lancamentos (
        id SERIAL PRIMARY KEY,
        transacao_id INTEGER NOT NULL REFERENCES transacoes (id) ON DELETE CASCADE,
        conta_id INTEGER NOT NULL REFERENCES contas (id),
        valor_centavos BIGINT NOT NULL,
        CONSTRAINT ck_lancamento_nao_zero CHECK (valor_centavos <> 0)
    )
    """,
    "CREATE INDEX ix_lancamentos_conta_id ON lancamentos (conta_id)",
    "CREATE INDEX ix_lancamentos_transacao_id ON lancamentos (transacao_id)",
    """
    CREATE TABLE notas_fiscais (
        id SERIAL PRIMARY KEY,
        chave_acesso VARCHAR(44) NOT NULL UNIQUE,
        uf VARCHAR(2) NOT NULL,
        cnpj_emitente VARCHAR(14) NOT NULL,
        emitente_nome TEXT,
        emitida_em TIMESTAMPTZ,
        total_centavos BIGINT,
        transacao_id INTEGER REFERENCES transacoes (id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX ix_notas_fiscais_cnpj_emitente ON notas_fiscais (cnpj_emitente)",
    """
    CREATE TABLE itens_nota (
        id SERIAL PRIMARY KEY,
        nota_id INTEGER NOT NULL REFERENCES notas_fiscais (id) ON DELETE CASCADE,
        descricao TEXT NOT NULL,
        produto_canonico TEXT,
        codigo VARCHAR(60),
        quantidade NUMERIC(14, 4) NOT NULL,
        unidade VARCHAR(10),
        valor_unitario_centavos BIGINT NOT NULL,
        valor_total_centavos BIGINT NOT NULL
    )
    """,
    "CREATE INDEX ix_itens_nota_nota_id ON itens_nota (nota_id)",
    "CREATE INDEX ix_itens_nota_produto_canonico ON itens_nota (produto_canonico)",
    """
    CREATE TABLE trechos (
        id SERIAL PRIMARY KEY,
        fonte_tipo VARCHAR(20) NOT NULL,
        fonte_id BIGINT NOT NULL,
        ordem INTEGER NOT NULL DEFAULT 0,
        texto TEXT NOT NULL,
        embedding VECTOR(1024),
        tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('portuguese', texto)) STORED NOT NULL,
        CONSTRAINT uq_trecho_fonte UNIQUE (fonte_tipo, fonte_id, ordem)
    )
    """,
    "CREATE INDEX ix_trechos_embedding ON trechos USING hnsw (embedding vector_cosine_ops)",
    "CREATE INDEX ix_trechos_tsv ON trechos USING gin (tsv)",
    """
    CREATE FUNCTION exigir_transacao_balanceada() RETURNS trigger AS $$
    DECLARE
        alvo BIGINT := COALESCE(NEW.transacao_id, OLD.transacao_id);
        soma BIGINT;
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM transacoes WHERE id = alvo) THEN
            RETURN NULL;
        END IF;
        SELECT COALESCE(SUM(valor_centavos), 0) INTO soma
        FROM lancamentos WHERE transacao_id = alvo;
        IF soma <> 0 THEN
            RAISE EXCEPTION 'transacao % desbalanceada: soma dos lancamentos = %', alvo, soma;
        END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE CONSTRAINT TRIGGER lancamentos_balanceados
    AFTER INSERT OR UPDATE OR DELETE ON lancamentos
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION exigir_transacao_balanceada()
    """,
    """
    INSERT INTO contas (nome, tipo) VALUES
        ('Despesa:A classificar', 'despesa'),
        ('Receita:A classificar', 'receita'),
        ('Patrimonio:Transferência interna', 'patrimonio'),
        ('Patrimonio:Saldo de abertura', 'patrimonio'),
        ('Despesa:Moradia', 'despesa'),
        ('Despesa:Mercado', 'despesa'),
        ('Despesa:Restaurantes e delivery', 'despesa'),
        ('Despesa:Transporte', 'despesa'),
        ('Despesa:Saúde', 'despesa'),
        ('Despesa:Educação', 'despesa'),
        ('Despesa:Lazer', 'despesa'),
        ('Despesa:Assinaturas', 'despesa'),
        ('Despesa:Vestuário', 'despesa'),
        ('Despesa:Pets', 'despesa'),
        ('Despesa:Impostos e taxas', 'despesa'),
        ('Despesa:Presentes e doações', 'despesa'),
        ('Despesa:Outros', 'despesa'),
        ('Receita:Salário', 'receita'),
        ('Receita:Rendimentos', 'receita'),
        ('Receita:Reembolsos', 'receita'),
        ('Receita:Outras receitas', 'receita')
    """,
]

DOWNGRADE = [
    "DROP TABLE IF EXISTS trechos, itens_nota, notas_fiscais, lancamentos, transacoes, contas",
    "DROP FUNCTION IF EXISTS exigir_transacao_balanceada()",
    "DROP TYPE IF EXISTS origem_categoria",
    "DROP TYPE IF EXISTS tipo_conta",
]


def upgrade() -> None:
    for comando in UPGRADE:
        op.execute(comando)


def downgrade() -> None:
    for comando in DOWNGRADE:
        op.execute(comando)
