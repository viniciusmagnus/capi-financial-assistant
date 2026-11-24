import json
from datetime import date
from types import SimpleNamespace

import pytest

from nota_a_nota.cofrinho import EstadoCofrinho, Humor, calcular_humor, dias_restantes, ler_mes
from nota_a_nota.llm import capivara


@pytest.mark.parametrize(
    ("teto", "gasto", "restantes", "esperado"),
    [
        (None, 50_000, 15, Humor.SEM_TETO),
        (100_000, 100_001, 15, Humor.ESTOUROU),
        (100_000, 40_000, 16, Humor.TRANQUILA),
        (100_000, 60_000, 16, Humor.DE_OLHO),
        (100_000, 75_000, 16, Humor.APERTADA),
        (100_000, 86_000, 2, Humor.APERTADA),
        (100_000, 0, 30, Humor.TRANQUILA),
    ],
)
def test_humor_compara_o_gasto_com_o_tempo_que_passou(teto, gasto, restantes, esperado):
    assert calcular_humor(teto, gasto, 30, restantes) == esperado


def test_dias_restantes_conta_o_dia_de_hoje():
    novembro = date(2026, 11, 1)

    assert dias_restantes(novembro, date(2026, 11, 19)) == 12
    assert dias_restantes(novembro, date(2026, 11, 30)) == 1
    assert dias_restantes(novembro, date(2026, 12, 1)) == 0
    assert dias_restantes(novembro, date(2026, 10, 31)) == 30


def test_ler_mes():
    assert ler_mes("2026-02") == date(2026, 2, 1)
    with pytest.raises(ValueError, match="AAAA-MM"):
        ler_mes("fevereiro")


def _estado(**mudancas) -> EstadoCofrinho:
    base = {
        "mes": "2026-11",
        "teto_centavos": 300_000,
        "gasto_centavos": 120_000,
        "pode_gastar_centavos": 180_000,
        "dias_no_mes": 30,
        "dias_restantes": 12,
        "por_dia_centavos": 15_000,
        "humor": Humor.TRANQUILA,
        "ultimos": [],
    }
    return EstadoCofrinho(**(base | mudancas))


class _ClienteFalso:
    def __init__(self, texto: str, stop_reason: str = "end_turn") -> None:
        self.chamadas: list[dict] = []
        self.messages = SimpleNamespace(parse=self._parse)
        self._resposta = SimpleNamespace(
            parsed_output=capivara._Resposta(texto=texto) if texto else None,
            stop_reason=stop_reason,
        )

    def _parse(self, **kwargs):
        self.chamadas.append(kwargs)
        return self._resposta


@pytest.fixture(autouse=True)
def _memoria_limpa():
    capivara._memoria.clear()


def test_fala_do_claude_fica_em_memoria_para_o_mesmo_estado():
    cliente = _ClienteFalso("Tudo calmo demais por aqui.")

    primeira = capivara.falar(_estado(), "pessoa", client=cliente)
    segunda = capivara.falar(_estado(), "pessoa", client=cliente)

    assert primeira == segunda == capivara.Fala(texto="Tudo calmo demais por aqui.", autor="claude")
    assert len(cliente.chamadas) == 1
    entrada = json.loads(cliente.chamadas[0]["messages"][0]["content"])
    assert entrada["humor"] == "tranquila"
    assert entrada["sobra"] == "R$ 1.800"
    assert entrada["expressao"] in capivara.EXPRESSOES
    assert capivara.fala_imediata(_estado(), "pessoa").autor == "claude"


def test_direcao_da_fala_e_estavel_para_o_mesmo_estado_e_varia_entre_estados():
    entradas = {capivara._entrada(_estado(gasto_centavos=120_000 + i)) for i in range(12)}

    assert capivara._entrada(_estado()) == capivara._entrada(_estado())
    assert len({json.loads(e)["expressao"] for e in entradas}) > 3


def test_foco_de_quem_passou_do_teto_fala_do_quanto_passou():
    estado = _estado(gasto_centavos=380_000, pode_gastar_centavos=-80_000, humor=Humor.ESTOUROU)

    assert "passou do teto em R$ 800" in capivara._focos(estado)


def test_fala_imediata_sem_memoria_usa_o_roteiro():
    assert capivara.fala_imediata(_estado(), "pessoa").autor == "roteiro"


@pytest.mark.parametrize(
    ("texto", "stop_reason"),
    [
        ("x" * 400, "end_turn"),
        ("Tudo calmo", "max_tokens"),
        ("", "end_turn"),
        ("Não", "refusal"),
        ("Bah, guria, que mês tranquilo.", "end_turn"),
        ("Uber até a esquina? Quem precisa de pernas.", "end_turn"),
        ("R$ 357 por dia e tu ainda tá calma? Caíram os butiá do bolso.", "end_turn"),
        ("Tu pegou um Ride de R$ 20 e seguiu calma? Desconfio.", "end_turn"),
        ("Passou do teto, tá mais perdido que umbigo de vedete, bah.", "end_turn"),
        ("Passou 1.200 do teto, e olha que o Guaíba transborda menos.", "end_turn"),
        ("Estourou. Vou me jogar no Guaiba e já volto.", "end_turn"),
        ("Teu cartão tá mais agitado que o rio em dia de vento.", "end_turn"),
        ("Gastou que nem enchente: tudo de uma vez.", "end_turn"),
    ],
)
def test_resposta_ruim_do_claude_cai_no_roteiro(texto, stop_reason):
    fala = capivara.falar(_estado(), "pessoa", client=_ClienteFalso(texto, stop_reason))

    assert fala.autor == "roteiro"
    assert fala.texto in capivara.ROTEIRO[Humor.TRANQUILA]


def test_sem_chave_usa_o_roteiro(monkeypatch):
    monkeypatch.setattr(capivara, "get_settings", lambda: SimpleNamespace(anthropic_api_key=""))

    fala = capivara.falar(_estado(humor=Humor.ESTOUROU), "pessoa")

    assert fala.autor == "roteiro"
    assert fala.texto in capivara.ROTEIRO[Humor.ESTOUROU]


def test_mes_sem_gastos_tem_fala_propria():
    assert capivara.fala_do_roteiro(_estado(gasto_centavos=0)).texto == capivara.SEM_GASTOS


def test_roteiro_passa_no_proprio_filtro_de_tom():
    falas = [f for opcoes in capivara.ROTEIRO.values() for f in opcoes] + [capivara.SEM_GASTOS]

    assert [
        f for f in falas if capivara.FORA_DO_TOM.search(f) or len(f) > capivara.LIMITE_PEDIDO
    ] == []
