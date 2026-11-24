import os
import time
import uuid
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import insert, text

from nota_a_nota import autenticacao, regras
from nota_a_nota.acesso import abrir_sessao, usuario_atual
from nota_a_nota.config import get_settings
from nota_a_nota.db import get_engine, get_sessionmaker
from nota_a_nota.ledger import criar_contas_padrao
from nota_a_nota.models import Usuario

RAIZ_BACKEND = Path(__file__).resolve().parents[1]
CHAVE_DE_TESTE = Ed25519PrivateKey.generate()


def _limpar_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _sem_chaves_reais():
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ANTHROPIC_API_KEY", "")
        mp.setenv("VOYAGE_API_KEY", "")
        mp.setattr(autenticacao, "chave_de_assinatura", lambda _token: CHAVE_DE_TESTE.public_key())
        _limpar_caches()
        yield
    _limpar_caches()


def emitir_jwt(usuario_id: str, **mudancas) -> str:
    settings = get_settings()
    agora = int(time.time())
    dados = {
        "sub": usuario_id,
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
        "iat": agora,
        "exp": agora + 300,
        "email_verified": True,
    } | mudancas
    dados = {k: v for k, v in dados.items() if v is not None}
    return jwt.encode(dados, CHAVE_DE_TESTE, algorithm="EdDSA")


@pytest.fixture(scope="session")
def banco():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL não definido")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URL", url)
        _limpar_caches()
        config = Config(str(RAIZ_BACKEND / "alembic.ini"))
        with get_engine().begin() as conexao:
            if conexao.execute(text("""SELECT to_regclass('public."user"')""")).scalar():
                conexao.execute(text('TRUNCATE "user" CASCADE'))
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        yield
        get_engine().dispose()
    _limpar_caches()


def criar_usuario(verificado: bool = True, provisionar: bool = True) -> str:
    usuario_id = f"teste-{uuid.uuid4()}"
    with get_sessionmaker()() as session:
        session.execute(
            insert(Usuario).values(
                id=usuario_id,
                name="Pessoa de teste",
                email=f"{usuario_id}@exemplo.test",
                email_verificado=verificado,
            )
        )
        session.commit()
    if provisionar:
        with abrir_sessao(usuario_id) as session:
            criar_contas_padrao(session)
            regras.criar_regras_padrao(session)
            session.commit()
    return usuario_id


@pytest.fixture(scope="session")
def cliente():
    from fastapi.testclient import TestClient

    from nota_a_nota.main import app

    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def usuario(banco) -> str:
    return criar_usuario()


@pytest.fixture
def session(usuario):
    marca = usuario_atual.set(usuario)
    with abrir_sessao(usuario) as session:
        yield session
        session.rollback()
    usuario_atual.reset(marca)
