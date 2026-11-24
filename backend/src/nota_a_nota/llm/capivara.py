import json
import random
from typing import Literal

import anthropic
from pydantic import BaseModel

from nota_a_nota.cofrinho import EstadoCofrinho, Humor
from nota_a_nota.config import get_settings
from nota_a_nota.llm.persona import FORA_DO_TOM, PERSONA

LIMITE_PEDIDO = 120
LIMITE_CARACTERES = 160

EXPRESSOES = (
    "bah: interjeição de espanto, no começo da frase",
    "tchê: vocativo, no fim da frase",
    "barbaridade: exclamação de choque",
    "tri: intensificador, como em tri caro ou tri rápido",
    "capaz: ironia de quem duvida, no sentido de até parece",
    "pila: reais, como em 69 pila",
    "de vereda: na hora, rapidinho",
    "mais por fora que umbigo de vedete: totalmente perdido",
    "caíram os butiá do bolso: fiquei chocada",
    "lagartear: ficar deitada no sol à toa",
    "dar uma banda: dar uma volta",
    "minuano: o vento gelado que chega sem avisar",
)
RECURSOS = (
    "falsa empolgação, como quem dá parabéns sem querer dar",
    "drama exagerado de capivara ofendida",
    "pergunta retórica que já traz a resposta",
    "comparação absurda com alguma coisa de Porto Alegre",
    "constatação seca e irônica, curta",
    "ameaça teatral de ir lagartear bem longe dessa fatura",
)

ROTEIRO: dict[Humor, tuple[str, ...]] = {
    Humor.SEM_TETO: (
        "Sem teto, tchê? Isso não é orçamento, é rodeio.",
        "Gastar sem teto é fazer churrasco sem saber quantos vêm.",
        "Me dá um teto pro mês. Ou pelo menos me deixa reclamar com propriedade.",
    ),
    Humor.TRANQUILA: (
        "Bah, tudo em ordem. Tão em ordem que até o chimarrão tá desconfiado.",
        "Tu tá no ritmo. Vou lagartear no sol antes que tu invente moda.",
        "Vou tirar um cochilo. Me acorda se tu abrir o app de delivery.",
    ),
    Humor.DE_OLHO: (
        "O mês ainda tá no chimarrão e teus gastos já tão no churrasco.",
        "Não tô julgando, tchê. Tô só anotando. Bem devagarinho.",
        "Teu cartão tá correndo mais que ônibus atrasado na Ipiranga.",
    ),
    Humor.APERTADA: (
        "Sobrou pouco pila e muito mês. Que emocionante, né?",
        "Daqui pra frente é cacetinho com margarina e olhe lá.",
        "Respira. Guarda o cartão. Isso, devagarinho, como quem não quer nada.",
    ),
    Humor.ESTOUROU: (
        "Barbaridade, passou do teto. Caíram os butiá do bolso aqui.",
        "Estourou. Vou ali lagartear e fingir que não vi.",
        "Parabéns, tu zerou o mês. Que orgulho. Que desgosto.",
    ),
}
SEM_GASTOS = "Nenhum gasto até agora. Bah, que paz. Que medo."

SISTEMA = f"""{PERSONA}

Tarefa: você recebe em JSON como vai o mês da pessoa (valores já em reais, arredondados) e responde com UMA piada de uma linha falando direto com ela. Quem gasta é ela, não você.

A fala aparece num balãozinho em cima da capivara, no celular. O JSON traz uma direção para esta fala:
- foco: o único detalhe do mês que a piada zoa. Ignore o resto do JSON, ele é só contexto.
- expressao: a única marca gaúcha da fala, com o significado depois dos dois-pontos só para você entender (não escreva o significado na fala). Use no sentido certo, com naturalidade, e nenhuma outra gíria (nem "bah" ou "tchê" a mais).
- recurso: o tipo de piada.

Formato:
- De 6 a 14 palavras, no máximo {LIMITE_PEDIDO} caracteres.
- No máximo um número na fala. Sem emoji, hashtag ou aspas.
- Não reaproveite frases nem imagens dos exemplos abaixo; invente a sua.

Conteúdo:
- Nunca invente gasto, loja ou número que não esteja no JSON.
- Zoe o hábito, nunca a pessoa: nada sobre corpo, renda, salário, emprego, chefe, família, saúde ou condição de vida.
- Não dê conselho de investimento nem recomende produto financeiro.
- O humor manda na temperatura: tranquila desconfia da calma, de_olho fica de olho torto, apertada fica tensa, estourou fica dramática, sem_teto cobra um teto.

Exemplos só de tom e tamanho (lojas e situações inventadas):
- Tudo em ordem. Tão em ordem que até o chimarrão tá desconfiado.
- Mais um iFood? O motoboy já sabe até o meu nome.
- O mês ainda tá no chimarrão e teus gastos já tão no churrasco.
- Sobrou pouco pila e muito mês. Que emocionante, né?
- Barbaridade, passou do teto. Caíram os butiá do bolso aqui."""


