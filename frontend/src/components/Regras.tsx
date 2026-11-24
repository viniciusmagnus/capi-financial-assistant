"use client";

import { X } from "lucide-react";
import { useState, useTransition } from "react";

import { apagarRegra, categorizarPendentes, criarCategoria, salvarRegra } from "@/app/acoes";
import { OpcoesDeCategoria } from "@/components/OpcoesDeCategoria";
import type { Categoria, Categorias, Regra, ResultadoCategorizacao, Sentido } from "@/lib/cofrinho";

function normalizar(texto: string) {
  return texto.normalize("NFKD").replace(/[̀-ͯ]/g, "").toUpperCase().split(/\s+/).filter(Boolean).join(" ");
}

function resumo(r: ResultadoCategorizacao) {
  const partes = [`${r.por_regra} por regra`];
  if (r.enviadas_ao_claude > 0) partes.push(`${r.pelo_claude} pelo Claude`);
  partes.push(r.pendentes === 0 ? "nada pendente" : `${r.pendentes} ainda sem categoria`);
  return partes.join(" · ");
}

function NovaCategoria({
  modoDemo,
  aoCriar,
}: {
  modoDemo: boolean;
  aoCriar: (nome: string, sentido: Sentido, categorias?: Categorias) => void;
}) {
  const [nome, setNome] = useState("");
  const [sentido, setSentido] = useState<Sentido>("despesa");
  const [erro, setErro] = useState<string | null>(null);
  const [pendente, iniciar] = useTransition();

  return (
    <form
      className="mt-3 space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const limpo = nome.trim().replace(/\s+/g, " ");
        if (limpo.length < 2) return;
        setErro(null);
        iniciar(async () => {
          if (modoDemo) {
            aoCriar(limpo.charAt(0).toUpperCase() + limpo.slice(1), sentido);
            setNome("");
            return;
          }
          const r = await criarCategoria(limpo, sentido);
          if (!r.ok) {
            setErro(r.erro.charAt(0).toUpperCase() + r.erro.slice(1) + ".");
            return;
          }
          const criada = r.categorias.criadas.find((c) => c.toLowerCase() === limpo.toLowerCase()) ?? limpo;
          aoCriar(criada, sentido, r.categorias);
          setNome("");
        });
      }}
    >
      <label className="block">
        <span className="text-sm text-suave">Nome</span>
        <input
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          maxLength={40}
          placeholder="ex.: Celular e internet"
          className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2.5 outline-none focus:border-poente"
        />
      </label>
      <div className="flex rounded-xl border border-borda p-1 text-sm" role="group" aria-label="Tipo da categoria">
        {(["despesa", "receita"] as const).map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={sentido === s}
            onClick={() => setSentido(s)}
            className="flex-1 rounded-lg px-3 py-1.5 text-suave aria-pressed:bg-elevada aria-pressed:font-semibold aria-pressed:text-texto"
          >
            {s === "despesa" ? "Gasto" : "Entrada"}
          </button>
        ))}
      </div>
      {erro && (
        <p className="text-sm text-brasa" role="alert">
          {erro}
        </p>
      )}
      <button
        type="submit"
        disabled={nome.trim().length < 2 || pendente}
        className="w-full rounded-xl border border-borda px-4 py-2.5 font-semibold hover:bg-elevada disabled:opacity-40"
      >
        {pendente ? "Criando…" : "Criar categoria"}
      </button>
    </form>
  );
}

