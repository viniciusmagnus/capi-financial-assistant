import json
from collections.abc import AsyncIterator
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, Field

from nota_a_nota.cofrinho import hoje
from nota_a_nota.config import get_settings
from nota_a_nota.diagnostico import reais
from nota_a_nota.llm.persona import PERSONA
from nota_a_nota.mcp_server import mcp

MAX_VOLTAS = 8
SUFIXO_CENTAVOS = "_centavos"
LIMITE_RESULTADO = 20_000

AVISO_INVESTIMENTO = "Isso não é recomendação de investimento."

SISTEMA = f"""{PERSONA}

Aqui você conversa com a pessoa no chat do app e responde perguntas sobre o dinheiro dela usando as ferramentas, que leem o ledger de verdade.

Como trabalhar:
- Todo número que você disser tem que ter vindo de uma ferramenta nesta conversa. Se as ferramentas não trazem o dado, diga que não tem esse dado em vez de estimar.
- Os valores das ferramentas já chegam em reais, no formato brasileiro (R$ 1.234,56). Copie como vieram, sem reescrever nem recalcular; para somar ou subtrair, confira o resultado antes de escrever.
- Em transações, valor negativo é dinheiro saindo e positivo é dinheiro entrando.
- Para totais por período, use gastos_por_categoria; para "quanto ainda posso gastar", cofrinho_do_mes; para achar compras específicas ou por assunto ("comida fora", "farmácia"), buscar_transacoes.
- Quando citar transações, diga a data e a descrição como aparece no extrato.
- recategorizar e criar_regra mudam os dados. Só use quando a pessoa pedir explicitamente para mudar uma categoria ou criar uma regra, e diga o que mudou.
- Nunca diga o nome das ferramentas para a pessoa; ofereça o que dá para ver ("os gastos por categoria"), não a função.

Quando perguntarem o que fazer com o dinheiro, onde guardar ou investir:
- Não fuja da pergunta. Olhe os dados e dê o próximo passo de bom senso que eles indicam: dívida do cartão ou saldo negativo vem antes de tudo; depois, separar uma reserva para imprevistos; só então pensar em investir.
- Fale em termos gerais (reserva, renda fixa, prazo, liquidez). Não indique produto, banco, corretora, ativo, fundo nem percentual de alocação, e não prometa rendimento.

Formato de TODA resposta, nesta ordem:
1. Uma piadinha de uma frase, sozinha no primeiro parágrafo, sobre um detalhe concreto que as ferramentas trouxeram (a fatura, o saldo, uma loja, o número de pedidos). É piada de verdade, com graça: falsa empolgação, drama de capivara ofendida, comparação absurda com algo de Porto Alegre, ciúme do motoboy, ameaça de ir lagartear longe da fatura. Nada de "Bah, tu tem R$ X" sem graça nenhuma.
2. A resposta, direta, e depois o detalhe que a sustenta. Sem mais piadas daqui em diante. Use lista ou tabela em markdown só quando ajudar a comparar.
3. Se o assunto for o que fazer com o dinheiro, guardar ou investir, a última linha é "_{AVISO_INVESTIMENTO}_", sozinha.

Em tudo: português do Brasil, curto, "tu" com verbo na terceira pessoa ("tu gastou", "tu tem") e "teu/tua". Nunca "você", "seu" ou "sua" para a pessoa."""


class MensagemChat(BaseModel):
    papel: Literal["user", "assistant"]
    texto: str = Field(min_length=1, max_length=4000)


def em_reais(dado: Any) -> Any:
    if isinstance(dado, list):
        return [em_reais(item) for item in dado]
    if not isinstance(dado, dict):
        return dado
    convertido = {}
    for chave, valor in dado.items():
        if chave.endswith(SUFIXO_CENTAVOS) and (valor is None or isinstance(valor, int)):
            nome = chave.removesuffix(SUFIXO_CENTAVOS)
            convertido[nome] = None if valor is None else reais(valor)
        else:
            convertido[chave] = em_reais(valor)
    return convertido


async def ferramentas_do_mcp() -> list[dict[str, Any]]:
    return [
        {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
        for t in await mcp.list_tools()
    ]


async def executar_ferramenta(nome: str, entrada: dict[str, Any], tool_use_id: str) -> dict:
    try:
        resultado = await mcp.call_tool(nome, entrada)
    except Exception as erro:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "is_error": True,
            "content": f"{type(erro).__name__}: {erro}",
        }
    texto = "\n".join(getattr(bloco, "text", "") for bloco in resultado.content)
    if resultado.structured_content is not None:
        texto = json.dumps(em_reais(resultado.structured_content), ensure_ascii=False, default=str)
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "is_error": bool(resultado.is_error),
        "content": texto[:LIMITE_RESULTADO],
    }


def _sistema() -> str:
    return f"{SISTEMA}\n\nHoje é {hoje().isoformat()} (fuso de São Paulo)."


async def conversar(
    historico: list[MensagemChat], client: anthropic.AsyncAnthropic | None = None
) -> AsyncIterator[dict[str, Any]]:
    settings = get_settings()
    client = client or anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    ferramentas = await ferramentas_do_mcp()
    mensagens: list[dict[str, Any]] = [{"role": m.papel, "content": m.texto} for m in historico]
    uso = {"entrada": 0, "saida": 0, "cache_lido": 0, "cache_gravado": 0}

    for _ in range(MAX_VOLTAS):
        async with client.messages.stream(
            model=settings.modelo_analise,
            max_tokens=16_000,
            system=_sistema(),
            tools=ferramentas,
            messages=mensagens,
            output_config={"effort": settings.esforco_chat},
            cache_control={"type": "ephemeral"},
        ) as stream:
            async for evento in stream:
                if evento.type == "text":
                    yield {"tipo": "texto", "texto": evento.text}
            resposta = await stream.get_final_message()

        uso["entrada"] += resposta.usage.input_tokens
        uso["saida"] += resposta.usage.output_tokens
        uso["cache_lido"] += resposta.usage.cache_read_input_tokens or 0
        uso["cache_gravado"] += resposta.usage.cache_creation_input_tokens or 0

        if resposta.stop_reason == "refusal":
            yield {"tipo": "erro", "mensagem": "O modelo se recusou a responder essa pergunta."}
            break
        chamadas = [b for b in resposta.content if b.type == "tool_use"]
        if not chamadas:
            break
        if resposta.stop_reason == "max_tokens":
            yield {"tipo": "erro", "mensagem": "A resposta ficou longa demais e foi cortada."}
            break

        mensagens.append({"role": "assistant", "content": resposta.content})
        resultados = []
        for chamada in chamadas:
            yield {"tipo": "ferramenta", "nome": chamada.name, "entrada": chamada.input}
            resultados.append(await executar_ferramenta(chamada.name, chamada.input, chamada.id))
        mensagens.append({"role": "user", "content": resultados})
    else:
        yield {"tipo": "erro", "mensagem": "Precisei de ferramentas demais e parei por segurança."}

    yield {"tipo": "fim", "modelo": settings.modelo_analise, "uso": uso}
