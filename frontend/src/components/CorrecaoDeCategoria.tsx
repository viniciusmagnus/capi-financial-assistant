"use client";

import { useId, useState, useTransition } from "react";

import { corrigirCategoria } from "@/app/acoes";
import { OpcoesDeCategoria } from "@/components/OpcoesDeCategoria";
import type { Categorias } from "@/lib/cofrinho";
import type { TransacaoDiagnostico } from "@/lib/diagnostico";

export function CorrecaoDeCategoria({
  transacao,
  nomeLoja,
  categorias,
  modoDemo,
}: {
  transacao: TransacaoDiagnostico;
  nomeLoja: string;
  categorias: Categorias;
  modoDemo: boolean;
}) {
  const id = useId();
  const conhecida = [...categorias.despesa, categorias.transferencia].includes(transacao.categoria);
  const [categoria, setCategoria] = useState(conhecida ? transacao.categoria : "");
  const [criarRegra, setCriarRegra] = useState(false);
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [pendente, iniciar] = useTransition();
  const mudou = categoria !== "" && categoria !== transacao.categoria;

  function salvar() {
    const escolhida = categoria;
    if (escolhida === "" || escolhida === transacao.categoria) return;
    setMensagem(null);
    iniciar(async () => {
      const r = await corrigirCategoria(transacao.id, escolhida, criarRegra);
      if (!r.ok) setMensagem(r.erro);
      else if (r.regra) setMensagem(`Salvo. Regra ${r.regra.padrao} → ${r.regra.categoria} criada; ${r.outras_categorizadas} outras ajustadas.`);
      else setMensagem("Salvo.");
    });
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
      <label htmlFor={id} className="sr-only">
        Categoria de {transacao.descricao}
      </label>
      <select
        id={id}
        value={categoria}
        disabled={modoDemo || pendente}
        onChange={(e) => setCategoria(e.target.value)}
        className="min-w-0 rounded-lg border border-borda bg-fundo px-2 py-1.5 text-texto"
      >
        {!conhecida && <option value="">{transacao.categoria}</option>}
        <OpcoesDeCategoria categorias={categorias} sentido="despesa" />
      </select>
      {mudou && (
        <>
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={criarRegra} onChange={(e) => setCriarRegra(e.target.checked)} />
            sempre que for {nomeLoja}
          </label>
          <button type="button" onClick={salvar} disabled={pendente} className="rounded-lg bg-destaque px-3 py-1.5 font-semibold text-sobre-destaque">
            {pendente ? "Salvando…" : "Salvar"}
          </button>
        </>
      )}
      {mensagem && (
        <span className="text-suave" role="status">
          {mensagem}
        </span>
      )}
    </div>
  );
}
