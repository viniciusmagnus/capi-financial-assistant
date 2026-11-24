import hashlib
import json
import re
from collections import OrderedDict
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from nota_a_nota import categorias as catalogo
from nota_a_nota import estabelecimentos, regras
from nota_a_nota.ledger import TRANSFERENCIA_INTERNA, aplicar_categoria, nome_conta_categoria
from nota_a_nota.models import (
    AlteracaoRevisao,
    Conta,
    Lancamento,
    LoteRevisao,
    OrigemCategoria,
    PropostaRevisao,
    RegraCategoria,
    TipoConta,
    Transacao,
)

CATEGORIA_PADRAO = "Outros"
SEM_ESTABELECIMENTO = "Estabelecimento não identificado"
POR_PAGINA_MAXIMO = 100
LIMITE_SELECAO = 2000
LIMITE_GRUPOS = 5000
LIMITE_CORRESPONDENCIAS = 20000

OrigemInformacao = Literal["usuario", "regra", "historico", "pesquisa", "hipotese"]
OrigemAlteracao = Literal["usuario", "regra", "historico", "pesquisa"]
Alcance = Literal["selecionadas", "correspondencias"]

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


class RevisaoInvalida(ValueError):
    pass


class PreviaDesatualizada(RuntimeError):
    pass


class FiltroRevisao(BaseModel):
    categoria: str = CATEGORIA_PADRAO
    q: str | None = Field(None, max_length=100)
    inicio: date | None = None
    fim: date | None = None
    conta_id: int | None = None


class ItemRevisao(BaseModel):
    id: int
    data: date
    descricao: str
    valor_centavos: int
    conta_id: int
    conta: str
    categoria: str
    estabelecimento: str
    estabelecimento_confirmado: bool
    marca: str | None
    forma_pagamento: str | None
    parcela: str | None
    categorizada_por: OrigemCategoria | None


class PaginaRevisao(BaseModel):
    itens: list[ItemRevisao]
    total: int
    total_centavos: int
    pagina: int
    por_pagina: int


class GrupoRevisao(BaseModel):
    chave: str
    estabelecimento: str
    marca: str | None
    confirmado: bool
    quantidade: int
    total_centavos: int
    descricoes: list[str]
    ids: list[int]


class ContaDeOrigem(BaseModel):
    id: int
    nome: str


class Evidencia(BaseModel):
    origem: OrigemInformacao
    texto: str = Field(min_length=1, max_length=400)
    fontes: list[str] = Field(default_factory=list, max_length=5)


class RegraSugerida(BaseModel):
    padrao: str = Field(min_length=3, max_length=120)
    categoria: str | None = None
    estabelecimento: str | None = Field(None, max_length=80)


class ConteudoProposta(BaseModel):
    transacao_ids: list[int] = Field(min_length=1, max_length=LIMITE_SELECAO)
    estabelecimento: str | None = Field(None, max_length=80)
    categoria: str | None = None
    motivo: str = Field("", max_length=600)
    evidencias: list[Evidencia] = Field(default_factory=list, max_length=8)
    incertezas: list[str] = Field(default_factory=list, max_length=6)
    regra: RegraSugerida | None = None

    @field_validator("transacao_ids")
    @classmethod
    def sem_repeticao(cls, ids: list[int]) -> list[int]:
        return sorted(set(ids))

    @field_validator("estabelecimento", "categoria")
    @classmethod
    def vazio_vira_nulo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return " ".join(valor.split()) or None


class OpcoesAplicacao(BaseModel):
    alcance: Alcance = "selecionadas"
    salvar_regra: bool = False
    substituir_manuais: bool = False
    confirmar_transferencia: bool = False


class RegraNaPrevia(BaseModel):
    padrao: str
    categoria: str | None
    estabelecimento: str | None
    valida: bool
    erro: str | None
    existente: regras.Regra | None
    casa_com_selecionadas: int
    correspondencias_existentes: int


class LinhaPrevia(BaseModel):
    id: int
    data: date
    descricao: str
    valor_centavos: int
    categoria_atual: str
    categoria_nova: str
    estabelecimento_atual: str | None
    estabelecimento_novo: str | None
    categorizada_por: OrigemCategoria | None
    por: Literal["selecao", "regra"]
    motivo: str | None = None


