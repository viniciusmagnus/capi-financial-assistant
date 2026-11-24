"""revisão de "Outros" vira um botão com aprovação em modal: saem as conversas e as propostas
guardadas, ficam os lotes aplicados e o registro de cada alteração

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGORA = "timestamptz NOT NULL DEFAULT now()"
DONO = 'usuario_id text NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE'


def upgrade() -> None:
    op.execute("ALTER TABLE revisao_lotes DROP CONSTRAINT fk_lote_proposta_do_dono")
    op.execute("ALTER TABLE revisao_lotes DROP COLUMN proposta_id")
    op.execute("DROP TABLE revisao_propostas")
    op.execute("DROP TABLE revisao_conversas")


def downgrade() -> None:
    op.execute(
        f"""CREATE TABLE revisao_conversas (
            id serial PRIMARY KEY,
            {DONO},
            mensagens jsonb NOT NULL DEFAULT '[]',
            historico jsonb NOT NULL DEFAULT '[]',
            fontes jsonb NOT NULL DEFAULT '[]',
            criada_em {AGORA},
            atualizada_em {AGORA},
            CONSTRAINT uq_revisao_conversa_dono UNIQUE (id, usuario_id)
        )"""
    )
    op.execute(
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
        )"""
    )
    op.execute("CREATE INDEX ix_revisao_conversas_usuario_id ON revisao_conversas (usuario_id)")
    op.execute("CREATE INDEX ix_revisao_propostas_usuario_id ON revisao_propostas (usuario_id)")
    op.execute("ALTER TABLE revisao_lotes ADD COLUMN proposta_id integer")
    op.execute(
        "ALTER TABLE revisao_lotes ADD CONSTRAINT fk_lote_proposta_do_dono"
        " FOREIGN KEY (proposta_id, usuario_id) REFERENCES revisao_propostas (id, usuario_id)"
        " ON DELETE SET NULL (proposta_id) DEFERRABLE INITIALLY IMMEDIATE"
    )
