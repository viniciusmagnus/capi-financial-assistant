import argparse
import sys

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from nota_a_nota.db import get_sessionmaker

DONO_LEGADO = "legado-pre-autenticacao"
TABELAS = (
    "contas",
    "importacoes",
    "transacoes",
    "lancamentos",
    "notas_fiscais",
    "itens_nota",
    "trechos",
    "regras_categoria",
    "perfil_financeiro",
    "tetos_mensais",
)
DADOS_PROPRIOS = (
    "transacoes",
    "importacoes",
    "perfil_financeiro",
    "tetos_mensais",
    "notas_fiscais",
)


class TransferenciaRecusada(Exception):
    pass


class Transferencia(BaseModel):
    destino: str
    linhas: dict[str, int]
    aplicada: bool


def _contar(session: Session, tabela: str, usuario_id: str) -> int:
    return session.execute(
        text(f"SELECT count(*) FROM {tabela} WHERE usuario_id = :u"), {"u": usuario_id}
    ).scalar_one()


def transferir(session: Session, email: str, confirmar: bool) -> Transferencia:
    destino = session.execute(
        text('SELECT id, "emailVerified" FROM "user" WHERE lower(email) = lower(:e)'),
        {"e": email},
    ).first()
    if destino is None:
        raise TransferenciaRecusada(f"nenhuma conta com o e-mail {email}")
    if not destino.emailVerified:
        raise TransferenciaRecusada("a conta de destino ainda não verificou o e-mail")
    if destino.id == DONO_LEGADO:
        raise TransferenciaRecusada("o destino não pode ser o próprio dono legado")
    linhas = {t: _contar(session, t, DONO_LEGADO) for t in TABELAS}
    if not any(linhas.values()):
        raise TransferenciaRecusada("não há dados legados para transferir")
    com_dados = [t for t in DADOS_PROPRIOS if _contar(session, t, destino.id)]
    if com_dados:
        raise TransferenciaRecusada(
            "a conta de destino já tem dados próprios em " + ", ".join(com_dados)
        )
    if not confirmar:
        return Transferencia(destino=destino.id, linhas=linhas, aplicada=False)

    parametros = {"destino": destino.id, "legado": DONO_LEGADO}
    for tabela in ("trechos", "regras_categoria", "contas"):
        session.execute(text(f"DELETE FROM {tabela} WHERE usuario_id = :destino"), parametros)
    session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    for tabela in TABELAS:
        session.execute(
            text(f"UPDATE {tabela} SET usuario_id = :destino WHERE usuario_id = :legado"),
            parametros,
        )
    session.execute(text('DELETE FROM "user" WHERE id = :legado'), parametros)
    session.commit()
    return Transferencia(destino=destino.id, linhas=linhas, aplicada=True)


def main(argumentos: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(
        description="Entrega os dados de antes da autenticação a uma conta já verificada."
    )
    leitor.add_argument("--email", required=True)
    leitor.add_argument("--confirmar", action="store_true")
    opcoes = leitor.parse_args(argumentos)
    with get_sessionmaker()() as session:
        try:
            resultado = transferir(session, opcoes.email, opcoes.confirmar)
        except TransferenciaRecusada as erro:
            print(f"Nada foi feito: {erro}.", file=sys.stderr)
            return 1
    for tabela, quantidade in resultado.linhas.items():
        print(f"{tabela:18} {quantidade}")
    if resultado.aplicada:
        print("Transferido. O dono legado foi apagado.")
    else:
        print("Simulação. Rode de novo com --confirmar para transferir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
