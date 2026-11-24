import "server-only";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { auth, autenticacaoConfigurada } from "@/lib/auth";
import type { Categoria, Categorias, Cofrinho, Fala, Regra, ResultadoCategorizacao, Sentido, TokenMcp, TokenMcpCriado, TransacaoEncontrada } from "./cofrinho";
import { paginaDeEntrada } from "./destino";
import type { Diagnostico, Renda, ResultadoImportacao } from "./diagnostico";
import type { AnaliseOutros, Decisao, ResultadoConfirmacao, ResultadoDesfazer } from "./revisao";

const API_URL = process.env.NOTA_API_URL?.replace(/\/$/, "");

export const apiConfigurada = Boolean(API_URL) && autenticacaoConfigurada;

export class SessaoExpirada extends Error {
  constructor() {
    super("sessão expirada");
  }
}

export class ErroDaApi extends Error {
  constructor(
    public status: number,
    public detalhe: string,
  ) {
    super(detalhe);
  }
}

const tokenDaSessao = cache(async (): Promise<string> => {
  const resposta = await auth.api.getToken({ headers: await headers() }).catch(() => null);
  if (!resposta?.token) throw new SessaoExpirada();
  return resposta.token;
});

export async function requisitar(caminho: string, init: RequestInit = {}): Promise<Response> {
  if (!apiConfigurada) throw new Error("API do nota-a-nota não configurada");
  const token = await tokenDaSessao();
  const cabecalhos = new Headers({ Authorization: `Bearer ${token}` });
  if (typeof init.body === "string") cabecalhos.set("Content-Type", "application/json");
  const resposta = await fetch(`${API_URL}${caminho}`, { ...init, cache: "no-store", headers: cabecalhos });
  if (resposta.status === 401) throw new SessaoExpirada();
  return resposta;
}

async function voltarParaEntrar(): Promise<never> {
  const referencia = (await headers()).get("referer");
  let volta = "/";
  if (referencia) {
    try {
      const url = new URL(referencia);
      volta = `${url.pathname}${url.search}`;
    } catch {}
  }
  redirect(paginaDeEntrada(volta, { expirou: "1" }));
}

async function chamar(caminho: string, init: RequestInit = {}) {
  let resposta: Response;
  try {
    resposta = await requisitar(caminho, init);
  } catch (erro) {
    if (erro instanceof SessaoExpirada) return voltarParaEntrar();
    throw erro;
  }
  if (!resposta.ok) throw new ErroDaApi(resposta.status, await detalhe(resposta));
  return resposta;
}

