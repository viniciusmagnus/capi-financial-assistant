from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from nota_a_nota import cofrinho, estabelecimentos
from nota_a_nota.ledger import (
    CARTEIRA,
    DESPESA_A_CLASSIFICAR,
    RECEITA_A_CLASSIFICAR,
    TRANSFERENCIA_INTERNA,
)
from nota_a_nota.models import Conta, Importacao, Lancamento, TipoConta, Transacao
from nota_a_nota.perfil import Renda, obter_renda

DIAS_MINIMOS_PARA_PROJETAR = 7
ECONOMIA_MINIMA = 1_000
SEM_CATEGORIA = "A classificar"
REEMBOLSOS = "Reembolsos"
ESSENCIAIS = {"Moradia", "Mercado", "Saúde", "Educação", "Impostos e taxas", "Pets"}
APPS_DELIVERY = {"ifood", "ubereats", "rappi"}
APPS_TRANSPORTE = {"uber", "99"}

Base = Literal["mes_completo", "projecao", "periodo"]


class ContaNoPeriodo(BaseModel):
    nome: str
    tipo: Literal["ativo", "passivo"]
    inicio: date | None
    fim: date | None
    cobre_o_mes: bool
    anotada_a_mao: bool


class Periodo(BaseModel):
    inicio: date | None
    fim: date | None
    dias_cobertos: int
    dias_no_mes: int
    parcial: bool
    descricao: str


class Projecao(BaseModel):
    fator: float
    dias_base: int
    gastos_centavos: int
    comprometimento: float | None
    diferenca_centavos: int | None


class Entrada(BaseModel):
    categoria: str
    total_centavos: int
    quantidade: int


class Totais(BaseModel):
    gastos_centavos: int
    quantidade_gastos: int
    sem_categoria_centavos: int
    sem_categoria_quantidade: int
    para_revisar: int
    estornos_centavos: int
    entradas: list[Entrada]
    transferencias_saida_centavos: int
    transferencias_entrada_centavos: int


class Linha(BaseModel):
    chave: str
    nome: str
    marca: str | None
    categoria: str
    total_centavos: int
    quantidade: int
    pct_gastos: float
    pct_renda: float | None


class TransacaoDiagnostico(BaseModel):
    id: int
    data: date
    descricao: str
    valor_centavos: int
    categoria: str
    estabelecimento: str
    conta: str
    revisar: bool
    confianca: str | None


class Aviso(BaseModel):
    tipo: str
    nivel: Literal["info", "atencao"]
    texto: str


class Recomendacao(BaseModel):
    id: str
    tipo: str
    alvo_tipo: Literal["categoria", "estabelecimento"]
    alvo_chave: str
    alvo_nome: str
    titulo: str
    fato: str
    consequencia: str
    acao: str
    reducao: float
    economia_centavos: int
    base: Base
    calculo: str
    capi: str = ""


class Diagnostico(BaseModel):
    mes: str
    meses_disponiveis: list[str]
    renda: Renda | None
    renda_referencia_centavos: int | None
    periodo: Periodo
    contas: list[ContaNoPeriodo]
    totais: Totais
    comprometimento: float | None
    diferenca_centavos: int | None
    projecao: Projecao | None
    base: Base
    fator_base: float
    categorias: list[Linha]
    estabelecimentos: list[Linha]
    transacoes: list[TransacaoDiagnostico]
    avisos: list[Aviso]
    recomendacoes: list[Recomendacao]
    economia_combinada_centavos: int


def reais(centavos: int) -> str:
    sinal = "-" if centavos < 0 else ""
    inteiro, resto = divmod(abs(centavos), 100)
    return f"{sinal}R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def porcento(fracao: float) -> str:
    valor = round(fracao * 100, 1)
    return f"{valor:.0f}%" if valor == int(valor) else f"{valor:.1f}%".replace(".", ",")


def _dia(d: date) -> str:
    return d.strftime("%d/%m")


