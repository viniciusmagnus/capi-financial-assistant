"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { CorrecaoDeCategoria } from "@/components/CorrecaoDeCategoria";
import type { Categorias } from "@/lib/cofrinho";
import { type Diagnostico, nomeDoMes } from "@/lib/diagnostico";
import { formatarData, formatarReais } from "@/lib/formato";

const INICIAIS = 5;

export function GastosDoMes({ diagnostico: d, categorias, modoDemo }: { diagnostico: Diagnostico; categorias: Categorias; modoDemo: boolean }) {
  const [todos, setTodos] = useState(false);
  const [aberto, setAberto] = useState<number | null>(null);
  const gastos = d.transacoes
    .filter((t) => t.valor_centavos > 0)
    .sort((a, b) => (a.data === b.data ? b.id - a.id : b.data.localeCompare(a.data)));
  const visiveis = todos ? gastos : gastos.slice(0, INICIAIS);
  const nomes = new Map(d.estabelecimentos.map((e) => [e.chave, e.nome]));
  const mes = nomeDoMes(d.mes).split(" ")[0].toLowerCase();

  return (
    <section aria-labelledby="titulo-gastos">
      <h2 id="titulo-gastos" className="largo text-2xl font-bold">
        {todos ? `Todos os gastos de ${mes}` : "Últimos gastos"}
      </h2>
      <p className="mt-1 text-sm text-suave">Toque num gasto para trocar a categoria.</p>
      {gastos.length === 0 ? (
        <p className="mt-3 text-sm text-suave">Nada por aqui ainda.</p>
      ) : (
        <ul className="mt-3 divide-y divide-borda border-y border-borda">
          {visiveis.map((g) => {
            const expandido = aberto === g.id;
            return (
              <li key={g.id}>
                <button
                  type="button"
                  aria-expanded={expandido}
                  onClick={() => setAberto(expandido ? null : g.id)}
                  className={`flex w-full items-center justify-between gap-3 px-1 py-3 text-left text-sm hover:bg-superficie ${expandido ? "bg-superficie" : ""}`}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{g.descricao}</span>
                    <span className="block text-suave">
                      {formatarData(g.data)} · {g.categoria}
                    </span>
                  </span>
                  <span className="largo shrink-0 font-semibold">{formatarReais(g.valor_centavos)}</span>
                </button>
                {expandido && (
                  <div className="bg-superficie px-1 pb-3">
                    <CorrecaoDeCategoria
                      key={`${g.id}-${g.categoria}`}
                      transacao={g}
                      nomeLoja={nomes.get(g.estabelecimento) ?? "esse estabelecimento"}
                      categorias={categorias}
                      modoDemo={modoDemo}
                    />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {gastos.length > INICIAIS && (
        <button
          type="button"
          onClick={() => setTodos(!todos)}
          aria-expanded={todos}
          className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-borda px-4 py-2.5 text-sm font-medium hover:bg-elevada"
        >
          <ChevronDown className={`size-4 transition-transform ${todos ? "rotate-180" : ""}`} aria-hidden />
          {todos ? "Mostrar só os últimos" : `Ver todos os ${gastos.length} gastos de ${mes}`}
        </button>
      )}
    </section>
  );
}
