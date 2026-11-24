import Link from "next/link";
import { Suspense } from "react";

import { buscarTransacoes } from "@/lib/api";
import { formatarData, formatarReais } from "@/lib/formato";
import { exigirUsuario } from "@/lib/sessao";

const SUGESTOES = ["comida fora", "transporte", "zaffari", "pagamento do cartão"];

async function Resultados({ searchParams }: { searchParams: PageProps<"/busca">["searchParams"] }) {
  const { q } = await searchParams;
  const termo = typeof q === "string" ? q.trim() : "";
  await exigirUsuario(termo ? `/busca?q=${encodeURIComponent(termo)}` : "/busca");

  return (
    <>
      <form action="/busca" className="mt-6 flex gap-2">
        <input
          name="q"
          defaultValue={termo}
          minLength={2}
          maxLength={200}
          placeholder="ex.: comida fora, transporte, zaffari"
          className="min-w-0 flex-1 rounded-xl border border-borda bg-superficie px-4 py-3 outline-none focus:border-destaque"
        />
        <button type="submit" className="rounded-xl bg-destaque px-4 py-3 font-semibold text-sobre-destaque">
          Buscar
        </button>
      </form>

      {termo.length < 2 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {SUGESTOES.map((s) => (
            <Link key={s} href={`/busca?q=${encodeURIComponent(s)}`} className="rounded-full border border-borda px-3 py-1.5 text-sm text-suave hover:bg-trilho">
              {s}
            </Link>
          ))}
        </div>
      ) : (
        <Lista termo={termo} />
      )}
    </>
  );
}

async function Lista({ termo }: { termo: string }) {
  const achadas = await buscarTransacoes(termo);
  if (achadas.length === 0) {
    return <p className="mt-6 text-sm text-suave">Nada encontrado para “{termo}”.</p>;
  }
  return (
    <ul className="mt-6 divide-y divide-borda rounded-2xl border border-borda bg-superficie px-4">
      {achadas.map((t) => (
        <li key={t.id} className="flex items-center justify-between gap-3 py-3 text-sm">
          <div className="min-w-0">
            <p className="truncate">{t.descricao}</p>
            <p className="text-suave">
              {formatarData(t.data)} · {t.categoria}
            </p>
            <div className="mt-1 flex gap-1">
              {t.encontrada_por.map((origem) => (
                <span key={origem} className="rounded-full bg-trilho px-2 py-0.5 text-[11px] text-suave">
                  por {origem}
                </span>
              ))}
            </div>
          </div>
          <span className={`shrink-0 tabular-nums ${t.valor_centavos > 0 ? "text-entrada" : ""}`}>{formatarReais(t.valor_centavos)}</span>
        </li>
      ))}
    </ul>
  );
}

export default function PaginaBusca({ searchParams }: PageProps<"/busca">) {
  return (
    <main className="mx-auto w-full max-w-md flex-1 px-4 pb-10 pt-6">
      <h1 className="text-2xl font-semibold tracking-tight">Buscar gastos</h1>
      <p className="mt-2 text-sm text-suave">
        Procura pelo nome que aparece no extrato e pelo assunto ao mesmo tempo: “comida fora” acha a padaria e o iFood sem essas palavras estarem lá.
      </p>
      <Suspense fallback={<p className="mt-6 text-sm text-suave">Buscando…</p>}>
        <Resultados searchParams={searchParams} />
      </Suspense>
    </main>
  );
}