@dataclass
class _Linha:
    id: int
    data: date
    descricao: str
    confianca: str | None
    contra_nome: str
    contra_tipo: TipoConta
    contra_valor: int
    conta_nome: str | None


def _carregar(session: Session, inicio: date, fim: date) -> list[_Linha]:
    contra_conta = aliased(Conta)
    contra = aliased(Lancamento)
    origem_conta = aliased(Conta)
    origem = aliased(Lancamento)
    linhas = session.execute(
        select(
            Transacao.id,
            Transacao.data,
            Transacao.descricao,
            Transacao.confianca_categoria,
            contra_conta.nome,
            contra_conta.tipo,
            contra.valor_centavos,
            origem_conta.nome,
        )
        .join(contra, contra.transacao_id == Transacao.id)
        .join(contra_conta, contra_conta.id == contra.conta_id)
        .join(origem, origem.transacao_id == Transacao.id)
        .join(origem_conta, origem_conta.id == origem.conta_id)
        .where(
            Transacao.data.between(inicio, fim),
            contra_conta.tipo.in_([TipoConta.DESPESA, TipoConta.RECEITA, TipoConta.PATRIMONIO]),
            origem_conta.tipo.in_([TipoConta.ATIVO, TipoConta.PASSIVO]),
        )
        .order_by(Transacao.data.desc(), Transacao.id.desc())
    )
    return [_Linha(*linha) for linha in linhas]


def meses_com_dados(session: Session) -> list[str]:
    mes = func.to_char(Transacao.data, "YYYY-MM").label("mes")
    return list(session.scalars(select(mes).group_by(mes).order_by(mes.desc())))


def _juntar(intervalos: list[tuple[date, date]]) -> list[tuple[date, date]]:
    juntos: list[tuple[date, date]] = []
    for inicio, fim in sorted(intervalos):
        if juntos and inicio <= juntos[-1][1] + timedelta(days=1):
            juntos[-1] = (juntos[-1][0], max(juntos[-1][1], fim))
        else:
            juntos.append((inicio, fim))
    return juntos


def _cobertura(
    session: Session, inicio: date, fim: date, hoje: date, contas_com_movimento: set[str]
) -> tuple[list[ContaNoPeriodo], list[tuple[date, date]]]:
    por_conta: dict[tuple[str, TipoConta], list[tuple[date, date]]] = defaultdict(list)
    for nome, tipo, imp_inicio, imp_fim in session.execute(
        select(Conta.nome, Conta.tipo, Importacao.inicio, Importacao.fim)
        .join(Importacao, Importacao.conta_id == Conta.id)
        .where(
            Importacao.inicio.is_not(None),
            Importacao.fim.is_not(None),
            Importacao.inicio <= fim,
            Importacao.fim >= inicio,
        )
    ):
        limite = min(fim, hoje)
        a, b = max(imp_inicio, inicio), min(imp_fim, limite)
        if a <= b:
            por_conta[(nome, tipo)].append((a, b))

    contas: list[ContaNoPeriodo] = []
    todos: list[tuple[date, date]] = []
    for (nome, tipo), intervalos in sorted(por_conta.items()):
        juntos = _juntar(intervalos)
        todos.extend(juntos)
        cobre = len(juntos) == 1 and juntos[0][0] == inicio and juntos[0][1] == fim
        contas.append(
            ContaNoPeriodo(
                nome=nome.split(":", 1)[1],
                tipo=tipo.value,
                inicio=juntos[0][0],
                fim=juntos[-1][1],
                cobre_o_mes=cobre,
                anotada_a_mao=False,
            )
        )
    nomes_cobertos = {f"{'Ativo' if c.tipo == 'ativo' else 'Passivo'}:{c.nome}" for c in contas}
    for nome in sorted(contas_com_movimento - nomes_cobertos):
        contas.append(
            ContaNoPeriodo(
                nome=nome.split(":", 1)[1],
                tipo="passivo" if nome.startswith("Passivo:") else "ativo",
                inicio=None,
                fim=None,
                cobre_o_mes=False,
                anotada_a_mao=nome == CARTEIRA,
            )
        )
    return contas, _juntar(todos)


