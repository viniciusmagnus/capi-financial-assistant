import logging
from typing import Literal, Protocol

import httpx

from nota_a_nota.config import get_settings
from nota_a_nota.models import DIMENSOES_EMBEDDING

URL_VOYAGE = "https://api.voyageai.com/v1/embeddings"
TAMANHO_LOTE = 128

log = logging.getLogger(__name__)

Uso = Literal["document", "query"]


class Embedder(Protocol):
    def embed(self, textos: list[str], uso: Uso) -> list[list[float]]: ...


class FalhaNoEmbedding(RuntimeError):
    pass


class Voyage:
    def __init__(self, chave: str, modelo: str, cliente: httpx.Client | None = None) -> None:
        self.modelo = modelo
        self.cliente = cliente or httpx.Client(
            timeout=30, headers={"Authorization": f"Bearer {chave}"}
        )

    def embed(self, textos: list[str], uso: Uso) -> list[list[float]]:
        vetores: list[list[float]] = []
        for inicio in range(0, len(textos), TAMANHO_LOTE):
            lote = textos[inicio : inicio + TAMANHO_LOTE]
            try:
                resposta = self.cliente.post(
                    URL_VOYAGE,
                    json={
                        "input": lote,
                        "model": self.modelo,
                        "input_type": uso,
                        "output_dimension": DIMENSOES_EMBEDDING,
                    },
                )
                resposta.raise_for_status()
            except httpx.HTTPError as erro:
                raise FalhaNoEmbedding(str(erro)) from erro
            dados = sorted(resposta.json()["data"], key=lambda d: d["index"])
            vetores.extend(d["embedding"] for d in dados)
        return vetores


def obter_embedder() -> Embedder | None:
    settings = get_settings()
    if not settings.voyage_api_key:
        return None
    return Voyage(settings.voyage_api_key, settings.modelo_embedding)


def embed_ou_nada(
    embedder: Embedder | None, textos: list[str], uso: Uso
) -> list[list[float]] | None:
    if embedder is None or not textos:
        return None
    try:
        return embedder.embed(textos, uso)
    except FalhaNoEmbedding as erro:
        log.warning("embedding indisponível, seguindo só com busca por palavra: %s", erro)
        return None
