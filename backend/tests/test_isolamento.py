import asyncio
import json

import pytest
from conftest import criar_usuario, emitir_jwt
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from nota_a_nota import legado
from nota_a_nota.acesso import AcessoSemUsuario, DonoDiferente, abrir_sessao, usuario_atual
from nota_a_nota.db import get_sessionmaker
from nota_a_nota.llm.chat import executar_ferramenta
from nota_a_nota.models import Conta, TipoConta

FATURA = b"""date,title,amount
2026-03-02,Quitanda Orvalho,120.50
2026-03-05,Ifood *Pizzaria Segredo Da Ana,64.90
2026-03-09,Drogaria Luar Ltda,33.10
"""
MCP = {"accept": "application/json, text/event-stream"}


def entrar(usuario_id: str) -> dict[str, str]:
    return {"authorization": f"Bearer {emitir_jwt(usuario_id)}"}


def chamar_ferramenta(cliente, token: str, nome: str, argumentos: dict | None = None) -> str:
    resposta = cliente.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": nome, "arguments": argumentos or {}},
        },
        headers={**MCP, "authorization": f"Bearer {token}"},
    )
    assert resposta.status_code == 200, resposta.text
    return json.dumps(resposta.json()["result"], ensure_ascii=False)


@pytest.fixture
def ana_e_bia(cliente, banco):
    ana, bia = criar_usuario(), criar_usuario()
    importada = cliente.post(
        "/api/importar",
        files={"arquivo": ("Nubank_2026-03-10.csv", FATURA)},
        headers=entrar(ana),
    ).json()
    cliente.put("/api/renda", json={"valor_centavos": 900_000}, headers=entrar(ana))
    cliente.put(
        "/api/cofrinho/teto", json={"mes": "2026-03", "teto_centavos": 50_000}, headers=entrar(ana)
    )
    cliente.post("/api/categorias", json={"nome": "Segredos da Ana"}, headers=entrar(ana))
    regra = cliente.post(
        "/api/regras",
        json={"padrao": "SEGREDO", "categoria": "Segredos da Ana"},
        headers=entrar(ana),
    ).json()
    with abrir_sessao(ana) as session:
        transacao_id = session.execute(
            text("SELECT id FROM transacoes WHERE usuario_id = :u ORDER BY id LIMIT 1"), {"u": ana}
        ).scalar_one()
    return {
        "ana": ana,
        "bia": bia,
        "importacao_id": importada["importacao_id"],
        "regra_id": regra["id"],
        "transacao_id": transacao_id,
    }


def test_leituras_da_bia_nao_mostram_nada_da_ana(cliente, ana_e_bia):
    ana, bia = ana_e_bia["ana"], ana_e_bia["bia"]

    diagnostico_da_ana = cliente.get("/api/diagnostico?mes=2026-03", headers=entrar(ana)).json()
    respostas = {
        rota: cliente.get(rota, headers=entrar(bia))
        for rota in (
            "/api/diagnostico?mes=2026-03",
            "/api/saldos",
            "/api/busca?q=segredo",
            "/api/busca?q=orvalho",
            "/api/regras",
            "/api/categorias",
            "/api/renda",
            "/api/cofrinho?mes=2026-03",
            "/api/gastos?inicio=2026-03-01&fim=2026-03-31",
            "/api/tokens-mcp",
        )
    }

    assert diagnostico_da_ana["totais"]["gastos_centavos"] > 0
    assert all(r.status_code == 200 for r in respostas.values())
    tudo = json.dumps({rota: r.json() for rota, r in respostas.items()}, ensure_ascii=False)
    for segredo in ("Orvalho", "ORVALHO", "Segredo", "SEGREDO", "Nubank", "Luar", "LUAR", "900000"):
        assert segredo not in tudo
    assert respostas["/api/diagnostico?mes=2026-03"].json()["meses_disponiveis"] == []
    assert respostas["/api/renda"].json() is None
    assert respostas["/api/cofrinho?mes=2026-03"].json()["teto_centavos"] is None


