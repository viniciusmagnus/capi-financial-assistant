import json
from datetime import date

import httpx
import pytest
from sqlalchemy import select

from nota_a_nota.ingestao.extrato import Extrato, TransacaoExtrato
from nota_a_nota.ledger import aplicar_categoria, importar_extrato
from nota_a_nota.models import DIMENSOES_EMBEDDING, OrigemCategoria, Transacao, Trecho
from nota_a_nota.rag.busca import (
    FONTE,
    buscar,
    exemplos_parecidos,
    fundir,
    indexar,
    texto_da_transacao,
)
from nota_a_nota.rag.embeddings import FalhaNoEmbedding, Voyage, embed_ou_nada

TEMAS = {
    "SMARTFIT": 0,
    "ACADEMIA": 0,
    "ZAFFARI": 1,
    "MERCADO": 1,
    "CINEMA": 2,
    "LAZER": 2,
}


class EmbedderFalso:
    def __init__(self) -> None:
        self.chamadas: list[tuple[list[str], str]] = []

    def embed(self, textos, uso):
        self.chamadas.append((textos, uso))
        vetores = []
        for texto in textos:
            vetor = [0.0] * DIMENSOES_EMBEDDING
            vetor[-1] = 0.05
            for palavra, dimensao in TEMAS.items():
                if palavra in texto.upper():
                    vetor[dimensao] = 1.0
            vetores.append(vetor)
        return vetores


def test_rrf_premia_quem_aparece_nas_duas_listas():
    pontos = fundir([10, 20, 30], [30, 40])

    assert max(pontos, key=pontos.get) == 30
    assert pontos[10] == pytest.approx(1 / 61)
    assert set(pontos) == {10, 20, 30, 40}


def test_texto_do_trecho_so_leva_categoria_quando_ja_existe():
    assert texto_da_transacao("ZAFFARI", "Despesa:A classificar") == "ZAFFARI"
    assert texto_da_transacao("ZAFFARI", "Despesa:Mercado") == "ZAFFARI · Mercado"


def test_voyage_manda_o_tipo_de_uso_e_reordena_pelo_indice():
    enviados = []

    def responder(request: httpx.Request) -> httpx.Response:
        enviados.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]},
        )

    voyage = Voyage(
        "chave", "voyage-4-lite", httpx.Client(transport=httpx.MockTransport(responder))
    )

    assert voyage.embed(["a", "b"], "query") == [[1.0], [2.0]]
    assert enviados[0]["input_type"] == "query"
    assert enviados[0]["output_dimension"] == DIMENSOES_EMBEDDING


def test_falha_da_voyage_vira_busca_so_por_palavra():
    class Quebrado:
        def embed(self, textos, uso):
            raise FalhaNoEmbedding("503")

    assert embed_ou_nada(Quebrado(), ["x"], "query") is None
    assert embed_ou_nada(None, ["x"], "query") is None


def _importar(session, conta: str, itens: list[tuple[str, str, int]]):
    importar_extrato(
        session,
        Extrato(
            banco="0260",
            conta=conta,
            cartao_de_credito=False,
            transacoes=[
                TransacaoExtrato(fitid, date(2027, 4, 10), valor, descricao, "DEBIT")
                for fitid, descricao, valor in itens
            ],
        ),
    )


def _id(session, id_externo: str) -> int:
    return session.scalar(select(Transacao.id).where(Transacao.id_externo == id_externo))


def test_busca_hibrida_acha_por_significado_o_que_a_palavra_nao_acha(session):
    _importar(
        session,
        "RAG-1",
        [
            ("A1", "MP*SMARTFIT", -12_990),
            ("A2", "ZAFFARI IPIRANGA", -20_000),
            ("A3", "CINEMA X", -4_000),
        ],
    )
    embedder = EmbedderFalso()
    indexar(session, embedder)

    abril = {"inicio": date(2027, 4, 1), "fim": date(2027, 4, 30)}
    academia = buscar(session, "academia", embedder, **abril)
    zaffari = buscar(session, "zaffari", embedder, **abril)
    sem_vetor = buscar(session, "academia", None, **abril)

    assert academia[0].descricao == "MP*SMARTFIT"
    assert academia[0].encontrada_por == ["significado"]
    assert [t.descricao for t in academia] == ["MP*SMARTFIT"]
    assert zaffari[0].descricao == "ZAFFARI IPIRANGA"
    assert zaffari[0].encontrada_por == ["significado", "palavra"]
    assert sem_vetor == []


def test_recategorizar_refaz_o_trecho_com_a_categoria_nova(session):
    _importar(session, "RAG-2", [("B1", "PADARIA BOM PAO", -1_500)])
    indexar(session, EmbedderFalso())
    transacao_id = _id(session, "RAG-2:B1")

    aplicar_categoria(session, transacao_id, "Restaurantes e delivery", OrigemCategoria.USUARIO)
    session.commit()
    resultado = indexar(session, EmbedderFalso())

    trecho = session.scalar(
        select(Trecho).where(Trecho.fonte_tipo == FONTE, Trecho.fonte_id == transacao_id)
    )
    assert resultado.novos == 1
    assert trecho.texto == "PADARIA BOM PAO · Restaurantes e delivery"
    assert trecho.embedding is not None


def test_exemplos_parecidos_vem_do_historico_ja_categorizado(session):
    _importar(
        session, "RAG-3", [("C1", "ZAFFARI CRISTAL", -9_000), ("C2", "ZAFFARI BOURBON", -7_000)]
    )
    cristal = _id(session, "RAG-3:C1")
    bourbon = _id(session, "RAG-3:C2")
    aplicar_categoria(session, cristal, "Mercado", OrigemCategoria.USUARIO)
    session.commit()
    indexar(session, EmbedderFalso())

    exemplos = exemplos_parecidos(session, [bourbon])

    assert [(e.descricao, e.categoria) for e in exemplos[bourbon]][0] == (
        "ZAFFARI CRISTAL",
        "Mercado",
    )
    assert all(e.categoria != "A classificar" for e in exemplos[bourbon])
