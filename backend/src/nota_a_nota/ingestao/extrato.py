import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Literal

Formato = Literal["ofx", "csv", "pdf"]


class ArquivoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class TransacaoExtrato:
    fitid: str
    data: date
    valor_centavos: int
    descricao: str
    tipo: str


@dataclass(frozen=True)
class Extrato:
    banco: str | None
    conta: str | None
    cartao_de_credito: bool
    transacoes: list[TransacaoExtrato]
    inicio: date | None = None
    fim: date | None = None
    formato: Formato = "ofx"


BANCOS: list[tuple[str, tuple[str, ...], str]] = [
    ("Nubank", ("260",), r"NUBANK|NU PAGAMENTOS|^NU_"),
    ("Itaú", ("341",), r"ITAU|ITAUCARD"),
    ("Inter", ("77",), r"BANCO INTER|\bINTER\b"),
    ("Bradesco", ("237",), r"BRADESCO"),
    ("Santander", ("33",), r"SANTANDER"),
    ("C6 Bank", ("336",), r"\bC6\b"),
    ("Banco do Brasil", ("1",), r"BANCO DO BRASIL|OUROCARD"),
    ("Caixa", ("104",), r"CAIXA ECONOMICA|\bCAIXA\b"),
    ("Banrisul", ("41",), r"BANRISUL"),
    ("Sicredi", ("748",), r"SICREDI"),
    ("Sicoob", ("756",), r"SICOOB"),
    ("BTG Pactual", ("208",), r"\bBTG\b"),
    ("XP", ("102", "348"), r"\bXP\b"),
    ("Mercado Pago", ("323",), r"MERCADO ?PAGO"),
    ("PicPay", ("380",), r"PICPAY"),
    ("Neon", ("735",), r"\bNEON\b"),
    ("Original", ("212",), r"BANCO ORIGINAL"),
    ("Pan", ("623",), r"BANCO PAN"),
]


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def nucleo_descricao(descricao: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", sem_acento(descricao).upper())


def identificar_banco(*textos: str | None) -> str | None:
    for texto in textos:
        if not texto:
            continue
        bruto = texto.strip()
        if bruto.isdigit():
            codigo = bruto.lstrip("0") or "0"
            for nome, codigos, _ in BANCOS:
                if codigo in codigos:
                    return nome
            continue
        normalizado = sem_acento(bruto).upper()
        for nome, _, padrao in BANCOS:
            if re.search(padrao, normalizado):
                return nome
    return None


def gerar_fitids(transacoes: list[tuple[date, int, str]]) -> list[str]:
    vistas: Counter[tuple[date, int, str]] = Counter()
    fitids = []
    for data, valor, descricao in transacoes:
        chave = (data, valor, nucleo_descricao(descricao))
        vistas[chave] += 1
        bruto = f"{data.isoformat()}|{valor}|{chave[2]}|{vistas[chave]}"
        fitids.append(hashlib.sha1(bruto.encode()).hexdigest()[:20])
    return fitids


def periodo(transacoes: list[TransacaoExtrato]) -> tuple[date | None, date | None]:
    datas = [t.data for t in transacoes]
    return min(datas, default=None), max(datas, default=None)


def ler_arquivo(nome: str | None, conteudo: bytes) -> Extrato:
    from nota_a_nota.ingestao.csv_extrato import ler_csv
    from nota_a_nota.ingestao.ofx import ler_ofx
    from nota_a_nota.ingestao.pdf_fatura import ler_pdf

    inicio = conteudo[:2048].lstrip(b"\xef\xbb\xbf \r\n\t")
    if inicio.startswith(b"%PDF"):
        return ler_pdf(nome, conteudo)
    if b"<OFX>" in conteudo[:4096].upper() or inicio.upper().startswith(b"OFXHEADER"):
        return ler_ofx(conteudo)
    if b"\x00" in conteudo[:2048]:
        raise ArquivoInvalido("formato não reconhecido: envie OFX, CSV ou o PDF da fatura")
    return ler_csv(nome, conteudo)