class Fala(BaseModel):
    texto: str
    autor: Literal["claude", "roteiro"]


class _Resposta(BaseModel):
    texto: str


_memoria: dict[tuple, Fala] = {}


def _chave(estado: EstadoCofrinho, usuario_id: str = "") -> tuple:
    return (
        usuario_id,
        estado.mes,
        estado.teto_centavos,
        estado.gasto_centavos,
        estado.dias_restantes,
    )


def fala_do_roteiro(estado: EstadoCofrinho) -> Fala:
    if estado.gasto_centavos == 0 and estado.humor != Humor.SEM_TETO:
        return Fala(texto=SEM_GASTOS, autor="roteiro")
    opcoes = ROTEIRO[estado.humor]
    return Fala(texto=opcoes[estado.gasto_centavos % len(opcoes)], autor="roteiro")


def _reais(centavos: int | None) -> str | None:
    if centavos is None:
        return None
    return "R$ " + f"{round(abs(centavos) / 100):,}".replace(",", ".")


def _focos(estado: EstadoCofrinho) -> list[str]:
    focos = [
        f"o gasto recente em {t.descricao} ({_reais(t.valor_centavos)})" for t in estado.ultimos[:3]
    ]
    pode = estado.pode_gastar_centavos
    if pode is not None and pode < 0:
        focos += [f"passou do teto em {_reais(pode)}"] * 2
    elif pode is not None and estado.dias_restantes:
        focos.append(f"sobra {_reais(estado.por_dia_centavos)} por dia até o fim do mês")
        focos.append(f"faltam {estado.dias_restantes} dias e sobram {_reais(pode)}")
    if estado.teto_centavos is None:
        focos = [f"não tem teto e já gastou {_reais(estado.gasto_centavos)}"]
    return focos or [f"gastou {_reais(estado.gasto_centavos)} no mês"]


def _entrada(estado: EstadoCofrinho) -> str:
    sorteio = random.Random(repr(_chave(estado)))
    pode = estado.pode_gastar_centavos
    dados = {
        "foco": sorteio.choice(_focos(estado)),
        "expressao": sorteio.choice(EXPRESSOES),
        "recurso": sorteio.choice(RECURSOS),
        "humor": estado.humor.value,
        "teto": _reais(estado.teto_centavos),
        "gasto_no_mes": _reais(estado.gasto_centavos),
        "passou_do_teto": _reais(pode) if pode is not None and pode < 0 else None,
        "sobra": _reais(pode) if pode is not None and pode >= 0 else None,
        "dias_restantes": estado.dias_restantes,
        "gastos_recentes": [
            {"loja": t.descricao, "categoria": t.categoria, "valor": _reais(t.valor_centavos)}
            for t in estado.ultimos[:3]
        ],
    }
    return json.dumps({k: v for k, v in dados.items() if v is not None}, ensure_ascii=False)


def fala_imediata(estado: EstadoCofrinho, usuario_id: str) -> Fala:
    return _memoria.get(_chave(estado, usuario_id)) or fala_do_roteiro(estado)


def _guardar(chave: tuple, fala: Fala) -> Fala:
    if len(_memoria) > 500:
        _memoria.clear()
    _memoria[chave] = fala
    return fala


def falar(
    estado: EstadoCofrinho, usuario_id: str, client: anthropic.Anthropic | None = None
) -> Fala:
    settings = get_settings()
    if client is None and not settings.anthropic_api_key:
        return fala_do_roteiro(estado)
    chave = _chave(estado, usuario_id)
    if chave in _memoria:
        return _memoria[chave]

    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        resposta = client.messages.parse(
            model=settings.modelo_categorizacao,
            max_tokens=300,
            system=SISTEMA,
            thinking={"type": "disabled"},
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": _entrada(estado)}],
            output_format=_Resposta,
        )
    except anthropic.APIError:
        return fala_do_roteiro(estado)

    texto = resposta.parsed_output.texto.strip().strip('"“”') if resposta.parsed_output else ""
    if (
        resposta.stop_reason != "end_turn"
        or not texto
        or len(texto) > LIMITE_CARACTERES
        or FORA_DO_TOM.search(texto)
    ):
        return _guardar(chave, fala_do_roteiro(estado))
    return _guardar(chave, Fala(texto=texto, autor="claude"))
