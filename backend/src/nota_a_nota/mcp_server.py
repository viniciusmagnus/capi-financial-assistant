from datetime import date

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from nota_a_nota import categorias as catalogo
from nota_a_nota import cofrinho, consultas, regras
from nota_a_nota.acesso import sessao_do_usuario_atual
from nota_a_nota.ledger import aplicar_categoria
from nota_a_nota.models import OrigemCategoria
from nota_a_nota.rag import atualizar_indice
from nota_a_nota.rag.busca import TransacaoEncontrada, buscar
from nota_a_nota.rag.embeddings import obter_embedder

INSTRUCOES = """Finanças pessoais de uma pessoa no Brasil, guardadas em um ledger de partidas dobradas.
Todos os valores estão em centavos de real (inteiros). Em transações, negativo é saída de dinheiro.
Para saber quanto ainda dá para gastar no mês use cofrinho_do_mes; para totais por período use gastos_por_categoria; para achar transações específicas use buscar_transacoes, que entende tanto o nome que aparece no extrato quanto o assunto ("comida fora", "transporte")."""

SOMENTE_LEITURA = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

mcp = MCPServer(name="nota-a-nota", instructions=INSTRUCOES)


@mcp.tool(annotations=SOMENTE_LEITURA)
def gastos_por_categoria(inicio: date, fim: date) -> list[consultas.GastoCategoria]:
    """Total gasto por categoria entre duas datas (inclusive), do maior para o menor."""
    with sessao_do_usuario_atual() as session:
        return consultas.gastos_por_categoria(session, inicio, fim)


@mcp.tool(annotations=SOMENTE_LEITURA)
def saldos() -> list[consultas.SaldoConta]:
    """Saldo atual de cada conta bancária (ativo) e cartão de crédito (passivo, negativo = dívida)."""
    with sessao_do_usuario_atual() as session:
        return consultas.saldos(session)


@mcp.tool(annotations=SOMENTE_LEITURA)
def buscar_transacoes(
    texto: str, inicio: date | None = None, fim: date | None = None, limite: int = 20
) -> list[TransacaoEncontrada]:
    """Busca híbrida de transações: por palavra (descrição do extrato) e por significado (embeddings), fundidas por Reciprocal Rank Fusion. Opcionalmente dentro de um período."""
    with sessao_do_usuario_atual() as session:
        return buscar(session, texto, obter_embedder(), inicio, fim, limite)


@mcp.tool(annotations=SOMENTE_LEITURA)
def cofrinho_do_mes(mes: str | None = None) -> cofrinho.EstadoCofrinho:
    """Teto de gastos do mês (AAAA-MM, padrão o mês atual), quanto já foi gasto, quanto ainda pode gastar por dia e os últimos gastos."""
    try:
        inicio = cofrinho.ler_mes(mes) if mes else cofrinho.hoje().replace(day=1)
    except ValueError as erro:
        raise ToolError(str(erro)) from erro
    with sessao_do_usuario_atual() as session:
        return cofrinho.estado(session, inicio)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True, openWorldHint=False))
def recategorizar(transacao_id: int, categoria: str) -> str:
    """Corrige a categoria de uma transação. A categoria precisa existir (as padrão ou uma criada pela pessoa)."""
    with sessao_do_usuario_atual() as session:
        existentes = catalogo.listar(session)
        if categoria not in existentes.todas:
            raise ToolError(
                f"categoria desconhecida: {categoria}. Existentes: {', '.join(existentes.todas)}"
            )
        try:
            aplicar_categoria(session, transacao_id, categoria, OrigemCategoria.USUARIO)
        except LookupError as erro:
            raise ToolError(str(erro)) from erro
        session.commit()
        atualizar_indice(session)
    return f"transação {transacao_id} agora é {categoria}"


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True, openWorldHint=False))
def criar_regra(padrao: str, categoria: str) -> str:
    """Cria (ou troca a categoria de) uma regra fixa: toda transação cuja descrição tem uma palavra começando com o padrão recebe essa categoria, sem passar pelo modelo. Já aplica nas transações pendentes."""
    with sessao_do_usuario_atual() as session:
        try:
            regra = regras.salvar(session, padrao, categoria)
        except regras.RegraInvalida as erro:
            raise ToolError(str(erro)) from erro
        aplicadas = regras.aplicar(session)
        atualizar_indice(session)
    return f"regra {regra.padrao} -> {regra.categoria} salva; {aplicadas} transações pendentes categorizadas"
