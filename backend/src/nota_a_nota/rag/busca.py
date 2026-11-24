from collections import defaultdict
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import Float, Select, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from nota_a_nota import consultas
from nota_a_nota.ledger import DESPESA_A_CLASSIFICAR, RECEITA_A_CLASSIFICAR
from nota_a_nota.models import Transacao, Trecho
from nota_a_nota.rag.embeddings import Embedder, embed_ou_nada

FONTE = "transacao"
K_RRF = 60
CANDIDATOS = 50
DISTANCIA_MAXIMA_BUSCA = 0.56
DISTANCIA_MAXIMA_EXEMPLO = 0.30
SEM_CATEGORIA = (DESPESA_A_CLASSIFICAR, RECEITA_A_CLASSIFICAR)


class ResultadoIndexacao(BaseModel):
    novos: int
    vetorizados: int


class TransacaoEncontrada(consultas.TransacaoResumo):
    relevancia: float
    encontrada_por: list[Literal["significado", "palavra"]]


class Exemplo(BaseModel):
    descricao: str
    categoria: str


def texto_da_transacao(descricao: str, conta: str) -> str:
    if conta in SEM_CATEGORIA:
        return descricao
    return f"{descricao} · {conta.split(':', 1)[1]}"


def indexar(session: Session, embedder: Embedder | None) -> ResultadoIndexacao:
    contra = consultas.contrapartidas()
    faltando = session.execute(
        select(Transacao.id, Transacao.descricao, contra.c.nome)
        .join(contra, contra.c.transacao_id == Transacao.id)
        .where(~exists().where(Trecho.fonte_tipo == FONTE, Trecho.fonte_id == Transacao.id))
    ).all()
    session.add_all(
        Trecho(fonte_tipo=FONTE, fonte_id=i, texto=texto_da_transacao(descricao, conta))
        for i, descricao, conta in faltando
    )
    session.flush()

    sem_vetor = session.scalars(
        select(Trecho).where(Trecho.fonte_tipo == FONTE, Trecho.embedding.is_(None))
    ).all()
    vetores = embed_ou_nada(embedder, [t.texto for t in sem_vetor], "document") or []
    for trecho, vetor in zip(sem_vetor, vetores, strict=False):
        trecho.embedding = vetor
    session.commit()
    return ResultadoIndexacao(novos=len(faltando), vetorizados=len(vetores))


def _no_periodo(consulta: Select, inicio: date | None, fim: date | None) -> Select:
    consulta = consulta.join(Transacao, Transacao.id == Trecho.fonte_id).where(
        Trecho.fonte_tipo == FONTE
    )
    if inicio:
        consulta = consulta.where(Transacao.data >= inicio)
    if fim:
        consulta = consulta.where(Transacao.data <= fim)
    return consulta


def ranking_por_palavra(
    session: Session, texto: str, inicio: date | None = None, fim: date | None = None
) -> list[int]:
    consulta = func.websearch_to_tsquery("portuguese", texto)
    nota = func.ts_rank_cd(Trecho.tsv, consulta)
    return list(
        session.scalars(
            _no_periodo(select(Trecho.fonte_id), inicio, fim)
            .where(
                or_(Trecho.tsv.op("@@")(consulta), Trecho.texto.icontains(texto, autoescape=True))
            )
            .order_by(nota.desc(), Transacao.data.desc())
            .limit(CANDIDATOS)
        )
    )


def ranking_por_significado(
    session: Session, vetor: list[float], inicio: date | None = None, fim: date | None = None
) -> list[int]:
    distancia = Trecho.embedding.cosine_distance(vetor)
    return list(
        session.scalars(
            _no_periodo(select(Trecho.fonte_id), inicio, fim)
            .where(Trecho.embedding.is_not(None), distancia <= DISTANCIA_MAXIMA_BUSCA)
            .order_by(distancia)
            .limit(CANDIDATOS)
        )
    )


def fundir(*rankings: list[int]) -> dict[int, float]:
    pontos: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for posicao, transacao_id in enumerate(ranking, start=1):
            pontos[transacao_id] += 1 / (K_RRF + posicao)
    return pontos


def buscar(
    session: Session,
    texto: str,
    embedder: Embedder | None,
    inicio: date | None = None,
    fim: date | None = None,
    limite: int = 20,
) -> list[TransacaoEncontrada]:
    por_palavra = ranking_por_palavra(session, texto, inicio, fim)
    vetor = embed_ou_nada(embedder, [texto], "query")
    por_significado = ranking_por_significado(session, vetor[0], inicio, fim) if vetor else []

    pontos = fundir(por_significado, por_palavra)
    melhores = sorted(pontos, key=pontos.__getitem__, reverse=True)[: min(limite, 200)]
    resumos = {t.id: t for t in consultas.resumir_transacoes(session, melhores)}
    return [
        TransacaoEncontrada(
            **resumos[i].model_dump(),
            relevancia=round(pontos[i], 5),
            encontrada_por=[
                origem
                for origem, ranking in (("significado", por_significado), ("palavra", por_palavra))
                if i in ranking
            ],
        )
        for i in melhores
        if i in resumos
    ]


def exemplos_parecidos(
    session: Session, transacao_ids: list[int], por_transacao: int = 3
) -> dict[int, list[Exemplo]]:
    contra = consultas.contrapartidas()
    alvo = aliased(Trecho)
    exemplos: dict[int, list[Exemplo]] = {}
    for transacao_id in transacao_ids:
        vetor_alvo = (
            select(alvo.embedding)
            .where(alvo.fonte_tipo == FONTE, alvo.fonte_id == transacao_id)
            .scalar_subquery()
        )
        distancia = Trecho.embedding.op("<=>", return_type=Float)(vetor_alvo)
        linhas = session.execute(
            select(Transacao.descricao, contra.c.nome)
            .join(Trecho, Trecho.fonte_id == Transacao.id)
            .join(contra, contra.c.transacao_id == Transacao.id)
            .where(
                Trecho.fonte_tipo == FONTE,
                Trecho.fonte_id != transacao_id,
                Trecho.embedding.is_not(None),
                contra.c.nome.not_in(SEM_CATEGORIA),
                distancia <= DISTANCIA_MAXIMA_EXEMPLO,
            )
            .order_by(distancia)
            .limit(por_transacao)
        ).all()
        if linhas:
            exemplos[transacao_id] = [
                Exemplo(descricao=d, categoria=nome.split(":", 1)[1]) for d, nome in linhas
            ]
    return exemplos
