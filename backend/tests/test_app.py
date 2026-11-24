import asyncio
import time

import jwt
import pytest
from conftest import criar_usuario, emitir_jwt

from nota_a_nota.mcp_server import mcp

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    },
}
CABECALHOS_MCP = {"accept": "application/json, text/event-stream"}


def entrar(usuario_id: str, **mudancas) -> dict[str, str]:
    return {"authorization": f"Bearer {emitir_jwt(usuario_id, **mudancas)}"}


def test_health_e_publico(cliente):
    assert cliente.get("/health").json() == {"status": "ok"}


def test_api_sem_login_responde_401(cliente):
    resposta = cliente.get("/api/saldos")

    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "mudancas",
    [
        {"exp": int(time.time()) - 120},
        {"aud": "outra-api"},
        {"iss": "https://atacante.example"},
        {"email_verified": False},
        {"email_verified": None},
        {"sub": None},
    ],
    ids=["expirado", "audiencia", "emissor", "nao-verificado", "sem-verificacao", "sem-sub"],
)
def test_jwt_invalido_e_recusado(cliente, usuario, mudancas):
    assert cliente.get("/api/saldos", headers=entrar(usuario, **mudancas)).status_code == 401


def test_jwt_assinado_com_segredo_simetrico_e_recusado(cliente, usuario):
    forjado = jwt.encode(
        {"sub": usuario, "email_verified": True, "exp": int(time.time()) + 60},
        "segredo-adivinhado-por-quem-ataca-a-api",
        algorithm="HS256",
    )

    resposta = cliente.get("/api/saldos", headers={"authorization": f"Bearer {forjado}"})

    assert resposta.status_code == 401


def test_jwt_de_usuario_apagado_ou_nao_verificado_no_banco_e_recusado(cliente, banco):
    nao_verificado = criar_usuario(verificado=False, provisionar=False)

    assert cliente.get("/api/saldos", headers=entrar("nao-existe")).status_code == 401
    assert cliente.get("/api/saldos", headers=entrar(nao_verificado)).status_code == 401


def test_primeiro_acesso_cria_categorias_e_regras_padrao(cliente, banco):
    novo = criar_usuario(provisionar=False)

    categorias = cliente.get("/api/categorias", headers=entrar(novo))
    regras = cliente.get("/api/regras", headers=entrar(novo))

    assert categorias.status_code == 200
    assert "Mercado" in categorias.json()["despesa"]
    assert any(r["padrao"] == "IFOOD" for r in regras.json())


def test_mcp_exige_token_pessoal(cliente, usuario):
    sem_token = cliente.post("/mcp", json=INITIALIZE, headers=CABECALHOS_MCP)
    com_jwt_do_app = cliente.post(
        "/mcp", json=INITIALIZE, headers={**CABECALHOS_MCP, **entrar(usuario)}
    )

    assert sem_token.status_code == 401
    assert com_jwt_do_app.status_code == 401


def test_token_do_mcp_aparece_uma_vez_e_pode_ser_revogado(cliente, usuario):
    criado = cliente.post(
        "/api/tokens-mcp", json={"nome": "Claude Desktop"}, headers=entrar(usuario)
    )
    token = criado.json()["token"]
    cabecalhos = {**CABECALHOS_MCP, "authorization": f"Bearer {token}"}

    listados = cliente.get("/api/tokens-mcp", headers=entrar(usuario)).json()
    inicializado = cliente.post("/mcp", json=INITIALIZE, headers=cabecalhos)
    revogado = cliente.delete(f"/api/tokens-mcp/{criado.json()['id']}", headers=entrar(usuario))
    depois = cliente.post("/mcp", json=INITIALIZE, headers=cabecalhos)

    assert criado.status_code == 201 and token.startswith("capi_")
    assert [t["nome"] for t in listados] == ["Claude Desktop"]
    assert "token" not in listados[0] and token.startswith(listados[0]["prefixo"])
    assert inicializado.status_code == 200, inicializado.text
    assert inicializado.json()["result"]["serverInfo"]["name"] == "nota-a-nota"
    assert revogado.status_code == 204
    assert depois.status_code == 401


def test_valida_chave_nfce(cliente, usuario):
    resposta = cliente.post("/api/nfce/chave", json={"entrada": "1234"}, headers=entrar(usuario))

    assert resposta.status_code == 422


def test_ferramentas_mcp_expostas():
    ferramentas = {f.name: f for f in asyncio.run(mcp.list_tools())}

    assert set(ferramentas) == {
        "gastos_por_categoria",
        "saldos",
        "buscar_transacoes",
        "recategorizar",
        "cofrinho_do_mes",
        "criar_regra",
    }
    assert ferramentas["saldos"].annotations.read_only_hint is True
    assert ferramentas["recategorizar"].input_schema["properties"]["categoria"]["type"] == "string"


def test_anotar_gasto_valida_a_entrada(cliente, usuario):
    resposta = cliente.post(
        "/api/gastos/anotar",
        json={"valor_centavos": 0, "categoria": "x" * 81},
        headers=entrar(usuario),
    )

    assert resposta.status_code == 422
    campos = {erro["loc"][-1] for erro in resposta.json()["detail"]}
    assert campos == {"valor_centavos", "categoria"}
