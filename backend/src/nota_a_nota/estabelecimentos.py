import re
import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class Marca:
    slug: str
    nome: str
    padroes: tuple[str, ...]
    regra: str


MARCAS: tuple[Marca, ...] = (
    Marca("ubereats", "Uber Eats", (r"UBER ?EATS",), "UBER EATS"),
    Marca("uber", "Uber", (r"UBER",), "UBER"),
    Marca("99", "99", (r"99 ?APP", r"99 ?TECNOLOGIA", r"99 ?POP", r"99 ?TAXI"), "99APP"),
    Marca("ifood", "iFood", (r"IFOOD", r"IFD"), "IFD"),
    Marca("rappi", "Rappi", (r"RAPPI",), "RAPPI"),
    Marca("netflix", "Netflix", (r"NETFLIX",), "NETFLIX"),
    Marca("spotify", "Spotify", (r"SPOTIFY",), "SPOTIFY"),
    Marca(
        "youtube",
        "YouTube Premium",
        (r"YOUTUBE ?PREMIUM", r"GOOGLE ?YOUTUBE", r"YOUTUBE"),
        "YOUTUBE",
    ),
    Marca("disneyplus", "Disney+", (r"DISNEY ?PLUS", r"DISNEY"), "DISNEY"),
    Marca("hbomax", "HBO Max", (r"HBO ?MAX", r"HBO"), "HBO"),
    Marca("primevideo", "Prime Video", (r"PRIME ?VIDEO", r"AMAZON ?PRIME"), "PRIME VIDEO"),
    Marca(
        "amazon",
        "Amazon",
        (r"AMAZON ?(?:MKTPLC|MKTP|MARKETPLACE)", r"AMAZON", r"AMZN ?(?:MKTP)?"),
        "AMAZON",
    ),
    Marca("mercadolivre", "Mercado Livre", (r"MERCADO ?LIVRE",), "MERCADOLIVRE"),
    Marca("shopee", "Shopee", (r"SHOPEE",), "SHOPEE"),
    Marca("aliexpress", "AliExpress", (r"ALIEXPRESS",), "ALIEXPRESS"),
    Marca("zaffari", "Zaffari", (r"ZAFFARI",), "ZAFFARI"),
    Marca("carrefour", "Carrefour", (r"CARREFOUR",), "CARREFOUR"),
    Marca("assai", "Assaí", (r"ASSAI",), "ASSAI"),
    Marca("atacadao", "Atacadão", (r"ATACADAO",), "ATACADAO"),
    Marca("panvel", "Panvel", (r"PANVEL",), "PANVEL"),
    Marca("drogaraia", "Droga Raia", (r"DROGA ?RAIA",), "DROGA RAIA"),
    Marca("drogasil", "Drogasil", (r"DROGASIL",), "DROGASIL"),
    Marca("saojoao", "Farmácias São João", (r"FARMACIAS? SAO JOAO",), "FARMACIA SAO JOAO"),
    Marca("smartfit", "Smart Fit", (r"SMART ?FIT",), "SMARTFIT"),
    Marca("mcdonalds", "McDonald's", (r"MC ?DONALDS", r"ARCOS DOURADOS"), "MCDONALDS"),
    Marca("burgerking", "Burger King", (r"BURGER ?KING", r"BK BRASIL"), "BURGER KING"),
    Marca("starbucks", "Starbucks", (r"STARBUCKS",), "STARBUCKS"),
    Marca("kfc", "KFC", (r"KFC",), "KFC"),
    Marca("shell", "Shell", (r"SHELL",), "SHELL"),
    Marca("cinemark", "Cinemark", (r"CINEMARK",), "CINEMARK"),
    Marca("steam", "Steam", (r"STEAM ?(?:GAMES|POWERED|PURCHASE)?",), "STEAM"),
    Marca("playstation", "PlayStation", (r"PLAYSTATION", r"PSN"), "PLAYSTATION"),
    Marca("icloud", "iCloud", (r"ICLOUD",), "ICLOUD"),
    Marca("apple", "Apple", (r"APPLE ?COM",), "APPLE COM"),
    Marca("google", "Google", (r"GOOGLE",), "GOOGLE"),
    Marca("airbnb", "Airbnb", (r"AIRBNB",), "AIRBNB"),
    Marca("duolingo", "Duolingo", (r"DUOLINGO",), "DUOLINGO"),
    Marca("udemy", "Udemy", (r"UDEMY",), "UDEMY"),
    Marca("coursera", "Coursera", (r"COURSERA",), "COURSERA"),
    Marca("claude", "Claude", (r"CLAUDE ?AI", r"ANTHROPIC"), "ANTHROPIC"),
)

_PADROES_MARCA = [
    (marca, re.compile(rf"(?<![A-Z0-9])(?:{'|'.join(marca.padroes)})(?:COM(?:BR)?)?(?![A-Z0-9])"))
    for marca in MARCAS
]

_PREFIXOS = re.compile(
    r"^(?:(?:PAG|PAGSEGURO|MP|MERCADOPAGO|EC|PIC|PG|IZ|SUMUP|STONE|CIELO|GETNET|SQ|PP|EBN|DL|HTM|IFD)"
    r"\s?\*\s?|COMPRA (?:NO )?(?:CARTAO|DEBITO|CREDITO)(?: (?:DEB|CRED))?\s+|COMPRA\s+"
    r"|DEB(?:ITO)? AUTOM(?:ATICO)?\s+)+"
)
_RUIDO = (
    re.compile(r"\bPARCELA\s*\d+(?:\s*(?:DE|/)\s*\d+)?\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}\b"),
    re.compile(r"\b\d{4,}\b"),
    re.compile(r"\s+(?:BR|BRA|BRASIL)$"),
    re.compile(
        r"\s+(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$"
    ),
)
_MINUSCULAS = {"DE", "DO", "DA", "DOS", "DAS", "E", "NO", "NA", "NOS", "NAS", "EM", "A", "O"}


class Estabelecimento(BaseModel):
    chave: str
    nome: str
    marca: str | None
    regra: str | None


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().replace(".", " ").split())


def _titulo(texto: str) -> str:
    palavras = texto.split()
    return " ".join(
        p.lower() if i and p in _MINUSCULAS else p.capitalize() for i, p in enumerate(palavras)
    )


def _limpar(texto: str) -> str:
    texto = _PREFIXOS.sub("", texto)
    for padrao in _RUIDO:
        texto = padrao.sub("", texto)
    texto = re.sub(r"[*#]+", " ", texto)
    return " ".join(texto.split())


def nucleo(descricao: str) -> str:
    return _limpar(normalizar(descricao)) or normalizar(descricao)


def identificar(descricao: str) -> Estabelecimento:
    normalizado = normalizar(descricao)
    for marca, padrao in _PADROES_MARCA:
        if padrao.search(normalizado):
            return Estabelecimento(
                chave=f"marca:{marca.slug}", nome=marca.nome, marca=marca.slug, regra=marca.regra
            )
    base = nucleo(descricao)
    exibido = _limpar(" ".join(descricao.upper().replace(".", " ").split())) or base
    return Estabelecimento(
        chave=f"texto:{base}",
        nome=_titulo(exibido),
        marca=None,
        regra=base[:60] if len(base) >= 3 else None,
    )
