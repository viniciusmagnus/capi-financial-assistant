from datetime import date

import pytest

from nota_a_nota.ingestao.ofx import OFXInvalido, ler_ofx

EXTRATO_SGML = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
ENCODING:USASCII
CHARSET:1252

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>0260
<ACCTID>12345-6
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20261103120000[-3:BRT]
<TRNAMT>-87,90
<FITID>A1
<MEMO>PAG*Padaria São João
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261105
<TRNAMT>7500.00
<FITID>A2
<NAME>SALARIO   EMPRESA X
</BANKTRANLIST>
</STMTRS></STMTTRNRS></BANKMSGSRSV1>
</OFX>
""".encode("cp1252")

FATURA_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<OFX><CREDITCARDMSGSRSV1><CCSTMTTRNRS><CCSTMTRS>
<CCACCTFROM><ACCTID>5502********1234</ACCTID></CCACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT</TRNTYPE><DTPOSTED>20261110</DTPOSTED><TRNAMT>-1.234,56</TRNAMT><FITID>F1</FITID><MEMO>IFD*RESTAURANTE</MEMO></STMTTRN>
</BANKTRANLIST>
</CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"""


def test_le_extrato_sgml_em_cp1252_com_virgula_decimal():
    extrato = ler_ofx(EXTRATO_SGML)

    assert extrato.banco == "Nubank"
    assert extrato.conta == "12345-6"
    assert not extrato.cartao_de_credito
    assert [t.fitid for t in extrato.transacoes] == ["A1", "A2"]

    padaria, salario = extrato.transacoes
    assert padaria.data == date(2026, 11, 3)
    assert padaria.valor_centavos == -8790
    assert padaria.descricao == "PAG*Padaria São João"
    assert salario.valor_centavos == 750000
    assert salario.descricao == "SALARIO EMPRESA X"


def test_le_fatura_de_cartao_em_xml_com_milhar():
    extrato = ler_ofx(FATURA_XML)

    assert extrato.cartao_de_credito
    assert extrato.transacoes[0].valor_centavos == -123456


def test_rejeita_arquivo_que_nao_e_ofx():
    with pytest.raises(OFXInvalido):
        ler_ofx(b"data,valor\n2026-11-01,10")
