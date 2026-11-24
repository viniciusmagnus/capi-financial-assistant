import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import anthropic
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import exists, select
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send

from nota_a_nota import (
    autenticacao,
    cofrinho,
    consultas,
    diagnostico,
    estabelecimentos,
    perfil,
    regras,
    revisao,
)
from nota_a_nota import categorias as catalogo
from nota_a_nota.acesso import abrir_sessao, dono, usuario_atual
from nota_a_nota.config import get_settings
from nota_a_nota.db import get_sessionmaker
from nota_a_nota.ingestao.extrato import ArquivoInvalido, Formato, ler_arquivo
from nota_a_nota.ingestao.nfce import ChaveAcesso, ChaveInvalida, ler_chave
from nota_a_nota.ledger import (
    anotar_gasto,
    aplicar_categoria,
    criar_contas_padrao,
    importar_extrato,
)
from nota_a_nota.llm import analise_outros
from nota_a_nota.llm.capi_diagnostico import comentar
from nota_a_nota.llm.capivara import Fala, fala_imediata, falar
from nota_a_nota.llm.categorizar import CategorizacaoRecusada, categorizar
from nota_a_nota.llm.chat import MensagemChat, conversar
from nota_a_nota.mcp_server import mcp
from nota_a_nota.models import Conta, OrigemCategoria, Transacao
from nota_a_nota.pesquisa_web import obter_pesquisador
from nota_a_nota.rag import atualizar_indice
from nota_a_nota.rag.busca import (
    ResultadoIndexacao,
    TransacaoEncontrada,
    buscar,
    exemplos_parecidos,
)
from nota_a_nota.rag.embeddings import obter_embedder

NAO_AUTENTICADO = {"WWW-Authenticate": "Bearer"}


