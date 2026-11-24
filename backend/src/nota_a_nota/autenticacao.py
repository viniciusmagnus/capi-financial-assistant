import hashlib
import secrets
from datetime import UTC, datetime
from functools import lru_cache

import jwt
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from nota_a_nota.config import get_settings
from nota_a_nota.models import TokenMcp, Usuario

ALGORITMOS = ["EdDSA"]
PREFIXO_TOKEN_MCP = "capi_"
MAXIMO_TOKENS_MCP = 10


class NaoAutenticado(Exception):
    pass


class TokenMcpCriado(BaseModel):
    id: int
    nome: str
    token: str


class TokenMcpResumo(BaseModel):
    id: int
    nome: str
    prefixo: str
    criado_em: datetime
    ultimo_uso_em: datetime | None


@lru_cache
def _cliente_jwks() -> jwt.PyJWKClient:
    settings = get_settings()
    if not settings.auth_jwks_url:
        raise NaoAutenticado("AUTH_JWKS_URL não configurada")
    return jwt.PyJWKClient(settings.auth_jwks_url, cache_keys=True, lifespan=600, timeout=5)


def chave_de_assinatura(token: str):
    try:
        return _cliente_jwks().get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientError as erro:
        raise NaoAutenticado("chave de assinatura desconhecida") from erro


def validar_jwt(token: str) -> str:
    settings = get_settings()
    try:
        dados = jwt.decode(
            token,
            chave_de_assinatura(token),
            algorithms=ALGORITMOS,
            audience=settings.auth_audience,
            issuer=settings.auth_issuer,
            leeway=30,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.InvalidTokenError as erro:
        raise NaoAutenticado("token inválido ou expirado") from erro
    if dados.get("email_verified") is not True:
        raise NaoAutenticado("e-mail ainda não verificado")
    return str(dados["sub"])


def exigir_usuario_ativo(session: Session, usuario_id: str) -> None:
    verificado = session.scalar(select(Usuario.email_verificado).where(Usuario.id == usuario_id))
    if not verificado:
        raise NaoAutenticado("usuário inexistente ou com e-mail não verificado")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def criar_token_mcp(session: Session, usuario_id: str, nome: str) -> TokenMcpCriado:
    ativos = session.scalars(
        select(TokenMcp.id).where(TokenMcp.usuario_id == usuario_id, TokenMcp.revogado_em.is_(None))
    ).all()
    if len(ativos) >= MAXIMO_TOKENS_MCP:
        raise ValueError(f"no máximo {MAXIMO_TOKENS_MCP} tokens ativos; revogue um antes")
    token = PREFIXO_TOKEN_MCP + secrets.token_urlsafe(32)
    registro = TokenMcp(
        usuario_id=usuario_id,
        nome=nome.strip()[:60] or "Claude",
        hash=_hash(token),
        prefixo=token[: len(PREFIXO_TOKEN_MCP) + 6],
    )
    session.add(registro)
    session.commit()
    return TokenMcpCriado(id=registro.id, nome=registro.nome, token=token)


def listar_tokens_mcp(session: Session, usuario_id: str) -> list[TokenMcpResumo]:
    linhas = session.scalars(
        select(TokenMcp)
        .where(TokenMcp.usuario_id == usuario_id, TokenMcp.revogado_em.is_(None))
        .order_by(TokenMcp.criado_em.desc())
    )
    return [
        TokenMcpResumo(
            id=t.id,
            nome=t.nome,
            prefixo=t.prefixo,
            criado_em=t.criado_em,
            ultimo_uso_em=t.ultimo_uso_em,
        )
        for t in linhas
    ]


def revogar_token_mcp(session: Session, usuario_id: str, token_id: int) -> bool:
    revogados = session.execute(
        update(TokenMcp)
        .where(
            TokenMcp.id == token_id,
            TokenMcp.usuario_id == usuario_id,
            TokenMcp.revogado_em.is_(None),
        )
        .values(revogado_em=datetime.now(UTC))
    ).rowcount
    session.commit()
    return revogados > 0


def usuario_do_token_mcp(session: Session, token: str) -> str:
    if not token.startswith(PREFIXO_TOKEN_MCP):
        raise NaoAutenticado("token do MCP inválido")
    linha = session.execute(
        select(TokenMcp.id, TokenMcp.usuario_id, Usuario.email_verificado)
        .join(Usuario, Usuario.id == TokenMcp.usuario_id)
        .where(TokenMcp.hash == _hash(token), TokenMcp.revogado_em.is_(None))
    ).first()
    if linha is None or not linha.email_verificado:
        raise NaoAutenticado("token do MCP inválido ou revogado")
    session.execute(
        update(TokenMcp).where(TokenMcp.id == linha.id).values(ultimo_uso_em=datetime.now(UTC))
    )
    session.commit()
    return linha.usuario_id
