import io
from datetime import date
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi import HTTPException, UploadFile

from nota_a_nota import diagnostico, main, perfil
from nota_a_nota.config import get_settings
from nota_a_nota.estabelecimentos import identificar, nucleo
from nota_a_nota.ingestao.ofx import OFXInvalido, ler_ofx
from nota_a_nota.llm import capi_diagnostico


def ofx(
    conta: str, itens: list[tuple[str, str, str, str]], inicio: str | None, fim: str | None
) -> bytes:
    periodo = (f"<DTSTART>{inicio}\n" if inicio else "") + (f"<DTEND>{fim}\n" if fim else "")
    transacoes = "".join(
        f"<STMTTRN><TRNTYPE>{'CREDIT' if valor[0] != '-' else 'DEBIT'}<DTPOSTED>{data}"
        f"<TRNAMT>{valor}<FITID>{fitid}<MEMO>{memo}</STMTTRN>\n"
        for fitid, data, valor, memo in itens
    )
    return (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nENCODING:USASCII\nCHARSET:1252\n\n"
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL\n"
        f"<BANKACCTFROM><BANKID>0260<ACCTID>{conta}</BANKACCTFROM>\n"
        f"<BANKTRANLIST>{periodo}{transacoes}</BANKTRANLIST>"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    ).encode("cp1252")


def importar(session, conteudo: bytes, apelido: str, nome="extrato.ofx"):
    return main.importar_arquivo(session, UploadFile(io.BytesIO(conteudo), filename=nome), apelido)


@pytest.fixture
def sem_ia(monkeypatch):
    monkeypatch.setattr(
        capi_diagnostico, "get_settings", lambda: SimpleNamespace(anthropic_api_key="")
    )


def test_marcas_agrupam_variacoes_e_texto_incerto_fica_sem_marca():
    assert (
        identificar("IFD*BURGER DO BAIRRO").chave
        == identificar("IFOOD *PIZZARIA").chave
        == "marca:ifood"
    )
    assert identificar("Zaffari Bourbon 1234").marca == "zaffari"
    assert identificar("RESTAURANTE VIVO SABOR").marca is None
    assert identificar("APPLE STORE DO ZE").marca is None
    assert (
        nucleo("COMPRA CARTAO DEB LANCHERIA DA ANA PARCELA 2/3 PORTO ALEGRE RS")
        == "LANCHERIA DA ANA PORTO ALEGRE"
    )


def test_formatos_em_reais_e_porcento():
    assert diagnostico.reais(123456) == "R$ 1.234,56"
    assert diagnostico.reais(-5) == "-R$ 0,05"
    assert diagnostico.porcento(0.25) == "25%"
    assert diagnostico.porcento(0.1875) == "18,8%"


def test_periodo_do_ofx_vem_do_dtstart_dtend_ou_das_transacoes():
    com_periodo = ler_ofx(ofx("1", [("A", "20280105", "-1,00", "X")], "20280101", "20280131"))
    sem_periodo = ler_ofx(
        ofx("1", [("A", "20280105", "-1,00", "X"), ("B", "20280109", "-1,00", "Y")], None, None)
    )

    assert (com_periodo.inicio, com_periodo.fim) == (date(2028, 1, 1), date(2028, 1, 31))
    assert (sem_periodo.inicio, sem_periodo.fim) == (date(2028, 1, 5), date(2028, 1, 9))
    with pytest.raises(OFXInvalido, match="invertido"):
        ler_ofx(ofx("1", [], "20280131", "20280101"))


def test_importacao_valida_registra_periodo_e_reimportar_nao_duplica(session):
    conteudo = ofx(
        "DIAG-1",
        [
            ("I1", "20280103", "-50,00", "PADARIA ESQUINA"),
            ("I2", "20280104", "-20,00", "ZAFFARI CENTRO"),
        ],
        "20280101",
        "20280131",
    )

    primeira = importar(session, conteudo, "Conta Diag 1")
    segunda = importar(session, conteudo, "Conta Diag 1")

    assert (primeira.novas, primeira.duplicadas, primeira.no_arquivo) == (2, 0, 2)
    assert (primeira.inicio, primeira.fim) == (date(2028, 1, 1), date(2028, 1, 31))
    assert primeira.categorizadas_por_regra >= 1
    assert primeira.para_revisar == 1
    assert (segunda.novas, segunda.duplicadas) == (0, 2)
    assert segunda.importacao_id != primeira.importacao_id