class Previa(BaseModel):
    afetadas: list[LinhaPrevia]
    ignoradas: list[LinhaPrevia]
    manuais_preservadas: int
    efeito_nos_gastos_centavos: int
    regra: RegraNaPrevia | None
    avisos: list[str]
    exige_confirmar_transferencia: bool
    assinatura: str


class ResultadoLote(BaseModel):
    lote_id: int
    alteradas: int
    regra: regras.Regra | None
    repetido: bool


class ResultadoDesfazer(BaseModel):
    lote_id: int
    desfeitas: int
    conflitos: list[int]
    ja_desfeito: bool


class LoteResumo(BaseModel):
    id: int
    resumo: str
    criado_em: datetime
    desfeito_em: datetime | None
    alteracoes: int
    regra_id: int | None


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


def _nome_categoria(nome_conta: str) -> str:
    return nome_conta.split(":", 1)[1] if ":" in nome_conta else nome_conta


def _base() -> tuple[Select, dict]:
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
            conta_contra.tipo,
            conta_origem.id,
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
    return consulta, {"conta_contra": conta_contra, "conta_origem": conta_origem, "contra": contra}


def _filtrada(filtro: FiltroRevisao) -> tuple[Select, dict]:
    consulta, a = _base()
    consulta = consulta.where(a["conta_contra"].nome == nome_conta_categoria(filtro.categoria))
    if filtro.inicio:
        consulta = consulta.where(Transacao.data >= filtro.inicio)
    if filtro.fim:
        consulta = consulta.where(Transacao.data <= filtro.fim)
    if filtro.conta_id:
        consulta = consulta.where(a["conta_origem"].id == filtro.conta_id)
    if filtro.q and filtro.q.strip():
        termo = re.sub(r"([%_\\])", r"\\\1", filtro.q.strip())
        consulta = consulta.where(
            or_(
                Transacao.descricao.ilike(f"%{termo}%"),
                Transacao.estabelecimento.ilike(f"%{termo}%"),
            )
        )
    return consulta, a


def _item(linha) -> ItemRevisao:
    (
        transacao_id,
        data,
        descricao,
        confirmado,
        categorizada_por,
        valor,
        nome_contra,
        _tipo_contra,
        conta_id,
        nome_origem,
        tipo_origem,
    ) = linha
    identificado = estabelecimentos.identificar(descricao)
    forma, parcela = detalhes_de_pagamento(descricao, tipo_origem == TipoConta.PASSIVO)
    return ItemRevisao(
        id=transacao_id,
        data=data,
        descricao=descricao,
        valor_centavos=valor,
        conta_id=conta_id,
        conta=_nome_categoria(nome_origem),
        categoria=_nome_categoria(nome_contra),
        estabelecimento=confirmado
        or (
            identificado.nome
            if identificado.marca or regras.termos_distintivos(identificado.nome)
            else SEM_ESTABELECIMENTO
        ),
        estabelecimento_confirmado=confirmado is not None,
        marca=identificado.marca,
        forma_pagamento=forma,
        parcela=parcela,
        categorizada_por=categorizada_por,
    )


def listar(
    session: Session, filtro: FiltroRevisao, pagina: int = 1, por_pagina: int = 50
) -> PaginaRevisao:
    por_pagina = max(1, min(por_pagina, POR_PAGINA_MAXIMO))
    pagina = max(1, pagina)
    consulta, _ = _filtrada(filtro)
    subconsulta = consulta.subquery()
    total, soma = session.execute(
        select(func.count(), func.coalesce(func.sum(subconsulta.c.valor_centavos), 0))
    ).one()
    linhas = session.execute(
        consulta.order_by(Transacao.data.desc(), Transacao.id.desc())
        .limit(por_pagina)
        .offset((pagina - 1) * por_pagina)
    )
    return PaginaRevisao(
        itens=[_item(linha) for linha in linhas],
        total=total,
        total_centavos=soma,
        pagina=pagina,
        por_pagina=por_pagina,
    )


def ids_do_filtro(session: Session, filtro: FiltroRevisao) -> list[int]:
    consulta, _ = _filtrada(filtro)
    ids = list(
        session.scalars(
            consulta.with_only_columns(Transacao.id)
            .order_by(Transacao.id)
            .limit(LIMITE_SELECAO + 1)
        )
    )
    if len(ids) > LIMITE_SELECAO:
        raise RevisaoInvalida(
            f"o filtro tem mais de {LIMITE_SELECAO} transações; restrinja por período ou conta"
        )
    return ids


