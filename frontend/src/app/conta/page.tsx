import type { Metadata } from "next";
import { headers } from "next/headers";
import { Suspense } from "react";

import { PainelConta, type SessaoListada } from "@/components/conta/PainelConta";
import { buscarTokensMcp } from "@/lib/api";
import { auth, googleConfigurado } from "@/lib/auth";
import { exigirUsuario, obterSessao, sessoesAtivas } from "@/lib/sessao";

export const metadata: Metadata = { title: "Conta · Capi" };

function aparelho(userAgent: string | null | undefined) {
  if (!userAgent) return "Aparelho desconhecido";
  const sistema = /Android/i.test(userAgent)
    ? "Android"
    : /iPhone|iPad/i.test(userAgent)
      ? "iPhone ou iPad"
      : /Windows/i.test(userAgent)
        ? "Windows"
        : /Mac OS/i.test(userAgent)
          ? "Mac"
          : /Linux/i.test(userAgent)
            ? "Linux"
            : "Outro sistema";
  const navegador = /Edg\//.test(userAgent)
    ? "Edge"
    : /Firefox\//.test(userAgent)
      ? "Firefox"
      : /Chrome\//.test(userAgent)
        ? "Chrome"
        : /Safari\//.test(userAgent)
          ? "Safari"
          : "navegador";
  return `${navegador} no ${sistema}`;
}

async function ContaCarregada() {
  const usuario = await exigirUsuario("/conta");
  const cabecalhos = await headers();
  const [{ sessao }, contas, sessoes, tokens] = await Promise.all([
    obterSessao(),
    auth.api.listUserAccounts({ headers: cabecalhos }),
    sessoesAtivas(usuario.id),
    buscarTokensMcp(),
  ]);
  const listadas: SessaoListada[] = sessoes
    .map((s) => ({
      id: s.id,
      aparelho: aparelho(s.userAgent),
      desde: new Date(s.createdAt).toISOString(),
      ultimoUso: new Date(s.updatedAt).toISOString(),
      atual: s.id === sessao?.session.id,
    }))
    .sort((a, b) => Number(b.atual) - Number(a.atual) || b.ultimoUso.localeCompare(a.ultimoUso));
  return (
    <PainelConta
      usuario={usuario}
      temSenha={contas.some((c) => c.providerId === "credential")}
      temGoogle={contas.some((c) => c.providerId === "google")}
      googleDisponivel={googleConfigurado}
      sessoes={listadas}
      tokens={tokens}
      urlDoMcp={`${(process.env.NOTA_API_URL_PUBLICA ?? process.env.NOTA_API_URL ?? "").replace(/\/$/, "")}/mcp`}
    />
  );
}

export default function PaginaConta() {
  return (
    <Suspense fallback={<main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-6 text-suave">Abrindo a sua conta…</main>}>
      <ContaCarregada />
    </Suspense>
  );
}