export function Regras({ iniciais, categorias: categoriasIniciais, modoDemo }: { iniciais: Regra[]; categorias: Categorias; modoDemo: boolean }) {
  const [demo, setDemo] = useState(iniciais);
  const lista = modoDemo ? demo : iniciais;
  const [categorias, setCategorias] = useState(categoriasIniciais);
  const [padrao, setPadrao] = useState("");
  const [categoria, setCategoria] = useState<Categoria>(categoriasIniciais.despesa[0] ?? "Outros");
  const [pendente, iniciar] = useTransition();
  const [aviso, setAviso] = useState<string | null>(null);

  function executar(acao: () => Promise<string | void>) {
    setAviso(null);
    iniciar(async () => {
      try {
        const mensagem = await acao();
        if (mensagem) setAviso(mensagem);
      } catch {
        setAviso("Não consegui falar com a API. Tenta de novo?");
      }
    });
  }

  function adicionar() {
    const limpo = normalizar(padrao);
    if (limpo.length < 3) return;
    executar(async () => {
      if (modoDemo) {
        setDemo((atual) => [...atual.filter((r) => r.padrao !== limpo), { id: Date.now(), padrao: limpo, categoria }].sort((a, b) => a.padrao.localeCompare(b.padrao)));
      } else {
        await salvarRegra(limpo, categoria);
      }
      setPadrao("");
    });
  }

  function remover(id: number) {
    executar(async () => {
      if (modoDemo) setDemo((atual) => atual.filter((r) => r.id !== id));
      else await apagarRegra(id);
    });
  }

  return (
    <main className="mx-auto w-full max-w-md flex-1 px-4 pb-10 pt-6">
      {modoDemo && <p className="mb-4 rounded-xl bg-destaque-fundo px-3 py-2 text-sm text-poente">Demonstração: nada aqui é salvo.</p>}

      <h1 className="largo text-2xl font-bold">Regras de categoria</h1>
      <p className="mt-2 text-sm text-suave">
        Quando a descrição do extrato tem uma palavra que começa com o padrão, a transação ganha a categoria na hora, sem gastar token. Se
        duas regras servem, vale a mais longa. O que nenhuma regra pega vai para o Claude.
      </p>

      <form
        className="mt-6 rounded-2xl border border-borda bg-superficie p-4"
        onSubmit={(e) => {
          e.preventDefault();
          adicionar();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
          <label className="block">
            <span className="text-sm text-suave">Se a descrição tiver</span>
            <input
              value={padrao}
              onChange={(e) => setPadrao(e.target.value)}
              maxLength={120}
              placeholder="ex.: TIM"
              className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2.5 uppercase outline-none focus:border-poente"
            />
          </label>
          <label className="block">
            <span className="text-sm text-suave">vira</span>
            <select
              value={categoria}
              onChange={(e) => setCategoria(e.target.value)}
              className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2.5 text-texto outline-none focus:border-poente"
            >
              <OpcoesDeCategoria categorias={categorias} />
            </select>
          </label>
        </div>
        <button
          type="submit"
          disabled={normalizar(padrao).length < 3 || pendente}
          className="mt-3 w-full rounded-xl bg-destaque px-4 py-2.5 font-semibold text-sobre-destaque disabled:opacity-40"
        >
          Salvar regra
        </button>
      </form>

      <section aria-labelledby="titulo-categorias" className="mt-6 rounded-2xl border border-borda bg-superficie p-4">
        <h2 id="titulo-categorias" className="font-semibold">
          Suas categorias
        </h2>
        <p className="mt-1 text-sm text-suave">Falta alguma? Crie aqui e ela aparece nas regras, na correção do gráfico, no anotar gasto e para a IA.</p>
        {categorias.criadas.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2">
            {categorias.criadas.map((c) => (
              <li key={c} className="rounded-lg border border-borda px-2.5 py-1 text-sm">
                {c} <span className="text-suave">· {categorias.receita.includes(c) ? "entrada" : "gasto"}</span>
              </li>
            ))}
          </ul>
        )}
        <NovaCategoria
          modoDemo={modoDemo}
          aoCriar={(nome, sentido, novas) => {
            setCategorias(
              novas ??
                ((atual) => ({
                  ...atual,
                  despesa: sentido === "despesa" ? [...atual.despesa, nome] : atual.despesa,
                  receita: sentido === "receita" ? [...atual.receita, nome] : atual.receita,
                  criadas: [...atual.criadas, nome].sort((a, b) => a.localeCompare(b)),
                }))(categorias),
            );
            setCategoria(nome);
            setAviso(`Categoria ${nome} criada. Já dá para usar na regra acima.`);
          }}
        />
      </section>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={modoDemo || pendente}
          onClick={() => executar(async () => resumo(await categorizarPendentes()))}
          className="rounded-xl border border-borda bg-superficie px-4 py-2.5 text-sm font-medium hover:bg-elevada disabled:opacity-40"
        >
          {pendente ? "Categorizando…" : "Categorizar pendentes"}
        </button>
        {aviso && (
          <p className="text-sm text-suave" aria-live="polite">
            {aviso}
          </p>
        )}
      </div>

      <ul className="mt-6 divide-y divide-borda rounded-2xl border border-borda bg-superficie px-4">
        {lista.map((r) => (
          <li key={r.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold tracking-wide">{r.padrao}</p>
              <p className="text-suave">{r.categoria}</p>
            </div>
            <button
              type="button"
              onClick={() => remover(r.id)}
              disabled={pendente}
              aria-label={`Apagar a regra ${r.padrao}`}
              className="shrink-0 rounded-lg p-1.5 text-suave hover:bg-elevada hover:text-texto"
            >
              <X className="size-4" aria-hidden />
            </button>
          </li>
        ))}
        {lista.length === 0 && <li className="py-4 text-sm text-suave">Nenhuma regra ainda: tudo vai para o Claude.</li>}
      </ul>
    </main>
  );
}
