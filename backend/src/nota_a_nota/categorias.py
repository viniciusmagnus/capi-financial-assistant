import re
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from nota_a_nota.ledger import (
    CATEGORIAS_DESPESA,
    CATEGORIAS_RECEITA,
    TRANSFERENCIA_INTERNA,
    obter_ou_criar_conta,
)
from nota_a_nota.models import Conta, TipoConta

A_CLASSIFICAR = "A classificar"
TAMANHO_MAXIMO = 40

Sentido = Literal["despesa", "receita"]


class CategoriaInvalida(ValueError):
    pass


class Categorias(BaseModel):
    despesa: list[str]
    receita: list[str]
    transferencia: str = TRANSFERENCIA_INTERNA
    criadas: list[str] = []

    @property
    def todas(self) -> list[str]:
        return [*self.despesa, *self.receita, self.transferencia]

    def sentido(self, nome: str) -> Literal["despesa", "receita", "transferencia"] | None:
        if nome == self.transferencia:
            return "transferencia"
        if nome in self.despesa:
            return "despesa"
        if nome in self.receita:
            return "receita"
        return None


PADRAO = Categorias(despesa=list(CATEGORIAS_DESPESA), receita=list(CATEGORIAS_RECEITA))


def _ordenar(nomes: list[str], fixas: tuple[str, ...]) -> list[str]:
    proprias = sorted((n for n in nomes if n not in fixas), key=str.casefold)
    return [*(n for n in fixas if n in nomes), *proprias]


def listar(session: Session) -> Categorias:
    linhas = session.execute(
        select(Conta.nome, Conta.tipo).where(Conta.tipo.in_([TipoConta.DESPESA, TipoConta.RECEITA]))
    )
    despesa: list[str] = []
    receita: list[str] = []
    for nome, tipo in linhas:
        categoria = nome.split(":", 1)[1]
        if categoria == A_CLASSIFICAR:
            continue
        (despesa if tipo == TipoConta.DESPESA else receita).append(categoria)
    fixas = {*CATEGORIAS_DESPESA, *CATEGORIAS_RECEITA}
    return Categorias(
        despesa=_ordenar(despesa, CATEGORIAS_DESPESA),
        receita=_ordenar(receita, CATEGORIAS_RECEITA),
        criadas=sorted((n for n in [*despesa, *receita] if n not in fixas), key=str.casefold),
    )


def criar(session: Session, nome: str, sentido: Sentido) -> Categorias:
    limpo = re.sub(r"\s+", " ", nome).strip()
    if len(limpo) < 2 or len(limpo) > TAMANHO_MAXIMO:
        raise CategoriaInvalida(f"o nome precisa ter de 2 a {TAMANHO_MAXIMO} caracteres")
    limpo = limpo[0].upper() + limpo[1:]
    if ":" in limpo:
        raise CategoriaInvalida("o nome não pode ter dois-pontos")
    existentes = listar(session)
    repetida = next(
        (c for c in [*existentes.todas, A_CLASSIFICAR] if c.casefold() == limpo.casefold()), None
    )
    if repetida:
        raise CategoriaInvalida(f"já existe a categoria {repetida}")
    if sentido == "despesa":
        obter_ou_criar_conta(session, f"Despesa:{limpo}", TipoConta.DESPESA)
    else:
        obter_ou_criar_conta(session, f"Receita:{limpo}", TipoConta.RECEITA)
    session.commit()
    return listar(session)
