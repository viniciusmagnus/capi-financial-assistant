"use server";

import { refresh } from "next/cache";
import { headers } from "next/headers";
import { unstable_rethrow } from "next/navigation";

import {
  ErroDaApi,
  criarTokenMcp,
  enviarCategoria,
  enviarConfirmacaoDeOutros,
  enviarCorrecao,
  enviarDesfazerLote,
  enviarEdicaoDeRegra,
  enviarGasto,
  enviarRegra,
  enviarRenda,
  enviarTeto,
  pedirAnaliseDeOutros,
  pedirCategorizacao,
  removerRegra,
  removerTeto,
  revogarTokenMcp,
} from "@/lib/api";
import { auth } from "@/lib/auth";
import type { Categoria, Sentido } from "@/lib/cofrinho";
import type { Decisao, Resultado } from "@/lib/revisao";

const LIMITE_DECISOES = 500;

function falha(erro: string, status?: number) {
  return { ok: false as const, erro, status };
}

async function tentar<T>(fn: () => Promise<T>): Promise<Resultado<T>> {
  try {
    return { ok: true, dados: await fn() };
  } catch (erro) {
    unstable_rethrow(erro);
    if (erro instanceof ErroDaApi) return falha(erro.detalhe, erro.status);
    return falha("não consegui falar com a API");
  }
}

function idValido(id: unknown): id is number {
  return Number.isInteger(id) && (id as number) > 0;
}

function textoOuNulo(valor: unknown, maximo: number): string | null {
  if (typeof valor !== "string") return null;
  const limpo = valor.replace(/\s+/g, " ").trim();
  return limpo ? limpo.slice(0, maximo) : null;
}

export async function analisarOutros() {
  return tentar(() => pedirAnaliseDeOutros());
}

const ORIGENS = new Set(["usuario", "historico", "pesquisa"]);

export async function confirmarOutros(decisoes: Decisao[], lembrar: boolean, chaveIdempotencia: string) {
  if (!Array.isArray(decisoes) || decisoes.length === 0 || decisoes.length > LIMITE_DECISOES) return falha("nenhuma alteração aprovada");
  if (typeof chaveIdempotencia !== "string" || !/^[A-Za-z0-9_-]{8,64}$/.test(chaveIdempotencia)) return falha("chave inválida");
  const limpas: Decisao[] = [];
  for (const d of decisoes) {
    if (!idValido(d?.transacao_id) || !categoriaValida(d?.categoria)) return falha("decisão inválida");
    limpas.push({
      transacao_id: d.transacao_id,
      categoria: d.categoria.trim(),
      estabelecimento: textoOuNulo(d.estabelecimento, 80),
      origem: ORIGENS.has(d.origem) ? d.origem : "usuario",
    });
  }
  const resultado = await tentar(() => enviarConfirmacaoDeOutros(limpas, lembrar === true, chaveIdempotencia));
  if (resultado.ok) refresh();
  return resultado;
}

export async function desfazerLote(id: number) {
  if (!idValido(id)) return falha("lote inválido");
  const resultado = await tentar(() => enviarDesfazerLote(id));
  if (resultado.ok) refresh();
  return resultado;
}

function validarValor(centavos: number) {
  if (!Number.isInteger(centavos) || centavos <= 0 || centavos > 100_000_000) {
    throw new Error("valor inválido");
  }
}

function categoriaValida(categoria: unknown): categoria is Categoria {
  return typeof categoria === "string" && categoria.trim().length > 0 && categoria.length <= 80;
}

export async function anotarGasto(valorCentavos: number, categoria: Categoria, descricao: string) {
  validarValor(valorCentavos);
  if (!categoriaValida(categoria)) throw new Error("categoria inválida");
  await enviarGasto(valorCentavos, categoria, descricao.trim().slice(0, 200));
  refresh();
}

export async function definirTeto(mes: string, tetoCentavos: number) {
  validarValor(tetoCentavos);
  if (!/^\d{4}-\d{2}$/.test(mes)) throw new Error("mês inválido");
  await enviarTeto(mes, tetoCentavos);
  refresh();
}

export async function voltarAoSalario(mes: string) {
  if (!/^\d{4}-\d{2}$/.test(mes)) throw new Error("mês inválido");
  await removerTeto(mes);
  refresh();
}

export async function salvarRegra(padrao: string, categoria: Categoria) {
  const limpo = padrao.trim();
  if (limpo.length < 3 || limpo.length > 120) throw new Error("padrão inválido");
  if (!categoriaValida(categoria)) throw new Error("categoria inválida");
  const resultado = await tentar(() => enviarRegra(limpo, categoria));
  if (resultado.ok) refresh();
  return resultado;
}

