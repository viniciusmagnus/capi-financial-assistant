import re
import unicodedata

from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nota_a_nota import categorias as catalogo
from nota_a_nota import consultas
from nota_a_nota.acesso import dono
from nota_a_nota.ledger import aplicar_categoria
from nota_a_nota.models import OrigemCategoria, RegraCategoria, Transacao

TAMANHO_MINIMO = 3
TAMANHO_MAXIMO_ESTABELECIMENTO = 80

GENERICOS = frozenset(
    {
        "PIX",
        "ENVIADO",
        "ENVIADA",
        "RECEBIDO",
        "RECEBIDA",
        "TED",
        "DOC",
        "TEF",
        "TRANSF",
        "TRANSFERENCIA",
        "TRANSFERENCIAS",
        "PAGAMENTO",
        "PAGTO",
        "PGTO",
        "PAG",
        "COMPRA",
        "COMPRAS",
        "CARTAO",
        "DEBITO",
        "DEB",
        "CREDITO",
        "CRED",
        "PARCELA",
        "PARCELADO",
        "PARC",
        "BOLETO",
        "SAQUE",
        "TARIFA",
        "QRCODE",
        "CODE",
        "APLICACAO",
        "RESGATE",
        "ELO",
        "VISA",
        "MASTER",
        "MASTERCARD",
        "NACIONAL",
        "INTERNACIONAL",
        "ONLINE",
        "INTERNET",
        "LOJA",
        "LOJAS",
        "BRASIL",
        "LTDA",
        "EIRELI",
        "VIA",
        "APP",
        "CONTA",
        "ENVIO",
        "RECEBIMENTO",
    }
)

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
    categoria: str | None
    estabelecimento: str | None = None


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().split())


def _distintivo(termo: str) -> bool:
    letras = sum(c.isalpha() for c in termo)
    return (
        len(termo) >= TAMANHO_MINIMO
        and letras >= 2
        and letras * 2 >= len(termo)
        and termo not in GENERICOS
    )


def termos_distintivos(padrao: str) -> list[str]:
    return [t for t in re.split(r"[^A-Z0-9]+", normalizar(padrao)) if _distintivo(t)]


def validar_padrao(padrao: str) -> str:
    padrao = normalizar(padrao)
    if len(padrao) < TAMANHO_MINIMO:
        raise RegraInvalida(f"o padrão precisa ter pelo menos {TAMANHO_MINIMO} letras")
    if not termos_distintivos(padrao):
        raise RegraInvalida(
            f"o padrão {padrao!r} é genérico demais: casaria com pagamentos para qualquer "
            "estabelecimento ou pessoa. Inclua o nome de quem recebe."
        )
    return padrao


def limpar_estabelecimento(nome: str | None) -> str | None:
    if nome is None:
        return None
    limpo = " ".join(nome.split())
    if not limpo:
        return None
    if len(limpo) > TAMANHO_MAXIMO_ESTABELECIMENTO:
        raise RegraInvalida(
            f"o estabelecimento pode ter até {TAMANHO_MAXIMO_ESTABELECIMENTO} caracteres"
        )
    return limpo


def casa(padrao: str, descricao: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(padrao)}", normalizar(descricao)) is not None


def escolher(regras: list[Regra], descricao: str) -> Regra | None:
    candidatas = [r for r in regras if r.categoria and casa(r.padrao, descricao)]
    return max(candidatas, key=lambda r: len(r.padrao), default=None)


def escolher_estabelecimento(regras: list[Regra], descricao: str) -> Regra | None:
    candidatas = [r for r in regras if r.estabelecimento and casa(r.padrao, descricao)]
    return max(candidatas, key=lambda r: len(r.padrao), default=None)


def combina_com_o_sentido(
    categoria: str, valor_centavos: int, categorias: catalogo.Categorias | None = None
) -> bool:
    sentido = (categorias or catalogo.PADRAO).sentido(categoria)
    if sentido == "transferencia":
        return True
    return sentido == ("despesa" if valor_centavos < 0 else "receita")


def _modelo(linha: RegraCategoria) -> Regra:
    return Regra(
        id=linha.id,
        padrao=linha.padrao,
        categoria=linha.categoria,
        estabelecimento=linha.estabelecimento,
    )


