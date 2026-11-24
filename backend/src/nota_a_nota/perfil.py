from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nota_a_nota.acesso import dono
from nota_a_nota.models import PerfilFinanceiro


class Renda(BaseModel):
    valor_centavos: int
    variavel: bool
    atualizada_em: datetime


def obter_renda(session: Session) -> Renda | None:
    perfil = session.scalar(select(PerfilFinanceiro))
    if perfil is None:
        return None
    return Renda(
        valor_centavos=perfil.renda_mensal_centavos,
        variavel=perfil.renda_variavel,
        atualizada_em=perfil.atualizado_em,
    )


def salvar_renda(session: Session, valor_centavos: int, variavel: bool) -> Renda:
    if valor_centavos < 0:
        raise ValueError("a renda não pode ser negativa")
    agora = datetime.now(UTC)
    session.execute(
        insert(PerfilFinanceiro)
        .values(
            usuario_id=dono(session),
            renda_mensal_centavos=valor_centavos,
            renda_variavel=variavel,
        )
        .on_conflict_do_update(
            index_elements=[PerfilFinanceiro.usuario_id],
            set_={
                "renda_mensal_centavos": valor_centavos,
                "renda_variavel": variavel,
                "atualizado_em": agora,
            },
        )
    )
    session.commit()
    session.expire_all()
    renda = obter_renda(session)
    assert renda is not None
    return renda