def _periodo(inicio: date, fim: date, hoje: date, uniao: list[tuple[date, date]]) -> Periodo:
    dias_no_mes = (fim - inicio).days + 1
    if not uniao:
        return Periodo(
            inicio=None,
            fim=None,
            dias_cobertos=0,
            dias_no_mes=dias_no_mes,
            parcial=True,
            descricao="Nenhum extrato importado cobre este mês; só aparecem gastos anotados à mão.",
        )
    p_inicio, p_fim = uniao[0][0], uniao[-1][1]
    dias = sum((b - a).days + 1 for a, b in uniao)
    parcial = dias < dias_no_mes
    if not parcial:
        descricao = f"O extrato cobre o mês inteiro ({dias_no_mes} dias)."
    else:
        descricao = (
            f"O extrato cobre {dias} de {dias_no_mes} dias ({_dia(p_inicio)} a {_dia(p_fim)})"
        )
        descricao += ", com um intervalo sem dados." if len(uniao) > 1 else "."
        if fim >= hoje >= inicio:
            descricao += " O mês ainda está em andamento."
    return Periodo(
        inicio=p_inicio,
        fim=p_fim,
        dias_cobertos=dias,
        dias_no_mes=dias_no_mes,
        parcial=parcial,
        descricao=descricao,
    )


def _linhas(
    grupos: dict[str, list[TransacaoDiagnostico]],
    nomes: dict[str, tuple[str, str | None]],
    gastos: int,
    renda_ref: int | None,
) -> list[Linha]:
    resultado = []
    for chave, itens in grupos.items():
        total = sum(t.valor_centavos for t in itens)
        if total <= 0:
            continue
        por_categoria: dict[str, int] = defaultdict(int)
        for t in itens:
            por_categoria[t.categoria] += t.valor_centavos
        nome, marca = nomes[chave]
        resultado.append(
            Linha(
                chave=chave,
                nome=nome,
                marca=marca,
                categoria=max(por_categoria, key=por_categoria.__getitem__),
                total_centavos=total,
                quantidade=len(itens),
                pct_gastos=total / gastos if gastos > 0 else 0.0,
                pct_renda=total / renda_ref if renda_ref else None,
            )
        )
    return sorted(resultado, key=lambda linha: (-linha.total_centavos, linha.nome))


@dataclass
class _Contexto:
    gastos: int
    renda_ref: int | None
    renda: Renda | None
    base: Base
    fator: float
    periodo: Periodo


def _texto_base(ctx: _Contexto, total: int, reducao: float, economia: int) -> str:
    pct = porcento(reducao)
    if ctx.base == "mes_completo":
        return f"{pct} de {reais(total)} gastos no mês = {reais(economia)} por mês."
    if ctx.base == "projecao":
        mensal = round(total * ctx.fator)
        return (
            f"{reais(total)} em {ctx.periodo.dias_cobertos} dias viram {reais(mensal)} projetados "
            f"para {ctx.periodo.dias_no_mes} dias (mesmo ritmo). {pct} disso = {reais(economia)} por mês."
        )
    return (
        f"{pct} de {reais(total)} gastos nos {ctx.periodo.dias_cobertos} dias do extrato = "
        f"{reais(economia)} nesse período. É pouco tempo para projetar o mês."
    )


def _consequencia(ctx: _Contexto, total: int, posicao: int) -> str:
    mensal = round(total * ctx.fator)
    if ctx.renda and ctx.renda.valor_centavos > 0 and ctx.base != "periodo":
        dias = max(1, round(mensal / ctx.renda.valor_centavos * 30))
        unidade = "dia" if dias == 1 else "dias"
        return f"É o equivalente a {dias} {unidade} da sua renda do mês."
    if ctx.renda_ref:
        return f"É {porcento(total / ctx.renda_ref)} da sua renda do mês."
    return f"É a {posicao}ª maior fatia dos seus gastos ({porcento(total / ctx.gastos)} do total)."