def listar(session: Session) -> list[Regra]:
    linhas = session.scalars(select(RegraCategoria).order_by(RegraCategoria.padrao))
    return [_modelo(r) for r in linhas]


def obter(session: Session, regra_id: int) -> Regra | None:
    linha = session.scalar(select(RegraCategoria).where(RegraCategoria.id == regra_id))
    return _modelo(linha) if linha else None


def obter_por_padrao(session: Session, padrao: str) -> Regra | None:
    linha = session.scalar(
        select(RegraCategoria).where(RegraCategoria.padrao == normalizar(padrao))
    )
    return _modelo(linha) if linha else None


def validar(
    session: Session,
    padrao: str,
    categoria: str | None,
    estabelecimento: str | None,
    padrao_existente: str | None = None,
) -> tuple[str, str | None, str | None]:
    if padrao_existente is None or normalizar(padrao) != padrao_existente:
        padrao = validar_padrao(padrao)
    else:
        padrao = padrao_existente
    estabelecimento = limpar_estabelecimento(estabelecimento)
    if categoria is not None and categoria not in catalogo.listar(session).todas:
        raise RegraInvalida(f"categoria desconhecida: {categoria}")
    if categoria is None and estabelecimento is None:
        raise RegraInvalida("a regra precisa definir uma categoria, um estabelecimento ou os dois")
    return padrao, categoria, estabelecimento


def salvar(
    session: Session,
    padrao: str,
    categoria: str | None,
    estabelecimento: str | None = None,
    commit: bool = True,
) -> Regra:
    padrao, categoria, estabelecimento = validar(session, padrao, categoria, estabelecimento)
    regra_id = session.scalar(
        insert(RegraCategoria)
        .values(
            usuario_id=dono(session),
            padrao=padrao,
            categoria=categoria,
            estabelecimento=estabelecimento,
        )
        .on_conflict_do_update(
            index_elements=[RegraCategoria.usuario_id, RegraCategoria.padrao],
            set_={"categoria": categoria, "estabelecimento": estabelecimento},
        )
        .returning(RegraCategoria.id)
    )
    if commit:
        session.commit()
    return Regra(id=regra_id, padrao=padrao, categoria=categoria, estabelecimento=estabelecimento)


def editar(
    session: Session,
    regra_id: int,
    padrao: str,
    categoria: str | None,
    estabelecimento: str | None,
) -> Regra | None:
    linha = session.scalar(select(RegraCategoria).where(RegraCategoria.id == regra_id))
    if linha is None:
        return None
    padrao, categoria, estabelecimento = validar(
        session, padrao, categoria, estabelecimento, padrao_existente=linha.padrao
    )
    outra = obter_por_padrao(session, padrao)
    if outra and outra.id != regra_id:
        raise RegraInvalida(f"já existe uma regra para {padrao}")
    linha.padrao, linha.categoria, linha.estabelecimento = padrao, categoria, estabelecimento
    session.commit()
    return _modelo(linha)


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


def nomear_estabelecimentos(session: Session, regras: list[Regra]) -> int:
    com_nome = [r for r in regras if r.estabelecimento]
    if not com_nome:
        return 0
    nomeadas = 0
    sem_nome = session.execute(
        select(Transacao.id, Transacao.descricao).where(Transacao.estabelecimento.is_(None))
    ).all()
    for transacao_id, descricao in sem_nome:
        regra = escolher_estabelecimento(com_nome, descricao)
        if regra:
            session.execute(
                update(Transacao)
                .where(Transacao.id == transacao_id)
                .values(estabelecimento=regra.estabelecimento)
            )
            nomeadas += 1
    return nomeadas


def aplicar(session: Session) -> int:
    regras = listar(session)
    if not regras:
        return 0
    nomear_estabelecimentos(session, regras)
    aplicadas = 0
    categorias = catalogo.listar(session)
    for pendente in consultas.pendentes_de_categoria(session, limite=None):
        regra = escolher(regras, pendente.descricao)
        if regra and combina_com_o_sentido(regra.categoria, pendente.valor_centavos, categorias):
            aplicar_categoria(session, pendente.id, regra.categoria, OrigemCategoria.REGRA)
            aplicadas += 1
    session.commit()
    return aplicadas