export async function editarRegra(id: number, padrao: string, categoria: Categoria | null, estabelecimento: string | null) {
  if (!idValido(id)) return falha("regra inválida");
  if (typeof padrao !== "string" || padrao.trim().length < 3 || padrao.length > 120) return falha("o padrão precisa ter de 3 a 120 letras");
  if (categoria !== null && !categoriaValida(categoria)) return falha("categoria inválida");
  const nome = textoOuNulo(estabelecimento, 80);
  if (categoria === null && nome === null) return falha("defina uma categoria, um estabelecimento ou os dois");
  const resultado = await tentar(() => enviarEdicaoDeRegra(id, padrao.trim(), categoria, nome));
  if (resultado.ok) refresh();
  return resultado;
}

export async function apagarRegra(id: number) {
  if (!Number.isInteger(id) || id <= 0) throw new Error("regra inválida");
  await removerRegra(id);
  refresh();
}

export async function criarCategoria(nome: string, sentido: Sentido) {
  if (typeof nome !== "string" || nome.trim().length < 2 || nome.length > 80) return { ok: false as const, erro: "o nome precisa ter de 2 a 40 caracteres" };
  if (sentido !== "despesa" && sentido !== "receita") return { ok: false as const, erro: "tipo inválido" };
  try {
    const categorias = await enviarCategoria(nome.trim(), sentido);
    refresh();
    return { ok: true as const, categorias };
  } catch (erro) {
    unstable_rethrow(erro);
    return { ok: false as const, erro: erro instanceof ErroDaApi ? erro.detalhe : "não consegui falar com a API" };
  }
}

export async function categorizarPendentes() {
  const resultado = await pedirCategorizacao();
  refresh();
  return resultado;
}

export async function salvarRenda(valorCentavos: number, variavel: boolean) {
  if (!Number.isInteger(valorCentavos) || valorCentavos < 0 || valorCentavos > 100_000_000_000) {
    throw new Error("renda inválida");
  }
  const renda = await enviarRenda(valorCentavos, Boolean(variavel));
  refresh();
  return renda;
}

export async function categorizarImportacoes(importacoes: number[]) {
  if (!Array.isArray(importacoes) || importacoes.length === 0 || importacoes.length > 50) throw new Error("importações inválidas");
  if (!importacoes.every((id) => Number.isInteger(id) && id > 0)) throw new Error("importação inválida");
  const resultado = await pedirCategorizacao(importacoes);
  refresh();
  return resultado;
}

export async function corrigirCategoria(transacaoId: number, categoria: Categoria, criarRegra: boolean) {
  if (!Number.isInteger(transacaoId) || transacaoId <= 0) return { ok: false as const, erro: "transação inválida" };
  if (!categoriaValida(categoria)) return { ok: false as const, erro: "categoria inválida" };
  try {
    const resultado = await enviarCorrecao(transacaoId, categoria, Boolean(criarRegra));
    refresh();
    return { ok: true as const, ...resultado };
  } catch (erro) {
    unstable_rethrow(erro);
    return { ok: false as const, erro: erro instanceof ErroDaApi ? erro.detalhe : "não consegui falar com a API" };
  }
}

export async function novoTokenDoMcp(nome: string) {
  const limpo = typeof nome === "string" ? nome.trim().slice(0, 60) : "";
  if (!limpo) return { ok: false as const, erro: "Dê um nome para lembrar onde o token está." };
  try {
    const criado = await criarTokenMcp(limpo);
    refresh();
    return { ok: true as const, ...criado };
  } catch (erro) {
    unstable_rethrow(erro);
    return { ok: false as const, erro: erro instanceof ErroDaApi ? erro.detalhe : "não consegui falar com a API" };
  }
}

export async function apagarTokenDoMcp(id: number) {
  if (!Number.isInteger(id) || id <= 0) throw new Error("token inválido");
  await revogarTokenMcp(id);
  refresh();
}

export async function encerrarSessao(id: string) {
  if (typeof id !== "string" || id.length === 0 || id.length > 200) throw new Error("sessão inválida");
  const cabecalhos = await headers();
  const sessoes = await auth.api.listSessions({ headers: cabecalhos });
  const alvo = sessoes.find((s) => s.id === id);
  if (!alvo) return { ok: false as const };
  await auth.api.revokeSession({ headers: cabecalhos, body: { token: alvo.token } });
  refresh();
  return { ok: true as const };
}
