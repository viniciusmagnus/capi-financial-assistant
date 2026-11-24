import re
from collections import OrderedDict
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from nota_a_nota import categorias as catalogo
from nota_a_nota import estabelecimentos, regras
from nota_a_nota.ledger import aplicar_categoria, nome_conta_categoria
from nota_a_nota.models import (
    AlteracaoRevisao,
    Conta,
    Lancamento,
    LoteRevisao,
    OrigemCategoria,
    RegraCategoria,
    TipoConta,
    Transacao,
)

CATEGORIA_REVISADA = "Outros"
SEM_ESTABELECIMENTO = "Estabelecimento não identificado"
LIMITE_DECISOES = 500

OrigemSugestao = Literal["usuario", "historico", "pesquisa"]

_PIX = re.compile(r"(?<![A-Z])PIX(?![A-Z])")
_TRANSFERENCIA = re.compile(r"(?<![A-Z])(?:TED|DOC|TEF|TRANSF(?:ERENCIA)?)(?![A-Z])")
_BOLETO = re.compile(r"(?<![A-Z])BOLETO(?![A-Z])")
_DEBITO_AUTOMATICO = re.compile(r"DEB(?:ITO)?\.? AUTOM")
_PARCELA = re.compile(r"PARC(?:ELA)?\.?\s*(\d{1,2})\s*(?:/|DE)\s*(\d{1,2})")
_PARCELA_SEM_NUMERO = re.compile(r"(?<![A-Z])PARC(?:ELA|ELADO)?(?![A-Z])")


class NaoEncontradas(LookupError):
    def __init__(self, ids: list[int]):
        super().__init__(f"transações não encontradas: {', '.join(map(str, ids[:20]))}")
        self.ids = ids


class ItemRevisao(BaseModel):
    id: int
    data: date
    descricao: str
    valor_centavos: int
    conta: str
    categoria: str
    estabelecimento: str
    estabelecimento_confirmado: bool
    forma_pagamento: str | None
    parcela: str | None
    categorizada_por: OrigemCategoria | None


class GrupoRevisao(BaseModel):
    chave: str
    estabelecimento: str
    marca: str | None = None
    quantidade: int
    total_centavos: int
    descricoes: list[str]
    ids: list[int]
    regra_sugerida: str | None = None


class Decisao(BaseModel):
    transacao_id: int
    categoria: str = Field(min_length=1, max_length=80)
    estabelecimento: str | None = Field(None, max_length=80)
    origem: OrigemSugestao = "usuario"

    @field_validator("estabelecimento")
    @classmethod
    def vazio_vira_nulo(cls, valor: str | None) -> str | None:
        return " ".join(valor.split()) or None if valor else None


class Ignorada(BaseModel):
    transacao_id: int
    motivo: str


class ResultadoConfirmacao(BaseModel):
    lote_id: int | None
    alteradas: int
    ignoradas: list[Ignorada]
    regras_salvas: list[str]
    repetido: bool


class ResultadoDesfazer(BaseModel):
    lote_id: int
    desfeitas: int
    conflitos: list[int]
    ja_desfeito: bool


def detalhes_de_pagamento(descricao: str, cartao: bool) -> tuple[str | None, str | None]:
    texto = estabelecimentos.normalizar(descricao)
    if _PIX.search(texto):
        forma = "Pix"
    elif _TRANSFERENCIA.search(texto):
        forma = "Transferência"
    elif _BOLETO.search(texto):
        forma = "Boleto"
    elif _DEBITO_AUTOMATICO.search(texto):
        forma = "Débito automático"
    elif cartao:
        forma = "Cartão de crédito"
    else:
        forma = None
    numeros = _PARCELA.search(texto)
    if numeros:
        parcela = f"{int(numeros.group(1))}/{int(numeros.group(2))}"
    elif _PARCELA_SEM_NUMERO.search(texto):
        parcela = "parcelada"
    else:
        parcela = None
    return forma, parcela


def descricao_identifica(descricao: str) -> bool:
    identificado = estabelecimentos.identificar(descricao)
    return bool(identificado.marca or regras.termos_distintivos(identificado.nome))


def padrao_para_regra(descricao: str) -> str | None:
    candidato = estabelecimentos.identificar(descricao).regra
    if not candidato:
        return None
    padrao = regras.normalizar(candidato)
    if len(padrao) < regras.TAMANHO_MINIMO or not regras.termos_distintivos(padrao):
        return None
    return padrao if regras.casa(padrao, descricao) else None


