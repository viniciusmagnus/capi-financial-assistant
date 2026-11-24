import re
import unicodedata

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nota_a_nota import categorias as catalogo
from nota_a_nota import consultas
from nota_a_nota.acesso import dono
from nota_a_nota.ledger import aplicar_categoria
from nota_a_nota.models import OrigemCategoria, RegraCategoria

TAMANHO_MINIMO = 3

REGRAS_PADRAO = (
    ("UBER EATS", "Restaurantes e delivery"),
    ("UBER", "Transporte"),
    ("IFD", "Restaurantes e delivery"),
    ("IFOOD", "Restaurantes e delivery"),
    ("RAPPI", "Restaurantes e delivery"),
    ("ZAFFARI", "Mercado"),
    ("CARREFOUR", "Mercado"),
    ("ASSAI", "Mercado"),
    ("ATACADAO", "Mercado"),
    ("NETFLIX", "Assinaturas"),
    ("SPOTIFY", "Assinaturas"),
    ("DISNEY", "Assinaturas"),
    ("DROGASIL", "Saúde"),
    ("PANVEL", "Saúde"),
    ("FARMACIA", "Saúde"),
    ("POSTO", "Transporte"),
    ("SALARIO", "Salário"),
    ("RENDIMENTO", "Rendimentos"),
    ("ESTORNO", "Reembolsos"),
    ("PAGTO FATURA", "Transferência interna"),
    ("PAGAMENTO FATURA", "Transferência interna"),
    ("PAG FATURA", "Transferência interna"),
    ("PAGAMENTO RECEBIDO", "Transferência interna"),
    ("PAGAMENTO EM", "Transferência interna"),
    ("PAGAMENTO DE FATURA", "Transferência interna"),
)


class RegraInvalida(ValueError):
    pass


class Regra(BaseModel):
    id: int
    padrao: str
    categoria: str


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


def casa(padrao: str, descricao: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(padrao)}", normalizar(descricao)) is not None


def escolher(regras: list[Regra], descricao: str) -> Regra | None:
    candidatas = [r for r in regras if casa(r.padrao, descricao)]
    return max(candidatas, key=lambda r: len(r.padrao), default=None)


def combina_com_o_sentido(
    categoria: str, valor_centavos: int, categorias: catalogo.Categorias | None = None
) -> bool:
    sentido = (categorias or catalogo.PADRAO).sentido(categoria)
    if sentido == "transferencia":
        return True
    return sentido == ("despesa" if valor_centavos < 0 else "receita")


def listar(session: Session) -> list[Regra]:
    linhas = session.scalars(select(RegraCategoria).order_by(RegraCategoria.padrao))
    return [Regra(id=r.id, padrao=r.padrao, categoria=r.categoria) for r in linhas]


def salvar(session: Session, padrao: str, categoria: str) -> Regra:
    padrao = normalizar(padrao)
    if len(padrao) < TAMANHO_MINIMO:
        raise RegraInvalida(f"o padrão precisa ter pelo menos {TAMANHO_MINIMO} letras")
    if categoria not in catalogo.listar(session).todas:
        raise RegraInvalida(f"categoria desconhecida: {categoria}")
    regra_id = session.scalar(
        insert(RegraCategoria)
        .values(usuario_id=dono(session), padrao=padrao, categoria=categoria)
        .on_conflict_do_update(
            index_elements=[RegraCategoria.usuario_id, RegraCategoria.padrao],
            set_={"categoria": categoria},
        )
        .returning(RegraCategoria.id)
    )
    session.commit()
    return Regra(id=regra_id, padrao=padrao, categoria=categoria)


def criar_regras_padrao(session: Session) -> None:
    session.execute(
        insert(RegraCategoria)
        .values(
            [
                {"usuario_id": dono(session), "padrao": padrao, "categoria": categoria}
                for padrao, categoria in REGRAS_PADRAO
            ]
        )
        .on_conflict_do_nothing(constraint="uq_regra_padrao")
    )


def apagar(session: Session, regra_id: int) -> bool:
    apagadas = session.execute(delete(RegraCategoria).where(RegraCategoria.id == regra_id)).rowcount
    session.commit()
    return apagadas > 0


def aplicar(session: Session) -> int:
    regras = listar(session)
    if not regras:
        return 0
    aplicadas = 0
    categorias = catalogo.listar(session)
    for pendente in consultas.pendentes_de_categoria(session, limite=None):
        regra = escolher(regras, pendente.descricao)
        if regra and combina_com_o_sentido(regra.categoria, pendente.valor_centavos, categorias):
            aplicar_categoria(session, pendente.id, regra.categoria, OrigemCategoria.REGRA)
            aplicadas += 1
    session.commit()
    return aplicadas