def test_bia_nao_altera_nada_da_ana_mesmo_sabendo_os_ids(cliente, ana_e_bia):
    ana, bia = ana_e_bia["ana"], ana_e_bia["bia"]
    transacao_id, regra_id = ana_e_bia["transacao_id"], ana_e_bia["regra_id"]
    token_da_ana = cliente.post("/api/tokens-mcp", json={"nome": "Ana"}, headers=entrar(ana)).json()

    correcao = cliente.patch(
        f"/api/transacoes/{transacao_id}/categoria",
        json={"categoria": "Lazer", "criar_regra": True},
        headers=entrar(bia),
    )
    apagar_regra = cliente.delete(f"/api/regras/{regra_id}", headers=entrar(bia))
    revogar_token = cliente.delete(f"/api/tokens-mcp/{token_da_ana['id']}", headers=entrar(bia))
    voltar_teto = cliente.delete("/api/cofrinho/teto?mes=2026-03", headers=entrar(bia))
    categorizar = cliente.post(
        f"/api/categorizar?importacao_id={ana_e_bia['importacao_id']}", headers=entrar(bia)
    )

    assert correcao.status_code == 404
    assert apagar_regra.status_code == 404
    assert revogar_token.status_code == 404
    assert voltar_teto.status_code == 204
    assert categorizar.json()["para_revisar_na_importacao"] == 0
    assert any(r["id"] == regra_id for r in cliente.get("/api/regras", headers=entrar(ana)).json())
    assert (
        cliente.get("/api/cofrinho?mes=2026-03", headers=entrar(ana)).json()["teto_centavos"]
        == 50_000
    )
    assert "Nubank" in chamar_ferramenta(cliente, token_da_ana["token"], "saldos")


def test_mcp_e_chat_respondem_so_com_os_dados_de_quem_chamou(cliente, ana_e_bia):
    ana, bia = ana_e_bia["ana"], ana_e_bia["bia"]
    token_ana = cliente.post("/api/tokens-mcp", json={"nome": "a"}, headers=entrar(ana)).json()
    token_bia = cliente.post("/api/tokens-mcp", json={"nome": "b"}, headers=entrar(bia)).json()

    saldos_ana = chamar_ferramenta(cliente, token_ana["token"], "saldos")
    saldos_bia = chamar_ferramenta(cliente, token_bia["token"], "saldos")
    busca_bia = chamar_ferramenta(
        cliente, token_bia["token"], "buscar_transacoes", {"texto": "orvalho"}
    )
    recategorizar = chamar_ferramenta(
        cliente,
        token_bia["token"],
        "recategorizar",
        {"transacao_id": ana_e_bia["transacao_id"], "categoria": "Lazer"},
    )
    marca = usuario_atual.set(bia)
    try:
        pelo_chat = asyncio.run(
            executar_ferramenta(
                "gastos_por_categoria", {"inicio": "2026-03-01", "fim": "2026-03-31"}, "t1"
            )
        )
    finally:
        usuario_atual.reset(marca)

    assert "Nubank" in saldos_ana
    assert "Nubank" not in saldos_bia
    assert "ORVALHO" not in busca_bia.upper()
    assert '"isError": true' in recategorizar
    assert "Mercado" not in json.dumps(pelo_chat, ensure_ascii=False)


def test_sessao_sem_usuario_nao_le_dado_financeiro(banco):
    with get_sessionmaker()() as session, pytest.raises(AcessoSemUsuario):
        session.scalars(select(Conta)).all()


def test_ferramenta_sem_usuario_autenticado_falha_fechada(banco):
    resultado = asyncio.run(executar_ferramenta("saldos", {}, "t2"))

    assert resultado["is_error"] is True


def test_objeto_com_dono_trocado_nao_e_gravado(banco):
    ana, bia = criar_usuario(), criar_usuario()
    with abrir_sessao(ana) as session:
        session.add(Conta(usuario_id=bia, nome="Ativo:Infiltrada", tipo=TipoConta.ATIVO))
        with pytest.raises(DonoDiferente):
            session.flush()