def problema_no_estabelecimento(nome: str | None) -> str | None:
    if nome is None:
        return None
    if not regras.termos_distintivos(nome):
        return f"{nome!r} é forma de pagamento, não quem recebeu"
    return None


def _nome_categoria(nome_conta: str) -> str:
    return nome_conta.split(":", 1)[1] if ":" in nome_conta else nome_conta


def _base() -> tuple[Select, object]:
    contra = aliased(Lancamento)
    conta_contra = aliased(Conta)
    origem = aliased(Lancamento)
    conta_origem = aliased(Conta)
    consulta = (
        select(
            Transacao.id,
            Transacao.data,
            Transacao.descricao,
            Transacao.estabelecimento,
            Transacao.categorizada_por,
            contra.valor_centavos,
            conta_contra.nome,
            conta_origem.nome,
            conta_origem.tipo,
        )
        .join(contra, contra.transacao_id == Transacao.id)
        .join(conta_contra, conta_contra.id == contra.conta_id)
        .join(origem, origem.transacao_id == Transacao.id)
        .join(conta_origem, conta_origem.id == origem.conta_id)
        .where(
            conta_contra.tipo.in_([TipoConta.DESPESA, TipoConta.RECEITA, TipoConta.PATRIMONIO]),
            conta_origem.tipo.in_([TipoConta.ATIVO, TipoConta.PASSIVO]),
        )
    )
    return consulta, conta_contra


def _item(linha) -> ItemRevisao:
    transacao_id, data, descricao, confirmado, por, valor, contra, origem, tipo_origem = linha
    identificado = estabelecimentos.identificar(descricao)
    forma, parcela = detalhes_de_pagamento(descricao, tipo_origem == TipoConta.PASSIVO)
    return ItemRevisao(
        id=transacao_id,
        data=data,
        descricao=descricao,
        valor_centavos=valor,
        conta=_nome_categoria(origem),
        categoria=_nome_categoria(contra),
        estabelecimento=confirmado
        or (identificado.nome if descricao_identifica(descricao) else SEM_ESTABELECIMENTO),
        estabelecimento_confirmado=confirmado is not None,
        forma_pagamento=forma,
        parcela=parcela,
        categorizada_por=por,
    )


def _em_outros() -> Select:
    consulta, conta_contra = _base()
    return consulta.where(conta_contra.nome == nome_conta_categoria(CATEGORIA_REVISADA))


def em_outros(session: Session, limite: int) -> list[ItemRevisao]:
    linhas = session.execute(
        _em_outros().order_by(Transacao.data.desc(), Transacao.id.desc()).limit(limite)
    )
    return [_item(linha) for linha in linhas]


def quantos_em_outros(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(_em_outros().subquery()))


def agrupar(itens: list[ItemRevisao]) -> list[GrupoRevisao]:
    grupos: OrderedDict[str, GrupoRevisao] = OrderedDict()
    for item in itens:
        chave = (
            f"confirmado:{estabelecimentos.normalizar(item.estabelecimento)}"
            if item.estabelecimento_confirmado
            else estabelecimentos.identificar(item.descricao).chave
        )
        grupo = grupos.get(chave)
        if grupo is None:
            grupo = grupos[chave] = GrupoRevisao(
                chave=chave,
                estabelecimento=item.estabelecimento,
                marca=estabelecimentos.identificar(item.descricao).marca,
                quantidade=0,
                total_centavos=0,
                descricoes=[],
                ids=[],
                regra_sugerida=padrao_para_regra(item.descricao),
            )
        elif grupo.regra_sugerida and not regras.casa(grupo.regra_sugerida, item.descricao):
            grupo.regra_sugerida = None
        grupo.quantidade += 1
        grupo.total_centavos += item.valor_centavos
        grupo.ids.append(item.id)
        if item.descricao not in grupo.descricoes and len(grupo.descricoes) < 6:
            grupo.descricoes.append(item.descricao)
    return list(grupos.values())


def itens(session: Session, ids: list[int]) -> list[ItemRevisao]:
    if not ids:
        return []
    consulta, _ = _base()
    encontrados = [_item(linha) for linha in session.execute(consulta.where(Transacao.id.in_(ids)))]
    faltando = sorted(set(ids) - {i.id for i in encontrados})
    if faltando:
        raise NaoEncontradas(faltando)
    return encontrados


