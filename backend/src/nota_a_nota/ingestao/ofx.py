import re
from datetime import date
from decimal import Decimal, InvalidOperation

from nota_a_nota.ingestao.extrato import (
    ArquivoInvalido,
    Extrato,
    TransacaoExtrato,
    identificar_banco,
)


class OFXInvalido(ArquivoInvalido):
    pass


_BLOCO_TRANSACAO = re.compile(
    r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", re.S
)


def _decodificar(conteudo: bytes) -> str:
    cabecalho = conteudo[:400].decode("ascii", errors="ignore").upper()
    if "ENCODING:UTF-8" in cabecalho or 'ENCODING="UTF-8"' in cabecalho:
        try:
            return conteudo.decode("utf-8")
        except UnicodeDecodeError:
            pass
    try:
        return conteudo.decode("utf-8")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252")


def _campo(bloco: str, nome: str) -> str | None:
    achado = re.search(rf"<{nome}>([^<\r\n]*)", bloco)
    if not achado:
        return None
    valor = achado.group(1).strip()
    return valor or None


def _data(bruta: str) -> date:
    digitos = bruta[:8]
    if not digitos.isdigit():
        raise OFXInvalido(f"data inválida: {bruta!r}")
    return date(int(digitos[:4]), int(digitos[4:6]), int(digitos[6:8]))


def _centavos(bruto: str) -> int:
    normalizado = bruto.replace(" ", "")
    if "," in normalizado and "." in normalizado:
        normalizado = normalizado.replace(".", "").replace(",", ".")
    else:
        normalizado = normalizado.replace(",", ".")
    try:
        return int((Decimal(normalizado) * 100).quantize(Decimal("1")))
    except InvalidOperation as erro:
        raise OFXInvalido(f"valor inválido: {bruto!r}") from erro


def ler_ofx(conteudo: bytes) -> Extrato:
    texto = _decodificar(conteudo)
    if "<OFX>" not in texto.upper():
        raise OFXInvalido("arquivo não parece ser OFX")

    cartao = "<CCSTMTRS>" in texto
    conta = _campo(texto, "ACCTID")
    if not conta:
        raise OFXInvalido("ACCTID ausente")

    transacoes = []
    for bloco in _BLOCO_TRANSACAO.findall(texto):
        fitid = _campo(bloco, "FITID")
        data_bruta = _campo(bloco, "DTPOSTED")
        valor_bruto = _campo(bloco, "TRNAMT")
        if not (fitid and data_bruta and valor_bruto):
            raise OFXInvalido(f"transação incompleta: {bloco.strip()[:120]!r}")
        descricao = _campo(bloco, "MEMO") or _campo(bloco, "NAME") or ""
        transacoes.append(
            TransacaoExtrato(
                fitid=fitid,
                data=_data(data_bruta),
                valor_centavos=_centavos(valor_bruto),
                descricao=re.sub(r"\s+", " ", descricao),
                tipo=_campo(bloco, "TRNTYPE") or "OTHER",
            )
        )

    datas = [t.data for t in transacoes]
    inicio_bruto = _campo(texto, "DTSTART")
    fim_bruto = _campo(texto, "DTEND")
    inicio = _data(inicio_bruto) if inicio_bruto else min(datas, default=None)
    fim = _data(fim_bruto) if fim_bruto else max(datas, default=None)
    if datas:
        inicio = min(inicio, *datas) if inicio else min(datas)
        fim = max(fim, *datas) if fim else max(datas)
    if inicio and fim and inicio > fim:
        raise OFXInvalido("período do extrato invertido (DTSTART depois de DTEND)")

    return Extrato(
        banco=identificar_banco(
            _campo(texto, "BANKID"), _campo(texto, "ORG"), _campo(texto, "FID")
        ),
        conta=conta,
        cartao_de_credito=cartao,
        transacoes=transacoes,
        inicio=inicio,
        fim=fim,
        formato="ofx",
    )
