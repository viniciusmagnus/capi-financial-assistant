"use client";

import { X } from "lucide-react";
import { useId, useMemo, useRef, useState, useTransition } from "react";

import { definirTeto } from "@/app/acoes";
import { CampoReais } from "@/components/CampoReais";
import {
  type Agrupamento,
  type Diagnostico,
  baseDoMes,
  chaveDoCorte,
  mesAtual,
  nomeDoMes,
  simular,
} from "@/lib/diagnostico";
import { formatarPorcento, formatarReais } from "@/lib/formato";

type Alvo = { tipo: Agrupamento; chave: string; nome: string; total: number };


export function Simulador({ diagnostico, modoDemo }: { diagnostico: Diagnostico; modoDemo: boolean }) {
  const idSelecao = useId();
  const [cortes, setCortes] = useState<Record<string, number>>({});
  const [escolha, setEscolha] = useState("");
  const dialogo = useRef<HTMLDialogElement>(null);
  const [teto, setTeto] = useState(0);
  const [aviso, setAviso] = useState<string | null>(null);
  const [pendente, iniciar] = useTransition();

  const alvos = useMemo(() => {
    const mapa = new Map<string, Alvo>();
    for (const c of diagnostico.categorias)
      if (c.categoria !== "A classificar") mapa.set(chaveDoCorte("categoria", c.chave), { tipo: "categoria", chave: c.chave, nome: c.nome, total: c.total_centavos });
    for (const e of diagnostico.estabelecimentos)
      mapa.set(chaveDoCorte("estabelecimento", e.chave), { tipo: "estabelecimento", chave: e.chave, nome: e.nome, total: e.total_centavos });
    return mapa;
  }, [diagnostico]);

  const base = baseDoMes(diagnostico);
  const atual = simular(diagnostico, {});
  const resultado = simular(diagnostico, cortes);
  const ativos = Object.keys(cortes).filter((k) => alvos.has(k));
  const mensal = diagnostico.base !== "periodo";
  const mes = mesAtual();

  function sugestoes() {
    const novos: Record<string, number> = {};
    for (const r of diagnostico.recomendacoes) {
      const chave = chaveDoCorte(r.alvo_tipo, r.alvo_chave);
      novos[chave] = Math.max(novos[chave] ?? 0, Math.round(r.reducao * 20) / 20);
    }
    setCortes(novos);
  }

  function abrirTeto() {
    setTeto(Math.ceil(resultado.gastos_centavos / 1000) * 1000);
    setAviso(null);
    dialogo.current?.showModal();
  }

  function confirmarTeto() {
    iniciar(async () => {
      try {
        await definirTeto(mes, teto);
        dialogo.current?.close();
        setAviso(`Teto de ${formatarReais(teto)} aplicado ao Cofrinho de ${nomeDoMes(mes).toLowerCase()}.`);
      } catch {
        setAviso("Não consegui salvar o teto. Tenta de novo?");
      }
    });
  }

  return (
    <section aria-labelledby="titulo-simulador">
      <h2 id="titulo-simulador" className="largo text-2xl font-bold">
        E se você mudasse algo?
      </h2>
      <p className="mt-1 text-sm text-suave">
        Hipóteses: nenhuma transação real muda. Valores {base.rotulo}.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <label htmlFor={idSelecao} className="sr-only">
          Escolher categoria ou estabelecimento para reduzir
        </label>
        <select
          id={idSelecao}
          value={escolha}
          onChange={(e) => {
            const chave = e.target.value;
            setEscolha("");
            if (chave) setCortes((c) => ({ ...c, [chave]: c[chave] ?? 0.2 }));
          }}
          className="w-full min-w-0 rounded-xl border border-borda bg-superficie px-3 py-2.5 text-sm text-texto sm:w-auto sm:flex-1"
        >
          <option value="">Escolher o que reduzir…</option>
          <optgroup label="Categorias">
            {[...alvos].filter(([k, a]) => a.tipo === "categoria" && !(k in cortes)).map(([k, a]) => (
              <option key={k} value={k}>
                {a.nome} ({formatarReais(a.total)})
              </option>
            ))}
          </optgroup>
          <optgroup label="Estabelecimentos">
            {[...alvos].filter(([k, a]) => a.tipo === "estabelecimento" && !(k in cortes)).map(([k, a]) => (
              <option key={k} value={k}>
                {a.nome} ({formatarReais(a.total)})
              </option>
            ))}
          </optgroup>
        </select>
        {diagnostico.recomendacoes.length > 0 && (
          <button type="button" onClick={sugestoes} className="rounded-xl border border-borda px-3 py-2.5 text-sm font-medium hover:bg-elevada">
            Usar as sugestões da Capi
          </button>
        )}
      </div>

      {ativos.length > 0 && (
        <ul className="mt-4 space-y-3">
          {ativos.map((chave) => {
            const alvo = alvos.get(chave)!;
            const fracao = cortes[chave];
            return (
              <li key={chave} className="rounded-xl bg-superficie p-3">
                <div className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium">
                    {alvo.nome} <span className="font-normal text-suave">({alvo.tipo === "categoria" ? "categoria" : "estabelecimento"})</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => setCortes((c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== chave)))}
                    aria-label={`Remover ${alvo.nome} da simulação`}
                    className="rounded-lg p-1 text-suave hover:bg-elevada hover:text-texto"
                  >
                    <X className="size-4" aria-hidden />
                  </button>
                </div>
                <div className="mt-2 flex items-center gap-3">
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={5}
                    value={Math.round(fracao * 100)}
                    onChange={(e) => setCortes((c) => ({ ...c, [chave]: Number(e.target.value) / 100 }))}
                    aria-label={`Reduzir ${alvo.nome} em porcentagem`}
                    aria-valuetext={`${Math.round(fracao * 100)}%`}
                    className="flex-1"
                  />
                  <output className="w-12 text-right text-sm font-semibold tabular-nums">−{Math.round(fracao * 100)}%</output>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {ativos.length === 0 ? (
        <p className="mt-4 text-sm text-suave">Escolha o que reduzir, ou use as sugestões da Capi, para ver quanto sobra.</p>
      ) : (
        <div className="mt-5 border-t border-borda pt-4">
          <p className="text-sm text-suave">Economia estimada {mensal ? "por mês" : "no período"}</p>
          <p className="largo text-3xl font-bold text-correnteza">{formatarReais(resultado.economia_centavos)}</p>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-suave">Da renda</dt>
              <dd className="font-semibold">
                {atual.comprometimento === null || resultado.comprometimento === null
                  ? "sem renda para comparar"
                  : `${formatarPorcento(atual.comprometimento)} → ${formatarPorcento(resultado.comprometimento)}`}
              </dd>
            </div>
            <div>
              <dt className="text-suave">{mensal ? "Renda − gastos (projeção)" : "Renda − gastos"}</dt>
              <dd className="font-semibold">
                {atual.diferenca_centavos === null || resultado.diferenca_centavos === null
                  ? "sem renda para comparar"
                  : `${formatarReais(atual.diferenca_centavos)} → ${formatarReais(resultado.diferenca_centavos)}`}
              </dd>
            </div>
          </dl>
          <p className="mt-2 text-xs text-suave">Um gasto que entra em duas reduções conta só uma vez, pela maior.</p>
        </div>
      )}

      {mensal && resultado.economia_centavos > 0 && (
        <div className="mt-4">
          <button
            type="button"
            onClick={abrirTeto}
            disabled={modoDemo}
            className="rounded-xl bg-destaque px-5 py-3 font-semibold text-sobre-destaque disabled:opacity-40"
          >
            Usar isso como teto do Cofrinho
          </button>
          {modoDemo && <p className="mt-1 text-xs text-suave">Na demonstração o Cofrinho não muda.</p>}
        </div>
      )}
      {aviso && (
        <p className="mt-3 text-sm" role="status">
          {aviso}
        </p>
      )}

      <dialog
        ref={dialogo}
        aria-labelledby="titulo-teto"
        className="m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl border border-borda bg-superficie p-5 text-texto backdrop:bg-black/60"
      >
        <h3 id="titulo-teto" className="text-lg font-semibold">
          Aplicar teto ao Cofrinho de {nomeDoMes(mes).toLowerCase()}?
        </h3>
        <p className="mt-2 text-sm text-suave">
          Sugestão: os gastos {base.rotulo} com as reduções simuladas, arredondados para cima. O teto atual do Cofrinho só muda se você
          confirmar.
        </p>
        <div className="mt-4">
          <CampoReais rotulo="Teto do mês" centavos={teto} onChange={setTeto} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={confirmarTeto}
            disabled={teto <= 0 || pendente}
            className="rounded-xl bg-destaque px-5 py-3 font-semibold text-sobre-destaque disabled:opacity-40"
          >
            {pendente ? "Salvando…" : `Confirmar teto de ${formatarReais(teto)}`}
          </button>
          <button type="button" onClick={() => dialogo.current?.close()} className="rounded-xl border border-borda px-5 py-3 font-medium hover:bg-elevada">
            Cancelar
          </button>
        </div>
      </dialog>
    </section>
  );
}
