import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

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

COLUNAS_DATA = {"data", "date", "dt", "data lancamento", "data da compra", "data de compra"}
COLUNAS_DESCRICAO = {
    "descricao",
    "title",
    "titulo",
    "historico",
    "estabelecimento",
    "lancamento",
    "descricao/estabelecimento",
    "memo",
    "detalhe",
    "detalhes",
}
COLUNAS_VALOR = {"valor", "amount", "quantia", "valor (r$)", "valor r$", "valor em r$"}
COLUNAS_ID = {"identificador", "id"}
PISTAS_DE_CARTAO = re.compile(r"FATURA|CART(A|Ã)O|CARD|CREDIT|CREDITO", re.I)


def _texto(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("cp1252")


def _cabecalho(nome: str) -> str:
    return re.sub(r"\s+", " ", sem_acento(nome).strip().lower())


def _achar_coluna(cabecalho: list[str], nomes: set[str], prefixo: str | None = None) -> int | None:
    for i, coluna in enumerate(cabecalho):
        if coluna in nomes:
            return i
    if prefixo:
        for i, coluna in enumerate(cabecalho):
            if coluna.startswith(prefixo):
                return i
    return None


def ler_data(bruta: str) -> date | None:
    limpa = bruta.strip()
    if achado := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?", limpa):
        ano, mes, dia = achado.groups()
    elif achado := re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})", limpa):
        dia, mes, ano = achado.groups()
        if len(ano) == 2:
            ano = f"20{ano}"
    else:
        return None
    try:
        return date(int(ano), int(mes), int(dia))
    except ValueError:
        return None


def ler_valor(bruto: str) -> int | None:
    limpo = bruto.strip().replace("−", "-").replace(" ", " ")
    negativo = limpo.startswith("-") or limpo.endswith("-") or "-R$" in limpo.replace(" ", "")
    numero = re.sub(r"[^\d,.]", "", limpo)
    if not re.search(r"\d", numero):
        return None
    if "," in numero and "." in numero:
        decimal = "," if numero.rfind(",") > numero.rfind(".") else "."
        milhar = "." if decimal == "," else ","
        numero = numero.replace(milhar, "").replace(decimal, ".")
    elif "," in numero:
        numero = numero.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", numero):
        numero = numero.replace(".", "")
    try:
        centavos = int((Decimal(numero) * 100).quantize(Decimal("1")))
    except InvalidOperation:
        return None
    return -centavos if negativo else centavos


def _delimitador(amostra: str) -> str:
    try:
        return csv.Sniffer().sniff(amostra, delimiters=",;\t").delimiter
    except csv.Error:
        contagem = {d: amostra.count(d) for d in (";", ",", "\t")}
        return max(contagem, key=contagem.get)


def _localizar_cabecalho(linhas: list[list[str]]) -> tuple[int, list[str], int, int, int]:
    for posicao, linha in enumerate(linhas[:20]):
        cabecalho = [_cabecalho(c) for c in linha]
        i_data = _achar_coluna(cabecalho, COLUNAS_DATA, "data")
        i_desc = _achar_coluna(cabecalho, COLUNAS_DESCRICAO, "descri")
        i_valor = _achar_coluna(cabecalho, COLUNAS_VALOR, "valor")
        if i_data is not None and i_desc is not None and i_valor is not None:
            return posicao, cabecalho, i_data, i_desc, i_valor
    raise ArquivoInvalido("não encontrei colunas de data, descrição e valor nesse CSV")


def ler_csv(nome: str | None, conteudo: bytes) -> Extrato:
    texto = _texto(conteudo)
    linhas = list(csv.reader(io.StringIO(texto), delimiter=_delimitador(texto[:4096])))
    posicao, cabecalho, i_data, i_desc, i_valor = _localizar_cabecalho(linhas)
    i_id = _achar_coluna(cabecalho, COLUNAS_ID)
    formato_nubank_cartao = "title" in cabecalho and "amount" in cabecalho

    brutas: list[tuple[date, int, str, str | None]] = []
    for linha in linhas[posicao + 1 :]:
        if len(linha) <= max(i_data, i_desc, i_valor) or not any(c.strip() for c in linha):
            continue
        data = ler_data(linha[i_data])
        valor = ler_valor(linha[i_valor])
        descricao = re.sub(r"\s+", " ", linha[i_desc]).strip()
        if data is None or not valor or nucleo_descricao(descricao).startswith("SALDO"):
            continue
        identificador = linha[i_id].strip() if i_id is not None and i_id < len(linha) else None
        brutas.append((data, valor, descricao, identificador or None))
    if not brutas:
        raise ArquivoInvalido("o CSV não tem nenhuma transação com data e valor válidos")

    nome_arquivo = nome or ""
    cartao = formato_nubank_cartao or (
        i_id is None and bool(PISTAS_DE_CARTAO.search(sem_acento(nome_arquivo)))
    )
    if cartao and sum(1 for b in brutas if b[1] > 0) > len(brutas) / 2:
        brutas = [(d, -v, desc, i) for d, v, desc, i in brutas]

    gerados = gerar_fitids([(d, v, desc) for d, v, desc, _ in brutas])
    transacoes = [
        TransacaoExtrato(
            fitid=identificador or gerado,
            data=data,
            valor_centavos=valor,
            descricao=descricao,
            tipo="DEBIT" if valor < 0 else "CREDIT",
        )
        for (data, valor, descricao, identificador), gerado in zip(brutas, gerados, strict=True)
    ]
    banco = identificar_banco(nome_arquivo) or ("Nubank" if formato_nubank_cartao else None)
    numero = re.match(r"NU_(\d+)", nome_arquivo, re.I)
    inicio, fim = periodo(transacoes)
    return Extrato(
        banco=banco,
        conta=numero.group(1) if numero else None,
        cartao_de_credito=cartao,
        transacoes=transacoes,
        inicio=inicio,
        fim=fim,
        formato="csv",
    )
