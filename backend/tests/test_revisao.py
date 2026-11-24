import uuid
from types import SimpleNamespace

import pytest
from anthropic.types import Message, ToolUseBlock
from conftest import criar_usuario, emitir_jwt
from sqlalchemy import select, text

from nota_a_nota import consultas, revisao
from nota_a_nota.acesso import abrir_sessao, usuario_atual
from nota_a_nota.ledger import aplicar_categoria
from nota_a_nota.llm import analise_outros
from nota_a_nota.models import OrigemCategoria, Transacao
from nota_a_nota.pesquisa_web import (
    FonteEncontrada,
    PesquisaAnthropic,
    PesquisaRecusada,
    ResultadoPesquisa,
    preparar_termo,
)

FATURA = b"""date,title,amount
2026-10-02,Lords ZS,450.00
2026-10-03,Gianluca - Bom Fim,28.00
2026-10-04,amazon parcela,89.90
2026-10-05,Amazonmktplc*Rchsports - Parcela 1/6,120.00
2026-10-06,PIX enviado,75.00
2026-10-07,LORDS ZS,150.00
"""
NOVA_FATURA = b"""date,title,amount
2026-11-02,LORDS ZS,99.00
"""


def entrar(usuario_id: str) -> dict[str, str]:
    return {"authorization": f"Bearer {emitir_jwt(usuario_id)}"}


def chave() -> str:
    return uuid.uuid4().hex


def ids_por_descricao(usuario_id: str) -> dict[str, int]:
    with abrir_sessao(usuario_id) as session:
        return {d: i for i, d in session.execute(select(Transacao.id, Transacao.descricao))}


def estado(usuario_id: str, transacao_id: int) -> dict:
    with abrir_sessao(usuario_id) as session:
        linha = session.execute(
            text(
                """SELECT c.nome, t.estabelecimento, t.categorizada_por, t.descricao, l.valor_centavos
                FROM transacoes t JOIN lancamentos l ON l.transacao_id = t.id
                JOIN contas c ON c.id = l.conta_id
                WHERE t.id = :id AND c.tipo IN ('despesa', 'receita', 'patrimonio')"""
            ),
            {"id": transacao_id},
        ).one()
    return {
        "conta": linha[0],
        "estabelecimento": linha[1],
        "por": linha[2],
        "descricao": linha[3],
        "valor": linha[4],
    }


def ledger_balanceado(usuario_id: str) -> bool:
    with abrir_sessao(usuario_id) as session:
        return (
            session.execute(
                text(
                    "SELECT count(*) FROM (SELECT transacao_id FROM lancamentos WHERE usuario_id = :u "
                    "GROUP BY transacao_id HAVING sum(valor_centavos) <> 0) x"
                ),
                {"u": usuario_id},
            ).scalar_one()
            == 0
        )


def alteracoes(usuario_id: str) -> list[tuple]:
    with abrir_sessao(usuario_id) as session:
        return session.execute(
            text(
                "SELECT transacao_id, categoria_anterior, categoria_nova, origem FROM revisao_alteracoes "
                "WHERE usuario_id = :u ORDER BY id"
            ),
            {"u": usuario_id},
        ).all()


@pytest.fixture
def ana(cliente, banco):
    usuario = criar_usuario()
    resposta = cliente.post(
        "/api/importar",
        files={"arquivo": ("Nubank_2026-10-10.csv", FATURA)},
        headers=entrar(usuario),
    )
    assert resposta.status_code == 200, resposta.text
    with abrir_sessao(usuario) as session:
        for pendente in consultas.pendentes_de_categoria(session, limite=None):
            aplicar_categoria(session, pendente.id, "Outros", OrigemCategoria.CLAUDE, "baixa")
        session.commit()
    return usuario


def confirmar(cliente, usuario, decisoes, lembrar=True, chave_idem=None):
    return cliente.post(
        "/api/revisao/confirmar",
        json={
            "decisoes": decisoes,
            "lembrar": lembrar,
            "chave_idempotencia": chave_idem or chave(),
        },
        headers=entrar(usuario),
    )


