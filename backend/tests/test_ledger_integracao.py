import asyncio
from datetime import date

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError

from nota_a_nota import cofrinho, consultas
from nota_a_nota.ingestao.extrato import Extrato, TransacaoExtrato
from nota_a_nota.ledger import anotar_gasto, aplicar_categoria, importar_extrato
from nota_a_nota.mcp_server import mcp
from nota_a_nota.models import Conta, Lancamento, OrigemCategoria, Transacao
from nota_a_nota.rag.busca import indexar


def _extrato(conta: str) -> Extrato:
    return Extrato(
        banco="0260",
        conta=conta,
        cartao_de_credito=False,
        transacoes=[
            TransacaoExtrato("T1", date(2026, 11, 3), -8790, "PAG*PADARIA", "DEBIT"),
            TransacaoExtrato("T2", date(2026, 11, 4), -25000, "ZAFFARI CRISTAL", "DEBIT"),
            TransacaoExtrato("T3", date(2026, 11, 5), 750000, "SALARIO EMPRESA X", "CREDIT"),
        ],
    )


def test_reimportar_o_mesmo_extrato_nao_duplica(session):
    primeira = importar_extrato(session, _extrato("111-1"))
    segunda = importar_extrato(session, _extrato("111-1"))

    assert (primeira.novas, primeira.duplicadas) == (3, 0)
    assert (segunda.novas, segunda.duplicadas) == (0, 3)


def test_categorizar_move_o_gasto_para_a_conta_certa(session):
    importar_extrato(session, _extrato("222-2"), apelido="Conta teste")
    mercado = session.scalar(select(Transacao.id).where(Transacao.id_externo == "222-2:T2"))

    aplicar_categoria(session, mercado, "Mercado", OrigemCategoria.CLAUDE)
    session.commit()

    gastos = {
        g.categoria: g.total_centavos
        for g in consultas.gastos_por_categoria(session, date(2026, 11, 1), date(2026, 11, 30))
    }
    assert gastos["Mercado"] == 25000
    saldo = {s.conta: s.saldo_centavos for s in consultas.saldos(session)}
    assert saldo["Ativo:Conta teste"] == 750000 - 8790 - 25000


def test_pendentes_trazem_o_valor_do_ponto_de_vista_do_extrato(session):
    importar_extrato(session, _extrato("333-3"))

    pendentes = {p.descricao: p.valor_centavos for p in consultas.pendentes_de_categoria(session)}

    assert pendentes["PAG*PADARIA"] == -8790
    assert pendentes["SALARIO EMPRESA X"] == 750000


def test_banco_recusa_transacao_desbalanceada(session):
    importar_extrato(session, _extrato("444-4"))
    transacao_id = session.scalar(select(Transacao.id).where(Transacao.id_externo == "444-4:T1"))
    conta_id = session.scalar(select(Conta.id).where(Conta.nome == "Despesa:Lazer"))
    session.add(Lancamento(transacao_id=transacao_id, conta_id=conta_id, valor_centavos=100))

    with pytest.raises(DBAPIError, match="desbalanceada"):
        session.commit()


def test_ferramenta_mcp_le_do_banco(session):
    importar_extrato(session, _extrato("666-6"), apelido="Conta MCP")
    indexar(session, embedder=None)

    resultado = asyncio.run(mcp.call_tool("buscar_transacoes", {"texto": "zaffari"}))

    achadas = {t["descricao"]: t["valor_centavos"] for t in resultado.structured_content["result"]}
    assert achadas["ZAFFARI CRISTAL"] == -25000


def test_apagar_transacao_leva_os_lancamentos_junto(session):
    importar_extrato(session, _extrato("555-5"))

    session.execute(delete(Transacao).where(Transacao.id_externo.like("555-5:%")))
    session.commit()

    restantes = session.scalars(
        select(Lancamento.id).join(Transacao).where(Transacao.id_externo.like("555-5:%"))
    ).all()
    assert restantes == []


def test_cofrinho_soma_gastos_anotados_e_importados(session):
    fevereiro = date(2027, 2, 1)
    cofrinho.definir_teto(session, fevereiro, 100_000)
    cofrinho.definir_teto(session, fevereiro, 200_000)
    anotar_gasto(session, 4_500, "Restaurantes e delivery", "Pastel da feira", date(2027, 2, 6))
    importar_extrato(
        session,
        Extrato(
            banco="0260",
            conta="777-7",
            cartao_de_credito=False,
            transacoes=[TransacaoExtrato("F1", date(2027, 2, 3), -95_500, "ZAFFARI", "DEBIT")],
        ),
    )

    estado = cofrinho.estado(session, fevereiro, referencia=date(2027, 2, 15))

    assert estado.teto_centavos == 200_000
    assert estado.gasto_centavos == 100_000
    assert estado.pode_gastar_centavos == 100_000
    assert estado.dias_restantes == 14
    assert estado.por_dia_centavos == 100_000 // 14
    assert estado.humor == cofrinho.Humor.TRANQUILA
    assert [(t.descricao, t.valor_centavos) for t in estado.ultimos] == [
        ("Pastel da feira", -4_500),
        ("ZAFFARI", -95_500),
    ]
    saldo = {s.conta: s.saldo_centavos for s in consultas.saldos(session)}
    assert saldo["Ativo:Carteira"] <= -4_500


def test_gasto_anotado_precisa_de_categoria_de_despesa(session):
    with pytest.raises(ValueError, match="categoria"):
        anotar_gasto(session, 1_000, "Salário", "errado", date(2027, 2, 6))
