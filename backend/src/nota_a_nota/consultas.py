from datetime import date

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nota_a_nota.ledger import DESPESA_A_CLASSIFICAR, RECEITA_A_CLASSIFICAR
from nota_a_nota.models import Conta, Lancamento, TipoConta, Transacao


class GastoCategoria(BaseModel):
    categoria: str
    total_centavos: int
    transacoes: int


class SaldoConta(BaseModel):
    conta: str
    tipo: TipoConta
    saldo_centavos: int


class TransacaoResumo(BaseModel):
    id: int
    data: date
    descricao: str
    valor_centavos: int
    categoria: str


class Pendente(BaseModel):
    id: int
    descricao: str
    valor_centavos: int


def gastos_por_categoria(session: Session, inicio: date, fim: date) -> list[GastoCategoria]:
    total = func.sum(Lancamento.valor_centavos)
    linhas = session.execute(
        select(Conta.nome, total, func.count(Lancamento.id))
        .join(Lancamento, Lancamento.conta_id == Conta.id)
        .join(Transacao, Transacao.id == Lancamento.transacao_id)
        .where(Conta.tipo == TipoConta.DESPESA, Transacao.data.between(inicio, fim))
        .group_by(Conta.nome)
        .order_by(total.desc())
    )
    return [
        GastoCategoria(categoria=nome.split(":", 1)[1], total_centavos=soma, transacoes=qtd)
        for nome, soma, qtd in linhas
    ]


def saldos(session: Session) -> list[SaldoConta]:
    linhas = session.execute(
        select(Conta.nome, Conta.tipo, func.coalesce(func.sum(Lancamento.valor_centavos), 0))
        .outerjoin(Lancamento, Lancamento.conta_id == Conta.id)
        .where(Conta.tipo.in_([TipoConta.ATIVO, TipoConta.PASSIVO]))
        .group_by(Conta.nome, Conta.tipo)
        .order_by(Conta.nome)
    )
    return [SaldoConta(conta=n, tipo=t, saldo_centavos=s) for n, t, s in linhas]


def contrapartidas():
    return (
        select(Lancamento.transacao_id, Lancamento.valor_centavos, Conta.nome)
        .join(Conta, Conta.id == Lancamento.conta_id)
        .where(Conta.tipo.in_([TipoConta.DESPESA, TipoConta.RECEITA, TipoConta.PATRIMONIO]))
        .subquery()
    )


def resumir_transacoes(session: Session, ids: list[int]) -> list[TransacaoResumo]:
    if not ids:
        return []
    contra = contrapartidas()
    linhas = session.execute(
        select(
            Transacao.id,
            Transacao.data,
            Transacao.descricao,
            contra.c.valor_centavos,
            contra.c.nome,
        )
        .join(contra, contra.c.transacao_id == Transacao.id)
        .where(Transacao.id.in_(ids))
    )
    return [
        TransacaoResumo(
            id=i, data=d, descricao=desc, valor_centavos=-v, categoria=nome.split(":", 1)[1]
        )
        for i, d, desc, v, nome in linhas
    ]


def pendentes_de_categoria(session: Session, limite: int | None = 100) -> list[Pendente]:
    contra = contrapartidas()
    linhas = session.execute(
        select(Transacao.id, Transacao.descricao, contra.c.valor_centavos)
        .join(contra, contra.c.transacao_id == Transacao.id)
        .where(contra.c.nome.in_([DESPESA_A_CLASSIFICAR, RECEITA_A_CLASSIFICAR]))
        .order_by(Transacao.data)
        .limit(limite)
    )
    return [Pendente(id=i, descricao=d, valor_centavos=-v) for i, d, v in linhas]


def gasto_total(session: Session, inicio: date, fim: date) -> int:
    return session.scalar(
        select(func.coalesce(func.sum(Lancamento.valor_centavos), 0))
        .join(Conta, Conta.id == Lancamento.conta_id)
        .join(Transacao, Transacao.id == Lancamento.transacao_id)
        .where(Conta.tipo == TipoConta.DESPESA, Transacao.data.between(inicio, fim))
    )


def ultimas_despesas(
    session: Session, inicio: date, fim: date, limite: int = 5
) -> list[TransacaoResumo]:
    linhas = session.execute(
        select(
            Transacao.id,
            Transacao.data,
            Transacao.descricao,
            Lancamento.valor_centavos,
            Conta.nome,
        )
        .join(Lancamento, Lancamento.transacao_id == Transacao.id)
        .join(Conta, Conta.id == Lancamento.conta_id)
        .where(Conta.tipo == TipoConta.DESPESA, Transacao.data.between(inicio, fim))
        .order_by(Transacao.data.desc(), Transacao.id.desc())
        .limit(limite)
    )
    return [
        TransacaoResumo(
            id=i, data=d, descricao=desc, valor_centavos=-v, categoria=nome.split(":", 1)[1]
        )
        for i, d, desc, v, nome in linhas
    ]


def revisar_na_importacao(session: Session, importacao_id: int) -> int:
    contra = contrapartidas()
    return session.scalar(
        select(func.count())
        .select_from(Transacao)
        .join(contra, contra.c.transacao_id == Transacao.id)
        .where(
            Transacao.importacao_id == importacao_id,
            (contra.c.nome.in_([DESPESA_A_CLASSIFICAR, RECEITA_A_CLASSIFICAR]))
            | (Transacao.confianca_categoria == "baixa"),
        )
    )


def valor_no_extrato(session: Session, transacao_id: int) -> int | None:
    return session.scalar(
        select(Lancamento.valor_centavos)
        .join(Conta, Conta.id == Lancamento.conta_id)
        .where(
            Lancamento.transacao_id == transacao_id,
            Conta.tipo.in_([TipoConta.ATIVO, TipoConta.PASSIVO]),
        )
    )
