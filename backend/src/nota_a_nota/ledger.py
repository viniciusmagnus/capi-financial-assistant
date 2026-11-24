from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nota_a_nota.acesso import dono
from nota_a_nota.ingestao.extrato import Extrato, TransacaoExtrato, nucleo_descricao
from nota_a_nota.models import (
    Conta,
    Importacao,
    Lancamento,
    OrigemCategoria,
    TipoConta,
    Transacao,
    Trecho,
)

DESPESA_A_CLASSIFICAR = "Despesa:A classificar"
RECEITA_A_CLASSIFICAR = "Receita:A classificar"
CARTEIRA = "Ativo:Carteira"

CATEGORIAS_DESPESA = (
    "Moradia",
    "Mercado",
    "Restaurantes e delivery",
    "Transporte",
    "Saúde",
    "Educação",
    "Lazer",
    "Assinaturas",
    "Vestuário",
    "Pets",
    "Impostos e taxas",
    "Presentes e doações",
    "Outros",
)
CATEGORIAS_RECEITA = ("Salário", "Rendimentos", "Reembolsos", "Outras receitas")
TRANSFERENCIA_INTERNA = "Transferência interna"

CONTAS_PADRAO: list[tuple[str, TipoConta]] = [
    (DESPESA_A_CLASSIFICAR, TipoConta.DESPESA),
    (RECEITA_A_CLASSIFICAR, TipoConta.RECEITA),
    (CARTEIRA, TipoConta.ATIVO),
    (f"Patrimonio:{TRANSFERENCIA_INTERNA}", TipoConta.PATRIMONIO),
    ("Patrimonio:Saldo de abertura", TipoConta.PATRIMONIO),
    *((f"Despesa:{nome}", TipoConta.DESPESA) for nome in CATEGORIAS_DESPESA),
    *((f"Receita:{nome}", TipoConta.RECEITA) for nome in CATEGORIAS_RECEITA),
]


@dataclass(frozen=True)
class ResultadoImportacao:
    conta: str
    novas: int
    duplicadas: int
    importacao_id: int | None = None
    inicio: date | None = None
    fim: date | None = None


def nome_conta_categoria(categoria: str) -> str:
    if categoria == TRANSFERENCIA_INTERNA:
        return f"Patrimonio:{TRANSFERENCIA_INTERNA}"
    if categoria in CATEGORIAS_RECEITA:
        return f"Receita:{categoria}"
    return f"Despesa:{categoria}"


def obter_ou_criar_conta(session: Session, nome: str, tipo: TipoConta) -> Conta:
    conta = session.scalar(select(Conta).where(Conta.nome == nome))
    if conta is None:
        conta = Conta(nome=nome, tipo=tipo)
        session.add(conta)
        session.flush()
    return conta


def criar_contas_padrao(session: Session) -> None:
    session.execute(
        insert(Conta)
        .values([{"usuario_id": dono(session), "nome": n, "tipo": t} for n, t in CONTAS_PADRAO])
        .on_conflict_do_nothing(constraint="uq_conta_nome")
    )


def _compativel(conta: Conta, extrato: Extrato) -> bool:
    return not (conta.numero and extrato.conta and conta.numero != extrato.conta)


def _completar(conta: Conta, extrato: Extrato) -> Conta:
    conta.banco = conta.banco or extrato.banco
    conta.numero = conta.numero or extrato.conta
    return conta


def _conta_do_extrato(session: Session, extrato: Extrato, apelido: str | None) -> Conta:
    tipo = TipoConta.PASSIVO if extrato.cartao_de_credito else TipoConta.ATIVO
    prefixo = "Passivo" if extrato.cartao_de_credito else "Ativo"
    if apelido:
        return _completar(obter_ou_criar_conta(session, f"{prefixo}:{apelido}", tipo), extrato)
    if extrato.conta:
        conta = session.scalar(
            select(Conta).where(Conta.tipo == tipo, Conta.numero == extrato.conta)
        )
        if conta is not None:
            return _completar(conta, extrato)
    if extrato.banco:
        candidatas = [
            c
            for c in session.scalars(
                select(Conta).where(Conta.tipo == tipo, Conta.banco == extrato.banco)
            )
            if _compativel(c, extrato)
        ]
        if len(candidatas) == 1:
            return _completar(candidatas[0], extrato)

    rotulo = "Cartão" if extrato.cartao_de_credito else "Conta"
    if extrato.banco:
        base = f"{rotulo} {extrato.banco}"
    elif extrato.conta:
        base = f"{rotulo} final {extrato.conta[-4:]}"
    else:
        base = "Cartão importado" if extrato.cartao_de_credito else "Conta importada"
    nome, sufixo = f"{prefixo}:{base}", 1
    while (existente := session.scalar(select(Conta).where(Conta.nome == nome))) is not None:
        if existente.tipo == tipo and _compativel(existente, extrato):
            return _completar(existente, extrato)
        sufixo += 1
        nome = f"{prefixo}:{base} {sufixo}"
    conta = Conta(nome=nome, tipo=tipo, banco=extrato.banco, numero=extrato.conta)
    session.add(conta)
    session.flush()
    return conta


def _parecidas(a: str, b: str) -> bool:
    prefixo = min(len(a), len(b), 10)
    return a == b or (prefixo >= 5 and a[:prefixo] == b[:prefixo])