def _proporcao(ctx: _Contexto, total: int) -> str:
    if ctx.renda_ref:
        return f"{porcento(total / ctx.renda_ref)} da sua renda"
    return f"{porcento(total / ctx.gastos)} de tudo que você gastou"


def _recomendacoes(
    ctx: _Contexto,
    categorias: list[Linha],
    lojas: list[Linha],
    transacoes: list[TransacaoDiagnostico],
) -> list[Recomendacao]:
    if ctx.gastos <= 0:
        return []
    candidatas: list[tuple[Recomendacao, set[int]]] = []
    periodo = "neste mês" if ctx.base == "mes_completo" else "no período do extrato"
    unidade = "por mês" if ctx.base != "periodo" else "no período"

    def relevante(total: int, pct_renda: float, pct_gastos: float) -> bool:
        if ctx.renda_ref:
            return total / ctx.renda_ref >= pct_renda
        return total / ctx.gastos >= pct_gastos

    def nova(
        tipo: str,
        linha: Linha,
        alvo_tipo: Literal["categoria", "estabelecimento"],
        reducao: float,
        titulo: str,
        fato: str,
        acao: str,
        ids: set[int],
    ) -> None:
        economia = round(linha.total_centavos * ctx.fator * reducao)
        if economia < ECONOMIA_MINIMA:
            return
        lista = categorias if alvo_tipo == "categoria" else lojas
        candidatas.append(
            (
                Recomendacao(
                    id=f"{tipo}:{linha.chave}",
                    tipo=tipo,
                    alvo_tipo=alvo_tipo,
                    alvo_chave=linha.chave,
                    alvo_nome=linha.nome,
                    titulo=titulo,
                    fato=fato,
                    consequencia=_consequencia(ctx, linha.total_centavos, lista.index(linha) + 1),
                    acao=f"{acao} Isso liberaria cerca de {reais(economia)} {unidade}.",
                    reducao=reducao,
                    economia_centavos=economia,
                    base=ctx.base,
                    calculo=_texto_base(ctx, linha.total_centavos, reducao, economia),
                ),
                ids,
            )
        )

    def ids_de(chave: str, campo: str) -> set[int]:
        return {t.id for t in transacoes if getattr(t, campo) == chave and t.valor_centavos > 0}

    for linha in lojas:
        if linha.marca in APPS_DELIVERY and linha.quantidade >= 4:
            menos = linha.quantidade // 2
            ticket = linha.total_centavos // linha.quantidade
            nova(
                "app_delivery",
                linha,
                "estabelecimento",
                menos / linha.quantidade,
                f"{linha.quantidade} pedidos no {linha.nome}",
                f"Foram {linha.quantidade} pedidos no {linha.nome} {periodo}, com ticket médio de "
                f"{reais(ticket)}, somando {reais(linha.total_centavos)}.",
                f"Trocar {menos} desses pedidos por comida feita em casa ou marmita.",
                ids_de(linha.chave, "estabelecimento"),
            )
        elif linha.marca in APPS_TRANSPORTE and linha.quantidade >= 4:
            nova(
                "app_transporte",
                linha,
                "estabelecimento",
                0.3,
                f"{linha.quantidade} corridas de {linha.nome}",
                f"Foram {linha.quantidade} corridas de {linha.nome} {periodo}, somando "
                f"{reais(linha.total_centavos)} ({_proporcao(ctx, linha.total_centavos)}).",
                "Trocar 3 em cada 10 corridas por ônibus, carona ou caminhada nos trajetos curtos.",
                ids_de(linha.chave, "estabelecimento"),
            )

    por_categoria = {linha.chave: linha for linha in categorias}
    regras_categoria = (
        (
            "Restaurantes e delivery",
            0.25,
            0.05,
            0.10,
            "Comer fora e delivery",
            "Definir dois dias fixos por semana para comer fora ou pedir comida e cortar 25% desse gasto.",
        ),
        (
            "Lazer",
            0.20,
            0.08,
            0.15,
            "Lazer em destaque",
            "Separar um valor para lazer no começo do mês e escolher antes onde gastar, cortando 20%.",
        ),
        (
            "Vestuário",
            0.30,
            0.05,
            0.10,
            "Compras de roupa",
            "Esperar 7 dias antes de comprar roupa que não estava planejada e cortar 30% desse gasto.",
        ),
    )
    for categoria, reducao, pct_renda, pct_gastos, titulo, acao in regras_categoria:
        linha = por_categoria.get(categoria)
        if linha and relevante(linha.total_centavos, pct_renda, pct_gastos):
            nova(
                f"categoria_{categoria}",
                linha,
                "categoria",
                reducao,
                titulo,
                f"{categoria} somou {reais(linha.total_centavos)} em {linha.quantidade} "
                f"{'gasto' if linha.quantidade == 1 else 'gastos'} {periodo} — "
                f"{_proporcao(ctx, linha.total_centavos)}.",
                acao,
                ids_de(categoria, "categoria"),
            )

    assinaturas = por_categoria.get("Assinaturas")
    if assinaturas and assinaturas.quantidade >= 2:
        valores = [
            t.valor_centavos
            for t in transacoes
            if t.categoria == "Assinaturas" and t.valor_centavos > 0
        ]
        menor = min(valores)
        nova(
            "assinaturas",
            assinaturas,
            "categoria",
            menor / assinaturas.total_centavos,
            f"{assinaturas.quantidade} cobranças de assinatura",
            f"Apareceram {assinaturas.quantidade} cobranças de assinatura {periodo}, somando "
            f"{reais(assinaturas.total_centavos)}. A menor foi de {reais(menor)}.",
            "Abrir cada uma e conferir quando foi o último uso; se alguma estiver parada, "
            "cancelar a menor já faz diferença.",
            ids_de("Assinaturas", "categoria"),
        )

    escolhidas: list[Recomendacao] = []
    cobertas: set[int] = set()
    for recomendacao, ids in sorted(candidatas, key=lambda par: -par[0].economia_centavos):
        if ids and len(ids & cobertas) / len(ids) >= 0.8:
            continue
        escolhidas.append(recomendacao)
        cobertas |= ids
        if len(escolhidas) == 3:
            break
    return escolhidas


