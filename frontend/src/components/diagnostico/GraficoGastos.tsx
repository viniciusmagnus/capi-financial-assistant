"use client";

import { CircleAlert } from "lucide-react";
import { useState } from "react";

import { CorrecaoDeCategoria } from "@/components/CorrecaoDeCategoria";
import { IconeGasto } from "@/components/IconeGasto";
import { RevisarOutros } from "@/components/RevisarOutros";
import type { Categorias } from "@/lib/cofrinho";
import { type Agrupamento, type Diagnostico, type Linha, formatarDiaMes } from "@/lib/diagnostico";
import { formatarPorcento, formatarReais } from "@/lib/formato";

const VISIVEIS = 8;

function Detalhe({
  linha,
  agrupamento,
  diagnostico,
  categorias,
  modoDemo,
}: {
  linha: Linha;
  agrupamento: Agrupamento;
  diagnostico: Diagnostico;
  categorias: Categorias;
  modoDemo: boolean;
}) {
  const itens = diagnostico.transacoes.filter((t) => (agrupamento === "categoria" ? t.categoria : t.estabelecimento) === linha.chave);
  const nomes = new Map(diagnostico.estabelecimentos.map((e) => [e.chave, e.nome]));
  return (
    <div className="mb-3 rounded-xl bg-superficie p-3">
      <p className="text-xs text-suave">
        {itens.length} {itens.length === 1 ? "transação compõe" : "transações compõem"} {formatarReais(linha.total_centavos)}. A descrição é a original do extrato.
      </p>
      <ul className="mt-2 divide-y divide-borda">
        {itens.map((t) => (
          <li key={t.id} className="py-2.5">
            <div className="flex items-start justify-between gap-3 text-sm">
              <div className="min-w-0">
                <p className="break-words text-xs font-medium">{t.descricao}</p>
                <p className="text-suave">
                  {formatarDiaMes(t.data)} · {t.conta} · {t.categoria}
                </p>
                {t.revisar && (
                  <p className="mt-0.5 flex items-center gap-1 text-xs text-sol">
                    <CircleAlert className="size-3.5" aria-hidden />
                    {t.categoria === "A classificar" ? "sem categoria" : "categoria com baixa confiança"}: revise
                  </p>
                )}
              </div>
              <span className="shrink-0 tabular-nums">{formatarReais(t.valor_centavos)}</span>
            </div>
            <CorrecaoDeCategoria
              key={`${t.id}-${t.categoria}`}
              transacao={t}
              nomeLoja={nomes.get(t.estabelecimento) ?? "esse estabelecimento"}
              categorias={categorias}
              modoDemo={modoDemo}
            />
          </li>
        ))}
      </ul>
      {modoDemo && <p className="mt-2 text-xs text-suave">Na demonstração não dá para mudar categorias.</p>}
    </div>
  );
}

export function GraficoGastos({ diagnostico, categorias, modoDemo }: { diagnostico: Diagnostico; categorias: Categorias; modoDemo: boolean }) {
  const [agrupamento, setAgrupamento] = useState<Agrupamento>("categoria");
  const [selecionada, setSelecionada] = useState<string | null>(null);
  const [todas, setTodas] = useState(false);
  const linhas = agrupamento === "categoria" ? diagnostico.categorias : diagnostico.estabelecimentos;
  const maior = linhas[0]?.total_centavos ?? 1;
  const visiveis = todas ? linhas : linhas.slice(0, VISIVEIS);

  return (
    <section aria-labelledby="titulo-grafico">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="titulo-grafico" className="largo text-2xl font-bold">
          Para onde foi o dinheiro
        </h2>
        <div className="flex rounded-xl border border-borda p-1 text-sm" role="group" aria-label="Agrupar gastos por">
          {(["categoria", "estabelecimento"] as const).map((opcao) => (
            <button
              key={opcao}
              type="button"
              aria-pressed={agrupamento === opcao}
              onClick={() => {
                setAgrupamento(opcao);
                setSelecionada(null);
                setTodas(false);
              }}
              className="rounded-lg px-3 py-1.5 text-suave aria-pressed:bg-elevada aria-pressed:font-semibold aria-pressed:text-texto"
            >
              {opcao === "categoria" ? "Categorias" : "Estabelecimentos"}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <p className="min-w-0 flex-1 text-sm text-suave">
          Do maior para o menor. Toque numa linha para ver as transações e corrigir a categoria.
          {diagnostico.renda_referencia_centavos ? " % da renda do mês." : ""}
        </p>
        {!modoDemo && <RevisarOutros categorias={categorias} />}
      </div>

      {linhas.length === 0 ? (
        <p className="mt-6 text-sm text-suave">Nenhum gasto registrado neste mês.</p>
      ) : (
        <ul className="mt-4 divide-y divide-borda border-y border-borda">
          {visiveis.map((linha) => {
            const aberta = selecionada === linha.chave;
            const semCategoria = linha.categoria === "A classificar" && agrupamento === "categoria";
            return (
              <li key={linha.chave}>
                <button
                  type="button"
                  aria-expanded={aberta}
                  onClick={() => setSelecionada(aberta ? null : linha.chave)}
                  className={`w-full px-1 py-3 text-left hover:bg-superficie ${aberta ? "bg-superficie" : ""}`}
                >
                  <div className="flex items-center gap-3">
                    <IconeGasto marca={linha.marca} nome={linha.nome} categoria={linha.categoria} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate font-medium">
                          {linha.nome}
                          {semCategoria && <span className="ml-1 text-xs font-normal text-sol">(revisar)</span>}
                        </span>
                        <span className="largo shrink-0 font-semibold">{formatarReais(linha.total_centavos)}</span>
                      </div>
                      <div className="mt-1.5 h-2.5 rounded-sm bg-trilho" aria-hidden>
                        <div
                          className={`h-2.5 rounded-sm ${semCategoria ? "bg-sol" : "bg-poente"}`}
                          style={{ width: `${Math.max((linha.total_centavos / maior) * 100, 2)}%` }}
                        />
                      </div>
                      <p className="mt-2 text-sm text-suave">
                        {formatarPorcento(linha.pct_gastos)} dos gastos
                        {linha.pct_renda !== null && ` · ${formatarPorcento(linha.pct_renda)} da renda`}
                        {` · ${linha.quantidade} ${linha.quantidade === 1 ? "transação" : "transações"}`}
                        {agrupamento === "estabelecimento" && ` · ${linha.categoria}`}
                      </p>
                    </div>
                  </div>
                </button>
                {aberta && <Detalhe linha={linha} agrupamento={agrupamento} diagnostico={diagnostico} categorias={categorias} modoDemo={modoDemo} />}
              </li>
            );
          })}
        </ul>
      )}
      {linhas.length > VISIVEIS && (
        <button type="button" onClick={() => setTodas(!todas)} className="mt-3 text-sm text-suave underline-offset-4 hover:text-texto hover:underline">
          {todas ? "Mostrar só os maiores" : `Mostrar todos (${linhas.length})`}
        </button>
      )}
    </section>
  );
}
