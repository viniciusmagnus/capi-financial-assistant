from datetime import date

import pytest
from conftest import emitir_jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from nota_a_nota.ingestao.csv_extrato import ler_csv, ler_valor
from nota_a_nota.ingestao.extrato import ArquivoInvalido, identificar_banco, ler_arquivo
from nota_a_nota.ingestao.pdf_fatura import ler_texto_de_fatura
from nota_a_nota.ledger import importar_extrato
from nota_a_nota.main import app
from nota_a_nota.models import Conta

FATURA_NUBANK_CSV = b"""date,title,amount
2027-05-03,Ifd*Burger do Bairro,45.90
2027-05-03,Ifd*Burger do Bairro,45.90
2027-05-07,Uber *Trip,23.10
2027-05-12,Pagamento recebido,-1250.00
"""

CONTA_NUBANK_CSV = """Data,Valor,Identificador,Descrição
01/05/2027,-87.90,6a1f-1,Compra no débito - Padaria São João
05/05/2027,5200.00,6a1f-2,Transferência recebida - Empresa X
""".encode()

FATURA_PDF_TEXTO = """
                         Nubank
  FATURA DE MAIO                         Vencimento: 10 JUN 2027
  Total a pagar                                        R$ 115,00
  TRANSAÇÕES DE 28 ABR A 28 MAI
  03 MAI   •••• 1234  Ifd*Burger do Bairro                 R$ 45,90
  03 MAI   •••• 1234  Ifd*Burger do Bairro                 R$ 45,90
  07 MAI   •••• 1234  Uber *Trip                           R$ 23,10
  12 MAI   Pagamento em 12 MAI                       −R$ 1.250,00
  15 MAI   •••• 1234  Steam                     USD 10,00
                                                       R$ 55,00
  29 DEZ   Loja Antiga - Parcela 3/10                  R$ 100,00
"""


def _pdf(linhas: list[str]) -> bytes:
    conteudo = (
        "BT /F1 10 Tf 40 800 Td 14 TL " + " ".join(f"({linha}) Tj T*" for linha in linhas) + " ET"
    )
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(conteudo)} >>\nstream\n{conteudo}\nendstream",
    ]
    saida = b"%PDF-1.4\n"
    posicoes = []
    for numero, corpo in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{numero} 0 obj\n{corpo}\nendobj\n".encode("latin-1")
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    saida += "".join(f"{p:010d} 00000 n \n" for p in posicoes).encode()
    saida += (
        f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    ).encode()
    return saida


def test_valor_em_formatos_brasileiros_e_americanos():
    assert ler_valor("R$ 1.234,56") == 123456
    assert ler_valor("−R$ 1.250,00") == -125000
    assert ler_valor("-45.90") == -4590
    assert ler_valor("1250.00") == 125000
    assert ler_valor("1.234") == 123400
    assert ler_valor("100,00-") == -10000
    assert ler_valor("abc") is None


def test_identifica_banco_por_codigo_nome_ou_arquivo():
    assert identificar_banco("0260") == "Nubank"
    assert identificar_banco(None, "NU_242042319_01OUT2026_31OUT2026.ofx") == "Nubank"
    assert identificar_banco("Fatura Itaucard.pdf") == "Itaú"
    assert identificar_banco("041") == "Banrisul"
    assert identificar_banco("extrato.csv") is None


def test_csv_da_fatura_do_nubank_vira_cartao_com_sinal_do_ledger():
    extrato = ler_arquivo("Nubank_2027-06-10.csv", FATURA_NUBANK_CSV)

    assert extrato.formato == "csv"
    assert extrato.cartao_de_credito
    assert extrato.banco == "Nubank"
    assert [t.valor_centavos for t in extrato.transacoes] == [-4590, -4590, -2310, 125000]
    assert len({t.fitid for t in extrato.transacoes}) == 4
    assert (extrato.inicio, extrato.fim) == (date(2027, 5, 3), date(2027, 5, 12))


def test_csv_da_conta_do_nubank_vira_conta_com_identificador():
    extrato = ler_arquivo("NU_242042319_01MAI2027_31MAI2027.csv", CONTA_NUBANK_CSV)

    assert not extrato.cartao_de_credito
    assert extrato.conta == "242042319"
    assert [t.fitid for t in extrato.transacoes] == ["6a1f-1", "6a1f-2"]
    assert extrato.transacoes[0].valor_centavos == -8790
    assert extrato.transacoes[0].descricao == "Compra no débito - Padaria São João"


def test_csv_generico_com_ponto_e_virgula_e_linhas_de_saldo():
    conteudo = (
        "Extrato da conta\n\nData;Histórico;Valor (R$)\n"
        "02/05/2027;SALDO ANTERIOR;1.000,00\n"
        "03/05/2027;PIX ENVIADO JOAO;-150,00\n"
        "04/05/2027;RENDIMENTO;1,23\n"
    ).encode("cp1252")
    extrato = ler_csv("extrato.csv", conteudo)

    assert [t.descricao for t in extrato.transacoes] == ["PIX ENVIADO JOAO", "RENDIMENTO"]
    assert [t.valor_centavos for t in extrato.transacoes] == [-15000, 123]


