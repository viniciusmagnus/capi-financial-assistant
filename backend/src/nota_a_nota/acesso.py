from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria
from sqlalchemy.sql.util import find_tables

from nota_a_nota.models import Base, Privado

CHAVE_USUARIO = "usuario_id"
TODOS_OS_USUARIOS = "todos_os_usuarios"

usuario_atual: ContextVar[str | None] = ContextVar("usuario_atual", default=None)


class AcessoSemUsuario(RuntimeError):
    pass


class DonoDiferente(RuntimeError):
    pass


def dono(session: Session) -> str:
    usuario_id = session.info.get(CHAVE_USUARIO)
    if not usuario_id:
        raise AcessoSemUsuario("sessão do banco sem usuário: dado financeiro não pode ser lido")
    return usuario_id


def _tabelas_privadas() -> frozenset[str]:
    return frozenset(
        m.local_table.name for m in Base.registry.mappers if issubclass(m.class_, Privado)
    )


def _toca_dado_privado(estado: ORMExecuteState) -> bool:
    if any(issubclass(m.class_, Privado) for m in estado.all_mappers):
        return True
    privadas = _tabelas_privadas()
    return any(
        getattr(t, "name", None) in privadas
        for t in find_tables(
            estado.statement, include_aliases=True, include_joins=True, include_crud=True
        )
    )


def _somente_do_usuario(estado: ORMExecuteState) -> None:
    if not (estado.is_select or estado.is_update or estado.is_delete):
        return
    if estado.execution_options.get(TODOS_OS_USUARIOS):
        return
    usuario_id = estado.session.info.get(CHAVE_USUARIO)
    if not usuario_id:
        if _toca_dado_privado(estado):
            raise AcessoSemUsuario("sessão do banco sem usuário: dado financeiro não pode ser lido")
        return
    estado.statement = estado.statement.options(
        with_loader_criteria(
            Privado,
            lambda cls: cls.usuario_id == usuario_id,
            include_aliases=True,
            propagate_to_loaders=True,
        )
    )


def _dono_nos_novos(session: Session, _contexto, _instancias) -> None:
    privados = [o for o in (*session.new, *session.dirty) if isinstance(o, Privado)]
    if not privados:
        return
    usuario_id = dono(session)
    for objeto in privados:
        if objeto.usuario_id is None:
            objeto.usuario_id = usuario_id
        elif objeto.usuario_id != usuario_id:
            raise DonoDiferente(f"{type(objeto).__name__} pertence a outra pessoa")


def registrar_filtros() -> None:
    if not event.contains(Session, "do_orm_execute", _somente_do_usuario):
        event.listen(Session, "do_orm_execute", _somente_do_usuario)
    if not event.contains(Session, "before_flush", _dono_nos_novos):
        event.listen(Session, "before_flush", _dono_nos_novos)


def abrir_sessao(usuario_id: str) -> Session:
    from nota_a_nota.db import get_sessionmaker

    if not usuario_id:
        raise AcessoSemUsuario("usuário vazio")
    session = get_sessionmaker()()
    session.info[CHAVE_USUARIO] = usuario_id
    return session


@contextmanager
def sessao_do_usuario_atual() -> Iterator[Session]:
    usuario_id = usuario_atual.get()
    if not usuario_id:
        raise AcessoSemUsuario("nenhum usuário autenticado nesta chamada")
    with abrir_sessao(usuario_id) as session:
        yield session
