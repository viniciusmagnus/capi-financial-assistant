import "server-only";

import { getSessionCookie } from "better-auth/cookies";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { connection } from "next/server";
import { cache } from "react";

import { apiConfigurada } from "@/lib/api";
import { auth } from "@/lib/auth";
import { paginaDeEntrada } from "@/lib/destino";

export type Usuario = { id: string; nome: string; email: string };

export const obterSessao = cache(async () => {
  const cabecalhos = await headers();
  const sessao = await auth.api.getSession({ headers: cabecalhos }).catch(() => null);
  return { sessao, tinhaCookie: Boolean(getSessionCookie(cabecalhos, { cookiePrefix: "capi" })) };
});

export async function sessoesAtivas(usuarioId: string) {
  const contexto = await auth.$context;
  const sessoes = await contexto.internalAdapter.listSessions(usuarioId, { onlyActiveSessions: true });
  const agora = new Date();
  return sessoes.filter((s) => new Date(s.expiresAt) > agora);
}

export async function exigirUsuario(volta: string): Promise<Usuario> {
  await connection();
  if (!apiConfigurada) redirect("/demonstracao");
  const { sessao, tinhaCookie } = await obterSessao();
  if (!sessao) redirect(paginaDeEntrada(volta, tinhaCookie ? { expirou: "1" } : {}));
  if (!sessao.user.emailVerified) redirect("/verificar-email");
  return { id: sessao.user.id, nome: sessao.user.name, email: sessao.user.email };
}

export function mesmaOrigem(request: Request): boolean {
  const esperada = new URL(process.env.BETTER_AUTH_URL ?? "http://localhost:3100").origin;
  const origem = request.headers.get("origin");
  if (origem) return origem === esperada;
  const site = request.headers.get("sec-fetch-site");
  return site === "same-origin";
}
