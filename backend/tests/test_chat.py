import asyncio
import json
from types import SimpleNamespace

from nota_a_nota.llm.chat import MensagemChat, conversar, ferramentas_do_mcp


def _uso():
    return SimpleNamespace(
        input_tokens=100,
        output_tokens=20,
        cache_read_input_tokens=80,
        cache_creation_input_tokens=0,
    )


def _resposta(stop_reason, *blocos):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocos), usage=_uso())


class _Stream:
    def __init__(self, textos, final):
        self.textos = textos
        self.final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        return self._eventos()

    async def _eventos(self):
        for texto in self.textos:
            yield SimpleNamespace(type="text", text=texto)

    async def get_final_message(self):
        return self.final


class ClienteFalso:
    def __init__(self, *voltas):
        self.voltas = list(voltas)
        self.pedidos = []
        self.messages = self

    def stream(self, **kwargs):
        self.pedidos.append({**kwargs, "messages": list(kwargs["messages"])})
        return _Stream(*self.voltas.pop(0))


def _coletar(cliente, pergunta="Quanto tenho nas contas?"):
    async def rodar():
        return [
            e async for e in conversar([MensagemChat(papel="user", texto=pergunta)], client=cliente)
        ]

    return asyncio.run(rodar())


def test_chat_oferece_as_mesmas_ferramentas_do_mcp():
    nomes = {f["name"] for f in asyncio.run(ferramentas_do_mcp())}

    assert {"saldos", "buscar_transacoes", "cofrinho_do_mes", "gastos_por_categoria"} <= nomes


def test_chat_chama_a_ferramenta_e_devolve_o_resultado_ao_modelo(session):
    chamada = SimpleNamespace(type="tool_use", id="tu_1", name="saldos", input={})
    cliente = ClienteFalso(
        ([], _resposta("tool_use", chamada)),
        (
            ["Você tem ", "R$ 10,00."],
            _resposta("end_turn", SimpleNamespace(type="text", text="...")),
        ),
    )

    eventos = _coletar(cliente)

    assert [e["tipo"] for e in eventos] == ["ferramenta", "texto", "texto", "fim"]
    assert eventos[0] == {"tipo": "ferramenta", "nome": "saldos", "entrada": {}}
    resultado = cliente.pedidos[1]["messages"][-1]["content"][0]
    assert resultado["tool_use_id"] == "tu_1"
    assert resultado["is_error"] is False
    assert isinstance(json.loads(resultado["content"]), (list, dict))
    assert eventos[-1]["uso"] == {
        "entrada": 200,
        "saida": 40,
        "cache_lido": 160,
        "cache_gravado": 0,
    }
    assert cliente.pedidos[0]["cache_control"] == {"type": "ephemeral"}


def test_erro_da_ferramenta_volta_como_is_error_sem_derrubar_o_chat(session):
    chamada = SimpleNamespace(
        type="tool_use", id="tu_2", name="cofrinho_do_mes", input={"mes": "fevereiro"}
    )
    cliente = ClienteFalso(
        ([], _resposta("tool_use", chamada)),
        (["Mês inválido."], _resposta("end_turn")),
    )

    eventos = _coletar(cliente, "E em fevereiro?")

    resultado = cliente.pedidos[1]["messages"][-1]["content"][0]
    assert resultado["is_error"] is True
    assert "AAAA-MM" in resultado["content"]
    assert eventos[-1]["tipo"] == "fim"


def test_recusa_encerra_com_mensagem():
    cliente = ClienteFalso(([], _resposta("refusal")))

    eventos = _coletar(cliente)

    assert [e["tipo"] for e in eventos] == ["erro", "fim"]