def _ja_registradas(
    session: Session, conta_id: int, inicio: date | None, fim: date | None
) -> dict[tuple[date, int], list[tuple[str, str]]]:
    consulta = (
        select(Transacao.data, Lancamento.valor_centavos, Transacao.descricao, Transacao.origem)
        .join(Lancamento, Lancamento.transacao_id == Transacao.id)
        .where(Lancamento.conta_id == conta_id)
    )
    if inicio and fim:
        consulta = consulta.where(Transacao.data.between(inicio, fim))
    registradas: dict[tuple[date, int], list[tuple[str, str]]] = {}
    for data, valor, descricao, origem in session.execute(consulta):
        registradas.setdefault((data, valor), []).append((nucleo_descricao(descricao), origem))
    return registradas


def _ja_existe(
    registradas: dict[tuple[date, int], list[tuple[str, str]]],
    item: TransacaoExtrato,
    formato: str,
) -> bool:
    candidatas = registradas.get((item.data, item.valor_centavos))
    if not candidatas:
        return False
    nucleo = nucleo_descricao(item.descricao)
    escolhida = next(
        (i for i, (outra, _) in enumerate(candidatas) if _parecidas(nucleo, outra)),
        next((i for i, (_, origem) in enumerate(candidatas) if origem != formato), None),
    )
    if escolhida is None:
        return False
    del candidatas[escolhida]
    return True


def importar_extrato(
    session: Session, extrato: Extrato, apelido: str | None = None, arquivo: str | None = None
) -> ResultadoImportacao:
    conta = _conta_do_extrato(session, extrato, apelido)
    registradas = _ja_registradas(session, conta.id, extrato.inicio, extrato.fim)
    prefixo_id = extrato.conta if extrato.formato == "ofx" else str(conta.id)
    importacao = Importacao(
        conta_id=conta.id,
        arquivo=(arquivo or "")[:200] or None,
        inicio=extrato.inicio,
        fim=extrato.fim,
        novas=0,
        duplicadas=0,
    )
    session.add(importacao)
    session.flush()
    despesa = obter_ou_criar_conta(session, DESPESA_A_CLASSIFICAR, TipoConta.DESPESA)
    receita = obter_ou_criar_conta(session, RECEITA_A_CLASSIFICAR, TipoConta.RECEITA)

    novas = duplicadas = 0
    for item in extrato.transacoes:
        if item.valor_centavos == 0:
            continue
        if _ja_existe(registradas, item, extrato.formato):
            duplicadas += 1
            continue
        transacao_id = session.scalar(
            insert(Transacao)
            .values(
                usuario_id=dono(session),
                data=item.data,
                descricao=item.descricao,
                origem=extrato.formato,
                id_externo=f"{prefixo_id}:{item.fitid}",
                importacao_id=importacao.id,
            )
            .on_conflict_do_nothing(constraint="uq_transacao_origem")
            .returning(Transacao.id)
        )
        if transacao_id is None:
            duplicadas += 1
            continue
        contrapartida = despesa if item.valor_centavos < 0 else receita
        session.add_all(
            [
                Lancamento(
                    transacao_id=transacao_id,
                    conta_id=conta.id,
                    valor_centavos=item.valor_centavos,
                ),
                Lancamento(
                    transacao_id=transacao_id,
                    conta_id=contrapartida.id,
                    valor_centavos=-item.valor_centavos,
                ),
            ]
        )
        novas += 1

    importacao.novas = novas
    importacao.duplicadas = duplicadas
    session.commit()
    return ResultadoImportacao(
        conta=conta.nome,
        novas=novas,
        duplicadas=duplicadas,
        importacao_id=importacao.id,
        inicio=extrato.inicio,
        fim=extrato.fim,
    )


def aplicar_categoria(
    session: Session,
    transacao_id: int,
    categoria: str,
    origem: OrigemCategoria,
    confianca: str | None = None,
) -> None:
    receita_propria = session.scalar(
        select(Conta).where(Conta.nome == f"Receita:{categoria}", Conta.tipo == TipoConta.RECEITA)
    )
    if receita_propria is not None:
        destino = receita_propria
    else:
        nome = nome_conta_categoria(categoria)
        destino = obter_ou_criar_conta(session, nome, TipoConta(nome.split(":", 1)[0].lower()))
    contrapartida = session.scalar(
        select(Lancamento)
        .join(Conta)
        .where(
            Lancamento.transacao_id == transacao_id,
            Conta.tipo.in_([TipoConta.DESPESA, TipoConta.RECEITA, TipoConta.PATRIMONIO]),
        )
    )
    if contrapartida is None:
        raise LookupError(f"transação {transacao_id} sem contrapartida categorizável")
    contrapartida.conta_id = destino.id
    session.execute(
        delete(Trecho).where(Trecho.fonte_tipo == "transacao", Trecho.fonte_id == transacao_id)
    )
    transacao = session.get(Transacao, transacao_id)
    if transacao is not None:
        transacao.categorizada_por = origem
        transacao.confianca_categoria = confianca


def anotar_gasto(
    session: Session, valor_centavos: int, categoria: str, descricao: str, data: date
) -> int:
    if valor_centavos <= 0:
        raise ValueError("o valor do gasto precisa ser positivo")
    despesa = session.scalar(
        select(Conta).where(Conta.nome == f"Despesa:{categoria}", Conta.tipo == TipoConta.DESPESA)
    )
    if despesa is None or categoria == "A classificar":
        raise ValueError(f"categoria de despesa desconhecida: {categoria}")
    carteira = obter_ou_criar_conta(session, CARTEIRA, TipoConta.ATIVO)
    transacao = Transacao(
        data=data,
        descricao=descricao,
        origem="manual",
        categorizada_por=OrigemCategoria.USUARIO,
        lancamentos=[
            Lancamento(conta_id=despesa.id, valor_centavos=valor_centavos),
            Lancamento(conta_id=carteira.id, valor_centavos=-valor_centavos),
        ],
    )
    session.add(transacao)
    session.commit()
    return transacao.id