def test_confirmar_aplica_so_o_aprovado_e_lembra_nas_importacoes(cliente, ana):
    ids = ids_por_descricao(ana)
    resposta = confirmar(
        cliente,
        ana,
        [
            {
                "transacao_id": ids["Lords ZS"],
                "categoria": "Vestuário",
                "estabelecimento": "Lords ZS",
                "origem": "pesquisa",
            },
            {
                "transacao_id": ids["LORDS ZS"],
                "categoria": "Vestuário",
                "estabelecimento": "Lords ZS",
                "origem": "pesquisa",
            },
            {"transacao_id": ids["Gianluca - Bom Fim"], "categoria": "Restaurantes e delivery"},
        ],
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["alteradas"] == 3 and corpo["ignoradas"] == []
    assert "LORDS ZS" in corpo["regras_salvas"]

    assert estado(ana, ids["Lords ZS"]) | {"descricao": None} == {
        "conta": "Despesa:Vestuário",
        "estabelecimento": "Lords ZS",
        "por": "usuario",
        "descricao": None,
        "valor": 45000,
    }
    for intocada in ("amazon parcela", "Amazonmktplc*Rchsports - Parcela 1/6", "PIX enviado"):
        assert estado(ana, ids[intocada])["conta"] == "Despesa:Outros"
    assert ledger_balanceado(ana)
    assert {(a[1], a[2], a[3]) for a in alteracoes(ana)} == {
        ("Despesa:Outros", "Despesa:Vestuário", "pesquisa"),
        ("Despesa:Outros", "Despesa:Restaurantes e delivery", "usuario"),
    }

    cliente.post(
        "/api/importar",
        files={"arquivo": ("Nubank_2026-11-10.csv", NOVA_FATURA)},
        headers=entrar(ana),
    )
    with abrir_sessao(ana) as session:
        nova = session.scalar(
            select(Transacao.id)
            .where(Transacao.descricao == "LORDS ZS")
            .order_by(Transacao.data.desc())
        )
    futura = estado(ana, nova)
    assert (
        futura["conta"] == "Despesa:Vestuário"
        and futura["por"] == "regra"
        and futura["estabelecimento"] == "Lords ZS"
    )


def test_confirmar_nao_mexe_fora_de_outros_nem_aceita_categoria_invalida(cliente, ana):
    ids = ids_por_descricao(ana)
    cliente.patch(
        f"/api/transacoes/{ids['LORDS ZS']}/categoria",
        json={"categoria": "Lazer"},
        headers=entrar(ana),
    )
    resposta = confirmar(
        cliente,
        ana,
        [
            {"transacao_id": ids["LORDS ZS"], "categoria": "Vestuário"},
            {"transacao_id": ids["PIX enviado"], "categoria": "Transferência interna"},
            {"transacao_id": ids["amazon parcela"], "categoria": "Outros"},
            {"transacao_id": ids["Gianluca - Bom Fim"], "categoria": "Moda inventada"},
        ],
    ).json()
    assert corpo_vazio(resposta)
    motivos = {i["transacao_id"]: i["motivo"] for i in resposta["ignoradas"]}
    assert motivos[ids["LORDS ZS"]] == "não está mais em Outros"
    assert "categoria inválida" in motivos[ids["PIX enviado"]]
    assert estado(ana, ids["LORDS ZS"])["conta"] == "Despesa:Lazer"
    assert estado(ana, ids["PIX enviado"])["conta"] == "Despesa:Outros"


def corpo_vazio(resposta: dict) -> bool:
    return (
        resposta["alteradas"] == 0
        and resposta["lote_id"] is None
        and len(resposta["ignoradas"]) == 4
    )


def test_confirmar_duas_vezes_com_a_mesma_chave_aplica_uma(cliente, ana):
    ids = ids_por_descricao(ana)
    decisoes = [{"transacao_id": ids["Gianluca - Bom Fim"], "categoria": "Restaurantes e delivery"}]
    mesma = chave()
    primeira = confirmar(cliente, ana, decisoes, chave_idem=mesma).json()
    segunda = confirmar(cliente, ana, decisoes, chave_idem=mesma).json()
    assert segunda["repetido"] is True and segunda["lote_id"] == primeira["lote_id"]
    assert len(alteracoes(ana)) == 1


def test_sem_lembrar_ou_com_escolhas_diferentes_nao_cria_regra(cliente, ana):
    ids = ids_por_descricao(ana)
    sem_lembrar = confirmar(
        cliente,
        ana,
        [{"transacao_id": ids["Gianluca - Bom Fim"], "categoria": "Lazer"}],
        lembrar=False,
    ).json()
    assert sem_lembrar["regras_salvas"] == []
    divergentes = confirmar(
        cliente,
        ana,
        [
            {"transacao_id": ids["Lords ZS"], "categoria": "Vestuário"},
            {"transacao_id": ids["LORDS ZS"], "categoria": "Presentes e doações"},
        ],
    ).json()
    assert divergentes["alteradas"] == 2 and divergentes["regras_salvas"] == []
    regras_ = cliente.get("/api/regras", headers=entrar(ana)).json()
    assert not any(r["padrao"] in {"LORDS ZS", "GIANLUCA - BOM FIM"} for r in regras_)


def test_desfazer_volta_para_outros_e_apaga_a_regra(cliente, ana):
    ids = ids_por_descricao(ana)
    lote = confirmar(
        cliente, ana, [{"transacao_id": ids["Lords ZS"], "categoria": "Vestuário"}]
    ).json()
    assert lote["regras_salvas"] == ["LORDS ZS"]
    desfeito = cliente.post(
        f"/api/revisao/lotes/{lote['lote_id']}/desfazer", headers=entrar(ana)
    ).json()
    assert desfeito["desfeitas"] == 1 and desfeito["conflitos"] == []
    assert estado(ana, ids["Lords ZS"])["conta"] == "Despesa:Outros"
    assert estado(ana, ids["Lords ZS"])["por"] == "claude"
    assert not any(
        r["padrao"] == "LORDS ZS" for r in cliente.get("/api/regras", headers=entrar(ana)).json()
    )
    de_novo = cliente.post(
        f"/api/revisao/lotes/{lote['lote_id']}/desfazer", headers=entrar(ana)
    ).json()
    assert de_novo["ja_desfeito"] is True
    assert ledger_balanceado(ana)


def test_outra_pessoa_nao_analisa_nem_altera(cliente, ana):
    bia = criar_usuario()
    ids = ids_por_descricao(ana)
    lote = confirmar(
        cliente, ana, [{"transacao_id": ids["Lords ZS"], "categoria": "Vestuário"}]
    ).json()
    assert (
        confirmar(
            cliente, bia, [{"transacao_id": ids["Gianluca - Bom Fim"], "categoria": "Lazer"}]
        ).status_code
        == 404
    )
    assert (
        cliente.post(
            f"/api/revisao/lotes/{lote['lote_id']}/desfazer", headers=entrar(bia)
        ).status_code
        == 404
    )
    analise = cliente.post("/api/revisao/analisar", headers=entrar(bia)).json()
    assert analise["total_em_outros"] == 0 and analise["sugestoes"] == []
    assert estado(ana, ids["Gianluca - Bom Fim"])["conta"] == "Despesa:Outros"
    assert estado(ana, ids["Lords ZS"])["conta"] == "Despesa:Vestuário"
    assert cliente.post("/api/revisao/analisar").status_code == 401


def test_analisar_sem_chave_avisa(cliente, ana):
    corpo = cliente.post("/api/revisao/analisar", headers=entrar(ana)).json()
    assert corpo["ia_disponivel"] is False
    assert corpo["total_em_outros"] == 6 and corpo["sugestoes"] == []
    assert corpo["pesquisa_disponivel"] is False


def ferramenta(nome: str, entrada: dict, identificador: str) -> ToolUseBlock:
    return ToolUseBlock.model_construct(type="tool_use", id=identificador, name=nome, input=entrada)


def mensagem(*blocos, stop_reason: str = "tool_use") -> Message:
    return Message.model_construct(
        id="m",
        type="message",
        role="assistant",
        model="teste",
        content=list(blocos),
        stop_reason=stop_reason,
    )


class ClaudeFalso:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas: list[dict] = []
        self.messages = SimpleNamespace(create=self._criar)

    def _criar(self, **kwargs):
        self.chamadas.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.respostas.pop(0)


class PesquisadorFalso:
    def __init__(self):
        self.chamadas: list[tuple[str, str | None]] = []

    def pesquisar(self, termo, cidade):
        self.chamadas.append((termo, cidade))
        return ResultadoPesquisa(
            termo=termo,
            cidade=cidade,
            consultas=[termo],
            fontes=[
                FonteEncontrada(titulo="Lords ZS Alfaiataria", url="https://exemplo.test/lords")
            ],
            resumo="Alfaiataria e loja de ternos.",
        )


@pytest.fixture
def sessao_da_ana(ana):
    marca = usuario_atual.set(ana)
    with abrir_sessao(ana) as session:
        yield session
    usuario_atual.reset(marca)


def test_analise_valida_sugestoes_e_nao_altera_nada(sessao_da_ana, ana):
    grupos = revisao.agrupar(
        [i for i in revisao.em_outros(sessao_da_ana, 300) if i.valor_centavos > 0]
    )
    numero = {g.estabelecimento.upper(): n for n, g in enumerate(grupos)}
    lords, amazon = numero["LORDS ZS"], numero["AMAZON"]
    gianluca = next(n for n, g in enumerate(grupos) if "Gianluca - Bom Fim" in g.descricoes)
    pix = next(n for n, g in enumerate(grupos) if "PIX enviado" in g.descricoes)
    pesquisador = PesquisadorFalso()
    claude = ClaudeFalso(
        [
            mensagem(
                ferramenta(
                    "pesquisar_estabelecimento",
                    {"grupo": lords, "termo": "Lords ZS R$ 450,00", "cidade": "Porto Alegre"},
                    "t1",
                ),
                ferramenta(
                    "pesquisar_estabelecimento", {"grupo": pix, "termo": "PIX enviado"}, "t2"
                ),
            ),
            mensagem(
                ferramenta(
                    "registrar_sugestoes",
                    {
                        "sugestoes": [
                            {
                                "grupo": lords,
                                "estabelecimento": "Lords ZS",
                                "categoria": "Vestuário",
                                "justificativa": "Loja de ternos.",
                                "origem": "pesquisa",
                                "fontes": ["f1"],
                            },
                            {
                                "grupo": gianluca,
                                "estabelecimento": "Gianluca",
                                "categoria": "Moda inventada",
                                "justificativa": "?",
                                "origem": "descricao",
                            },
                            {
                                "grupo": amazon,
                                "estabelecimento": "Amazon",
                                "categoria": "Assinaturas",
                                "justificativa": "Histórico tem Amazon Prime em Assinaturas.",
                                "origem": "historico",
                            },
                            {
                                "grupo": pix,
                                "estabelecimento": "PIX enviado",
                                "categoria": "Presentes e doações",
                                "justificativa": "Talvez presente.",
                                "origem": "descricao",
                            },
                        ]
                    },
                    "t3",
                ),
            ),
            mensagem(
                ferramenta(
                    "registrar_sugestoes",
                    {
                        "sugestoes": [
                            {
                                "grupo": n,
                                "categoria": None,
                                "justificativa": "Sem pista.",
                                "origem": "descricao",
                            }
                            for n in range(len(grupos))
                            if n not in {lords, gianluca, amazon, pix}
                        ]
                    },
                    "t4",
                ),
            ),
        ]
    )
    analise = analise_outros.analisar(sessao_da_ana, pesquisador, claude)
    assert pesquisador.chamadas == [("LORDS ZS", None)]
    assert analise.pesquisas_feitas == 1 and analise.analisadas == 6
    por = {s.descricao: s for s in analise.sugestoes}
    assert por["Lords ZS"].categoria == "Vestuário" and por["LORDS ZS"].categoria == "Vestuário"
    assert por["Lords ZS"].fontes[0].url == "https://exemplo.test/lords"
    assert por["Gianluca - Bom Fim"].categoria is None
    amazon_ = por["Amazonmktplc*Rchsports - Parcela 1/6"]
    assert amazon_.estabelecimento == "Amazon" and amazon_.categoria is None
    assert "produto" in amazon_.justificativa
    assert por["amazon parcela"].categoria is None and por["amazon parcela"].valor_centavos == 8990
    assert por["PIX enviado"].categoria is None and por["PIX enviado"].estabelecimento is None
    resultado_da_pesquisa_pix = claude.chamadas[1]["messages"][-1]["content"][1]
    assert resultado_da_pesquisa_pix.get("is_error") is True
    primeira = claude.chamadas[0]
    assert "Outros" not in str(
        primeira["tools"][-1]["input_schema"]["properties"]["sugestoes"]["items"]["properties"][
            "categoria"
        ]["enum"]
    )
    assert "Transferência interna" not in str(primeira["tools"][-1])
    assert "<grupos" in primeira["messages"][0]["content"]
    assert estado(ana, ids_por_descricao(ana)["Lords ZS"])["conta"] == "Despesa:Outros"


def test_analise_sem_pesquisa_configurada_avisa_o_modelo(sessao_da_ana):
    claude = ClaudeFalso(
        [
            mensagem(
                ferramenta("registrar_sugestoes", {"sugestoes": []}, "t1"), stop_reason="end_turn"
            )
        ]
    )
    analise = analise_outros.analisar(sessao_da_ana, None, claude)
    assert analise.pesquisa_disponivel is False
    assert "pesquisar_estabelecimento" not in {f["name"] for f in claude.chamadas[0]["tools"]}
    assert "NÃO configurada" in claude.chamadas[0]["system"]
    assert all(s.categoria is None for s in analise.sugestoes)


def test_preparar_termo_limita_o_que_vai_para_a_busca():
    assert preparar_termo("Lords ZS 450,00 123.456.789-00", None, ["Lords ZS"], []) == (
        "LORDS ZS",
        None,
    )
    assert preparar_termo("Gianluca", "Bom Fim", ["Gianluca - Bom Fim"], []) == (
        "GIANLUCA",
        "Bom Fim",
    )
    assert preparar_termo("Gianluca", "Porto Alegre", ["Gianluca - Bom Fim"], []) == (
        "GIANLUCA",
        None,
    )
    with pytest.raises(PesquisaRecusada, match="Pix"):
        preparar_termo("Maria Souza", None, ["PIX ENVIADO MARIA SOUZA"], [])
    with pytest.raises(PesquisaRecusada):
        preparar_termo("Fulano da Silva", None, ["Lords ZS"], [])


def test_pesquisa_anthropic_so_usa_links_devolvidos_pela_ferramenta():
    resultado_web = SimpleNamespace(
        type="web_search_tool_result",
        content=[
            SimpleNamespace(url=f"https://exemplo.test/{n}", title=str(n))
            for n in [1, 1, *range(2, 10)]
        ],
    )
    resposta = SimpleNamespace(
        content=[
            SimpleNamespace(type="server_tool_use", input={"query": "LORDS ZS"}),
            resultado_web,
            SimpleNamespace(type="text", text="Alfaiataria, veja https://inventado.test"),
        ]
    )
    chamadas = []
    client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: chamadas.append(kw) or resposta)
    )
    achado = PesquisaAnthropic(client, "modelo").pesquisar("LORDS ZS", None)
    urls = [f.url for f in achado.fontes]
    assert len(urls) == 5 and len(set(urls)) == 5 and "https://inventado.test" not in urls
    assert (
        chamadas[0]["messages"][0]["content"] == "Termo: LORDS ZS\nCidade ou bairro: não informado"
    )
    assert chamadas[0]["tools"][0]["type"] == "web_search_20250305"
