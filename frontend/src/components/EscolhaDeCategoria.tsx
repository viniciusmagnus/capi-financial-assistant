"use client";

import { useState } from "react";

import { criarCategoria } from "@/app/acoes";
import type { Categorias } from "@/lib/cofrinho";

const NOVA = "__nova__";

export function EscolhaDeCategoria({
  categorias,
  valor,
  aoMudar,
  aoCriar,
  vazio,
  rotulo,
}: {
  categorias: Categorias;
  valor: string;
  aoMudar: (categoria: string) => void;
  aoCriar: (categorias: Categorias) => void;
  vazio: string;
  rotulo: string;
}) {
  const [criando, setCriando] = useState(false);
  const [nome, setNome] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  async function criar() {
    const limpo = nome.trim().replace(/\s+/g, " ");
    if (limpo.length < 2) return;
    setSalvando(true);
    setErro(null);
    const r = await criarCategoria(limpo, "despesa");
    setSalvando(false);
    if (!r.ok) {
      setErro(r.erro.charAt(0).toUpperCase() + r.erro.slice(1) + ".");
      return;
    }
    const criada = r.categorias.criadas.find((c) => c.toLowerCase() === limpo.toLowerCase()) ?? limpo;
    aoCriar(r.categorias);
    aoMudar(criada);
    setCriando(false);
    setNome("");
  }

  if (criando) {
    return (
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        <label className="min-w-0 flex-1">
          <span className="sr-only">Nome da nova categoria</span>
          <input
            autoFocus
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void criar();
              }
              if (e.key === "Escape") setCriando(false);
            }}
            maxLength={40}
            placeholder="Nome da nova categoria"
            className="w-full rounded-lg border border-borda bg-fundo px-2.5 py-1.5 text-sm outline-none focus:border-poente"
          />
        </label>
        <button type="button" disabled={salvando || nome.trim().length < 2} onClick={criar} className="rounded-lg border border-borda px-2.5 py-1.5 text-sm hover:bg-elevada disabled:opacity-40">
          {salvando ? "Criando…" : "Criar"}
        </button>
        <button type="button" onClick={() => setCriando(false)} className="px-1.5 py-1.5 text-sm text-suave hover:text-texto">
          Cancelar
        </button>
        {erro && (
          <p role="alert" className="w-full text-xs text-brasa">
            {erro}
          </p>
        )}
      </div>
    );
  }

  return (
    <label className="min-w-0 flex-1">
      <span className="sr-only">{rotulo}</span>
      <select
        value={valor}
        onChange={(e) => (e.target.value === NOVA ? setCriando(true) : aoMudar(e.target.value))}
        className="w-full rounded-lg border border-borda bg-fundo px-2.5 py-1.5 text-sm outline-none focus:border-poente"
      >
        <option value="">{vazio}</option>
        {categorias.despesa
          .filter((c) => c !== "Outros")
          .map((c) => (
            <option key={c}>{c}</option>
          ))}
        <option value={NOVA}>+ Nova categoria…</option>
      </select>
    </label>
  );
}
