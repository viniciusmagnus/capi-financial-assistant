"use client";

import { Capivara } from "@/components/Capivara";

export default function Erro({ retry }: { error: unknown; retry: () => void }) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
      <Capivara humor="apertada" className="w-32 text-texto" />
      <p className="text-lg font-medium">Não consegui falar com a API.</p>
      <p className="text-sm text-suave">Confere se o backend está no ar e se o token do front é o mesmo do backend.</p>
      <button type="button" onClick={() => retry()} className="rounded-2xl bg-destaque px-5 py-3 font-semibold text-sobre-destaque">
        Tentar de novo
      </button>
    </main>
  );
}