def test_banco_recusa_lancamento_em_conta_de_outra_pessoa(banco):
    ana, bia = criar_usuario(), criar_usuario()
    with get_sessionmaker()() as session:
        conta_da_bia = session.execute(
            text("SELECT id FROM contas WHERE usuario_id = :u LIMIT 1"), {"u": bia}
        ).scalar_one()
        conta_da_ana = session.execute(
            text("SELECT id FROM contas WHERE usuario_id = :u LIMIT 1"), {"u": ana}
        ).scalar_one()
        transacao = session.execute(
            text(
                "INSERT INTO transacoes (usuario_id, data, descricao, origem)"
                " VALUES (:u, '2026-01-01', 'x', 'manual') RETURNING id"
            ),
            {"u": ana},
        ).scalar_one()
        with pytest.raises(IntegrityError):
            session.execute(
                text(
                    "INSERT INTO lancamentos (usuario_id, transacao_id, conta_id, valor_centavos)"
                    " VALUES (:u, :t, :c1, 100), (:u, :t, :c2, -100)"
                ),
                {"u": ana, "t": transacao, "c1": conta_da_ana, "c2": conta_da_bia},
            )
            session.flush()
        session.rollback()


def test_memoria_da_capi_nao_vaza_entre_pessoas():
    from nota_a_nota.cofrinho import EstadoCofrinho, Humor
    from nota_a_nota.llm import capivara

    estado = EstadoCofrinho(
        mes="2026-03",
        teto_centavos=100,
        gasto_centavos=50,
        pode_gastar_centavos=50,
        dias_no_mes=31,
        dias_restantes=10,
        por_dia_centavos=5,
        humor=Humor.TRANQUILA,
        ultimos=[],
    )
    capivara._memoria[capivara._chave(estado, "ana")] = capivara.Fala(
        texto="Mais um Zaffari, Ana?", autor="claude"
    )

    assert capivara.fala_imediata(estado, "bia").autor == "roteiro"


def _criar_dono_legado(session) -> None:
    session.execute(
        text(
            'INSERT INTO "user" (id, name, email, "emailVerified") VALUES '
            "(:id, 'legado', 'dados-legados@nota-a-nota.invalid', false) ON CONFLICT DO NOTHING"
        ),
        {"id": legado.DONO_LEGADO},
    )


def test_legado_so_vai_para_conta_verificada_e_vazia(cliente, banco):
    destino = criar_usuario()
    nao_verificado = criar_usuario(verificado=False)
    ocupado = criar_usuario()
    cliente.put("/api/renda", json={"valor_centavos": 1}, headers=entrar(ocupado))
    with get_sessionmaker()() as session:
        _criar_dono_legado(session)
        session.commit()
    with abrir_sessao(legado.DONO_LEGADO) as session:
        from nota_a_nota.ledger import criar_contas_padrao

        criar_contas_padrao(session)
        session.add(Conta(nome="Ativo:Conta antiga", tipo=TipoConta.ATIVO))
        session.commit()

    with get_sessionmaker()() as session:

        def email(u: str) -> str:
            return session.execute(
                text('SELECT email FROM "user" WHERE id = :u'), {"u": u}
            ).scalar_one()

        with pytest.raises(legado.TransferenciaRecusada, match="verificou"):
            legado.transferir(session, email(nao_verificado), confirmar=True)
        with pytest.raises(legado.TransferenciaRecusada, match="dados próprios"):
            legado.transferir(session, email(ocupado), confirmar=True)
        simulacao = legado.transferir(session, email(destino), confirmar=False)
        aplicada = legado.transferir(session, email(destino), confirmar=True)

    assert simulacao.aplicada is False and simulacao.linhas["contas"] > 1
    assert aplicada.aplicada is True
    saldos = cliente.get("/api/saldos", headers=entrar(destino)).json()
    assert any(s["conta"] == "Ativo:Conta antiga" for s in saldos)
    with get_sessionmaker()() as session:
        restante = session.execute(
            text('SELECT count(*) FROM "user" WHERE id = :u'), {"u": legado.DONO_LEGADO}
        ).scalar_one()
    assert restante == 0
