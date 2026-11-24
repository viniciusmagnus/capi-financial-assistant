from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DIMENSOES_EMBEDDING = 1024


class Base(DeclarativeBase):
    pass


class Privado:
    usuario_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), index=True
    )


class TipoConta(StrEnum):
    ATIVO = "ativo"
    PASSIVO = "passivo"
    PATRIMONIO = "patrimonio"
    RECEITA = "receita"
    DESPESA = "despesa"


class OrigemCategoria(StrEnum):
    REGRA = "regra"
    CLAUDE = "claude"
    USUARIO = "usuario"


class Conta(Privado, Base):
    __tablename__ = "contas"
    __table_args__ = (UniqueConstraint("usuario_id", "nome", name="uq_conta_nome"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[TipoConta] = mapped_column(
        Enum(TipoConta, name="tipo_conta", values_callable=lambda e: [m.value for m in e])
    )
    banco: Mapped[str | None] = mapped_column(String(40))
    numero: Mapped[str | None] = mapped_column(String(60))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Transacao(Privado, Base):
    __tablename__ = "transacoes"
    __table_args__ = (
        UniqueConstraint("usuario_id", "origem", "id_externo", name="uq_transacao_origem"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    descricao: Mapped[str] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(String(20))
    id_externo: Mapped[str | None] = mapped_column(String(200))
    importacao_id: Mapped[int | None] = mapped_column(
        ForeignKey("importacoes.id", ondelete="SET NULL"), index=True
    )
    estabelecimento: Mapped[str | None] = mapped_column(String(80))
    confianca_categoria: Mapped[str | None] = mapped_column(String(5))
    categorizada_por: Mapped[OrigemCategoria | None] = mapped_column(
        Enum(
            OrigemCategoria,
            name="origem_categoria",
            values_callable=lambda e: [m.value for m in e],
        )
    )
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lancamentos: Mapped[list["Lancamento"]] = relationship(
        back_populates="transacao", cascade="all, delete-orphan"
    )


class Lancamento(Privado, Base):
    __tablename__ = "lancamentos"
    __table_args__ = (CheckConstraint("valor_centavos <> 0", name="ck_lancamento_nao_zero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    transacao_id: Mapped[int] = mapped_column(
        ForeignKey("transacoes.id", ondelete="CASCADE"), index=True
    )
    conta_id: Mapped[int] = mapped_column(ForeignKey("contas.id"), index=True)
    valor_centavos: Mapped[int] = mapped_column(BigInteger)

    transacao: Mapped[Transacao] = relationship(back_populates="lancamentos")
    conta: Mapped[Conta] = relationship()


class RegraCategoria(Privado, Base):
    __tablename__ = "regras_categoria"
    __table_args__ = (UniqueConstraint("usuario_id", "padrao", name="uq_regra_padrao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    padrao: Mapped[str] = mapped_column(String(120))
    categoria: Mapped[str | None] = mapped_column(String(60))
    estabelecimento: Mapped[str | None] = mapped_column(String(80))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PerfilFinanceiro(Privado, Base):
    __tablename__ = "perfil_financeiro"
    __table_args__ = (CheckConstraint("renda_mensal_centavos >= 0", name="ck_renda_nao_negativa"),)

    usuario_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    renda_mensal_centavos: Mapped[int] = mapped_column(BigInteger)
    renda_variavel: Mapped[bool] = mapped_column(default=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Importacao(Privado, Base):
    __tablename__ = "importacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conta_id: Mapped[int] = mapped_column(ForeignKey("contas.id"), index=True)
    arquivo: Mapped[str | None] = mapped_column(String(200))
    inicio: Mapped[date | None] = mapped_column(Date)
    fim: Mapped[date | None] = mapped_column(Date)
    novas: Mapped[int]
    duplicadas: Mapped[int]
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conta: Mapped[Conta] = relationship()


class TetoMensal(Privado, Base):
    __tablename__ = "tetos_mensais"
    __table_args__ = (CheckConstraint("valor_centavos > 0", name="ck_teto_positivo"),)

    usuario_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    mes: Mapped[date] = mapped_column(Date, primary_key=True)
    valor_centavos: Mapped[int] = mapped_column(BigInteger)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotaFiscal(Privado, Base):
    __tablename__ = "notas_fiscais"
    __table_args__ = (UniqueConstraint("usuario_id", "chave_acesso", name="uq_nota_chave"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chave_acesso: Mapped[str] = mapped_column(String(44))
    uf: Mapped[str] = mapped_column(String(2))
    cnpj_emitente: Mapped[str] = mapped_column(String(14), index=True)
    emitente_nome: Mapped[str | None] = mapped_column(Text)
    emitida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_centavos: Mapped[int | None] = mapped_column(BigInteger)
    transacao_id: Mapped[int | None] = mapped_column(
        ForeignKey("transacoes.id", ondelete="SET NULL")
    )

    itens: Mapped[list["ItemNota"]] = relationship(
        back_populates="nota", cascade="all, delete-orphan"
    )


class ItemNota(Privado, Base):
    __tablename__ = "itens_nota"

    id: Mapped[int] = mapped_column(primary_key=True)
    nota_id: Mapped[int] = mapped_column(
        ForeignKey("notas_fiscais.id", ondelete="CASCADE"), index=True
    )
    descricao: Mapped[str] = mapped_column(Text)
    produto_canonico: Mapped[str | None] = mapped_column(Text, index=True)
    codigo: Mapped[str | None] = mapped_column(String(60))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unidade: Mapped[str | None] = mapped_column(String(10))
    valor_unitario_centavos: Mapped[int] = mapped_column(BigInteger)
    valor_total_centavos: Mapped[int] = mapped_column(BigInteger)

    nota: Mapped[NotaFiscal] = relationship(back_populates="itens")


class Trecho(Privado, Base):
    __tablename__ = "trechos"
    __table_args__ = (
        UniqueConstraint("fonte_tipo", "fonte_id", "ordem", name="uq_trecho_fonte"),
        Index("ix_trechos_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_trechos_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fonte_tipo: Mapped[str] = mapped_column(String(20))
    fonte_id: Mapped[int] = mapped_column(BigInteger)
    ordem: Mapped[int] = mapped_column(default=0, server_default="0")
    texto: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(DIMENSOES_EMBEDDING))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('portuguese', texto)", persisted=True)
    )


_ORIGEM_CATEGORIA = Enum(
    OrigemCategoria,
    name="origem_categoria",
    values_callable=lambda e: [m.value for m in e],
    create_type=False,
)


class LoteRevisao(Privado, Base):
    __tablename__ = "revisao_lotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    chave_idempotencia: Mapped[str] = mapped_column(String(64))
    regra_id: Mapped[int | None] = mapped_column(ForeignKey("regras_categoria.id"))
    regra_criada: Mapped[bool] = mapped_column(default=False)
    regra_anterior: Mapped[dict | None] = mapped_column(JSONB)
    opcoes: Mapped[dict] = mapped_column(JSONB)
    resumo: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    desfeito_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    alteracoes: Mapped[list["AlteracaoRevisao"]] = relationship(
        back_populates="lote", cascade="all, delete-orphan"
    )


class AlteracaoRevisao(Privado, Base):
    __tablename__ = "revisao_alteracoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("revisao_lotes.id"), index=True)
    transacao_id: Mapped[int] = mapped_column(ForeignKey("transacoes.id"), index=True)
    categoria_anterior: Mapped[str] = mapped_column(String(120))
    categoria_nova: Mapped[str] = mapped_column(String(120))
    estabelecimento_anterior: Mapped[str | None] = mapped_column(String(80))
    estabelecimento_novo: Mapped[str | None] = mapped_column(String(80))
    categorizada_por_anterior: Mapped[OrigemCategoria | None] = mapped_column(_ORIGEM_CATEGORIA)
    categorizada_por_nova: Mapped[OrigemCategoria | None] = mapped_column(_ORIGEM_CATEGORIA)
    origem: Mapped[str] = mapped_column(String(12))
    regra_id: Mapped[int | None] = mapped_column(ForeignKey("regras_categoria.id"))

    lote: Mapped[LoteRevisao] = relationship(back_populates="alteracoes")


class Usuario(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    email_verificado: Mapped[bool] = mapped_column("emailVerified")


class TokenMcp(Base):
    __tablename__ = "tokens_mcp"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    nome: Mapped[str] = mapped_column(String(60))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefixo: Mapped[str] = mapped_column(String(16))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_uso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