async def _responder_401(send: Send, mensagem: str) -> None:
    corpo = json.dumps({"detail": mensagem}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": corpo})


class AutenticarMcp:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        enviado = dict(scope["headers"]).get(b"authorization", b"").decode()
        token = enviado.removeprefix("Bearer ").strip() if enviado.startswith("Bearer ") else ""
        try:
            with get_sessionmaker()() as session:
                usuario_id = autenticacao.usuario_do_token_mcp(session, token)
        except autenticacao.NaoAutenticado as erro:
            await _responder_401(send, str(erro))
            return
        marca = usuario_atual.set(usuario_id)
        try:
            await self.app(scope, receive, send)
        finally:
            usuario_atual.reset(marca)


mcp_app = AutenticarMcp(
    mcp.streamable_http_app(stateless_http=True, json_response=True, host="0.0.0.0")
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="nota-a-nota", version="0.2.0", lifespan=lifespan)
_provisionados: set[str] = set()


def usuario_autenticado(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "faça login para continuar", headers=NAO_AUTENTICADO)
    try:
        usuario_id = autenticacao.validar_jwt(authorization.removeprefix("Bearer ").strip())
        with get_sessionmaker()() as session:
            autenticacao.exigir_usuario_ativo(session, usuario_id)
    except autenticacao.NaoAutenticado as erro:
        raise HTTPException(401, str(erro), headers=NAO_AUTENTICADO) from erro
    return usuario_id


UsuarioId = Annotated[str, Depends(usuario_autenticado)]


def _provisionar(session: Session) -> None:
    usuario_id = dono(session)
    if usuario_id in _provisionados:
        return
    if not session.scalar(select(exists().where(Conta.usuario_id == usuario_id))):
        criar_contas_padrao(session)
        regras.criar_regras_padrao(session)
        session.commit()
    _provisionados.add(usuario_id)


def sessao_do_usuario(usuario_id: UsuarioId) -> Iterator[Session]:
    with abrir_sessao(usuario_id) as session:
        _provisionar(session)
        yield session


SessaoDb = Annotated[Session, Depends(sessao_do_usuario)]
api = APIRouter(prefix="/api", dependencies=[Depends(usuario_autenticado)])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


TAMANHO_MAXIMO_ARQUIVO = 5 * 1024 * 1024


class ResultadoImportacao(BaseModel):
    importacao_id: int
    conta: str
    banco: str | None
    formato: Formato
    cartao_de_credito: bool
    inicio: date | None
    fim: date | None
    no_arquivo: int
    novas: int
    duplicadas: int
    categorizadas_por_regra: int
    para_revisar: int


@api.post("/importar")
@api.post("/importar/ofx")
def importar_arquivo(
    session: SessaoDb,
    arquivo: Annotated[UploadFile, File()],
    apelido: Annotated[str | None, Form(max_length=60)] = None,
) -> ResultadoImportacao:
    conteudo = arquivo.file.read(TAMANHO_MAXIMO_ARQUIVO + 1)
    if len(conteudo) > TAMANHO_MAXIMO_ARQUIVO:
        raise HTTPException(413, "arquivo maior que 5 MB")
    try:
        extrato = ler_arquivo(arquivo.filename, conteudo)
    except ArquivoInvalido as erro:
        raise HTTPException(422, str(erro)) from erro
    resultado = importar_extrato(
        session, extrato, (apelido or "").strip() or None, arquivo.filename
    )
    por_regra = regras.aplicar(session)
    atualizar_indice(session)
    return ResultadoImportacao(
        importacao_id=resultado.importacao_id,
        conta=resultado.conta,
        banco=extrato.banco,
        formato=extrato.formato,
        cartao_de_credito=extrato.cartao_de_credito,
        inicio=resultado.inicio,
        fim=resultado.fim,
        no_arquivo=len(extrato.transacoes),
        novas=resultado.novas,
        duplicadas=resultado.duplicadas,
        categorizadas_por_regra=por_regra,
        para_revisar=consultas.revisar_na_importacao(session, resultado.importacao_id),
    )


class EntradaRenda(BaseModel):
    valor_centavos: int = Field(ge=0, le=100_000_000_000)
    variavel: bool = False


@api.get("/renda")
def ver_renda(session: SessaoDb) -> perfil.Renda | None:
    return perfil.obter_renda(session)


@api.put("/renda")
def salvar_renda(session: SessaoDb, corpo: EntradaRenda) -> perfil.Renda:
    return perfil.salvar_renda(session, corpo.valor_centavos, corpo.variavel)


@api.get("/gastos")
def gastos(session: SessaoDb, inicio: date, fim: date) -> list[consultas.GastoCategoria]:
    return consultas.gastos_por_categoria(session, inicio, fim)


@api.get("/saldos")
def saldos(session: SessaoDb) -> list[consultas.SaldoConta]:
    return consultas.saldos(session)


class ResultadoCategorizacao(BaseModel):
    por_regra: int
    enviadas_ao_claude: int
    pelo_claude: int
    pendentes: int
    ia_disponivel: bool
    motivo: str | None
    para_revisar_na_importacao: int | None


@api.post("/categorizar")
def categorizar_pendentes(
    session: SessaoDb,
    limite: int = 100,
    importacao_id: Annotated[list[int] | None, Query()] = None,
) -> ResultadoCategorizacao:
    por_regra = regras.aplicar(session)
    atualizar_indice(session)
    pendentes = consultas.pendentes_de_categoria(session, limite)
    tem_chave = bool(get_settings().anthropic_api_key)
    ia_disponivel, motivo = tem_chave, None if tem_chave else "chave da Anthropic não configurada"
    enviadas = pelo_claude = 0
    if pendentes and tem_chave:
        valores = {p.id: p.valor_centavos for p in pendentes}
        exemplos = exemplos_parecidos(session, list(valores))
        existentes = catalogo.listar(session)
        try:
            classificacoes = categorizar(pendentes, exemplos=exemplos, categorias=existentes)
            enviadas = len(pendentes)
        except (anthropic.APIError, CategorizacaoRecusada) as erro:
            classificacoes = []
            ia_disponivel, motivo = (
                False,
                f"categorização por IA indisponível agora ({type(erro).__name__})",
            )
        for item in classificacoes:
            if regras.combina_com_o_sentido(item.categoria, valores[item.id], existentes):
                aplicar_categoria(
                    session, item.id, item.categoria, OrigemCategoria.CLAUDE, item.confianca
                )
                pelo_claude += 1
        session.commit()
        atualizar_indice(session)
    return ResultadoCategorizacao(
        por_regra=por_regra,
        enviadas_ao_claude=enviadas,
        pelo_claude=pelo_claude,
        pendentes=len(consultas.pendentes_de_categoria(session, limite=None)),
        ia_disponivel=ia_disponivel,
        motivo=motivo,
        para_revisar_na_importacao=(
            sum(consultas.revisar_na_importacao(session, i) for i in importacao_id)
            if importacao_id
            else None
        ),
    )


@api.get("/busca")
def buscar_transacoes(
    session: SessaoDb,
    q: Annotated[str, Query(min_length=2, max_length=200)],
    inicio: date | None = None,
    fim: date | None = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[TransacaoEncontrada]:
    return buscar(session, q, obter_embedder(), inicio, fim, limite)


@api.post("/indexar")
def reindexar(session: SessaoDb) -> ResultadoIndexacao:
    return atualizar_indice(session)


class EntradaChat(BaseModel):
    mensagens: list[MensagemChat] = Field(min_length=1, max_length=40)


@api.post("/chat")
async def chat(corpo: EntradaChat, usuario_id: UsuarioId) -> StreamingResponse:
    if not get_settings().anthropic_api_key:
        raise HTTPException(503, "chat precisa de ANTHROPIC_API_KEY")
    if corpo.mensagens[-1].papel != "user":
        raise HTTPException(422, "a última mensagem precisa ser da pessoa")

    async def linhas():
        marca = usuario_atual.set(usuario_id)
        try:
            async for evento in conversar(corpo.mensagens):
                yield json.dumps(evento, ensure_ascii=False, default=str) + "\n"
        except anthropic.APIError as erro:
            mensagem = f"Falha na API do Claude: {erro}"
            yield json.dumps({"tipo": "erro", "mensagem": mensagem}, ensure_ascii=False) + "\n"
        finally:
            usuario_atual.reset(marca)

    return StreamingResponse(linhas(), media_type="application/x-ndjson")


@api.get("/diagnostico")
def ver_diagnostico(session: SessaoDb, mes: str | None = None) -> diagnostico.Diagnostico:
    if mes is None:
        meses = diagnostico.meses_com_dados(session)
        inicio = cofrinho.ler_mes(meses[0]) if meses else cofrinho.hoje().replace(day=1)
    else:
        inicio = _mes(mes)
    resultado = diagnostico.montar(session, inicio)
    for recomendacao, fala in zip(
        resultado.recomendacoes, comentar(resultado.recomendacoes, dono(session)), strict=True
    ):
        recomendacao.capi = fala
    return resultado


@api.get("/categorias")
def listar_categorias(session: SessaoDb) -> catalogo.Categorias:
    return catalogo.listar(session)


class EntradaCategoria(BaseModel):
    nome: str = Field(max_length=80)
    sentido: catalogo.Sentido = "despesa"


@api.post("/categorias", status_code=201)
def criar_categoria(session: SessaoDb, corpo: EntradaCategoria) -> catalogo.Categorias:
    try:
        return catalogo.criar(session, corpo.nome, corpo.sentido)
    except catalogo.CategoriaInvalida as erro:
        raise HTTPException(422, str(erro)) from erro


class EntradaCorrecao(BaseModel):
    categoria: str = Field(max_length=80)
    criar_regra: bool = False


class ResultadoCorrecao(BaseModel):
    categoria: str
    regra: regras.Regra | None
    outras_categorizadas: int


@api.patch("/transacoes/{transacao_id}/categoria")
def corrigir_categoria(
    session: SessaoDb, transacao_id: int, corpo: EntradaCorrecao
) -> ResultadoCorrecao:
    valor = consultas.valor_no_extrato(session, transacao_id)
    if valor is None:
        raise HTTPException(404, "transação não encontrada")
    existentes = catalogo.listar(session)
    if corpo.categoria not in existentes.todas:
        raise HTTPException(422, f"categoria desconhecida: {corpo.categoria}")
    if not regras.combina_com_o_sentido(corpo.categoria, valor, existentes):
        sentido = "saída" if valor < 0 else "entrada"
        raise HTTPException(422, f"{corpo.categoria} não combina com uma {sentido} de dinheiro")
    aplicar_categoria(session, transacao_id, corpo.categoria, OrigemCategoria.USUARIO)
    session.commit()
    regra, outras = None, 0
    if corpo.criar_regra:
        descricao = session.get(Transacao, transacao_id).descricao
        padrao = estabelecimentos.identificar(descricao).regra
        if padrao:
            try:
                regra = regras.salvar(session, padrao, corpo.categoria)
                outras = regras.aplicar(session)
            except regras.RegraInvalida:
                regra = None
    atualizar_indice(session)
    return ResultadoCorrecao(categoria=corpo.categoria, regra=regra, outras_categorizadas=outras)


class EntradaRegra(BaseModel):
    padrao: str = Field(min_length=3, max_length=120)
    categoria: str | None = Field(None, max_length=80)
    estabelecimento: str | None = Field(None, max_length=80)


@api.get("/regras")
def listar_regras(session: SessaoDb) -> list[regras.Regra]:
    return regras.listar(session)


@api.post("/regras", status_code=201)
def salvar_regra(session: SessaoDb, corpo: EntradaRegra) -> regras.Regra:
    try:
        return regras.salvar(session, corpo.padrao, corpo.categoria, corpo.estabelecimento)
    except regras.RegraInvalida as erro:
        raise HTTPException(422, str(erro)) from erro


@api.patch("/regras/{regra_id}")
def editar_regra(session: SessaoDb, regra_id: int, corpo: EntradaRegra) -> regras.Regra:
    try:
        regra = regras.editar(
            session, regra_id, corpo.padrao, corpo.categoria, corpo.estabelecimento
        )
    except regras.RegraInvalida as erro:
        raise HTTPException(422, str(erro)) from erro
    if regra is None:
        raise HTTPException(404, "regra não encontrada")
    return regra


@api.delete("/regras/{regra_id}", status_code=204)
def apagar_regra(session: SessaoDb, regra_id: int) -> None:
    if not regras.apagar(session, regra_id):
        raise HTTPException(404, "regra não encontrada")


class EntradaNfce(BaseModel):
    entrada: str


@api.post("/nfce/chave")
def validar_chave_nfce(corpo: EntradaNfce) -> ChaveAcesso:
    try:
        return ler_chave(corpo.entrada)
    except ChaveInvalida as erro:
        raise HTTPException(422, str(erro)) from erro


def _mes(texto: str | None) -> date:
    if texto is None:
        return cofrinho.hoje().replace(day=1)
    try:
        return cofrinho.ler_mes(texto)
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from erro


class Cofrinho(cofrinho.EstadoCofrinho):
    fala: Fala


@api.get("/cofrinho")
def ver_cofrinho(session: SessaoDb, mes: str | None = None) -> Cofrinho:
    estado = cofrinho.estado(session, _mes(mes))
    return Cofrinho(**estado.model_dump(), fala=fala_imediata(estado, dono(session)))


@api.get("/cofrinho/fala")
def ver_fala(session: SessaoDb, mes: str | None = None) -> Fala:
    return falar(cofrinho.estado(session, _mes(mes)), dono(session))


class EntradaTeto(BaseModel):
    mes: str
    teto_centavos: int = Field(gt=0)


@api.put("/cofrinho/teto", status_code=204)
def definir_teto(session: SessaoDb, corpo: EntradaTeto) -> None:
    cofrinho.definir_teto(session, _mes(corpo.mes), corpo.teto_centavos)


@api.delete("/cofrinho/teto", status_code=204)
def voltar_ao_teto_padrao(session: SessaoDb, mes: str) -> None:
    cofrinho.remover_teto(session, _mes(mes))


class EntradaGasto(BaseModel):
    valor_centavos: int = Field(gt=0)
    categoria: str = Field(max_length=80)
    descricao: str | None = Field(default=None, max_length=200)
    data: date | None = None


class GastoAnotado(BaseModel):
    id: int


@api.post("/gastos/anotar", status_code=201)
def anotar(session: SessaoDb, corpo: EntradaGasto) -> GastoAnotado:
    try:
        transacao_id = anotar_gasto(
            session,
            corpo.valor_centavos,
            corpo.categoria,
            corpo.descricao or corpo.categoria,
            corpo.data or cofrinho.hoje(),
        )
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from erro
    atualizar_indice(session)
    return GastoAnotado(id=transacao_id)


class EntradaTokenMcp(BaseModel):
    nome: str = Field(min_length=1, max_length=60)


@api.get("/tokens-mcp")
def listar_tokens_mcp(session: SessaoDb) -> list[autenticacao.TokenMcpResumo]:
    return autenticacao.listar_tokens_mcp(session, dono(session))


@api.post("/tokens-mcp", status_code=201)
def criar_token_mcp(session: SessaoDb, corpo: EntradaTokenMcp) -> autenticacao.TokenMcpCriado:
    try:
        return autenticacao.criar_token_mcp(session, dono(session), corpo.nome)
    except ValueError as erro:
        raise HTTPException(422, str(erro)) from erro


@api.delete("/tokens-mcp/{token_id}", status_code=204)
def revogar_token_mcp(session: SessaoDb, token_id: int) -> None:
    if not autenticacao.revogar_token_mcp(session, dono(session), token_id):
        raise HTTPException(404, "token não encontrado")


@api.post("/revisao/analisar")
def analisar_outros(session: SessaoDb) -> analise_outros.AnaliseOutros:
    try:
        return analise_outros.analisar(session, obter_pesquisador())
    except anthropic.APIError as erro:
        raise HTTPException(503, f"o Claude não respondeu agora ({type(erro).__name__})") from erro


class EntradaConfirmacao(BaseModel):
    decisoes: list[revisao.Decisao] = Field(min_length=1, max_length=revisao.LIMITE_DECISOES)
    lembrar: bool = True
    chave_idempotencia: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")


@api.post("/revisao/confirmar")
def confirmar_revisao(session: SessaoDb, corpo: EntradaConfirmacao) -> revisao.ResultadoConfirmacao:
    try:
        resultado = revisao.confirmar(
            session, corpo.decisoes, corpo.lembrar, corpo.chave_idempotencia
        )
    except revisao.NaoEncontradas as erro:
        session.rollback()
        raise HTTPException(404, str(erro)) from erro
    atualizar_indice(session)
    return resultado


@api.post("/revisao/lotes/{lote_id}/desfazer")
def desfazer_revisao(session: SessaoDb, lote_id: int) -> revisao.ResultadoDesfazer:
    try:
        resultado = revisao.desfazer(session, lote_id)
    except LookupError as erro:
        raise HTTPException(404, str(erro)) from erro
    atualizar_indice(session)
    return resultado


app.include_router(api)
app.mount("/", mcp_app)