def test_arquivo_invalido_vira_422(session):
    with pytest.raises(HTTPException) as erro:
        importar(session, b"isto nao e um extrato", "Qualquer")

    assert erro.value.status_code == 422


def test_ia_indisponivel_mantem_a_importacao_e_sinaliza_pendencias(session, monkeypatch):
    resultado = importar(
        session,
        ofx("DIAG-2", [("P1", "20280205", "-33,00", "LOJA DESCONHECIDA XYZ")], None, None),
        "Conta Diag 2",
    )

    sem_chave = main.categorizar_pendentes(session, importacao_id=[resultado.importacao_id])

    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    get_settings.cache_clear()
    falha = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    monkeypatch.setattr(main, "categorizar", lambda *a, **k: (_ for _ in ()).throw(falha))
    com_falha = main.categorizar_pendentes(session, importacao_id=[resultado.importacao_id])
    get_settings.cache_clear()

    assert (sem_chave.ia_disponivel, sem_chave.para_revisar_na_importacao) == (False, 1)
    assert "chave" in sem_chave.motivo
    assert com_falha.ia_disponivel is False
    assert "APIConnectionError" in com_falha.motivo
    assert com_falha.para_revisar_na_importacao == 1


def test_renda_zero_nao_divide_por_zero(session, sem_ia):
    perfil.salvar_renda(session, 0, variavel=False)
    importar(
        session,
        ofx("DIAG-3", [("Z1", "20280310", "-100,00", "LIVRARIA CULTURA")], "20280301", "20280331"),
        "Conta Diag 3",
    )

    d = diagnostico.montar(session, date(2028, 3, 1), referencia=date(2028, 4, 15))

    assert d.base == "mes_completo"
    assert d.comprometimento is None
    assert d.diferenca_centavos == -d.totais.gastos_centavos
    assert all(linha.pct_renda is None for linha in d.categorias)
    assert "renda_zero" in {a.tipo for a in d.avisos}


def test_mes_completo_separa_entradas_transferencias_e_estornos(session, sem_ia):
    perfil.salvar_renda(session, 400_000, variavel=True)
    importar(
        session,
        ofx(
            "DIAG-4",
            [
                ("S1", "20280405", "5.000,00", "SALARIO EMPRESA X"),
                ("S2", "20280406", "-1.200,00", "PAGTO FATURA CARTAO"),
                ("S3", "20280407", "-300,00", "ZAFFARI CRISTAL"),
                ("S4", "20280408", "40,00", "ESTORNO COMPRA ZAFFARI"),
                ("S5", "20280409", "-100,00", "LOJA SEM REGRA ABC"),
            ],
            "20280401",
            "20280430",
        ),
        "Conta Diag 4",
    )

    d = diagnostico.montar(session, date(2028, 4, 1), referencia=date(2028, 5, 10))

    assert d.periodo.parcial is False
    assert d.totais.gastos_centavos == 40_000
    assert d.totais.sem_categoria_centavos == 10_000
    assert d.totais.transferencias_saida_centavos == 120_000
    assert [e.categoria for e in d.totais.entradas] == ["Salário"]
    assert d.renda_referencia_centavos == 400_000
    assert d.comprometimento == pytest.approx(0.1)
    assert d.diferenca_centavos == 360_000
    assert [c.nome for c in d.categorias] == ["Mercado", "A classificar"]
    assert d.categorias[0].pct_renda == pytest.approx(0.075)
    assert {"fatura_sem_cartao", "transferencias", "sem_categoria"} <= {a.tipo for a in d.avisos}


def test_periodo_parcial_compara_com_a_renda_cheia_e_projeta(session, sem_ia):
    perfil.salvar_renda(session, 290_000, variavel=False)
    importar(
        session,
        ofx("DIAG-5", [("Q1", "20280612", "-290,00", "ZAFFARI CENTRO")], "20280610", "20280619"),
        "Conta Diag 5",
    )

    d = diagnostico.montar(session, date(2028, 6, 1), referencia=date(2028, 7, 1))

    assert d.periodo.parcial and d.periodo.dias_cobertos == 10
    assert d.base == "projecao"
    assert d.renda_referencia_centavos == 290_000
    assert d.comprometimento == pytest.approx(0.1)
    assert d.diferenca_centavos == 261_000
    assert d.projecao.gastos_centavos == 87_000
    assert d.projecao.comprometimento == pytest.approx(0.3)
    assert "periodo_parcial" in {a.tipo for a in d.avisos}