def test_csv_sem_colunas_reconhecidas_e_recusado():
    with pytest.raises(ArquivoInvalido, match="colunas"):
        ler_arquivo("planilha.csv", b"nome,idade\nana,30\n")


def test_texto_da_fatura_em_pdf():
    extrato = ler_texto_de_fatura(FATURA_PDF_TEXTO, "Nubank_2027-06-10.pdf")

    assert extrato.cartao_de_credito
    assert extrato.banco == "Nubank"
    resumo = [(t.data, t.valor_centavos, t.descricao) for t in extrato.transacoes]
    assert resumo == [
        (date(2027, 5, 3), -4590, "IFD*BURGER DO BAIRRO"),
        (date(2027, 5, 3), -4590, "IFD*BURGER DO BAIRRO"),
        (date(2027, 5, 7), -2310, "UBER *TRIP"),
        (date(2027, 5, 12), 125000, "PAGAMENTO EM 12 MAI"),
        (date(2027, 5, 15), -5500, "STEAM"),
        (date(2026, 12, 29), -10000, "LOJA ANTIGA - PARCELA 3/10"),
    ]


def test_pdf_de_verdade_passa_pelo_leitor():
    conteudo = _pdf(
        [
            "Nubank   FATURA DE MAIO   Vencimento: 10 JUN 2027",
            "03 MAI   Ifd*Burger do Bairro      R$ 45,90",
            "07 MAI   Uber *Trip                R$ 23,10",
        ]
    )
    extrato = ler_arquivo("fatura.pdf", conteudo)

    assert extrato.formato == "pdf"
    assert [t.valor_centavos for t in extrato.transacoes] == [-4590, -2310]
    assert extrato.transacoes[0].data == date(2027, 5, 3)


def test_pdf_que_nao_e_fatura_e_recusado():
    with pytest.raises(ArquivoInvalido, match="fatura"):
        ler_arquivo("extrato.pdf", _pdf(["Extrato de conta corrente", "03/05 PIX 10,00"]))


def test_binario_desconhecido_e_recusado():
    with pytest.raises(ArquivoInvalido, match="formato"):
        ler_arquivo("foto.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00")


def test_mesma_fatura_em_csv_e_pdf_nao_duplica(session):
    csv = ler_arquivo("Nubank_2027-06-10.csv", FATURA_NUBANK_CSV)
    pdf = ler_texto_de_fatura(FATURA_PDF_TEXTO, "Nubank_2027-06-10.pdf")

    primeira = importar_extrato(session, csv, arquivo="fatura.csv")
    segunda = importar_extrato(session, pdf, arquivo="fatura.pdf")
    terceira = importar_extrato(session, csv, arquivo="fatura.csv")

    assert (primeira.novas, primeira.duplicadas) == (4, 0)
    assert (segunda.novas, segunda.duplicadas) == (2, 4)
    assert (terceira.novas, terceira.duplicadas) == (0, 4)
    assert primeira.conta == segunda.conta == "Passivo:Cartão Nubank"


def test_conta_e_cartao_sao_reconhecidos_sem_apelido(session):
    conta = importar_extrato(
        session, ler_arquivo("NU_999_01MAI2027_31MAI2027.csv", CONTA_NUBANK_CSV)
    )
    de_novo = importar_extrato(
        session, ler_arquivo("NU_999_01MAI2027_31MAI2027.csv", CONTA_NUBANK_CSV)
    )

    assert conta.conta == de_novo.conta
    assert conta.conta.startswith("Ativo:Conta Nubank")
    registro = session.scalar(select(Conta).where(Conta.nome == conta.conta))
    assert (registro.banco, registro.numero) == ("Nubank", "999")
    assert de_novo.duplicadas == 2


def test_rota_aceita_csv_e_recusa_lixo(usuario):
    cliente = TestClient(app, headers={"authorization": f"Bearer {emitir_jwt(usuario)}"})

    csv = cliente.post(
        "/api/importar",
        files={
            "arquivo": ("Nubank_2027-08-10.csv", FATURA_NUBANK_CSV.replace(b"2027-05", b"2027-08"))
        },
    )
    assert csv.status_code == 200
    corpo = csv.json()
    assert (corpo["formato"], corpo["banco"], corpo["cartao_de_credito"]) == ("csv", "Nubank", True)
    assert corpo["novas"] == 4

    lixo = cliente.post("/api/importar", files={"arquivo": ("x.csv", b"a,b\n1,2\n")})
    assert lixo.status_code == 422
