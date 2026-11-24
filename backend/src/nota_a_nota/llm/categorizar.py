import json
from functools import lru_cache
from typing import Literal

import anthropic
from pydantic import BaseModel, create_model

from nota_a_nota.categorias import PADRAO, Categorias
from nota_a_nota.config import get_settings
from nota_a_nota.consultas import Pendente
from nota_a_nota.ledger import TRANSFERENCIA_INTERNA
from nota_a_nota.rag.busca import Exemplo


class Classificacao(BaseModel):
    id: int
    categoria: str
    confianca: Literal["alta", "media", "baixa"]


class Lote(BaseModel):
    itens: list[Classificacao]


class CategorizacaoRecusada(RuntimeError):
    pass


@lru_cache(maxsize=16)
def formato_para(nomes: tuple[str, ...]) -> type[Lote]:
    item = create_model(
        "ClassificacaoPermitida", __base__=Classificacao, categoria=(Literal[nomes], ...)
    )
    return create_model("LotePermitido", __base__=Lote, itens=(list[item], ...))


def sistema(categorias: Categorias) -> str:
    proprias = ""
    if categorias.criadas:
        proprias = (
            f"\n\nA pessoa criou estas categorias: {', '.join(categorias.criadas)}. Quando a "
            "descrição combina com uma delas (por exemplo, a operadora de celular numa categoria "
            "de celular), prefira a dela à categoria genérica."
        )
    return f"""Você classifica transações de extratos bancários e faturas de cartão de uma pessoa no Brasil.

Cada transação tem id, descrição como aparece no banco e valor em centavos (negativo é saída, positivo é entrada).

Categorias de saída: {", ".join(categorias.despesa)}.
Categorias de entrada: {", ".join(categorias.receita)}.
Para os dois sentidos: {TRANSFERENCIA_INTERNA}.{proprias}

Como decidir:
- Descrições de banco são abreviadas e cheias de prefixos de adquirente (PAG*, MP*, IFD*, EC*, PIC*). Ignore o prefixo e pense no estabelecimento.
- iFood, Rappi, Zé Delivery, restaurantes, padarias e lanchonetes são "Restaurantes e delivery". Supermercados, atacarejos e hortifrútis são "Mercado".
- Uber, 99, combustível, pedágio, estacionamento e passagens são "Transporte".
- Streaming, apps, armazenamento em nuvem e planos de software são "Assinaturas".
- Aluguel, condomínio, luz, água, gás e internet são "Moradia".
- Pagamento de fatura, aplicação, resgate e transferência entre contas da própria pessoa são "{TRANSFERENCIA_INTERNA}".
- Entrada com cara de salário (empresa, "SALARIO", "PROVENTOS") é "Salário". Rendimento de investimento é "Rendimentos". Estorno é "Reembolsos".
- PIX para pessoa física sem outra pista é "Outros" com confiança baixa. Não invente contexto que a descrição não dá.
- Marketplace (Amazon, Mercado Livre, Shopee, AliExpress) sem o produto na descrição é "Outros" com confiança baixa: não adivinhe o que foi comprado.
- Saída só recebe categoria de saída e entrada só recebe categoria de entrada.

Algumas transações trazem "parecidos_no_historico": transações dessa mesma pessoa, com descrição parecida, que já foram categorizadas (por regra, por você antes ou corrigidas à mão por ela). Quando é claramente o mesmo estabelecimento ou o mesmo tipo de gasto, siga a categoria do histórico, porque ela reflete como essa pessoa organiza o dinheiro. Quando só a palavra é parecida e o negócio é outro, ignore.

Use confiança "alta" só quando o estabelecimento é inequívoco. Devolva exatamente um item para cada id recebido."""


def categorizar(
    pendentes: list[Pendente],
    client: anthropic.Anthropic | None = None,
    exemplos: dict[int, list[Exemplo]] | None = None,
    categorias: Categorias | None = None,
) -> list[Classificacao]:
    if not pendentes:
        return []
    settings = get_settings()
    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    categorias = categorias or PADRAO

    exemplos = exemplos or {}
    entrada = [
        p.model_dump()
        | (
            {"parecidos_no_historico": [e.model_dump() for e in exemplos[p.id]]}
            if exemplos.get(p.id)
            else {}
        )
        for p in pendentes
    ]
    resposta = client.messages.parse(
        model=settings.modelo_categorizacao,
        max_tokens=8000,
        system=sistema(categorias),
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": json.dumps(entrada, ensure_ascii=False)}],
        output_format=formato_para(tuple(categorias.todas)),
    )
    if resposta.stop_reason == "refusal" or resposta.parsed_output is None:
        raise CategorizacaoRecusada(f"stop_reason={resposta.stop_reason}")

    ids_validos = {p.id for p in pendentes}
    permitidas = set(categorias.todas)
    vistos: set[int] = set()
    resultado = []
    for item in resposta.parsed_output.itens:
        if item.id in ids_validos and item.id not in vistos and item.categoria in permitidas:
            vistos.add(item.id)
            resultado.append(
                Classificacao(id=item.id, categoria=item.categoria, confianca=item.confianca)
            )
    return resultado