def economia_combinada(
    recomendacoes: list[Recomendacao], transacoes: list[TransacaoDiagnostico], fator: float
) -> int:
    maior: dict[int, float] = defaultdict(float)
    for r in recomendacoes:
        campo = "categoria" if r.alvo_tipo == "categoria" else "estabelecimento"
        for t in transacoes:
            if getattr(t, campo) == r.alvo_chave and t.valor_centavos > 0:
                maior[t.id] = max(maior[t.id], r.reducao)
    valores = {t.id: t.valor_centavos for t in transacoes}
    return round(sum(valores[i] * fracao for i, fracao in maior.items()) * fator)


def montar(session: Session, inicio: date, referencia: date | None = None) -> Diagnostico:
    hoje = referencia or cofrinho.hoje()
    dias_no_mes = monthrange(inicio.year, inicio.month)[1]
    fim = inicio + timedelta(days=dias_no_mes - 1)
    renda = obter_renda(session)
    linhas = _carregar(session, inicio, fim)

    transacoes: list[TransacaoDiagnostico] = []
    nomes_loja: dict[str, tuple[str, str | None]] = {}
    entradas: dict[str, list[int]] = defaultdict(list)
    estornos = transf_saida = transf_entrada = 0
    para_revisar = 0
    contas_com_movimento: set[str] = set()
    descricoes_fatura: list[int] = []

    for linha in linhas:
        categoria = linha.contra_nome.split(":", 1)[1]
        if linha.conta_nome:
            contas_com_movimento.add(linha.conta_nome)
        pendente = linha.contra_nome in (DESPESA_A_CLASSIFICAR, RECEITA_A_CLASSIFICAR)
        revisar = pendente or linha.confianca == "baixa"
        para_revisar += revisar
        if linha.contra_tipo == TipoConta.DESPESA:
            loja = estabelecimentos.identificar(linha.descricao)
            nomes_loja[loja.chave] = (loja.nome, loja.marca)
            transacoes.append(
                TransacaoDiagnostico(
                    id=linha.id,
                    data=linha.data,
                    descricao=linha.descricao,
                    valor_centavos=linha.contra_valor,
                    categoria=categoria,
                    estabelecimento=loja.chave,
                    conta=(linha.conta_nome or "").split(":", 1)[-1],
                    revisar=revisar,
                    confianca=linha.confianca,
                )
            )
        elif linha.contra_tipo == TipoConta.RECEITA:
            valor = -linha.contra_valor
            if categoria == REEMBOLSOS:
                estornos += valor
            else:
                entradas[categoria].append(valor)
        elif categoria == TRANSFERENCIA_INTERNA:
            if linha.contra_valor > 0:
                transf_saida += linha.contra_valor
                if "FATURA" in estabelecimentos.normalizar(linha.descricao):
                    descricoes_fatura.append(linha.contra_valor)
            else:
                transf_entrada += -linha.contra_valor

    gastos = sum(t.valor_centavos for t in transacoes)
    sem_categoria = [t for t in transacoes if t.categoria == SEM_CATEGORIA]
    contas, uniao = _cobertura(session, inicio, fim, hoje, contas_com_movimento)
    periodo = _periodo(inicio, fim, hoje, uniao)

    renda_valor = renda.valor_centavos if renda else None
    renda_ref = renda_valor

    if not periodo.parcial:
        base: Base = "mes_completo"
        fator = 1.0
    elif periodo.dias_cobertos >= DIAS_MINIMOS_PARA_PROJETAR:
        base, fator = "projecao", dias_no_mes / periodo.dias_cobertos
    else:
        base, fator = "periodo", 1.0

    projecao = None
    if base == "projecao":
        gastos_mes = round(gastos * fator)
        projecao = Projecao(
            fator=round(fator, 4),
            dias_base=periodo.dias_cobertos,
            gastos_centavos=gastos_mes,
            comprometimento=gastos_mes / renda_valor if renda_valor else None,
            diferenca_centavos=renda_valor - gastos_mes if renda_valor is not None else None,
        )

    por_categoria: dict[str, list[TransacaoDiagnostico]] = defaultdict(list)
    por_loja: dict[str, list[TransacaoDiagnostico]] = defaultdict(list)
    for t in transacoes:
        por_categoria[t.categoria].append(t)
        por_loja[t.estabelecimento].append(t)
    categorias = _linhas(por_categoria, {c: (c, None) for c in por_categoria}, gastos, renda_ref)
    lojas = _linhas(por_loja, nomes_loja, gastos, renda_ref)

    ctx = _Contexto(
        gastos=gastos, renda_ref=renda_ref, renda=renda, base=base, fator=fator, periodo=periodo
    )
    recomendacoes = _recomendacoes(ctx, categorias, lojas, transacoes)

    avisos: list[Aviso] = []
    if periodo.parcial:
        texto = periodo.descricao
        if base == "projecao":
            texto += (
                " Os percentuais comparam os gastos registrados até aqui com a renda do mês"
                " inteiro, então ainda vão subir até o mês fechar."
            )
        elif periodo.dias_cobertos:
            texto += " É pouco tempo para projetar o mês inteiro com segurança."
        avisos.append(Aviso(tipo="periodo_parcial", nivel="atencao", texto=texto))
    if renda is None:
        avisos.append(
            Aviso(
                tipo="sem_renda",
                nivel="atencao",
                texto="Informe sua renda mensal para ver quanto dela os gastos consomem.",
            )
        )
    elif renda.valor_centavos == 0:
        avisos.append(
            Aviso(
                tipo="renda_zero",
                nivel="info",
                texto="Com renda zero informada, o diagnóstico mostra só como os gastos se dividem, sem percentuais da renda.",
            )
        )
    if renda_ref and gastos > renda_ref:
        avisos.append(
            Aviso(
                tipo="gastos_acima_da_renda",
                nivel="atencao",
                texto=f"Os gastos registrados passaram a renda do mês em {reais(gastos - renda_ref)}.",
            )
        )
    if sem_categoria:
        total = sum(t.valor_centavos for t in sem_categoria)
        avisos.append(
            Aviso(
                tipo="sem_categoria",
                nivel="atencao",
                texto=f"{reais(total)} em {len(sem_categoria)} {'gasto' if len(sem_categoria) == 1 else 'gastos'} ainda sem categoria. Eles entram no total e aparecem como “A classificar” até você revisar.",
            )
        )
    if descricoes_fatura and not any(c.tipo == "passivo" for c in contas):
        avisos.append(
            Aviso(
                tipo="fatura_sem_cartao",
                nivel="atencao",
                texto=f"Há {reais(sum(descricoes_fatura))} em pagamento de fatura, tratados como transferência para não contar duas vezes. As compras desse cartão só entram no diagnóstico se você importar o extrato do cartão.",
            )
        )
    if transf_saida or transf_entrada:
        avisos.append(
            Aviso(
                tipo="transferencias",
                nivel="info",
                texto=f"Transferências entre suas contas ({reais(transf_saida)} saindo e {reais(transf_entrada)} entrando) ficaram fora dos gastos.",
            )
        )
    if estornos:
        avisos.append(
            Aviso(
                tipo="estornos",
                nivel="info",
                texto=f"Estornos e reembolsos somaram {reais(estornos)}. Eles aparecem separados e não foram descontados dos gastos, porque nem sempre dá para saber a qual compra pertencem.",
            )
        )
    cobertas = [c for c in contas if c.inicio]
    if len({(c.inicio, c.fim) for c in cobertas}) > 1:
        avisos.append(
            Aviso(
                tipo="periodos_diferentes",
                nivel="info",
                texto="As contas importadas cobrem períodos diferentes; confira as datas de cada uma abaixo.",
            )
        )

    return Diagnostico(
        mes=inicio.strftime("%Y-%m"),
        meses_disponiveis=meses_com_dados(session),
        renda=renda,
        renda_referencia_centavos=renda_ref,
        periodo=periodo,
        contas=contas,
        totais=Totais(
            gastos_centavos=gastos,
            quantidade_gastos=len(transacoes),
            sem_categoria_centavos=sum(t.valor_centavos for t in sem_categoria),
            sem_categoria_quantidade=len(sem_categoria),
            para_revisar=para_revisar,
            estornos_centavos=estornos,
            entradas=sorted(
                (
                    Entrada(categoria=c, total_centavos=sum(v), quantidade=len(v))
                    for c, v in entradas.items()
                ),
                key=lambda e: -e.total_centavos,
            ),
            transferencias_saida_centavos=transf_saida,
            transferencias_entrada_centavos=transf_entrada,
        ),
        comprometimento=gastos / renda_ref if renda_ref else None,
        diferenca_centavos=renda_ref - gastos if renda_ref is not None else None,
        projecao=projecao,
        base=base,
        fator_base=round(fator, 4),
        categorias=categorias,
        estabelecimentos=lojas,
        transacoes=transacoes,
        avisos=avisos,
        recomendacoes=recomendacoes,
        economia_combinada_centavos=economia_combinada(recomendacoes, transacoes, fator),
    )
