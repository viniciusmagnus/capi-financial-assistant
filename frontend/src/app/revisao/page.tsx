import type { Metadata } from "next";
import { Suspense } from "react";

import { Revisao } from "@/components/revisao/Revisao";
import { buscarCategorias, buscarContasDaRevisao, buscarLotesDaRevisao, buscarRevisao } from "@/lib/api";
import { exigirUsuario } from "@/lib/sessao";

export const metadata: Metadata = { title: "Revisar Outros · Capi" };

async function RevisaoCarregada() {
  await exigirUsuario("/revisao");
  const [pagina, contas, categorias, lotes] = await Promise.all([buscarRevisao({}), buscarContasDaRevisao(), buscarCategorias(), buscarLotesDaRevisao()]);
  return <Revisao inicial={pagina} contas={contas} categorias={categorias} lotesIniciais={lotes} />;
}

export default function PaginaRevisao() {
  return (
    <Suspense fallback={<main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 text-suave">Carregando a revisão…</main>}>
      <RevisaoCarregada />
    </Suspense>
  );
}