def test_periodo_curto_nao_projeta(session, sem_ia):
    importar(
        session,
        ofx("DIAG-6", [("C1", "20280702", "-50,00", "ZAFFARI CENTRO")], "20280701", "20280703"),
        "Conta Diag 6",
    )

    d = diagnostico.montar(session, date(2028, 7, 1), referencia=date(2028, 8, 1))

    assert d.base == "periodo"
    assert d.projecao is None


def test_recomendacoes_nao_somam_economia_do_mesmo_gasto(session, sem_ia):
    perfil.salvar_renda(session, 300_000, variavel=False)
    pedidos = [(f"F{i}", f"202808{i + 1:02d}", "-60,00", f"IFD*RESTAURANTE {i}") for i in range(6)]
    importar(session, ofx("DIAG-7", pedidos, "20280801", "20280831"), "Conta Diag 7")

    d = diagnostico.montar(session, date(2028, 8, 1), referencia=date(2028, 9, 2))

    tipos = [r.tipo for r in d.recomendacoes]
    assert "app_delivery" in tipos
    app = next(r for r in d.recomendacoes if r.tipo == "app_delivery")
    assert app.economia_centavos == 18_000
    assert "3 desses pedidos" in app.acao
    assert d.economia_combinada_centavos <= sum(r.economia_centavos for r in d.recomendacoes)
    assert d.economia_combinada_centavos == 18_000
    assert len(d.recomendacoes) <= 3
    assert all(r.capi for r in diagnostico_com_capi(d))


def diagnostico_com_capi(d):
    for r, fala in zip(
        d.recomendacoes, capi_diagnostico.comentar(d.recomendacoes, "pessoa"), strict=True
    ):
        r.capi = fala
    return d.recomendacoes


def test_corrigir_categoria_valida_o_sentido_e_cria_regra(session):
    importar(
        session,
        ofx(
            "DIAG-8",
            [
                ("K1", "20280902", "-80,00", "PAG*ACADEMIA FORCA TOTAL"),
                ("K2", "20280903", "-80,00", "PAG*ACADEMIA FORCA TOTAL"),
            ],
            None,
            None,
        ),
        "Conta Diag 8",
    )
    d = diagnostico.montar(session, date(2028, 9, 1), referencia=date(2028, 10, 1))
    primeira = d.transacoes[0].id

    with pytest.raises(HTTPException) as erro:
        main.corrigir_categoria(session, primeira, main.EntradaCorrecao(categoria="Salário"))
    resultado = main.corrigir_categoria(
        session, primeira, main.EntradaCorrecao(categoria="Saúde", criar_regra=True)
    )

    depois = diagnostico.montar(session, date(2028, 9, 1), referencia=date(2028, 10, 1))
    assert erro.value.status_code == 422
    assert resultado.regra.padrao == "ACADEMIA FORCA TOTAL"
    assert resultado.outras_categorizadas == 1
    assert {t.categoria for t in depois.transacoes} == {"Saúde"}


@pytest.mark.parametrize(
    "fala",
    [
        "São 8 pedidos!",
        "O motoboy passa mais que o Guaíba na janela.",
        "Delivery que nem enchente.",
    ],
)
def test_fala_da_capi_fora_do_tom_cai_no_roteiro(fala):
    rec = diagnostico.Recomendacao(
        id="app_delivery:marca:ifood",
        tipo="app_delivery",
        alvo_tipo="estabelecimento",
        alvo_chave="marca:ifood",
        alvo_nome="iFood",
        titulo="t",
        fato="f",
        consequencia="c",
        acao="a",
        reducao=0.5,
        economia_centavos=1000,
        base="mes_completo",
        calculo="x",
    )
    cliente = SimpleNamespace(
        messages=SimpleNamespace(
            parse=lambda **_: SimpleNamespace(
                stop_reason="end_turn",
                parsed_output=capi_diagnostico.Falas(falas=[fala]),
            )
        )
    )
    capi_diagnostico._memoria.clear()

    assert capi_diagnostico.comentar([rec], "pessoa", client=cliente) == [
        capi_diagnostico.ROTEIRO["app_delivery"]
    ]


def test_roteiro_das_sugestoes_passa_no_filtro_de_tom():
    falas = [*capi_diagnostico.ROTEIRO.values(), capi_diagnostico.PADRAO]

    assert [f for f in falas if not capi_diagnostico._aceitavel(f)] == []
