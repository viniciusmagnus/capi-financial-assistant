import json
import re

import anthropic
from pydantic import BaseModel

from nota_a_nota.config import get_settings
from nota_a_nota.diagnostico import Recomendacao
from nota_a_nota.llm.persona import FORA_DO_TOM, PERSONA

LIMITE = 140

ROTEIRO = {
    "app_delivery": "O motoboy já sabe até o nome da capivara.",
    "app_transporte": "O motorista já sabe teu endereço de cor. Bah, eu também.",
    "categoria_Restaurantes e delivery": "Comer fora é tri bom. A fatura também achou.",
    "categoria_Lazer": "Diversão faz bem, tchê. Só precisa caber no mês inteiro.",
    "categoria_Vestuário": "Roupa nova é tri. O cartão é que pediu arrego.",
    "assinaturas": "Assinatura é que nem minuano: tu nem vê chegar, mas sente.",
}
PADRAO = "Anotei, tchê. Com carinho, mas anotei."

SISTEMA = f"""{PERSONA}

Tarefa: para cada recomendação recebida, escreva UMA frase curta de comentário, no tom de uma piada de uma linha.

Exemplos do tom (não copie):
- O motoboy já sabe até o nome da capivara.
- Assinatura é que nem minuano: tu nem vê chegar, mas sente.
- Comer fora é tri bom. A fatura também achou.

Regras:
- No máximo {LIMITE} caracteres por frase, sem emoji, sem aspas.
- Provoque o hábito descrito, nunca a pessoa. Nada sobre renda baixa, dívida, trabalho, corpo, família, saúde ou condição de vida.
- Não presuma idade, estado civil, onde a pessoa mora, o que tem em casa nem nada que não esteja no texto recebido.
- Não escreva números nem invente fatos: os números já aparecem ao lado do seu comentário.
- Não diga que um gasto foi inútil, desnecessário ou que se repete todo mês.
- Devolva exatamente uma frase por recomendação, na mesma ordem."""


class Falas(BaseModel):
    falas: list[str]


_memoria: dict[tuple, list[str]] = {}


def _aceitavel(fala: str) -> bool:
    limpa = fala.strip()
    return (
        0 < len(limpa) <= LIMITE
        and not re.search(r"\d|por cento|reais", limpa, re.I)
        and not FORA_DO_TOM.search(limpa)
    )


def _roteiro(recomendacoes: list[Recomendacao]) -> list[str]:
    return [ROTEIRO.get(r.tipo, PADRAO) for r in recomendacoes]


def comentar(
    recomendacoes: list[Recomendacao],
    usuario_id: str,
    client: anthropic.Anthropic | None = None,
) -> list[str]:
    if not recomendacoes:
        return []
    settings = get_settings()
    reserva = _roteiro(recomendacoes)
    if client is None and not settings.anthropic_api_key:
        return reserva
    chave = (usuario_id, *((r.id, r.economia_centavos) for r in recomendacoes))
    if chave in _memoria:
        return _memoria[chave]

    entrada = [{"titulo": r.titulo, "fato": r.fato, "acao": r.acao} for r in recomendacoes]
    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        resposta = client.messages.parse(
            model=settings.modelo_categorizacao,
            max_tokens=1000,
            system=SISTEMA,
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": json.dumps(entrada, ensure_ascii=False)}],
            output_format=Falas,
        )
    except anthropic.APIError:
        return reserva
    falas = resposta.parsed_output.falas if resposta.parsed_output else []
    if resposta.stop_reason == "refusal" or len(falas) != len(recomendacoes):
        return reserva
    resultado = [
        fala.strip().strip('"“”') if _aceitavel(fala) else reserva[i]
        for i, fala in enumerate(falas)
    ]
    if len(_memoria) > 200:
        _memoria.clear()
    _memoria[chave] = resultado
    return resultado
