from sqlalchemy.orm import Session

from nota_a_nota.rag.busca import ResultadoIndexacao, indexar
from nota_a_nota.rag.embeddings import obter_embedder


def atualizar_indice(session: Session) -> ResultadoIndexacao:
    return indexar(session, obter_embedder())
