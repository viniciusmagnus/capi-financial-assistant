import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { Painel } from "@/components/inicio/Painel";
import { CATEGORIAS_PADRAO } from "@/lib/cofrinho";
import { cofrinhoDemo } from "@/lib/demo-cofrinho";
import { diagnosticoDemo } from "@/lib/demo-diagnostico";

export const metadata: Metadata = { title: "Demonstração · Capi" };

async function PainelDeDemonstracao() {
  await connection();
  return (
    <Painel diagnostico={diagnosticoDemo} cofrinho={{ ...cofrinhoDemo, mes: diagnosticoDemo.mes }} categorias={CATEGORIAS_PADRAO} modoDemo />
  );
}

export default function Demonstracao() {
  return (
    <Suspense fallback={<main className="mx-auto w-full max-w-3xl flex-1 px-4 pt-6 text-suave">Montando a demonstração…</main>}>
      <PainelDeDemonstracao />
    </Suspense>
  );
}
