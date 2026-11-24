from datetime import date

import pytest
from sqlalchemy import select

from nota_a_nota import categorias, cofrinho, perfil, regras
from nota_a_nota.ingestao.extrato import Extrato, TransacaoExtrato
from nota_a_nota.ledger import (
    CATEGORIAS_DESPESA,
    anotar_gasto,
    aplicar_categoria,
    importar_extrato,
)
from nota_a_nota.models import Conta, Lancamento, OrigemCategoria, Transacao


def _categoria_de(session, id_externo: str) -> str:
    nome = session.scalar(
        select(Conta.nome)
        .join(Lancamento, Lancamento.conta_id == Conta.id)
        .join(Transacao, Transacao.id == Lancamento.transacao_id)
        .where(Transacao.id_externo == id_externo, ~Conta.nome.like("Ativo:%"))
    )
    return nome


def test_padrao_vem_primeiro_e_criadas_depois_em_ordem(session):
    categorias.criar(session, "  celular   e internet ", "despesa")
    lista = categorias.criar(session, "Academia", "despesa")

    assert lista.despesa[: len(CATEGORIAS_DESPESA)] == list(CATEGORIAS_DESPESA)
    assert lista.despesa[-2:] == ["Academia", "Celular e internet"]
    assert {"Academia", "Celular e internet"} <= set(lista.criadas)
    assert "A classificar" not in lista.despesa


def test_nome_repetido_ou_invalido_e_recusado(session):
    with pytest.raises(categorias.CategoriaInvalida, match="já existe"):
        categorias.criar(session, "mercado", "despesa")
    with pytest.raises(categorias.CategoriaInvalida, match="já existe"):
        categorias.criar(session, "a classificar", "despesa")
    with pytest.raises(categorias.CategoriaInvalida, match="2 a 40"):
        categorias.criar(session, "x", "despesa")
    with pytest.raises(categorias.CategoriaInvalida, match="dois-pontos"):
        categorias.criar(session, "Casa: reforma", "despesa")


def test_regra_com_categoria_criada_categoriza_o_pix_da_operadora(session):
    categorias.criar(session, "Telefonia", "despesa")
    importar_extrato(
        session,
        Extrato(
            banco="Nubank",
            conta="CAT-1",
            cartao_de_credito=False,
            transacoes=[
                TransacaoExtrato(
                    "P1",
                    date(2029, 1, 5),
                    -5_999,
                    "Transferência enviada pelo Pix - TIM S A",
                    "DEBIT",
                )
            ],
        ),
    )

    regras.salvar(session, "TIM", "Telefonia")
    regras.aplicar(session)

    assert _categoria_de(session, "CAT-1:P1") == "Despesa:Telefonia"


def test_categoria_criada_no_sentido_errado_nao_combina(session):
    existentes = categorias.criar(session, "Freelas", "receita")

    assert regras.combina_com_o_sentido("Freelas", 10_000, existentes)
    assert not regras.combina_com_o_sentido("Freelas", -10_000, existentes)
    assert not regras.combina_com_o_sentido("Categoria que não existe", -10_000, existentes)


def test_receita_criada_vai_para_conta_de_receita(session):
    categorias.criar(session, "Aulas particulares", "receita")
    importar_extrato(
        session,
        Extrato(
            banco="Nubank",
            conta="CAT-2",
            cartao_de_credito=False,
            transacoes=[
                TransacaoExtrato("R1", date(2029, 2, 5), 30_000, "PIX RECEBIDO ALUNO", "CREDIT")
            ],
        ),
    )
    transacao_id = session.scalar(select(Transacao.id).where(Transacao.id_externo == "CAT-2:R1"))

    aplicar_categoria(session, transacao_id, "Aulas particulares", OrigemCategoria.USUARIO)
    session.commit()

    assert _categoria_de(session, "CAT-2:R1") == "Receita:Aulas particulares"


def test_salario_e_o_teto_padrao_e_o_teto_do_mes_e_excecao(session):
    perfil.salvar_renda(session, 500_000, variavel=False)
    maio = date(2029, 5, 1)

    padrao = cofrinho.estado(session, maio, referencia=date(2029, 5, 10))
    cofrinho.definir_teto(session, maio, 300_000)
    excecao = cofrinho.estado(session, maio, referencia=date(2029, 5, 10))
    cofrinho.remover_teto(session, maio)
    de_volta = cofrinho.estado(session, maio, referencia=date(2029, 5, 10))

    assert (padrao.teto_centavos, padrao.teto_origem) == (500_000, "renda")
    assert (excecao.teto_centavos, excecao.teto_origem) == (300_000, "mes")
    assert (de_volta.teto_centavos, de_volta.teto_origem) == (500_000, "renda")


def test_renda_zero_nao_vira_teto(session):
    perfil.salvar_renda(session, 0, variavel=True)

    estado = cofrinho.estado(session, date(2029, 6, 1), referencia=date(2029, 6, 10))

    assert (estado.teto_centavos, estado.teto_origem, estado.humor) == (None, None, "sem_teto")


def test_anotar_gasto_aceita_categoria_criada_e_recusa_desconhecida(session):
    categorias.criar(session, "Presentinhos", "despesa")

    assert anotar_gasto(session, 2_500, "Presentinhos", "chaveiro", date(2029, 3, 1)) > 0
    with pytest.raises(ValueError, match="desconhecida"):
        anotar_gasto(session, 2_500, "Não existe", "x", date(2029, 3, 1))