def agrupar(session: Session, filtro: FiltroRevisao) -> list[GrupoRevisao]:
    consulta, _ = _filtrada(filtro)
    grupos: OrderedDict[str, GrupoRevisao] = OrderedDict()
    linhas = session.execute(consulta.order_by(Transacao.data.desc()).limit(LIMITE_GRUPOS))
    for linha in linhas:
        item = _item(linha)
        identificado = estabelecimentos.identificar(item.descricao)
        chave = (
            f"confirmado:{estabelecimentos.normalizar(item.estabelecimento)}"
            if item.estabelecimento_confirmado
            else identificado.chave
        )
        grupo = grupos.get(chave)
        if grupo is None:
            grupo = grupos[chave] = GrupoRevisao(
                chave=chave,
                estabelecimento=item.estabelecimento,
                marca=item.marca,
                confirmado=item.estabelecimento_confirmado,
                quantidade=0,
                total_centavos=0,
                descricoes=[],
                ids=[],
            )
        grupo.quantidade += 1
        grupo.total_centavos += item.valor_centavos
        grupo.ids.append(item.id)
        if item.descricao not in grupo.descricoes and len(grupo.descricoes) < 6:
            grupo.descricoes.append(item.descricao)
    return sorted(grupos.values(), key=lambda g: (-g.quantidade, -g.total_centavos))


def contas_de_origem(session: Session) -> list[ContaDeOrigem]:
    linhas = session.execute(
        select(Conta.id, Conta.nome)
        .where(Conta.tipo.in_([TipoConta.ATIVO, TipoConta.PASSIVO]))
        .order_by(Conta.nome)
    )
    return [ContaDeOrigem(id=i, nome=_nome_categoria(n)) for i, n in linhas]


def itens(session: Session, ids: list[int]) -> list[ItemRevisao]:
    if not ids:
        return []
    consulta, _ = _base()
    linhas = session.execute(consulta.where(Transacao.id.in_(ids)).order_by(Transacao.data.desc()))
    encontrados = [_item(linha) for linha in linhas]
    faltando = sorted(set(ids) - {i.id for i in encontrados})
    if faltando:
        raise NaoEncontradas(faltando)
    return encontrados


def problema_no_estabelecimento(nome: str | None) -> str | None:
    if nome is None:
        return None
    if not regras.termos_distintivos(nome):
        return (
            f"{nome!r} não identifica um estabelecimento: Pix, cartão, parcela e afins são forma "
            "de pagamento, não quem recebeu"
        )
    return None


def _origem_principal(conteudo: ConteudoProposta) -> OrigemAlteracao:
    origens = {e.origem for e in conteudo.evidencias}
    for candidata in ("usuario", "pesquisa", "historico", "regra"):
        if candidata in origens:
            return candidata
    return "usuario"


def _sentido_ok(categoria: str, valor_contra: int, existentes: catalogo.Categorias) -> bool:
    return regras.combina_com_o_sentido(categoria, -valor_contra, existentes)


def _avaliar_regra(
    session: Session, sugerida: RegraSugerida, selecionadas: list[ItemRevisao]
) -> tuple[RegraNaPrevia, list[ItemRevisao]]:
    erro = None
    padrao = regras.normalizar(sugerida.padrao)
    try:
        padrao, categoria, estabelecimento = regras.validar(
            session, sugerida.padrao, sugerida.categoria, sugerida.estabelecimento
        )
    except regras.RegraInvalida as falha:
        erro = str(falha)
        categoria, estabelecimento = sugerida.categoria, sugerida.estabelecimento
    casa_selecionadas = sum(regras.casa(padrao, i.descricao) for i in selecionadas)
    if erro is None and casa_selecionadas == 0:
        erro = "a regra não casa com nenhuma das transações selecionadas"
    correspondencias: list[ItemRevisao] = []
    if erro is None:
        consulta, _ = _base()
        for linha in session.execute(consulta.limit(LIMITE_CORRESPONDENCIAS)):
            if regras.casa(padrao, linha[2]):
                correspondencias.append(_item(linha))
    return (
        RegraNaPrevia(
            padrao=padrao,
            categoria=categoria,
            estabelecimento=estabelecimento,
            valida=erro is None,
            erro=erro,
            existente=regras.obter_por_padrao(session, padrao),
            casa_com_selecionadas=casa_selecionadas,
            correspondencias_existentes=len(correspondencias),
        ),
        correspondencias,
    )


