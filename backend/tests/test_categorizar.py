import json
from types import SimpleNamespace

import pytest

from nota_a_nota.categorias import Categorias
from nota_a_nota.consultas import Pendente
from nota_a_nota.llm.categorizar import (
    CategorizacaoRecusada,
    Classificacao,
    Lote,
    categorizar,
)
from nota_a_nota.rag.busca import Exemplo


class ClienteFalso:
    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas = []
        self.messages = self

    def parse(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.resposta


PENDENTES = [
    Pendente(id=1, descricao="IFD*BURGER", valor_centavos=-4590),
    Pendente(id=2, descricao="UBER *TRIP", valor_centavos=-2310),
]


def test_envia_pendentes_com_saida_estruturada_e_descarta_ids_estranhos():
    lote = Lote(
        itens=[
            Classificacao(id=1, categoria="Restaurantes e delivery", confianca="alta"),
            Classificacao(id=1, categoria="Outros", confianca="baixa"),
            Classificacao(id=99, categoria="Outros", confianca="baixa"),
            Classificacao(id=2, categoria="Transporte", confianca="alta"),
        ]
    )
    cliente = ClienteFalso(SimpleNamespace(stop_reason="end_turn", parsed_output=lote))

    resultado = categorizar(PENDENTES, client=cliente)

    assert [(c.id, c.categoria) for c in resultado] == [
        (1, "Restaurantes e delivery"),
        (2, "Transporte"),
    ]
    chamada = cliente.chamadas[0]
    assert chamada["model"] == "claude-haiku-5-5"
    assert issubclass(chamada["output_format"], Lote)
    enum = chamada["output_format"].model_json_schema()["$defs"]["ClassificacaoPermitida"][
        "properties"
    ]["categoria"]["enum"]
    assert "Mercado" in enum and "Transferência interna" in enum
    assert "IFD*BURGER" in chamada["messages"][0]["content"]


def test_categorias_criadas_entram_no_prompt_e_no_formato():
    lote = Lote(
        itens=[
            Classificacao(id=1, categoria="Celular e internet", confianca="alta"),
            Classificacao(id=2, categoria="Inventada pelo modelo", confianca="alta"),
        ]
    )
    cliente = ClienteFalso(SimpleNamespace(stop_reason="end_turn", parsed_output=lote))
    categorias = Categorias(
        despesa=["Mercado", "Outros", "Celular e internet"],
        receita=["Salário"],
        criadas=["Celular e internet"],
    )

    resultado = categorizar(PENDENTES, client=cliente, categorias=categorias)

    assert [(c.id, c.categoria) for c in resultado] == [(1, "Celular e internet")]
    chamada = cliente.chamadas[0]
    assert "A pessoa criou estas categorias: Celular e internet" in chamada["system"]
    enum = chamada["output_format"].model_json_schema()["$defs"]["ClassificacaoPermitida"][
        "properties"
    ]["categoria"]["enum"]
    assert "Celular e internet" in enum and "Lazer" not in enum


def test_recusa_vira_erro_explicito():
    cliente = ClienteFalso(SimpleNamespace(stop_reason="refusal", parsed_output=None))

    with pytest.raises(CategorizacaoRecusada):
        categorizar(PENDENTES, client=cliente)


def test_lista_vazia_nao_chama_a_api():
    cliente = ClienteFalso(None)

    assert categorizar([], client=cliente) == []
    assert cliente.chamadas == []


def test_exemplos_do_historico_vao_junto_so_com_quem_tem():
    lote = Lote(itens=[Classificacao(id=1, categoria="Restaurantes e delivery", confianca="alta")])
    cliente = ClienteFalso(SimpleNamespace(stop_reason="end_turn", parsed_output=lote))
    exemplos = {1: [Exemplo(descricao="IFD*PIZZARIA", categoria="Restaurantes e delivery")]}

    categorizar(PENDENTES, client=cliente, exemplos=exemplos)

    enviados = json.loads(cliente.chamadas[0]["messages"][0]["content"])
    assert enviados[0]["parecidos_no_historico"] == [
        {"descricao": "IFD*PIZZARIA", "categoria": "Restaurantes e delivery"}
    ]
    assert "parecidos_no_historico" not in enviados[1]