def _contrapartida(session: Session, transacao_id: int) -> Lancamento:
    lancamento = session.scalar(
        select(Lancamento)
        .join(Conta, Conta.id == Lancamento.conta_id)
        .where(
            Lancamento.transacao_id == transacao_id,
            Conta.tipo.in_([TipoConta.DESPESA, TipoConta.RECEITA, TipoConta.PATRIMONIO]),
        )
        .with_for_update()
    )
    if lancamento is None:
        raise NaoEncontradas([transacao_id])
    return lancamento


def _resultado_do_lote(session: Session, lote: LoteRevisao) -> ResultadoConfirmacao:
    alteradas = session.scalar(
        select(func.count())
        .select_from(AlteracaoRevisao)
        .where(AlteracaoRevisao.lote_id == lote.id)
    )
    return ResultadoConfirmacao(
        lote_id=lote.id,
        alteradas=alteradas,
        ignoradas=[],
        regras_salvas=[r["padrao"] for r in lote.opcoes.get("regras", [])],
        repetido=True,
    )


def _regras_por_padrao(
    aceitas: list[tuple[ItemRevisao, Decisao]],
) -> dict[str, tuple[str, str | None]]:
    escolhas: dict[str, set[tuple[str, str | None]]] = {}
    for item, decisao in aceitas:
        padrao = padrao_para_regra(item.descricao)
        if padrao:
            escolhas.setdefault(padrao, set()).add((decisao.categoria, decisao.estabelecimento))
    return {padrao: next(iter(opcoes)) for padrao, opcoes in escolhas.items() if len(opcoes) == 1}


def confirmar(
    session: Session, decisoes: list[Decisao], lembrar: bool, chave_idempotencia: str
) -> ResultadoConfirmacao:
    anterior = session.scalar(
        select(LoteRevisao).where(LoteRevisao.chave_idempotencia == chave_idempotencia)
    )
    if anterior is not None:
        return _resultado_do_lote(session, anterior)

    por_id = {d.transacao_id: d for d in decisoes}
    session.execute(
        select(Transacao.id)
        .where(Transacao.id.in_(por_id))
        .order_by(Transacao.id)
        .with_for_update()
    ).all()
    encontrados = {i.id: i for i in itens(session, list(por_id))}
    existentes = catalogo.listar(session)
    permitidas = {c for c in existentes.despesa if c != CATEGORIA_REVISADA}

    aceitas: list[tuple[ItemRevisao, Decisao]] = []
    ignoradas: list[Ignorada] = []
    for transacao_id, decisao in por_id.items():
        item = encontrados[transacao_id]
        if item.categoria != CATEGORIA_REVISADA:
            ignoradas.append(Ignorada(transacao_id=transacao_id, motivo="não está mais em Outros"))
        elif decisao.categoria not in permitidas:
            ignoradas.append(
                Ignorada(
                    transacao_id=transacao_id, motivo=f"categoria inválida: {decisao.categoria}"
                )
            )
        elif item.valor_centavos <= 0:
            ignoradas.append(
                Ignorada(transacao_id=transacao_id, motivo="não é uma saída de dinheiro")
            )
        else:
            if problema_no_estabelecimento(decisao.estabelecimento):
                decisao = decisao.model_copy(update={"estabelecimento": None})
            aceitas.append((item, decisao))

    if not aceitas:
        return ResultadoConfirmacao(
            lote_id=None, alteradas=0, ignoradas=ignoradas, regras_salvas=[], repetido=False
        )

    categorias_usadas = sorted({d.categoria for _, d in aceitas})
    lote = LoteRevisao(
        chave_idempotencia=chave_idempotencia,
        opcoes={"lembrar": lembrar, "regras": []},
        resumo=f"{len(aceitas)} saíram de Outros para {', '.join(categorias_usadas)}",
    )
    session.add(lote)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        repetido = session.scalar(
            select(LoteRevisao).where(LoteRevisao.chave_idempotencia == chave_idempotencia)
        )
        if repetido is None:
            raise
        return _resultado_do_lote(session, repetido)

    salvas: list[dict] = []
    if lembrar:
        for padrao, (categoria, estabelecimento) in _regras_por_padrao(aceitas).items():
            antes = regras.obter_por_padrao(session, padrao)
            try:
                regra = regras.salvar(session, padrao, categoria, estabelecimento, commit=False)
            except regras.RegraInvalida:
                continue
            salvas.append(
                {
                    "id": regra.id,
                    "padrao": padrao,
                    "criada": antes is None,
                    "anterior": antes.model_dump() if antes else None,
                }
            )
    regra_do_padrao = {r["padrao"]: r["id"] for r in salvas}

    for item, decisao in aceitas:
        lancamento = _contrapartida(session, item.id)
        conta_anterior = session.scalar(select(Conta.nome).where(Conta.id == lancamento.conta_id))
        transacao = session.scalar(select(Transacao).where(Transacao.id == item.id))
        estabelecimento_anterior = transacao.estabelecimento
        por_anterior = transacao.categorizada_por
        aplicar_categoria(session, item.id, decisao.categoria, OrigemCategoria.USUARIO)
        if decisao.estabelecimento:
            transacao.estabelecimento = decisao.estabelecimento
        session.flush()
        session.add(
            AlteracaoRevisao(
                lote_id=lote.id,
                transacao_id=item.id,
                categoria_anterior=conta_anterior,
                categoria_nova=nome_conta_categoria(decisao.categoria),
                estabelecimento_anterior=estabelecimento_anterior,
                estabelecimento_novo=transacao.estabelecimento,
                categorizada_por_anterior=por_anterior,
                categorizada_por_nova=OrigemCategoria.USUARIO,
                origem=decisao.origem,
                regra_id=regra_do_padrao.get(padrao_para_regra(item.descricao) or ""),
            )
        )
    lote.opcoes = {"lembrar": lembrar, "regras": salvas}
    lote.regra_id = salvas[0]["id"] if salvas else None
    session.commit()
    return ResultadoConfirmacao(
        lote_id=lote.id,
        alteradas=len(aceitas),
        ignoradas=ignoradas,
        regras_salvas=[r["padrao"] for r in salvas],
        repetido=False,
    )


