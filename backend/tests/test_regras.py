from datetime import date

import pytest
from sqlalchemy import select

from nota_a_nota import regras
from nota_a_nota.ingestao.extrato import Extrato, TransacaoExtrato
from nota_a_nota.ledger import importar_extrato
from nota_a_nota.models import Conta, Lancamento, OrigemCategoria, Transacao


def _regra(padrao: str, categoria: str) -> regras.Regra:
    return regras.Regra(id=0, padrao=padrao, categoria=categoria)


def test_normalizar_tira_acento_e_espaco_sobrando():
    assert regras.normalizar("  Farmácia   São João ") == "FARMACIA SAO JOAO"


@pytest.mark.parametrize(
    ("padrao", "descricao", "esperado"),
    [
        ("IFD", "IFD*BURGER DO BAIRRO", True),
        ("FARMACIA", "PAG*FARMACIA SAO JOAO", True),
        ("NETFLIX", "NETFLIXCOM", True),
        ("POSTO", "PAGTO IMPOSTO DE RENDA", False),
        ("ZAFFARI", "Zaffari Cristal", True),
        ("SAO JOAO", "Farmácia São João", True),
    ],
)
def test_regra_casa_com_o_comeco_de_uma_palavra(padrao, descricao, esperado):
    assert regras.casa(padrao, descricao) is esperado


def test_regra_mais_especifica_vence():
    lista = [_regra("UBER", "Transporte"), _regra("UBER EATS", "Restaurantes e delivery")]

    assert regras.escolher(lista, "UBER EATS *PEDIDO").categoria == "Restaurantes e delivery"
    assert regras.escolher(lista, "UBER *TRIP").categoria == "Transporte"
    assert regras.escolher(lista, "PADARIA") is None


def test_categoria_precisa_combinar_com_o_sentido_do_dinheiro():
    assert regras.combina_com_o_sentido("Mercado", -1000)
    assert not regras.combina_com_o_sentido("Mercado", 1000)
    assert regras.combina_com_o_sentido("Reembolsos", 1000)
    assert not regras.combina_com_o_sentido("Salário", -1000)
    assert regras.combina_com_o_sentido("Transferência interna", -1000)


def _categoria(session, id_externo: str) -> tuple[str, OrigemCategoria | None]:
    return session.execute(
        select(Conta.nome, Transacao.categorizada_por)
        .join(Lancamento, Lancamento.conta_id == Conta.id)
        .join(Transacao, Transacao.id == Lancamento.transacao_id)
        .where(Transacao.id_externo == id_externo, ~Conta.nome.like("Ativo:%"))
    ).one()


def test_regras_categorizam_pendentes_sem_chamar_o_modelo(session):
    regras.salvar(session, "  padaria  do zé ", "Restaurantes e delivery")
    regras.salvar(session, "estorno", "Reembolsos")
    importar_extrato(
        session,
        Extrato(
            banco="0260",
            conta="888-8",
            cartao_de_credito=False,
            transacoes=[
                TransacaoExtrato("R1", date(2027, 3, 2), -1_890, "PAG*PADARIA DO ZE", "DEBIT"),
                TransacaoExtrato("R2", date(2027, 3, 3), -5_000, "ESTORNO TARIFA", "DEBIT"),
                TransacaoExtrato("R3", date(2027, 3, 4), -7_700, "LOJA SEM REGRA", "DEBIT"),
            ],
        ),
    )

    aplicadas = regras.aplicar(session)

    assert aplicadas >= 1
    assert _categoria(session, "888-8:R1") == (
        "Despesa:Restaurantes e delivery",
        OrigemCategoria.REGRA,
    )
    assert _categoria(session, "888-8:R2") == ("Despesa:A classificar", None)
    assert _categoria(session, "888-8:R3") == ("Despesa:A classificar", None)


def test_salvar_de_novo_troca_a_categoria_e_apagar_remove(session):
    primeira = regras.salvar(session, "Cafe Bonobo", "Lazer")
    segunda = regras.salvar(session, "CAFÉ BONOBO", "Restaurantes e delivery")

    assert primeira.id == segunda.id
    salvas = {r.padrao: r.categoria for r in regras.listar(session)}
    assert salvas["CAFE BONOBO"] == "Restaurantes e delivery"
    assert regras.apagar(session, segunda.id) is True
    assert regras.apagar(session, segunda.id) is False


def test_regra_rejeita_padrao_curto_e_categoria_inventada(session):
    with pytest.raises(regras.RegraInvalida, match="3 letras"):
        regras.salvar(session, " a ", "Mercado")
    with pytest.raises(regras.RegraInvalida, match="categoria"):
        regras.salvar(session, "LOJA", "Bitcoin")


def test_migracao_traz_regras_iniciais(session):
    iniciais = {r.padrao: r.categoria for r in regras.listar(session)}

    assert iniciais["ZAFFARI"] == "Mercado"
    assert iniciais["UBER EATS"] == "Restaurantes e delivery"
