import io
import re
from datetime import date

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from nota_a_nota.cofrinho import hoje
from nota_a_nota.ingestao.csv_extrato import ler_valor
from nota_a_nota.ingestao.extrato import (
    ArquivoInvalido,
    Extrato,
    TransacaoExtrato,
    gerar_fitids,
    identificar_banco,
    nucleo_descricao,
    periodo,
    sem_acento,
)

MESES = {
    "JAN": 1,
    "FEV": 2,
    "MAR": 3,
    "ABR": 4,
    "MAI": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SET": 9,
    "OUT": 10,
    "NOV": 11,
    "DEZ": 12,
}
_MES = r"(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[A-Z]*\.?"
_INICIO_COM_DATA = re.compile(
    rf"^\s*(?:(\d{{1,2}})\s*(?:DE\s+)?{_MES}(?:\s+(?:DE\s+)?(\d{{4}}))?|(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{2,4}}))?)\s+(.*)$"
)
_VALOR_NO_FIM = re.compile(
    r"(?<!USD)(?<!US\$)(?<!EUR)\s((?:[-−]\s*)?(?:R\$\s*)?(?:[-−]\s*)?\d{1,3}(?:\.\d{3})*,\d{2}(?:\s*-)?)\s*$"
)
_DATAS_COM_ANO = re.compile(
    rf"\b(\d{{1,2}})\s*(?:DE\s+)?{_MES}\s+(?:DE\s+)?(\d{{4}})\b|\b(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})\b"
)
_RUIDO = re.compile(r"(?:[•*·]{2,}\s*\d{4})|\b(?:USD|US\$|EUR)\s*[\d.,]+")
_NAO_E_COMPRA = re.compile(r"^(TOTAL|SALDO|PAGAMENTOMINIMO|VENCIMENTO|LIMITE|FATURAANTERIOR)")


def _texto(conteudo: bytes) -> str:
    try:
        leitor = PdfReader(io.BytesIO(conteudo))
        if leitor.is_encrypted and not leitor.decrypt(""):
            raise ArquivoInvalido("o PDF está protegido por senha; exporte a fatura em CSV ou OFX")
        paginas = [p.extract_text(extraction_mode="layout") or "" for p in leitor.pages]
    except PdfReadError as erro:
        raise ArquivoInvalido("não consegui abrir esse PDF") from erro
    return "\n".join(paginas)


def _data_com_ano(achado: re.Match[str]) -> date | None:
    try:
        if achado.group(1):
            return date(int(achado.group(3)), MESES[achado.group(2)], int(achado.group(1)))
        return date(int(achado.group(6)), int(achado.group(5)), int(achado.group(4)))
    except ValueError:
        return None


def _referencia(texto: str) -> date:
    datas = [d for a in _DATAS_COM_ANO.finditer(texto) if (d := _data_com_ano(a))]
    plausiveis = [d for d in datas if d.year >= 2000 and d <= date(hoje().year + 1, 12, 31)]
    return max(plausiveis, default=hoje())


def _data_da_linha(achado: re.Match[str], referencia: date) -> date | None:
    if achado.group(1):
        dia, mes, ano = int(achado.group(1)), MESES[achado.group(2)], achado.group(3)
    else:
        dia, mes, ano = int(achado.group(4)), int(achado.group(5)), achado.group(6)
    if ano:
        ano_numero = int(ano) if len(ano) == 4 else 2000 + int(ano)
    else:
        ano_numero = (
            referencia.year
            if (mes, dia) <= (referencia.month, referencia.day)
            else referencia.year - 1
        )
    try:
        return date(ano_numero, mes, dia)
    except ValueError:
        return None


def ler_texto_de_fatura(texto: str, nome: str | None = None) -> Extrato:
    normalizado = sem_acento(texto).upper()
    if "FATURA" not in normalizado:
        raise ArquivoInvalido(
            "esse PDF não parece uma fatura de cartão; para a conta, exporte o extrato em OFX ou CSV"
        )
    referencia = _referencia(normalizado)
    linhas = normalizado.splitlines()

    brutas: list[tuple[date, int, str]] = []
    i = 0
    while i < len(linhas):
        achado = _INICIO_COM_DATA.match(linhas[i])
        if not achado:
            i += 1
            continue
        data = _data_da_linha(achado, referencia)
        corpo = achado.group(7)
        valor_achado = _VALOR_NO_FIM.search(" " + corpo)
        consumidas = 1
        while valor_achado is None and consumidas <= 2 and i + consumidas < len(linhas):
            seguinte = linhas[i + consumidas]
            if _INICIO_COM_DATA.match(seguinte):
                break
            corpo = f"{corpo} {seguinte.strip()}"
            valor_achado = _VALOR_NO_FIM.search(" " + corpo)
            consumidas += 1
        i += consumidas if valor_achado else 1
        if data is None or valor_achado is None:
            continue
        valor = ler_valor(valor_achado.group(1))
        descricao = _RUIDO.sub(" ", (" " + corpo)[: valor_achado.start()])
        descricao = re.sub(r"\s+", " ", descricao).strip(" -")
        if not valor or not descricao or _NAO_E_COMPRA.match(nucleo_descricao(descricao)):
            continue
        brutas.append((data, -valor, descricao))

    if not brutas:
        raise ArquivoInvalido(
            "não encontrei transações nesse PDF; se for uma imagem escaneada, exporte a fatura em CSV ou OFX"
        )
    fitids = gerar_fitids(brutas)
    transacoes = [
        TransacaoExtrato(
            fitid=fitid,
            data=data,
            valor_centavos=valor,
            descricao=descricao,
            tipo="DEBIT" if valor < 0 else "CREDIT",
        )
        for (data, valor, descricao), fitid in zip(brutas, fitids, strict=True)
    ]
    inicio, fim = periodo(transacoes)
    return Extrato(
        banco=identificar_banco(nome, normalizado[:1500]),
        conta=None,
        cartao_de_credito=True,
        transacoes=transacoes,
        inicio=inicio,
        fim=fim,
        formato="pdf",
    )


def ler_pdf(nome: str | None, conteudo: bytes) -> Extrato:
    return ler_texto_de_fatura(_texto(conteudo), nome)
