"""revisão assistida de "Outros": estabelecimento normalizado, regras que só nomeiam o
estabelecimento, conversas, propostas, lotes aplicados e o registro de cada alteração

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGORA = "timestamptz NOT NULL DEFAULT now()"
DONO = 'usuario_id text NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE'

COMANDOS = [
    "ALTER TABLE transacoes ADD COLUMN estabelecimento varchar(80)",
    "ALTER TABLE regras_categoria ALTER COLUMN categoria DROP NOT NULL",
    "ALTER TABLE regras_categoria ADD COLUMN estabelecimento varchar(80)",
    f"ALTER TABLE regras_categoria ADD COLUMN atualizada_em {AGORA}",
    "ALTER TABLE regras_categoria ADD CONSTRAINT ck_regra_faz_algo"
    " CHECK (categoria IS NOT NULL OR estabelecimento IS NOT NULL)",
    "ALTER TABLE regras_categoria ADD CONSTRAINT uq_regra_dono UNIQUE (id, usuario_id)",
    f"""CREATE TABLE revisao_conversas (
        id serial PRIMARY KEY,
        {DONO},
        mensagens jsonb NOT NULL DEFAULT '[]',
        historico jsonb NOT NULL DEFAULT '[]',
        fontes jsonb NOT NULL DEFAULT '[]',
        criada_em {AGORA},
        atualizada_em {AGORA},
        CONSTRAINT uq_revisao_conversa_dono UNIQUE (id, usuario_id)
    )""",
    f"""CREATE TABLE revisao_propostas (
        id serial PRIMARY KEY,
        {DONO},
        conversa_id integer,
        status varchar(12) NOT NULL DEFAULT 'pendente'
            CHECK (status IN ('pendente', 'aplicada', 'rejeitada')),
        conteudo jsonb NOT NULL,
        criada_em {AGORA},
        decidida_em timestamptz,
        CONSTRAINT uq_revisao_proposta_dono UNIQUE (id, usuario_id),
        CONSTRAINT fk_proposta_conversa_do_dono FOREIGN KEY (conversa_id, usuario_id)
            REFERENCES revisao_conversas (id, usuario_id) ON DELETE CASCADE
            DEFERRABLE INITIALLY IMMEDIATE
    )""",
    f"""CREATE TABLE revisao_lotes (
        id serial PRIMARY KEY,
        {DONO},
        chave_idempotencia varchar(64) NOT NULL,
        proposta_id integer,
        regra_id integer,
        regra_criada boolean NOT NULL DEFAULT false,
        regra_anterior jsonb,
        opcoes jsonb NOT NULL,
        resumo text NOT NULL,
        criado_em {AGORA},
        desfeito_em timestamptz,
        CONSTRAINT uq_revisao_lote_chave UNIQUE (usuario_id, chave_idempotencia),
        CONSTRAINT uq_revisao_lote_dono UNIQUE (id, usuario_id),
        CONSTRAINT fk_lote_proposta_do_dono FOREIGN KEY (proposta_id, usuario_id)
            REFERENCES revisao_propostas (id, usuario_id) ON DELETE SET NULL (proposta_id)
            DEFERRABLE INITIALLY IMMEDIATE,
        CONSTRAINT fk_lote_regra_do_dono FOREIGN KEY (regra_id, usuario_id)
            REFERENCES regras_categoria (id, usuario_id) ON DELETE SET NULL (regra_id)
            DEFERRABLE INITIALLY IMMEDIATE
    )""",
    f"""CREATE TABLE revisao_alteracoes (
        id serial PRIMARY KEY,
        {DONO},
        lote_id integer NOT NULL,
        transacao_id integer NOT NULL,
        categoria_anterior varchar(120) NOT NULL,
        categoria_nova varchar(120) NOT NULL,
        estabelecimento_anterior varchar(80),
        estabelecimento_novo varchar(80),
        categorizada_por_anterior origem_categoria,
        categorizada_por_nova origem_categoria,
        origem varchar(12) NOT NULL CHECK (origem IN ('usuario', 'regra', 'historico', 'pesquisa')),
        regra_id integer,
        CONSTRAINT fk_alteracao_lote_do_dono FOREIGN KEY (lote_id, usuario_id)
            REFERENCES revisao_lotes (id, usuario_id) ON DELETE CASCADE
            DEFERRABLE INITIALLY IMMEDIATE,
        CONSTRAINT fk_alteracao_transacao_do_dono FOREIGN KEY (transacao_id, usuario_id)
            REFERENCES transacoes (id, usuario_id) ON DELETE CASCADE
            DEFERRABLE INITIALLY IMMEDIATE,
        CONSTRAINT fk_alteracao_regra_do_dono FOREIGN KEY (regra_id, usuario_id)
            REFERENCES regras_categoria (id, usuario_id) ON DELETE SET NULL (regra_id)
            DEFERRABLE INITIALLY IMMEDIATE
    )""",
    "CREATE INDEX ix_revisao_conversas_usuario_id ON revisao_conversas (usuario_id)",
    "CREATE INDEX ix_revisao_propostas_usuario_id ON revisao_propostas (usuario_id)",
    "CREATE INDEX ix_revisao_lotes_usuario_id ON revisao_lotes (usuario_id)",
    "CREATE INDEX ix_revisao_alteracoes_usuario_id ON revisao_alteracoes (usuario_id)",
    "CREATE INDEX ix_revisao_alteracoes_lote_id ON revisao_alteracoes (lote_id)",
    "CREATE INDEX ix_revisao_alteracoes_transacao_id ON revisao_alteracoes (transacao_id)",
]


def upgrade() -> None:
    for comando in COMANDOS:
        op.execute(comando)


def downgrade() -> None:
    for tabela in ("revisao_alteracoes", "revisao_lotes", "revisao_propostas", "revisao_conversas"):
        op.execute(f"DROP TABLE {tabela}")
    op.execute("DELETE FROM regras_categoria WHERE categoria IS NULL")
    op.execute("ALTER TABLE regras_categoria DROP CONSTRAINT uq_regra_dono")
    op.execute("ALTER TABLE regras_categoria DROP CONSTRAINT ck_regra_faz_algo")
    op.execute("ALTER TABLE regras_categoria DROP COLUMN atualizada_em")
    op.execute("ALTER TABLE regras_categoria DROP COLUMN estabelecimento")
    op.execute("ALTER TABLE regras_categoria ALTER COLUMN categoria SET NOT NULL")
    op.execute("ALTER TABLE transacoes DROP COLUMN estabelecimento")