def desfazer(session: Session, lote_id: int) -> ResultadoDesfazer:
    lote = session.scalar(select(LoteRevisao).where(LoteRevisao.id == lote_id).with_for_update())
    if lote is None:
        raise LookupError("lote não encontrado")
    if lote.desfeito_em is not None:
        return ResultadoDesfazer(lote_id=lote.id, desfeitas=0, conflitos=[], ja_desfeito=True)
    alteracoes = session.scalars(
        select(AlteracaoRevisao)
        .where(AlteracaoRevisao.lote_id == lote.id)
        .order_by(AlteracaoRevisao.id.desc())
    ).all()
    desfeitas = 0
    conflitos: list[int] = []
    for alteracao in alteracoes:
        lancamento = _contrapartida(session, alteracao.transacao_id)
        conta_atual = session.scalar(select(Conta.nome).where(Conta.id == lancamento.conta_id))
        transacao = session.scalar(select(Transacao).where(Transacao.id == alteracao.transacao_id))
        if (
            conta_atual != alteracao.categoria_nova
            or transacao.estabelecimento != alteracao.estabelecimento_novo
        ):
            conflitos.append(alteracao.transacao_id)
            continue
        conta = session.scalar(select(Conta).where(Conta.nome == alteracao.categoria_anterior))
        if conta is None:
            conflitos.append(alteracao.transacao_id)
            continue
        lancamento.conta_id = conta.id
        transacao.estabelecimento = alteracao.estabelecimento_anterior
        transacao.categorizada_por = alteracao.categorizada_por_anterior
        desfeitas += 1
    for regra in lote.opcoes.get("regras", []):
        if regra["criada"]:
            session.execute(delete(RegraCategoria).where(RegraCategoria.id == regra["id"]))
        elif regra["anterior"]:
            session.execute(
                update(RegraCategoria)
                .where(RegraCategoria.id == regra["id"])
                .values(
                    categoria=regra["anterior"].get("categoria"),
                    estabelecimento=regra["anterior"].get("estabelecimento"),
                )
            )
    lote.desfeito_em = datetime.now(UTC)
    session.commit()
    return ResultadoDesfazer(
        lote_id=lote.id, desfeitas=desfeitas, conflitos=conflitos, ja_desfeito=False
    )
