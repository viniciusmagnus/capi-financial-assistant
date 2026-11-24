import uuid
from types import SimpleNamespace

import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock
from conftest import criar_usuario, emitir_jwt
from sqlalchemy import select, text

from nota_a_nota import consultas, regras
from nota_a_nota.acesso import abrir_sessao, usuario_atual
from nota_a_nota.ledger import aplicar_categoria
from nota_a_nota.llm import revisor
from nota_a_nota.models import ConversaRevisao, OrigemCategoria, PropostaRevisao, Transacao
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
2026-11-03,Amazonmktplc*Outraloja - Parcela 2/3,40.00
"""


def entrar(usuario_id: str) -> dict[str, str]:
    return {"authorization": f"Bearer {emitir_jwt(usuario_id)}"}


def chave() -> str:
    return uuid.uuid4().hex


def mover_tudo_para_outros(usuario_id: str) -> None:
    with abrir_sessao(usuario_id) as session:
        for pendente in consultas.pendentes_de_categoria(session, limite=None):
            aplicar_categoria(session, pendente.id, "Outros", OrigemCategoria.CLAUDE, "baixa")
        session.commit()


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
        desbalanceadas = session.execute(
            text(
                "SELECT count(*) FROM (SELECT transacao_id FROM lancamentos WHERE usuario_id = :u "
                "GROUP BY transacao_id HAVING sum(valor_centavos) <> 0) x"
            ),
            {"u": usuario_id},
        ).scalar_one()
    return desbalanceadas == 0


@pytest.fixture
def ana(cliente, banco):
    usuario = criar_usuario()
    resposta = cliente.post(
        "/api/importar",
        files={"arquivo": ("Nubank_2026-10-10.csv", FATURA)},
        headers=entrar(usuario),
    )
    assert resposta.status_code == 200, resposta.text
    mover_tudo_para_outros(usuario)
    return usuario


def previa(cliente, usuario, conteudo, **opcoes):
    resposta = cliente.post(
        "/api/revisao/previa",
        json={"conteudo": conteudo, "opcoes": opcoes},
        headers=entrar(usuario),
    )
    return resposta


def aplicar(
    cliente, usuario, conteudo, assinatura=None, chave_idem=None, proposta_id=None, **opcoes
):
    if assinatura is None:
        feita = previa(cliente, usuario, conteudo, **opcoes)
        assert feita.status_code == 200, feita.text
        assinatura = feita.json()["assinatura"]
    return cliente.post(
        "/api/revisao/aplicar",
        json={
            "conteudo": conteudo,
            "opcoes": opcoes,
            "assinatura": assinatura,
            "chave_idempotencia": chave_idem or chave(),
            "proposta_id": proposta_id,
        },
        headers=entrar(usuario),
    )


def lords(ids, **extra):
    return {
        "transacao_ids": [ids["Lords ZS"], ids["LORDS ZS"]],
        "estabelecimento": "Lords ZS",
        "categoria": "Vestuário",
        "motivo": "A pessoa disse que é a loja de ternos.",
        "evidencias": [{"origem": "usuario", "texto": "Lords ZS é a loja de ternos"}],
        **extra,
    }


def test_lista_paginada_filtra_e_agrupa(cliente, ana):
    pagina = cliente.get(
        "/api/revisao/transacoes", params={"por_pagina": 2}, headers=entrar(ana)
    ).json()
    assert pagina["total"] == 6
    assert len(pagina["itens"]) == 2
    assert pagina["total_centavos"] == 45000 + 2800 + 8990 + 12000 + 7500 + 15000

    segunda = cliente.get(
        "/api/revisao/transacoes", params={"por_pagina": 2, "pagina": 2}, headers=entrar(ana)
    ).json()
    assert {i["id"] for i in segunda["itens"]}.isdisjoint({i["id"] for i in pagina["itens"]})

    lords_ = cliente.get(
        "/api/revisao/transacoes", params={"q": "lords"}, headers=entrar(ana)
    ).json()
    assert lords_["total"] == 2
    outubro = cliente.get(
        "/api/revisao/transacoes",
        params={"inicio": "2026-10-04", "fim": "2026-10-05"},
        headers=entrar(ana),
    ).json()
    assert outubro["total"] == 2

    todos = cliente.get("/api/revisao/transacoes", headers=entrar(ana)).json()["itens"]
    por_descricao = {i["descricao"]: i for i in todos}
    assert por_descricao["Amazonmktplc*Rchsports - Parcela 1/6"]["parcela"] == "1/6"
    assert por_descricao["amazon parcela"]["parcela"] == "parcelada"
    assert por_descricao["PIX enviado"]["forma_pagamento"] == "Pix"
    assert por_descricao["amazon parcela"]["estabelecimento"] == "Amazon"
    assert por_descricao["amazon parcela"]["estabelecimento_confirmado"] is False

    grupos = cliente.get("/api/revisao/grupos", headers=entrar(ana)).json()
    amazon = next(g for g in grupos if g["marca"] == "amazon")
    assert amazon["quantidade"] == 2 and len(amazon["ids"]) == 2
    assert sorted(amazon["descricoes"]) == [
        "Amazonmktplc*Rchsports - Parcela 1/6",
        "amazon parcela",
    ]
    lords_grupo = next(g for g in grupos if g["estabelecimento"].upper() == "LORDS ZS")
    assert lords_grupo["quantidade"] == 2

    ids = cliente.get("/api/revisao/ids", params={"q": "amazon"}, headers=entrar(ana)).json()["ids"]
    assert sorted(ids) == sorted(amazon["ids"])


def test_aprovar_aplica_registra_e_atualiza_totais(cliente, ana):
    ids = ids_por_descricao(ana)
    conteudo = lords(ids)
    feita = previa(cliente, ana, conteudo)
    assert feita.status_code == 200, feita.text
    corpo = feita.json()
    assert len(corpo["afetadas"]) == 2
    assert corpo["efeito_nos_gastos_centavos"] == 0

    aplicada = aplicar(cliente, ana, conteudo, assinatura=corpo["assinatura"])
    assert aplicada.status_code == 200, aplicada.text
    assert aplicada.json()["alteradas"] == 2

    depois = estado(ana, ids["Lords ZS"])
    assert depois["conta"] == "Despesa:Vestuário"
    assert depois["estabelecimento"] == "Lords ZS"
    assert depois["por"] == "usuario"
    assert depois["descricao"] == "Lords ZS"
    assert depois["valor"] == 45000

    restante = cliente.get("/api/revisao/transacoes", headers=entrar(ana)).json()
    assert restante["total"] == 4
    assert restante["total_centavos"] == 2800 + 8990 + 12000 + 7500

    with abrir_sessao(ana) as session:
        registro = session.execute(
            text(
                "SELECT categoria_anterior, categoria_nova, origem, categorizada_por_anterior::text "
                "FROM revisao_alteracoes WHERE transacao_id = :id"
            ),
            {"id": ids["Lords ZS"]},
        ).one()
    assert tuple(registro) == ("Despesa:Outros", "Despesa:Vestuário", "usuario", "claude")
    assert ledger_balanceado(ana)


def test_reenvio_nao_aplica_duas_vezes(cliente, ana):
    ids = ids_por_descricao(ana)
    conteudo = lords(ids)
    assinatura = previa(cliente, ana, conteudo).json()["assinatura"]
    mesma_chave = chave()
    primeira = aplicar(cliente, ana, conteudo, assinatura=assinatura, chave_idem=mesma_chave)
    segunda = aplicar(cliente, ana, conteudo, assinatura=assinatura, chave_idem=mesma_chave)
    assert primeira.status_code == segunda.status_code == 200
    assert segunda.json()["repetido"] is True
    assert segunda.json()["lote_id"] == primeira.json()["lote_id"]
    with abrir_sessao(ana) as session:
        assert (
            session.execute(
                text("SELECT count(*) FROM revisao_alteracoes WHERE usuario_id = :u"), {"u": ana}
            ).scalar_one()
            == 2
        )

    outra_chave = aplicar(cliente, ana, conteudo, assinatura=assinatura)
    assert outra_chave.status_code == 409


def test_conteudo_editado_exige_nova_aprovacao(cliente, ana):
    ids = ids_por_descricao(ana)
    original = lords(ids)
    assinatura = previa(cliente, ana, original).json()["assinatura"]
    editado = lords(ids, categoria="Presentes e doações")
    recusado = aplicar(cliente, ana, editado, assinatura=assinatura)
    assert recusado.status_code == 409
    assert estado(ana, ids["Lords ZS"])["conta"] == "Despesa:Outros"

    so_uma = lords(ids, transacao_ids=[ids["Lords ZS"]])
    assert aplicar(cliente, ana, so_uma, assinatura=assinatura).status_code == 409
    assert aplicar(cliente, ana, editado).status_code == 200


def test_rejeitar_proposta_impede_aplicar(cliente, ana):
    ids = ids_por_descricao(ana)
    with abrir_sessao(ana) as session:
        conversa = ConversaRevisao(mensagens=[], historico=[], fontes=[])
        session.add(conversa)
        session.flush()
        proposta = PropostaRevisao(conversa_id=conversa.id, conteudo=lords(ids))
        session.add(proposta)
        session.commit()
        proposta_id = proposta.id
    rejeitada = cliente.post(f"/api/revisao/propostas/{proposta_id}/rejeitar", headers=entrar(ana))
    assert rejeitada.status_code == 204
    resposta = aplicar(cliente, ana, lords(ids), proposta_id=proposta_id)
    assert resposta.status_code == 409
    assert estado(ana, ids["Lords ZS"])["conta"] == "Despesa:Outros"


def test_aprovar_proposta_marca_como_aplicada(cliente, ana):
    ids = ids_por_descricao(ana)
    with abrir_sessao(ana) as session:
        proposta = PropostaRevisao(conteudo=lords(ids))
        session.add(proposta)
        session.commit()
        proposta_id = proposta.id
    assert aplicar(cliente, ana, lords(ids), proposta_id=proposta_id).status_code == 200
    with abrir_sessao(ana) as session:
        status = session.scalar(
            select(PropostaRevisao.status).where(PropostaRevisao.id == proposta_id)
        )
    assert status == "aplicada"
    assert aplicar(cliente, ana, lords(ids), proposta_id=proposta_id).status_code == 409


def test_regra_aplica_em_correspondencias_e_em_importacoes_futuras(cliente, ana):
    ids = ids_por_descricao(ana)
    conteudo = lords(
        ids,
        transacao_ids=[ids["Lords ZS"]],
        regra={"padrao": "LORDS ZS", "categoria": "Vestuário", "estabelecimento": "Lords ZS"},
    )
    so_selecionadas = previa(cliente, ana, conteudo).json()
    assert len(so_selecionadas["afetadas"]) == 1
    assert so_selecionadas["regra"]["valida"] is True
    assert so_selecionadas["regra"]["correspondencias_existentes"] == 2

    resposta = aplicar(cliente, ana, conteudo, alcance="correspondencias", salvar_regra=True)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["alteradas"] == 2
    assert resposta.json()["regra"]["padrao"] == "LORDS ZS"
    assert estado(ana, ids["LORDS ZS"])["conta"] == "Despesa:Vestuário"
    assert estado(ana, ids["LORDS ZS"])["por"] == "regra"
    with abrir_sessao(ana) as session:
        origens = dict(
            session.execute(
                text("SELECT transacao_id, origem FROM revisao_alteracoes WHERE usuario_id = :u"),
                {"u": ana},
            ).all()
        )
    assert origens == {ids["Lords ZS"]: "usuario", ids["LORDS ZS"]: "regra"}

    regras_ = cliente.get("/api/regras", headers=entrar(ana)).json()
    assert any(r["padrao"] == "LORDS ZS" and r["estabelecimento"] == "Lords ZS" for r in regras_)

    nova = cliente.post(
        "/api/importar",
        files={"arquivo": ("Nubank_2026-11-10.csv", NOVA_FATURA)},
        headers=entrar(ana),
    )
    assert nova.status_code == 200, nova.text
    assert nova.json()["categorizadas_por_regra"] >= 1
    with abrir_sessao(ana) as session:
        nova_id = session.scalar(
            select(Transacao.id)
            .where(Transacao.descricao == "LORDS ZS")
            .order_by(Transacao.data.desc())
        )
    assert nova_id != ids["LORDS ZS"]
    futura = estado(ana, nova_id)
    assert futura["conta"] == "Despesa:Vestuário"
    assert futura["estabelecimento"] == "Lords ZS"
    assert futura["por"] == "regra"


def test_classificacao_manual_anterior_e_preservada(cliente, ana):
    ids = ids_por_descricao(ana)
    manual = cliente.patch(
        f"/api/transacoes/{ids['LORDS ZS']}/categoria",
        json={"categoria": "Outros"},
        headers=entrar(ana),
    )
    assert manual.status_code == 200
    conteudo = lords(ids)
    sem_substituir = previa(cliente, ana, conteudo).json()
    assert sem_substituir["manuais_preservadas"] == 1
    assert [i["id"] for i in sem_substituir["ignoradas"]] == [ids["LORDS ZS"]]
    assert aplicar(cliente, ana, conteudo).status_code == 200
    assert estado(ana, ids["LORDS ZS"])["conta"] == "Despesa:Outros"

    substituindo = aplicar(cliente, ana, conteudo, substituir_manuais=True)
    assert substituindo.status_code == 200
    assert estado(ana, ids["LORDS ZS"])["conta"] == "Despesa:Vestuário"


def test_amazon_vira_estabelecimento_sem_inventar_categoria_nem_mexer_no_valor(cliente, ana):
    ids = ids_por_descricao(ana)
    amazon = [ids["amazon parcela"], ids["Amazonmktplc*Rchsports - Parcela 1/6"]]
    antes = {i: estado(ana, i) for i in amazon}
    with abrir_sessao(ana) as session:
        transacoes_antes = session.execute(
            text("SELECT count(*) FROM transacoes WHERE usuario_id = :u"), {"u": ana}
        ).scalar_one()
    conteudo = {
        "transacao_ids": [amazon[0]],
        "estabelecimento": "Amazon",
        "categoria": None,
        "motivo": "As duas descrições são compras na Amazon; o produto não aparece.",
        "evidencias": [{"origem": "usuario", "texto": "Essas descrições são compras na Amazon"}],
        "incertezas": ["produto desconhecido"],
        "regra": {"padrao": "AMAZON", "categoria": None, "estabelecimento": "Amazon"},
    }
    feita = previa(cliente, ana, conteudo, alcance="correspondencias", salvar_regra=True).json()
    assert {a["id"] for a in feita["afetadas"]} == set(amazon)
    assert all(a["categoria_nova"] == "Outros" for a in feita["afetadas"])
    assert any("Parcelas" in aviso for aviso in feita["avisos"])
    resposta = aplicar(cliente, ana, conteudo, alcance="correspondencias", salvar_regra=True)
    assert resposta.status_code == 200, resposta.text
    for transacao_id in amazon:
        depois = estado(ana, transacao_id)
        assert depois["estabelecimento"] == "Amazon"
        assert depois["conta"] == "Despesa:Outros"
        assert depois["descricao"] == antes[transacao_id]["descricao"]
        assert depois["valor"] == antes[transacao_id]["valor"]
    with abrir_sessao(ana) as session:
        assert (
            session.execute(
                text("SELECT count(*) FROM transacoes WHERE usuario_id = :u"), {"u": ana}
            ).scalar_one()
            == transacoes_antes
        )

    cliente.post(
        "/api/importar",
        files={"arquivo": ("Nubank_2026-11-10.csv", NOVA_FATURA)},
        headers=entrar(ana),
    )
    nova = ids_por_descricao(ana)["Amazonmktplc*Outraloja - Parcela 2/3"]
    futura = estado(ana, nova)
    assert futura["estabelecimento"] == "Amazon"
    assert futura["conta"] == "Despesa:A classificar"
    assert futura["valor"] == 4000
    assert ledger_balanceado(ana)


def test_pix_como_transferencia_exige_confirmacao_e_regra_generica_e_recusada(cliente, ana):
    ids = ids_por_descricao(ana)
    pix = {
        "transacao_ids": [ids["PIX enviado"]],
        "categoria": "Transferência interna",
        "motivo": "A pessoa disse que foi para a poupança dela.",
        "evidencias": [{"origem": "usuario", "texto": "esse Pix foi para minha poupança"}],
        "regra": {"padrao": "PIX ENVIADO", "categoria": "Transferência interna"},
    }
    feita = previa(cliente, ana, pix).json()
    assert feita["exige_confirmar_transferencia"] is True
    assert feita["efeito_nos_gastos_centavos"] == -7500
    assert feita["regra"]["valida"] is False
    assert "genérico" in feita["regra"]["erro"]
    assert any("Transferência interna sai do total" in a for a in feita["avisos"])

    assert previa(cliente, ana, pix, salvar_regra=True).status_code == 422
    sem_confirmar = aplicar(cliente, ana, pix)
    assert sem_confirmar.status_code == 422
    assert estado(ana, ids["PIX enviado"])["conta"] == "Despesa:Outros"

    confirmado = aplicar(cliente, ana, pix, confirmar_transferencia=True)
    assert confirmado.status_code == 200
    assert estado(ana, ids["PIX enviado"])["conta"] == "Patrimonio:Transferência interna"
    assert ledger_balanceado(ana)


def test_proposta_com_categoria_inexistente_e_recusada(cliente, ana):
    ids = ids_por_descricao(ana)
    resposta = previa(cliente, ana, lords(ids, categoria="Moda masculina"))
    assert resposta.status_code == 422
    assert "categoria desconhecida" in resposta.json()["detail"]


def test_forma_de_pagamento_nao_vira_estabelecimento(cliente, ana):
    ids = ids_por_descricao(ana)
    pix = {
        "transacao_ids": [ids["PIX enviado"]],
        "estabelecimento": "PIX Enviado",
        "categoria": None,
        "evidencias": [{"origem": "usuario", "texto": "padroniza"}],
    }
    resposta = previa(cliente, ana, pix)
    assert resposta.status_code == 422
    assert "forma de pagamento" in resposta.json()["detail"]


def test_desfazer_lote_volta_tudo_e_apaga_regra_criada(cliente, ana):
    ids = ids_por_descricao(ana)
    conteudo = lords(
        ids, regra={"padrao": "LORDS ZS", "categoria": "Vestuário", "estabelecimento": "Lords ZS"}
    )
    lote = aplicar(cliente, ana, conteudo, salvar_regra=True).json()
    desfeito = cliente.post(f"/api/revisao/lotes/{lote['lote_id']}/desfazer", headers=entrar(ana))
    assert desfeito.status_code == 200
    assert desfeito.json()["desfeitas"] == 2 and desfeito.json()["conflitos"] == []
    voltou = estado(ana, ids["Lords ZS"])
    assert voltou == {**voltou, "conta": "Despesa:Outros", "estabelecimento": None, "por": "claude"}
    assert not any(
        r["padrao"] == "LORDS ZS" for r in cliente.get("/api/regras", headers=entrar(ana)).json()
    )

    de_novo = cliente.post(f"/api/revisao/lotes/{lote['lote_id']}/desfazer", headers=entrar(ana))
    assert de_novo.json()["ja_desfeito"] is True
    lotes = cliente.get("/api/revisao/lotes", headers=entrar(ana)).json()
    assert lotes[0]["desfeito_em"] is not None
    assert ledger_balanceado(ana)


def test_desfazer_preserva_o_que_mudou_depois(cliente, ana):
    ids = ids_por_descricao(ana)
    lote = aplicar(cliente, ana, lords(ids)).json()
    cliente.patch(
        f"/api/transacoes/{ids['LORDS ZS']}/categoria",
        json={"categoria": "Lazer"},
        headers=entrar(ana),
    )
    desfeito = cliente.post(
        f"/api/revisao/lotes/{lote['lote_id']}/desfazer", headers=entrar(ana)
    ).json()
    assert desfeito["desfeitas"] == 1
    assert desfeito["conflitos"] == [ids["LORDS ZS"]]
    assert estado(ana, ids["LORDS ZS"])["conta"] == "Despesa:Lazer"
    assert estado(ana, ids["Lords ZS"])["conta"] == "Despesa:Outros"


def test_regra_editada_pela_api(cliente, ana):
    criada = cliente.post(
        "/api/regras",
        json={"padrao": "GIANLUCA", "categoria": "Restaurantes e delivery"},
        headers=entrar(ana),
    ).json()
    editada = cliente.patch(
        f"/api/regras/{criada['id']}",
        json={
            "padrao": "GIANLUCA",
            "categoria": "Restaurantes e delivery",
            "estabelecimento": "Gianluca",
        },
        headers=entrar(ana),
    )
    assert editada.status_code == 200 and editada.json()["estabelecimento"] == "Gianluca"
    generica = cliente.patch(
        f"/api/regras/{criada['id']}",
        json={"padrao": "PIX ENVIADO", "categoria": "Outros"},
        headers=entrar(ana),
    )
    assert generica.status_code == 422


def test_outra_pessoa_nao_ve_nem_altera_a_revisao(cliente, ana):
    bia = criar_usuario()
    ids = ids_por_descricao(ana)
    lote = aplicar(cliente, ana, lords(ids)).json()
    with abrir_sessao(ana) as session:
        conversa = ConversaRevisao(mensagens=[], historico=[], fontes=[])
        session.add(conversa)
        session.flush()
        proposta = PropostaRevisao(conversa_id=conversa.id, conteudo=lords(ids))
        session.add(proposta)
        session.commit()
        conversa_id, proposta_id = conversa.id, proposta.id
    regra_ana = cliente.post(
        "/api/regras", json={"padrao": "GIANLUCA", "categoria": "Lazer"}, headers=entrar(ana)
    ).json()

    assert cliente.get("/api/revisao/transacoes", headers=entrar(bia)).json()["total"] == 0
    assert previa(cliente, bia, lords(ids)).status_code == 404
    assert aplicar(cliente, bia, lords(ids), assinatura="0" * 64).status_code == 404
    assert cliente.get("/api/revisao/lotes", headers=entrar(bia)).json() == []
    assert (
        cliente.post(
            f"/api/revisao/lotes/{lote['lote_id']}/desfazer", headers=entrar(bia)
        ).status_code
        == 404
    )
    assert (
        cliente.post(
            f"/api/revisao/propostas/{proposta_id}/rejeitar", headers=entrar(bia)
        ).status_code
        == 404
    )
    assert (
        cliente.get(f"/api/revisao/conversas/{conversa_id}", headers=entrar(bia)).status_code == 404
    )
    assert (
        cliente.post(
            f"/api/revisao/conversas/{conversa_id}/mensagens",
            json={"texto": "oi", "transacao_ids": [ids["Lords ZS"]]},
            headers=entrar(bia),
        ).status_code
        == 404
    )
    assert (
        cliente.patch(
            f"/api/regras/{regra_ana['id']}",
            json={"padrao": "GIANLUCA", "categoria": "Outros"},
            headers=entrar(bia),
        ).status_code
        == 404
    )
    assert estado(ana, ids["Lords ZS"])["conta"] == "Despesa:Vestuário"
    assert cliente.get("/api/revisao/transacoes", headers=entrar(ana)).status_code == 200
    assert cliente.get("/api/revisao/transacoes").status_code == 401
    itens_da_ana = cliente.post(
        "/api/revisao/itens", json={"ids": [ids["Lords ZS"]]}, headers=entrar(ana)
    )
    assert itens_da_ana.status_code == 200 and itens_da_ana.json()[0]["descricao"] == "Lords ZS"
    assert (
        cliente.post(
            "/api/revisao/itens", json={"ids": [ids["Lords ZS"]]}, headers=entrar(bia)
        ).status_code
        == 404
    )


def bloco_ferramenta(nome: str, entrada: dict, identificador: str = "t1") -> ToolUseBlock:
    return ToolUseBlock.model_construct(type="tool_use", id=identificador, name=nome, input=entrada)


def mensagem(*blocos, stop_reason: str = "end_turn") -> Message:
    return Message.model_construct(
        id="msg",
        type="message",
        role="assistant",
        model="teste",
        content=list(blocos),
        stop_reason=stop_reason,
    )


class ClaudeFalso:
    def __init__(self, respostas: list[Message]):
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
                FonteEncontrada(titulo="Lords ZS - Alfaiataria", url="https://exemplo.test/lords")
            ],
            resumo="Alfaiataria e loja de ternos.",
        )


@pytest.fixture
def sessao_da_ana(ana):
    marca = usuario_atual.set(ana)
    with abrir_sessao(ana) as session:
        yield session
    usuario_atual.reset(marca)


def test_conversa_valida_propostas_e_nao_altera_o_ledger(sessao_da_ana, ana):
    ids = ids_por_descricao(ana)
    selecao = [ids["Lords ZS"], ids["LORDS ZS"], ids["PIX enviado"]]
    claude = ClaudeFalso(
        [
            mensagem(
                bloco_ferramenta(
                    "registrar_propostas",
                    {
                        "propostas": [
                            lords(ids),
                            lords(ids, transacao_ids=[ids["amazon parcela"]]),
                            lords(ids, categoria="Moda masculina"),
                            {
                                **lords(ids),
                                "evidencias": [
                                    {"origem": "pesquisa", "texto": "achei", "fontes": ["f9"]}
                                ],
                            },
                            {
                                "transacao_ids": [ids["PIX enviado"]],
                                "categoria": "Outros",
                                "motivo": "padronizar",
                                "evidencias": [{"origem": "usuario", "texto": "padroniza"}],
                                "regra": {"padrao": "PIX ENVIADO", "categoria": "Outros"},
                            },
                            {
                                "transacao_ids": [ids["PIX enviado"]],
                                "estabelecimento": "Pix Enviado",
                                "categoria": None,
                                "motivo": "padronizar",
                                "evidencias": [{"origem": "usuario", "texto": "padroniza"}],
                            },
                        ]
                    },
                ),
                stop_reason="tool_use",
            ),
            mensagem(
                TextBlock.model_construct(type="text", text="Propus Lords ZS como Vestuário.")
            ),
        ]
    )
    conversa = revisor.abrir(sessao_da_ana)
    resposta = revisor.conversar(
        sessao_da_ana,
        conversa,
        "Lords ZS é a loja de ternos; classifica como vestuário.",
        selecao,
        None,
        claude,
    )
    assert len(resposta.propostas) == 1
    assert resposta.propostas[0].conteudo.categoria == "Vestuário"
    motivos = " | ".join(resposta.descartadas)
    assert "fora da seleção" in motivos
    assert "categoria inexistente" in motivos
    assert "fontes que não vieram da pesquisa" in motivos
    assert "genérico" in motivos
    assert "forma de pagamento" in motivos
    assert resposta.resposta == "Propus Lords ZS como Vestuário."
    assert estado(ana, ids["Lords ZS"])["conta"] == "Despesa:Outros"

    primeira = claude.chamadas[0]
    assert "pesquisar_estabelecimento" not in {f["name"] for f in primeira["tools"]}
    assert "NÃO configurada" in primeira["system"]
    texto_enviado = primeira["messages"][-1]["content"][0]["text"]
    assert "<selecao_atual" in texto_enviado and "Lords ZS" in texto_enviado
    assert "Amazonmktplc" not in texto_enviado
    resultado = claude.chamadas[1]["messages"][-1]["content"][0]
    assert resultado["type"] == "tool_result"

    salva = revisor.carregar(sessao_da_ana, conversa.id)
    assert [m["papel"] for m in salva.mensagens] == ["usuario", "assistente"]
    assert salva.propostas[0].status == "pendente"


def test_conversa_pesquisa_so_com_termos_da_descricao_e_cita_fontes(sessao_da_ana, ana):
    ids = ids_por_descricao(ana)
    selecao = [ids["Lords ZS"], ids["PIX enviado"]]
    pesquisador = PesquisadorFalso()
    claude = ClaudeFalso(
        [
            mensagem(
                bloco_ferramenta(
                    "pesquisar_estabelecimento",
                    {
                        "termo": "Lords ZS R$ 450,00 123.456.789-00",
                        "cidade": "Porto Alegre",
                        "transacao_ids": [ids["Lords ZS"]],
                    },
                    "t1",
                ),
                bloco_ferramenta(
                    "pesquisar_estabelecimento",
                    {"termo": "PIX enviado", "cidade": None, "transacao_ids": [ids["PIX enviado"]]},
                    "t2",
                ),
                stop_reason="tool_use",
            ),
            mensagem(
                bloco_ferramenta(
                    "registrar_propostas",
                    {
                        "propostas": [
                            {
                                "transacao_ids": [ids["Lords ZS"]],
                                "estabelecimento": "Lords ZS",
                                "categoria": "Vestuário",
                                "motivo": "A pesquisa indica uma alfaiataria.",
                                "evidencias": [
                                    {"origem": "pesquisa", "texto": "alfaiataria", "fontes": ["f1"]}
                                ],
                                "incertezas": ["pode haver outra loja com o mesmo nome"],
                            }
                        ]
                    },
                ),
                stop_reason="tool_use",
            ),
            mensagem(
                TextBlock.model_construct(type="text", text="Achei uma alfaiataria; confirma?")
            ),
        ]
    )
    conversa = revisor.abrir(sessao_da_ana)
    resposta = revisor.conversar(
        sessao_da_ana,
        conversa,
        "Tenta descobrir quais são esses estabelecimentos.",
        selecao,
        pesquisador,
        claude,
    )
    assert pesquisador.chamadas == [("LORDS ZS", None)]
    assert resposta.fontes[0].id == "f1" and resposta.fontes[0].url == "https://exemplo.test/lords"
    assert [p.recusada for p in resposta.pesquisas][1].startswith("Pix e transferências")
    assert len(resposta.propostas) == 1
    assert resposta.propostas[0].conteudo.evidencias[0].fontes == ["f1"]
    resultados = claude.chamadas[1]["messages"][-1]["content"]
    assert resultados[1].get("is_error") is True
    assert estado(ana, ids["Lords ZS"])["conta"] == "Despesa:Outros"


def test_conversa_sem_chave_avisa_e_permite_manual(sessao_da_ana, ana):
    ids = ids_por_descricao(ana)
    conversa = revisor.abrir(sessao_da_ana)
    resposta = revisor.conversar(sessao_da_ana, conversa, "oi", [ids["Lords ZS"]], None)
    assert resposta.ia_disponivel is False
    assert "classificar à mão" in resposta.resposta


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
    assert preparar_termo(
        "Gianluca", "Porto Alegre", ["Gianluca - Bom Fim"], ["fica em porto alegre"]
    ) == ("GIANLUCA", "Porto Alegre")
    with pytest.raises(PesquisaRecusada, match="Pix"):
        preparar_termo("Maria Souza", None, ["PIX ENVIADO MARIA SOUZA"], [])
    with pytest.raises(PesquisaRecusada):
        preparar_termo("Fulano da Silva", None, ["Lords ZS"], [])
    with pytest.raises(PesquisaRecusada):
        preparar_termo("Lords", None, [], [])


def test_pesquisa_anthropic_so_usa_links_devolvidos_pela_ferramenta():
    resultado_web = SimpleNamespace(
        type="web_search_tool_result",
        content=[
            SimpleNamespace(url="https://exemplo.test/a", title="A"),
            SimpleNamespace(url="https://exemplo.test/a", title="A de novo"),
            SimpleNamespace(url="https://exemplo.test/b", title="B"),
            *(SimpleNamespace(url=f"https://exemplo.test/{n}", title=str(n)) for n in range(8)),
        ],
    )
    resposta = SimpleNamespace(
        content=[
            SimpleNamespace(type="server_tool_use", input={"query": "LORDS ZS"}),
            resultado_web,
            SimpleNamespace(type="text", text="É uma alfaiataria, veja https://inventado.test"),
        ]
    )
    chamadas = []
    client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **kw: chamadas.append(kw) or resposta)
    )
    achado = PesquisaAnthropic(client, "modelo").pesquisar("LORDS ZS", None)
    assert [f.url for f in achado.fontes][:2] == [
        "https://exemplo.test/a",
        "https://exemplo.test/b",
    ]
    assert len(achado.fontes) == 5
    assert "https://inventado.test" not in [f.url for f in achado.fontes]
    assert achado.consultas == ["LORDS ZS"]
    enviado = chamadas[0]
    assert enviado["messages"][0]["content"] == "Termo: LORDS ZS\nCidade ou bairro: não informado"
    assert enviado["tools"][0]["type"] == "web_search_20250305"

    erro = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="web_search_tool_result", content=SimpleNamespace(error_code="unavailable")
            )
        ]
    )
    client_erro = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: erro))
    falhou = PesquisaAnthropic(client_erro, "modelo").pesquisar("LORDS ZS", None)
    assert falhou.fontes == [] and falhou.erro == "unavailable"


def test_regra_generica_nao_passa_nem_pelo_modulo(session):
    with pytest.raises(regras.RegraInvalida):
        regras.salvar(session, "PIX ENVIADO", "Outros")