def calcular_previa(
    session: Session, conteudo: ConteudoProposta, opcoes: OpcoesAplicacao
) -> Previa:
    existentes = catalogo.listar(session)
    if conteudo.categoria is not None and conteudo.categoria not in existentes.todas:
        raise RevisaoInvalida(f"categoria desconhecida: {conteudo.categoria}")
    if conteudo.categoria is None and conteudo.estabelecimento is None:
        raise RevisaoInvalida("a proposta não muda nem a categoria nem o estabelecimento")
    problema = problema_no_estabelecimento(conteudo.estabelecimento)
    if problema:
        raise RevisaoInvalida(problema)
    selecionadas = itens(session, conteudo.transacao_ids)
    regra_previa, correspondencias = (None, [])
    if conteudo.regra is not None:
        regra_previa, correspondencias = _avaliar_regra(session, conteudo.regra, selecionadas)
    if (opcoes.salvar_regra or opcoes.alcance == "correspondencias") and not (
        regra_previa and regra_previa.valida
    ):
        motivo = regra_previa.erro if regra_previa else "não há regra sugerida"
        raise RevisaoInvalida(f"não dá para usar a regra: {motivo}")

    candidatas: list[tuple[ItemRevisao, Literal["selecao", "regra"], str | None, str | None]] = [
        (item, "selecao", conteudo.categoria, conteudo.estabelecimento) for item in selecionadas
    ]
    if opcoes.alcance == "correspondencias" and regra_previa:
        ja = {i.id for i in selecionadas}
        candidatas += [
            (item, "regra", regra_previa.categoria, regra_previa.estabelecimento)
            for item in correspondencias
            if item.id not in ja
        ]

    afetadas: list[LinhaPrevia] = []
    ignoradas: list[LinhaPrevia] = []
    manuais = efeito = 0
    for item, por, categoria, estabelecimento in candidatas:
        nova = categoria or item.categoria
        estabelecimento_atual = item.estabelecimento if item.estabelecimento_confirmado else None
        novo_estabelecimento = estabelecimento or estabelecimento_atual
        linha = LinhaPrevia(
            id=item.id,
            data=item.data,
            descricao=item.descricao,
            valor_centavos=item.valor_centavos,
            categoria_atual=item.categoria,
            categoria_nova=nova,
            estabelecimento_atual=estabelecimento_atual,
            estabelecimento_novo=novo_estabelecimento,
            categorizada_por=item.categorizada_por,
            por=por,
        )
        if nova == item.categoria and novo_estabelecimento == estabelecimento_atual:
            linha.motivo = "já está assim"
            ignoradas.append(linha)
        elif categoria and not _sentido_ok(categoria, item.valor_centavos, existentes):
            linha.motivo = f"{categoria} não combina com o sentido desse lançamento"
            ignoradas.append(linha)
        elif (
            item.categorizada_por == OrigemCategoria.USUARIO
            and nova != item.categoria
            and not opcoes.substituir_manuais
        ):
            linha.motivo = "classificada à mão antes; marque para substituir"
            manuais += 1
            ignoradas.append(linha)
        else:
            afetadas.append(linha)
            antes = existentes.sentido(item.categoria) == "despesa"
            depois = existentes.sentido(nova) == "despesa"
            if antes and not depois:
                efeito -= item.valor_centavos
            elif depois and not antes:
                efeito += item.valor_centavos

    avisos: list[str] = []
    transferencia = conteudo.categoria == TRANSFERENCIA_INTERNA or bool(
        regra_previa and regra_previa.categoria == TRANSFERENCIA_INTERNA
    )
    if transferencia:
        avisos.append(
            "Transferência interna sai do total de gastos: use só para dinheiro que foi para "
            "outra conta sua. Pix ou TED para outra pessoa ou empresa continua sendo gasto."
        )
    if conteudo.categoria is None:
        avisos.append("A categoria fica como está; só o estabelecimento muda.")
    if any(i.parcela for i in selecionadas):
        avisos.append(
            "Parcelas continuam com o valor de cada parcela e a descrição original; nada é "
            "somado nem multiplicado."
        )
    if manuais:
        avisos.append(f"{manuais} transação(ões) classificadas à mão antes ficam como estão.")

    estado = sorted(
        (
            linha.id,
            linha.categoria_atual,
            linha.estabelecimento_atual,
            linha.categorizada_por.value if linha.categorizada_por else None,
        )
        for linha in [*afetadas, *ignoradas]
    )
    assinatura = hashlib.sha256(
        json.dumps(
            {
                "conteudo": conteudo.model_dump(mode="json"),
                "opcoes": opcoes.model_dump(mode="json"),
                "estado": estado,
                "regra_existente": regra_previa.existente.model_dump()
                if regra_previa and regra_previa.existente
                else None,
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ).encode()
    ).hexdigest()
    return Previa(
        afetadas=afetadas,
        ignoradas=ignoradas,
        manuais_preservadas=manuais,
        efeito_nos_gastos_centavos=efeito,
        regra=regra_previa,
        avisos=avisos,
        exige_confirmar_transferencia=transferencia,
        assinatura=assinatura,
    )


def _lote_por_chave(session: Session, chave: str) -> LoteRevisao | None:
    return session.scalar(select(LoteRevisao).where(LoteRevisao.chave_idempotencia == chave))


def _resultado(session: Session, lote: LoteRevisao, repetido: bool) -> ResultadoLote:
    quantidade = session.scalar(
        select(func.count())
        .select_from(AlteracaoRevisao)
        .where(AlteracaoRevisao.lote_id == lote.id)
    )
    regra = regras.obter(session, lote.regra_id) if lote.regra_id else None
    return ResultadoLote(lote_id=lote.id, alteradas=quantidade, regra=regra, repetido=repetido)


def _conta_da_contrapartida(session: Session, transacao_id: int) -> Lancamento:
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


def aplicar(
    session: Session,
    conteudo: ConteudoProposta,
    opcoes: OpcoesAplicacao,
    assinatura: str,
    chave_idempotencia: str,
    proposta_id: int | None = None,
) -> ResultadoLote:
    repetido = _lote_por_chave(session, chave_idempotencia)
    if repetido is not None:
        return _resultado(session, repetido, repetido=True)
    proposta = None
    if proposta_id is not None:
        proposta = session.scalar(
            select(PropostaRevisao).where(PropostaRevisao.id == proposta_id).with_for_update()
        )
        if proposta is None:
            raise LookupError("proposta não encontrada")
        if proposta.status != "pendente":
            raise PreviaDesatualizada(f"essa proposta já foi {proposta.status}")
    session.execute(
        select(Transacao.id)
        .where(Transacao.id.in_(conteudo.transacao_ids))
        .order_by(Transacao.id)
        .with_for_update()
    ).all()
    previa = calcular_previa(session, conteudo, opcoes)
    if previa.assinatura != assinatura:
        raise PreviaDesatualizada(
            "a seleção, a proposta ou as transações mudaram desde a prévia; revise e aprove de novo"
        )
    if previa.exige_confirmar_transferencia and not opcoes.confirmar_transferencia:
        raise RevisaoInvalida("confirme que é dinheiro indo para outra conta sua")
    if not previa.afetadas and not opcoes.salvar_regra:
        raise RevisaoInvalida(
            "nada a aplicar: todas as transações já estão assim ou foram preservadas"
        )

    partes = []
    if conteudo.estabelecimento:
        partes.append(conteudo.estabelecimento)
    if conteudo.categoria:
        partes.append(f"→ {conteudo.categoria}")
    partes.append(f"({len(previa.afetadas)} transação(ões))")
    lote = LoteRevisao(
        chave_idempotencia=chave_idempotencia,
        proposta_id=proposta.id if proposta else None,
        opcoes={
            "opcoes": opcoes.model_dump(mode="json"),
            "conteudo": conteudo.model_dump(mode="json"),
        },
        resumo=" ".join(partes),
    )
    session.add(lote)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existente = _lote_por_chave(session, chave_idempotencia)
        if existente is None:
            raise
        return _resultado(session, existente, repetido=True)

    regra_salva = None
    if opcoes.salvar_regra and previa.regra:
        anterior = previa.regra.existente
        regra_salva = regras.salvar(
            session,
            previa.regra.padrao,
            previa.regra.categoria,
            previa.regra.estabelecimento,
            commit=False,
        )
        lote.regra_id = regra_salva.id
        lote.regra_criada = anterior is None
        lote.regra_anterior = anterior.model_dump() if anterior else None

    origem_da_selecao = _origem_principal(conteudo)
    for linha in previa.afetadas:
        lancamento = _conta_da_contrapartida(session, linha.id)
        conta_anterior = session.scalar(select(Conta.nome).where(Conta.id == lancamento.conta_id))
        transacao = session.scalar(select(Transacao).where(Transacao.id == linha.id))
        estabelecimento_anterior = transacao.estabelecimento
        por_anterior = transacao.categorizada_por
        origem_db = OrigemCategoria.USUARIO if linha.por == "selecao" else OrigemCategoria.REGRA
        if linha.categoria_nova != linha.categoria_atual:
            aplicar_categoria(session, linha.id, linha.categoria_nova, origem_db)
            session.flush()
        if linha.estabelecimento_novo != estabelecimento_anterior:
            transacao.estabelecimento = linha.estabelecimento_novo
        conta_nova = session.scalar(
            select(Conta.nome)
            .join(Lancamento, Lancamento.conta_id == Conta.id)
            .where(Lancamento.id == lancamento.id)
        )
        session.add(
            AlteracaoRevisao(
                lote_id=lote.id,
                transacao_id=linha.id,
                categoria_anterior=conta_anterior,
                categoria_nova=conta_nova,
                estabelecimento_anterior=estabelecimento_anterior,
                estabelecimento_novo=linha.estabelecimento_novo,
                categorizada_por_anterior=por_anterior,
                categorizada_por_nova=transacao.categorizada_por,
                origem=origem_da_selecao if linha.por == "selecao" else "regra",
                regra_id=lote.regra_id if (linha.por == "regra" or opcoes.salvar_regra) else None,
            )
        )
    if proposta is not None:
        proposta.status = "aplicada"
        proposta.decidida_em = datetime.now(UTC)
        proposta.conteudo = {**proposta.conteudo, "aprovado": conteudo.model_dump(mode="json")}
    session.commit()
    return ResultadoLote(
        lote_id=lote.id, alteradas=len(previa.afetadas), regra=regra_salva, repetido=False
    )


def rejeitar(session: Session, proposta_id: int) -> bool:
    proposta = session.scalar(
        select(PropostaRevisao).where(PropostaRevisao.id == proposta_id).with_for_update()
    )
    if proposta is None:
        return False
    if proposta.status == "pendente":
        proposta.status = "rejeitada"
        proposta.decidida_em = datetime.now(UTC)
        session.commit()
    return True


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
        lancamento = _conta_da_contrapartida(session, alteracao.transacao_id)
        conta_atual = session.scalar(select(Conta.nome).where(Conta.id == lancamento.conta_id))
        transacao = session.scalar(select(Transacao).where(Transacao.id == alteracao.transacao_id))
        if (
            conta_atual != alteracao.categoria_nova
            or transacao.estabelecimento != alteracao.estabelecimento_novo
        ):
            conflitos.append(alteracao.transacao_id)
            continue
        if alteracao.categoria_anterior != alteracao.categoria_nova:
            conta = session.scalar(select(Conta).where(Conta.nome == alteracao.categoria_anterior))
            if conta is None:
                conflitos.append(alteracao.transacao_id)
                continue
            lancamento.conta_id = conta.id
        transacao.estabelecimento = alteracao.estabelecimento_anterior
        transacao.categorizada_por = alteracao.categorizada_por_anterior
        desfeitas += 1
    if lote.regra_id is not None:
        if lote.regra_criada:
            session.execute(delete(RegraCategoria).where(RegraCategoria.id == lote.regra_id))
        elif lote.regra_anterior:
            session.execute(
                update(RegraCategoria)
                .where(RegraCategoria.id == lote.regra_id)
                .values(
                    categoria=lote.regra_anterior.get("categoria"),
                    estabelecimento=lote.regra_anterior.get("estabelecimento"),
                )
            )
    lote.desfeito_em = datetime.now(UTC)
    session.commit()
    return ResultadoDesfazer(
        lote_id=lote.id, desfeitas=desfeitas, conflitos=conflitos, ja_desfeito=False
    )


def historico(session: Session, limite: int = 30) -> list[LoteResumo]:
    quantidade = (
        select(func.count())
        .select_from(AlteracaoRevisao)
        .where(AlteracaoRevisao.lote_id == LoteRevisao.id)
        .scalar_subquery()
    )
    linhas = session.execute(
        select(LoteRevisao, quantidade).order_by(LoteRevisao.criado_em.desc()).limit(limite)
    )
    return [
        LoteResumo(
            id=lote.id,
            resumo=lote.resumo,
            criado_em=lote.criado_em,
            desfeito_em=lote.desfeito_em,
            alteracoes=qtd,
            regra_id=lote.regra_id,
        )
        for lote, qtd in linhas
    ]