async function detalhe(resposta: Response) {
  try {
    const corpo = await resposta.json();
    if (typeof corpo?.detail === "string") return corpo.detail;
    if (Array.isArray(corpo?.detail)) return corpo.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {}
  return `a API respondeu ${resposta.status}`;
}

export async function buscarCofrinho(mes?: string): Promise<Cofrinho> {
  const consulta = mes ? `?mes=${encodeURIComponent(mes)}` : "";
  return (await chamar(`/api/cofrinho${consulta}`)).json();
}

export async function buscarFala(mes: string): Promise<Fala> {
  return (await chamar(`/api/cofrinho/fala?mes=${encodeURIComponent(mes)}`)).json();
}

export async function enviarGasto(valorCentavos: number, categoria: Categoria, descricao: string) {
  await chamar("/api/gastos/anotar", {
    method: "POST",
    body: JSON.stringify({ valor_centavos: valorCentavos, categoria, descricao: descricao || null }),
  });
}

export async function enviarTeto(mes: string, tetoCentavos: number) {
  await chamar("/api/cofrinho/teto", { method: "PUT", body: JSON.stringify({ mes, teto_centavos: tetoCentavos }) });
}

export async function removerTeto(mes: string) {
  await chamar(`/api/cofrinho/teto?mes=${encodeURIComponent(mes)}`, { method: "DELETE" });
}

export async function buscarCategorias(): Promise<Categorias> {
  return (await chamar("/api/categorias")).json();
}

export async function enviarCategoria(nome: string, sentido: Sentido): Promise<Categorias> {
  return (await chamar("/api/categorias", { method: "POST", body: JSON.stringify({ nome, sentido }) })).json();
}

export async function buscarRegras(): Promise<Regra[]> {
  return (await chamar("/api/regras")).json();
}

export async function enviarRegra(padrao: string, categoria: Categoria | null, estabelecimento: string | null = null) {
  await chamar("/api/regras", { method: "POST", body: JSON.stringify({ padrao, categoria, estabelecimento }) });
}

export async function enviarEdicaoDeRegra(id: number, padrao: string, categoria: Categoria | null, estabelecimento: string | null): Promise<Regra> {
  return (await chamar(`/api/regras/${id}`, { method: "PATCH", body: JSON.stringify({ padrao, categoria, estabelecimento }) })).json();
}

export async function pedirAnaliseDeOutros(): Promise<AnaliseOutros> {
  return (await chamar("/api/revisao/analisar", { method: "POST" })).json();
}

export async function enviarConfirmacaoDeOutros(decisoes: Decisao[], lembrar: boolean, chaveIdempotencia: string): Promise<ResultadoConfirmacao> {
  return (
    await chamar("/api/revisao/confirmar", {
      method: "POST",
      body: JSON.stringify({ decisoes, lembrar, chave_idempotencia: chaveIdempotencia }),
    })
  ).json();
}

export async function enviarDesfazerLote(id: number): Promise<ResultadoDesfazer> {
  return (await chamar(`/api/revisao/lotes/${id}/desfazer`, { method: "POST" })).json();
}

export async function removerRegra(id: number) {
  await chamar(`/api/regras/${id}`, { method: "DELETE" });
}

export async function pedirCategorizacao(importacoes: number[] = []): Promise<ResultadoCategorizacao> {
  const consulta = importacoes.length ? `?${importacoes.map((id) => `importacao_id=${id}`).join("&")}` : "";
  return (await chamar(`/api/categorizar${consulta}`, { method: "POST" })).json();
}

export async function buscarTransacoes(q: string): Promise<TransacaoEncontrada[]> {
  return (await chamar(`/api/busca?q=${encodeURIComponent(q)}&limite=30`)).json();
}

export async function abrirChat(corpo: string) {
  return requisitar("/api/chat", { method: "POST", body: corpo });
}

export async function buscarRenda(): Promise<Renda | null> {
  return (await chamar("/api/renda")).json();
}

export async function enviarRenda(valorCentavos: number, variavel: boolean): Promise<Renda> {
  return (await chamar("/api/renda", { method: "PUT", body: JSON.stringify({ valor_centavos: valorCentavos, variavel }) })).json();
}

export async function buscarDiagnostico(mes?: string): Promise<Diagnostico> {
  const consulta = mes ? `?mes=${encodeURIComponent(mes)}` : "";
  return (await chamar(`/api/diagnostico${consulta}`)).json();
}

export async function enviarExtrato(formulario: FormData): Promise<ResultadoImportacao> {
  const resposta = await requisitar("/api/importar", { method: "POST", body: formulario });
  if (!resposta.ok) throw new ErroDaApi(resposta.status, await detalhe(resposta));
  return resposta.json();
}

export async function enviarCorrecao(transacaoId: number, categoria: Categoria, criarRegra: boolean) {
  const resposta = await chamar(`/api/transacoes/${transacaoId}/categoria`, {
    method: "PATCH",
    body: JSON.stringify({ categoria, criar_regra: criarRegra }),
  });
  return (await resposta.json()) as { categoria: string; regra: Regra | null; outras_categorizadas: number };
}

export async function buscarTokensMcp(): Promise<TokenMcp[]> {
  return (await chamar("/api/tokens-mcp")).json();
}

export async function criarTokenMcp(nome: string): Promise<TokenMcpCriado> {
  return (await chamar("/api/tokens-mcp", { method: "POST", body: JSON.stringify({ nome }) })).json();
}

export async function revogarTokenMcp(id: number) {
  await chamar(`/api/tokens-mcp/${id}`, { method: "DELETE" });
}
