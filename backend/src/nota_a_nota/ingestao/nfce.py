import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

UF_POR_CODIGO = {
    "11": "RO",
    "12": "AC",
    "13": "AM",
    "14": "RR",
    "15": "PA",
    "16": "AP",
    "17": "TO",
    "21": "MA",
    "22": "PI",
    "23": "CE",
    "24": "RN",
    "25": "PB",
    "26": "PE",
    "27": "AL",
    "28": "SE",
    "29": "BA",
    "31": "MG",
    "32": "ES",
    "33": "RJ",
    "35": "SP",
    "41": "PR",
    "42": "SC",
    "43": "RS",
    "50": "MS",
    "51": "MT",
    "52": "GO",
    "53": "DF",
}


class ChaveInvalida(ValueError):
    pass


@dataclass(frozen=True)
class ChaveAcesso:
    chave: str
    uf: str
    ano: int
    mes: int
    cnpj_emitente: str
    modelo: str
    serie: int
    numero: int

    @property
    def eh_nfce(self) -> bool:
        return self.modelo == "65"


def digito_verificador(chave_sem_dv: str) -> int:
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = sum(int(d) * pesos[i % 8] for i, d in enumerate(reversed(chave_sem_dv)))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def extrair_chave(entrada: str) -> str:
    entrada = entrada.strip()
    if entrada.lower().startswith("http"):
        parametro = parse_qs(urlparse(entrada).query).get("p", [""])[0]
        candidata = parametro.split("|")[0]
    else:
        candidata = entrada
    digitos = re.sub(r"\D", "", candidata)
    if len(digitos) != 44:
        raise ChaveInvalida(f"a chave precisa de 44 dígitos, veio {len(digitos)}")
    return digitos


def ler_chave(entrada: str) -> ChaveAcesso:
    chave = extrair_chave(entrada)
    if digito_verificador(chave[:43]) != int(chave[43]):
        raise ChaveInvalida("dígito verificador não confere")
    uf = UF_POR_CODIGO.get(chave[:2])
    if uf is None:
        raise ChaveInvalida(f"código de UF desconhecido: {chave[:2]}")
    return ChaveAcesso(
        chave=chave,
        uf=uf,
        ano=2000 + int(chave[2:4]),
        mes=int(chave[4:6]),
        cnpj_emitente=chave[6:20],
        modelo=chave[20:22],
        serie=int(chave[22:25]),
        numero=int(chave[25:34]),
    )
