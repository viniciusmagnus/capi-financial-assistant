import { Capivara } from "@/components/Capivara";
import type { Humor } from "@/lib/cofrinho";
import type { Diagnostico } from "@/lib/diagnostico";
import { formatarReais } from "@/lib/formato";

function humorGeral(d: Diagnostico): Humor {
  if (d.comprometimento === null) return d.recomendacoes.length ? "de_olho" : "tranquila";
  if (d.comprometimento > 1) return "estourou";
  if (d.comprometimento > 0.85) return "apertada";
  if (d.recomendacoes.length) return "de_olho";
  return "tranquila";
}

export function InsightsCapi({ diagnostico }: { diagnostico: Diagnostico }) {
  const { recomendacoes } = diagnostico;
  const unidade = diagnostico.base === "periodo" ? "no período" : "por mês";
  const soma = recomendacoes.reduce((total, r) => total + r.economia_centavos, 0);

  return (
    <section aria-labelledby="titulo-capi">
      <div className="flex items-end gap-3">
        <Capivara humor={humorGeral(diagnostico)} className="w-16 shrink-0" />
        <div className="pb-1">
          <h2 id="titulo-capi" className="largo text-2xl font-bold">
            O que a Capi viu
          </h2>
          <p className="text-sm text-suave">Até três sugestões, só com o que está no extrato.</p>
        </div>
      </div>

      {recomendacoes.length === 0 ? (
        <p className="mt-4 text-sm">
          Nada se destacou o bastante para virar sugestão. Ou você está no controle, ou o extrato ainda está curto. A Capi vai fingir que é a primeira
          opção.
        </p>
      ) : (
        <ol className="mt-5 divide-y divide-borda border-y border-borda">
          {recomendacoes.map((r) => (
            <li key={r.id} className="py-5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h3 className="text-lg font-semibold">{r.titulo}</h3>
                <p className="text-sm">
                  <span className="largo font-bold text-correnteza">{formatarReais(r.economia_centavos)}</span>{" "}
                  <span className="text-suave">{unidade} de economia possível</span>
                </p>
              </div>
              <p className="mt-2 max-w-[65ch] text-sm">{r.fato}</p>
              <p className="mt-1 max-w-[65ch] text-sm text-suave">{r.consequencia}</p>
              <p className="mt-2 max-w-[65ch] text-sm">
                <span className="font-semibold">O que fazer: </span>
                {r.acao}
              </p>
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer text-suave hover:text-texto">Como a conta foi feita</summary>
                <p className="mt-1 max-w-[65ch]">{r.calculo}</p>
              </details>
              {r.capi && (
                <p className="relative mt-4 inline-block max-w-[52ch] rounded-2xl rounded-bl-sm bg-balao px-4 py-2.5 text-sm text-balao-texto">
                  <span className="font-semibold">Capi: </span>
                  {r.capi}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}

      {recomendacoes.length > 1 && (
        <p className="mt-4 text-sm">
          Seguindo todas, a economia estimada é de <strong className="text-correnteza">{formatarReais(diagnostico.economia_combinada_centavos)}</strong>{" "}
          {unidade}
          {diagnostico.economia_combinada_centavos < soma &&
            `, menos que a soma (${formatarReais(soma)}), porque algumas sugestões atingem os mesmos gastos e eles não contam duas vezes`}
          .
        </p>
      )}
    </section>
  );
}
