"""autenticação (tabelas do Better Auth), dono em todo dado financeiro e tokens do MCP

Os dados que já existiam não são entregues a ninguém: ficam com um dono legado que não
consegue entrar (e-mail num domínio .invalid, sem senha e sem conta Google). Quem opera o
servidor transfere para a pessoa certa com `python -m nota_a_nota.legado --email ...`.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-23
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DONO_LEGADO = "legado-pre-autenticacao"

TABELAS_DO_BETTER_AUTH = [
    """CREATE TABLE "user" (
        "id" text NOT NULL PRIMARY KEY,
        "name" text NOT NULL,
        "email" text NOT NULL UNIQUE,
        "emailVerified" boolean NOT NULL,
        "image" text,
        "createdAt" timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
        "updatedAt" timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL
    )""",
    """CREATE TABLE "session" (
        "id" text NOT NULL PRIMARY KEY,
        "expiresAt" timestamptz NOT NULL,
        "token" text NOT NULL UNIQUE,
        "createdAt" timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
        "updatedAt" timestamptz NOT NULL,
        "ipAddress" text,
        "userAgent" text,
        "userId" text NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
    )""",
    """CREATE TABLE "account" (
        "id" text NOT NULL PRIMARY KEY,
        "accountId" text NOT NULL,
        "providerId" text NOT NULL,
        "userId" text NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
        "accessToken" text,
        "refreshToken" text,
        "idToken" text,
        "accessTokenExpiresAt" timestamptz,
        "refreshTokenExpiresAt" timestamptz,
        "scope" text,
        "password" text,
        "createdAt" timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
        "updatedAt" timestamptz NOT NULL
    )""",
    """CREATE TABLE "verification" (
        "id" text NOT NULL PRIMARY KEY,
        "identifier" text NOT NULL,
        "value" text NOT NULL,
        "expiresAt" timestamptz NOT NULL,
        "createdAt" timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL,
        "updatedAt" timestamptz DEFAULT CURRENT_TIMESTAMP NOT NULL
    )""",
    """CREATE TABLE "jwks" (
        "id" text NOT NULL PRIMARY KEY,
        "publicKey" text NOT NULL,
        "privateKey" text NOT NULL,
        "createdAt" timestamptz NOT NULL,
        "expiresAt" timestamptz,
        "alg" text,
        "crv" text
    )""",
    """CREATE TABLE "rateLimit" (
        "id" text NOT NULL PRIMARY KEY,
        "key" text NOT NULL UNIQUE,
        "count" integer NOT NULL,
        "lastRequest" bigint NOT NULL
    )""",
    'CREATE INDEX "session_userId_idx" ON "session" ("userId")',
    'CREATE INDEX "account_userId_idx" ON "account" ("userId")',
    'CREATE UNIQUE INDEX "account_provider_conta_idx" ON "account" ("providerId", "accountId")',
    'CREATE INDEX "verification_identifier_idx" ON "verification" ("identifier")',
]

TABELAS_COM_DONO = [
    "contas",
    "transacoes",
    "lancamentos",
    "regras_categoria",
    "perfil_financeiro",
    "importacoes",
    "tetos_mensais",
    "notas_fiscais",
    "itens_nota",
    "trechos",
]

HA_DADOS_ANTIGOS = """
SELECT EXISTS (SELECT 1 FROM transacoes) OR EXISTS (SELECT 1 FROM perfil_financeiro)
    OR EXISTS (SELECT 1 FROM tetos_mensais) OR EXISTS (SELECT 1 FROM importacoes)
    OR EXISTS (SELECT 1 FROM notas_fiscais)
