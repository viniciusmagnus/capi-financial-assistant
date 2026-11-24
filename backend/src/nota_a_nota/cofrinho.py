from calendar import monthrange
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nota_a_nota import consultas, perfil
from nota_a_nota.acesso import dono
from nota_a_nota.models import TetoMensal

FUSO = ZoneInfo("America/Sao_Paulo")


class Humor(StrEnum):
    SEM_TETO = "sem_teto"
    TRANQUILA = "tranquila"
    DE_OLHO = "de_olho"
    APERTADA = "apertada"
    ESTOUROU = "estourou"


class EstadoCofrinho(BaseModel):
    mes: str
    teto_centavos: int | None
    gasto_centavos: int
    pode_gastar_centavos: int | None
    dias_no_mes: int
    dias_restantes: int
    por_dia_centavos: int | None
    humor: Humor
    ultimos: list[consultas.TransacaoResumo]
    teto_origem: Literal["mes", "renda"] | None = None


def hoje() -> date:
    return datetime.now(FUSO).date()


def ler_mes(texto: str) -> date:
    try:
        ano, mes = (int(parte) for parte in texto.split("-"))
        return date(ano, mes, 1)
    except ValueError as erro:
        raise ValueError(f"mês inválido: {texto!r}, use AAAA-MM") from erro


def dias_restantes(inicio: date, referencia: date) -> int:
    dias_no_mes = monthrange(inicio.year, inicio.month)[1]
    fim = inicio + timedelta(days=dias_no_mes - 1)
    if referencia > fim:
        return 0
    if referencia < inicio:
        return dias_no_mes
    return (fim - referencia).days + 1


def calcular_humor(teto: int | None, gasto: int, dias_no_mes: int, restantes: int) -> Humor:
    if teto is None:
        return Humor.SEM_TETO
    if gasto > teto:
        return Humor.ESTOUROU
    usado = gasto / teto
    decorrido = (dias_no_mes - restantes + 1) / dias_no_mes if restantes else 1.0
    if usado >= 0.85 or usado > decorrido + 0.2:
        return Humor.APERTADA
    if usado > decorrido + 0.05:
        return Humor.DE_OLHO
    return Humor.TRANQUILA


def estado(session: Session, inicio: date, referencia: date | None = None) -> EstadoCofrinho:
    referencia = referencia or hoje()
    dias_no_mes = monthrange(inicio.year, inicio.month)[1]
    fim = inicio + timedelta(days=dias_no_mes - 1)
    teto = session.scalar(select(TetoMensal).where(TetoMensal.mes == inicio))
    teto_centavos, origem = (teto.valor_centavos, "mes") if teto else (None, None)
    if teto_centavos is None:
        renda = perfil.obter_renda(session)
        if renda and renda.valor_centavos > 0:
            teto_centavos, origem = renda.valor_centavos, "renda"
    gasto = consultas.gasto_total(session, inicio, fim)
    restantes = dias_restantes(inicio, referencia)
    pode_gastar = teto_centavos - gasto if teto_centavos is not None else None
    por_dia = max(pode_gastar, 0) // restantes if pode_gastar is not None and restantes else None
    return EstadoCofrinho(
        mes=inicio.strftime("%Y-%m"),
        teto_centavos=teto_centavos,
        gasto_centavos=gasto,
        pode_gastar_centavos=pode_gastar,
        dias_no_mes=dias_no_mes,
        dias_restantes=restantes,
        por_dia_centavos=por_dia,
        humor=calcular_humor(teto_centavos, gasto, dias_no_mes, restantes),
        ultimos=consultas.ultimas_despesas(session, inicio, fim),
        teto_origem=origem,
    )


def remover_teto(session: Session, inicio: date) -> None:
    session.execute(delete(TetoMensal).where(TetoMensal.mes == inicio))
    session.commit()


def definir_teto(session: Session, inicio: date, valor_centavos: int) -> None:
    if valor_centavos <= 0:
        raise ValueError("o teto precisa ser positivo")
    session.execute(
        insert(TetoMensal)
        .values(usuario_id=dono(session), mes=inicio, valor_centavos=valor_centavos)
        .on_conflict_do_update(
            index_elements=[TetoMensal.usuario_id, TetoMensal.mes],
            set_={"valor_centavos": valor_centavos, "atualizado_em": datetime.now(FUSO)},
        )
    )
    session.commit()
