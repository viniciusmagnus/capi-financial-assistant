import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from conftest import RAIZ_BACKEND, _limpar_caches
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

DONO_LEGADO = "legado-pre-autenticacao"


@pytest.fixture
def banco_na_0005(banco, monkeypatch):
    url = make_url(os.environ["TEST_DATABASE_URL"])
    nome = f"nota_a_nota_legado_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url.set(drivername="postgresql+psycopg"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conexao:
        conexao.execute(text(f"CREATE DATABASE {nome}"))
    url_temporaria = url.set(database=nome).render_as_string(hide_password=False)
    monkeypatch.setenv("DATABASE_URL", url_temporaria)
    _limpar_caches()
    config = Config(str(RAIZ_BACKEND / "alembic.ini"))
    command.upgrade(config, "0005")
    motor = create_engine(url.set(database=nome, drivername="postgresql+psycopg"))
    yield config, motor
    motor.dispose()
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    _limpar_caches()
    with admin.connect() as conexao:
        conexao.execute(text(f"DROP DATABASE {nome} WITH (FORCE)"))
    admin.dispose()


def test_dados_antigos_vao_para_um_dono_que_nao_entra(banco_na_0005):
    config, motor = banco_na_0005
    with motor.begin() as conexao:
        conexao.execute(
            text("INSERT INTO perfil_financeiro (id, renda_mensal_centavos) VALUES (1, 500000)")
        )
        conexao.execute(
            text("INSERT INTO tetos_mensais (mes, valor_centavos) VALUES ('2026-10-01', 300000)")
        )
        transacao = conexao.execute(
            text(
                "INSERT INTO transacoes (data, descricao, origem) VALUES ('2026-10-02', 'X', 'manual') RETURNING id"
            )
        ).scalar_one()
        contas = dict(conexao.execute(text("SELECT nome, id FROM contas")).all())
        conexao.execute(
            text(
                "INSERT INTO lancamentos (transacao_id, conta_id, valor_centavos) VALUES "
                "(:t, :a, -100), (:t, :b, 100)"
            ),
            {"t": transacao, "a": contas["Ativo:Carteira"], "b": contas["Despesa:Mercado"]},
        )

    command.upgrade(config, "head")

    with motor.connect() as conexao:
        donos = {
            tabela: set(
                conexao.execute(text(f"SELECT DISTINCT usuario_id FROM {tabela}")).scalars()
            )
            for tabela in (
                "contas",
                "transacoes",
                "lancamentos",
                "perfil_financeiro",
                "tetos_mensais",
                "regras_categoria",
            )
        }
        legado = conexao.execute(
            text('SELECT email, "emailVerified" FROM "user" WHERE id = :u'), {"u": DONO_LEGADO}
        ).one()
        formas_de_entrar = conexao.execute(
            text('SELECT count(*) FROM "account" WHERE "userId" = :u'), {"u": DONO_LEGADO}
        ).scalar_one()

    assert all(d == {DONO_LEGADO} for d in donos.values()), donos
    assert legado.email.endswith(".invalid") and legado.emailVerified is False
    assert formas_de_entrar == 0


def test_banco_sem_dados_nao_cria_dono_legado(banco_na_0005):
    config, motor = banco_na_0005

    command.upgrade(config, "head")

    with motor.connect() as conexao:
        usuarios = conexao.execute(text('SELECT count(*) FROM "user"')).scalar_one()
        contas = conexao.execute(text("SELECT count(*) FROM contas")).scalar_one()
    assert (usuarios, contas) == (0, 0)