"""

RESTRICOES_POR_USUARIO = [
    "ALTER TABLE contas DROP CONSTRAINT contas_nome_key",
    "ALTER TABLE contas ADD CONSTRAINT uq_conta_nome UNIQUE (usuario_id, nome)",
    "ALTER TABLE contas ADD CONSTRAINT uq_conta_dono UNIQUE (id, usuario_id)",
    "ALTER TABLE transacoes DROP CONSTRAINT uq_transacao_origem",
    "ALTER TABLE transacoes ADD CONSTRAINT uq_transacao_origem"
    " UNIQUE (usuario_id, origem, id_externo)",
    "ALTER TABLE transacoes ADD CONSTRAINT uq_transacao_dono UNIQUE (id, usuario_id)",
    "ALTER TABLE importacoes ADD CONSTRAINT uq_importacao_dono UNIQUE (id, usuario_id)",
    "ALTER TABLE notas_fiscais ADD CONSTRAINT uq_nota_dono UNIQUE (id, usuario_id)",
    "ALTER TABLE lancamentos ADD CONSTRAINT fk_lancamento_conta_do_dono"
    " FOREIGN KEY (conta_id, usuario_id) REFERENCES contas (id, usuario_id)",
    "ALTER TABLE lancamentos ADD CONSTRAINT fk_lancamento_transacao_do_dono"
    " FOREIGN KEY (transacao_id, usuario_id) REFERENCES transacoes (id, usuario_id)"
    " ON DELETE CASCADE",
    "ALTER TABLE importacoes ADD CONSTRAINT fk_importacao_conta_do_dono"
    " FOREIGN KEY (conta_id, usuario_id) REFERENCES contas (id, usuario_id)",
    "ALTER TABLE transacoes ADD CONSTRAINT fk_transacao_importacao_do_dono"
    " FOREIGN KEY (importacao_id, usuario_id) REFERENCES importacoes (id, usuario_id)"
    " ON DELETE SET NULL (importacao_id)",
    "ALTER TABLE notas_fiscais DROP CONSTRAINT notas_fiscais_chave_acesso_key",
    "ALTER TABLE notas_fiscais ADD CONSTRAINT uq_nota_chave UNIQUE (usuario_id, chave_acesso)",
    "ALTER TABLE notas_fiscais ADD CONSTRAINT fk_nota_transacao_do_dono"
    " FOREIGN KEY (transacao_id, usuario_id) REFERENCES transacoes (id, usuario_id)"
    " ON DELETE SET NULL (transacao_id)",
    "ALTER TABLE itens_nota ADD CONSTRAINT fk_item_nota_do_dono"
    " FOREIGN KEY (nota_id, usuario_id) REFERENCES notas_fiscais (id, usuario_id)"
    " ON DELETE CASCADE",
    "ALTER TABLE regras_categoria DROP CONSTRAINT regras_categoria_padrao_key",
    "ALTER TABLE regras_categoria ADD CONSTRAINT uq_regra_padrao UNIQUE (usuario_id, padrao)",
    "ALTER TABLE tetos_mensais DROP CONSTRAINT tetos_mensais_pkey",
    "ALTER TABLE tetos_mensais ADD PRIMARY KEY (usuario_id, mes)",
    "ALTER TABLE perfil_financeiro DROP CONSTRAINT ck_perfil_unico",
    "ALTER TABLE perfil_financeiro DROP CONSTRAINT perfil_financeiro_pkey",
    "ALTER TABLE perfil_financeiro DROP COLUMN id",
    "ALTER TABLE perfil_financeiro ADD PRIMARY KEY (usuario_id)",
]

TOKENS_MCP = """
CREATE TABLE tokens_mcp (
    id serial PRIMARY KEY,
    usuario_id text NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    nome varchar(60) NOT NULL,
    hash char(64) NOT NULL UNIQUE,
    prefixo varchar(16) NOT NULL,
    criado_em timestamptz NOT NULL DEFAULT now(),
    ultimo_uso_em timestamptz,
    revogado_em timestamptz
)
"""


def upgrade() -> None:
    for comando in TABELAS_DO_BETTER_AUTH:
        op.execute(comando)

    conexao = op.get_bind()
    tem_dados_antigos = conexao.execute(text(HA_DADOS_ANTIGOS)).scalar()
    if tem_dados_antigos:
        op.execute(
            f"""INSERT INTO "user" ("id", "name", "email", "emailVerified")
            VALUES ('{DONO_LEGADO}', 'Dados de antes da autenticação',
                    'dados-legados@nota-a-nota.invalid', false)"""
        )
    else:
        op.execute("DELETE FROM trechos")
        op.execute("DELETE FROM regras_categoria")
        op.execute("DELETE FROM contas")

    for tabela in TABELAS_COM_DONO:
        op.execute(f"ALTER TABLE {tabela} ADD COLUMN usuario_id text")
        if tem_dados_antigos:
            op.execute(f"UPDATE {tabela} SET usuario_id = '{DONO_LEGADO}'")
            op.execute("SET CONSTRAINTS ALL IMMEDIATE")
        op.execute(f"ALTER TABLE {tabela} ALTER COLUMN usuario_id SET NOT NULL")
        op.execute(
            f'ALTER TABLE {tabela} ADD CONSTRAINT fk_{tabela}_usuario FOREIGN KEY (usuario_id) REFERENCES "user" ("id") ON DELETE CASCADE'
        )
        op.execute(f"CREATE INDEX ix_{tabela}_usuario_id ON {tabela} (usuario_id)")

    for comando in RESTRICOES_POR_USUARIO:
        if "FOREIGN KEY" in comando:
            comando += " DEFERRABLE INITIALLY IMMEDIATE"
        op.execute(comando)
    op.execute(TOKENS_MCP)
    op.execute("CREATE INDEX ix_tokens_mcp_usuario_id ON tokens_mcp (usuario_id)")


def downgrade() -> None:
    conexao = op.get_bind()
    donos = conexao.execute(text("SELECT count(DISTINCT usuario_id) FROM contas")).scalar()
    if donos and donos > 1:
        raise RuntimeError(
            "há dados de mais de uma pessoa; voltar para antes da autenticação misturaria tudo"
        )
    op.execute("DROP TABLE tokens_mcp")
    op.execute("ALTER TABLE perfil_financeiro DROP CONSTRAINT perfil_financeiro_pkey")
    op.execute("ALTER TABLE perfil_financeiro ADD COLUMN id smallint NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE perfil_financeiro ADD PRIMARY KEY (id)")
    op.execute("ALTER TABLE perfil_financeiro ADD CONSTRAINT ck_perfil_unico CHECK (id = 1)")
    op.execute("ALTER TABLE tetos_mensais DROP CONSTRAINT tetos_mensais_pkey")
    op.execute("ALTER TABLE tetos_mensais ADD PRIMARY KEY (mes)")
    op.execute("ALTER TABLE regras_categoria DROP CONSTRAINT uq_regra_padrao")
    op.execute(
        "ALTER TABLE regras_categoria ADD CONSTRAINT regras_categoria_padrao_key UNIQUE (padrao)"
    )
    op.execute("ALTER TABLE notas_fiscais DROP CONSTRAINT uq_nota_chave")
    op.execute(
        "ALTER TABLE notas_fiscais ADD CONSTRAINT notas_fiscais_chave_acesso_key UNIQUE (chave_acesso)"
    )
    op.execute("ALTER TABLE transacoes DROP CONSTRAINT uq_transacao_origem")
    op.execute(
        "ALTER TABLE transacoes ADD CONSTRAINT uq_transacao_origem UNIQUE (origem, id_externo)"
    )
    op.execute("ALTER TABLE contas DROP CONSTRAINT uq_conta_nome")
    op.execute("ALTER TABLE contas ADD CONSTRAINT contas_nome_key UNIQUE (nome)")
    for tabela in reversed(TABELAS_COM_DONO):
        op.execute(f"ALTER TABLE {tabela} DROP COLUMN usuario_id CASCADE")
    for tabela in ("rateLimit", "jwks", "verification", "account", "session", "user"):
        op.execute(f'DROP TABLE "{tabela}"')
