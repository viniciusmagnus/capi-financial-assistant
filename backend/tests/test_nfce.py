import pytest

from nota_a_nota.ingestao.nfce import ChaveInvalida, digito_verificador, ler_chave

SEM_DV = "43" + "2611" + "12345678000195" + "65" + "001" + "000004321" + "1" + "87654321"
CHAVE = SEM_DV + str(digito_verificador(SEM_DV))


def test_le_chave_pura():
    chave = ler_chave(CHAVE)

    assert chave.uf == "RS"
    assert (chave.ano, chave.mes) == (2026, 11)
    assert chave.cnpj_emitente == "12345678000195"
    assert chave.eh_nfce
    assert chave.serie == 1
    assert chave.numero == 4321


def test_le_chave_da_url_do_qr_code():
    url = f"https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx?p={CHAVE}|2|1|1|ABCDEF0123"

    assert ler_chave(url).chave == CHAVE


def test_aceita_chave_com_espacos():
    agrupada = " ".join(CHAVE[i : i + 4] for i in range(0, 44, 4))

    assert ler_chave(agrupada).chave == CHAVE


def test_rejeita_digito_verificador_errado():
    errada = CHAVE[:43] + str((int(CHAVE[43]) + 1) % 10)

    with pytest.raises(ChaveInvalida):
        ler_chave(errada)


def test_rejeita_tamanho_errado():
    with pytest.raises(ChaveInvalida):
        ler_chave(CHAVE[:40])
