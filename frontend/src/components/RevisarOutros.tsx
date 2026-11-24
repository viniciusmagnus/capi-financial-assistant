"use client";

import { Check, ExternalLink, Sparkles, Undo2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { analisarOutros, confirmarOutros, desfazerLote } from "@/app/acoes";
import { EscolhaDeCategoria } from "@/components/EscolhaDeCategoria";
import type { Categorias } from "@/lib/cofrinho";
import { formatarData, formatarReais } from "@/lib/formato";
import type { AnaliseOutros, Decisao, SugestaoDeGasto } from "@/lib/revisao";

type Escolha = { categoria: string; estado: "pendente" | "aprovada" | "rejeitada" };

function novaChave() {
  return crypto.randomUUID().replaceAll("-", "");
}

function Linha({
  s,
  escolha,
  categorias,
  aoMudar,
  aoCriarCategoria,
}: {
  s: SugestaoDeGasto;
  escolha: Escolha;
  categorias: Categorias;
  aoMudar: (e: Escolha) => void;
  aoCriarCategoria: (c: Categorias) => void;
}) {
  const alterada = escolha.categoria !== (s.categoria ?? "");
  return (
    <li className={`py-3 ${escolha.estado === "rejeitada" ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-3 text-sm">
        <div className="min-w-0">
          <p className="break-words font-medium">{s.descricao}</p>
          <p className="text-xs text-suave">
            {formatarData(s.data)} · {s.conta}
            {s.parcela && s.parcela !== "parcelada" ? ` · parcela ${s.parcela}` : ""}
          </p>
        </div>
        <span className="shrink-0 tabular-nums">{formatarReais(s.valor_centavos)}</span>
      </div>
      <p className="mt-1 text-xs text-suave">
        {s.estabelecimento && <span className="text-texto">{s.estabelecimento}. </span>}
        {s.justificativa}
        {s.fontes.map((f) => (
          <a key={f.id} href={f.url} target="_blank" rel="noopener noreferrer nofollow" className="ml-1.5 inline-flex items-center gap-0.5 text-correnteza underline">
            fonte
            <ExternalLink className="size-3" aria-hidden />
          </a>
        ))}
      </p>
      <div className="mt-2 flex items-center gap-2">
        <EscolhaDeCategoria
          categorias={categorias}
          valor={escolha.categoria}
          aoMudar={(categoria) => aoMudar({ categoria, estado: categoria ? "aprovada" : "pendente" })}
          aoCriar={aoCriarCategoria}
          vazio="Fica em Outros"
          rotulo={`Categoria para ${s.descricao}`}
        />
        <button
          type="button"
          aria-pressed={escolha.estado === "aprovada"}
          aria-label={`Aprovar ${escolha.categoria || "categoria"} para ${s.descricao}`}
          disabled={!escolha.categoria}
          onClick={() => aoMudar({ ...escolha, estado: escolha.estado === "aprovada" ? "pendente" : "aprovada" })}
          className="rounded-lg border border-borda p-1.5 text-suave hover:bg-elevada disabled:opacity-30 aria-pressed:border-entrada aria-pressed:bg-entrada/15 aria-pressed:text-entrada"
        >
          <Check className="size-4" aria-hidden />
        </button>
        <button
          type="button"
          aria-pressed={escolha.estado === "rejeitada"}
          aria-label={`Rejeitar sugestão para ${s.descricao}`}
          onClick={() => aoMudar({ ...escolha, estado: escolha.estado === "rejeitada" ? "pendente" : "rejeitada" })}
          className="rounded-lg border border-borda p-1.5 text-suave hover:bg-elevada aria-pressed:border-brasa aria-pressed:bg-brasa/10 aria-pressed:text-brasa"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
      {alterada && escolha.estado === "aprovada" && <p className="mt-1 text-xs text-poente">Você trocou a sugestão.</p>}
    </li>
  );
}

function Modal({
  analise,
  categorias: categoriasIniciais,
  aoFechar,
  aoSalvar,
}: {
  analise: AnaliseOutros;
  categorias: Categorias;
  aoFechar: () => void;
  aoSalvar: (mensagem: string, loteId: number | null) => void;
}) {
  const caixa = useRef<HTMLDivElement>(null);
  const [categorias, setCategorias] = useState(categoriasIniciais);
  const [escolhas, setEscolhas] = useState<Record<number, Escolha>>(() =>
    Object.fromEntries(analise.sugestoes.map((s) => [s.transacao_id, { categoria: s.categoria ?? "", estado: "pendente" }])),
  );
  const [lembrar, setLembrar] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [chave] = useState(novaChave);

  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null;
    caixa.current?.focus();
    const aoTeclar = (e: KeyboardEvent) => e.key === "Escape" && !salvando && aoFechar();
    document.addEventListener("keydown", aoTeclar);
    const rolagem = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = rolagem;
      anterior?.focus?.();
    };
  }, [aoFechar, salvando]);

  const comSugestao = analise.sugestoes.filter((s) => s.categoria);
  const semSugestao = analise.sugestoes.filter((s) => !s.categoria);
  const aprovadas = analise.sugestoes.filter((s) => escolhas[s.transacao_id].estado === "aprovada" && escolhas[s.transacao_id].categoria);

  function mudar(id: number, e: Escolha) {
    setEscolhas((atual) => ({ ...atual, [id]: e }));
  }

  function aprovarTodas() {
    setEscolhas((atual) => {
      const novo = { ...atual };
      for (const s of comSugestao) if (novo[s.transacao_id].estado !== "rejeitada") novo[s.transacao_id] = { ...novo[s.transacao_id], estado: "aprovada" };
      return novo;
    });
  }

  async function salvar() {
    if (!aprovadas.length || salvando) return;
    setSalvando(true);
    setErro(null);
    const decisoes: Decisao[] = aprovadas.map((s) => {
      const categoria = escolhas[s.transacao_id].categoria;
      const daSugestao = categoria === s.categoria;
      return {
        transacao_id: s.transacao_id,
        categoria,
        estabelecimento: s.estabelecimento,
        origem: daSugestao && (s.origem === "pesquisa" || s.origem === "historico") ? s.origem : "usuario",
      };
    });
    const r = await confirmarOutros(decisoes, lembrar, chave);
    setSalvando(false);
    if (!r.ok) {
      setErro(r.erro.charAt(0).toUpperCase() + r.erro.slice(1) + ".");
      return;
    }
    const { alteradas, ignoradas, regras_salvas } = r.dados;
    const partes = [`${alteradas} ${alteradas === 1 ? "gasto saiu" : "gastos saíram"} de Outros`];
    if (regras_salvas.length) partes.push("o Capi vai lembrar nas próximas importações");
    if (ignoradas.length) partes.push(`${ignoradas.length} não ${ignoradas.length === 1 ? "mudou" : "mudaram"} (${ignoradas[0].motivo})`);
    aoSalvar(partes.join("; ") + ".", r.dados.lote_id);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && !salvando && aoFechar()}>
      <div ref={caixa} role="dialog" aria-modal="true" aria-labelledby="titulo-revisao" tabIndex={-1} className="flex max-h-[92dvh] w-full flex-col rounded-t-2xl border border-borda bg-fundo outline-none sm:max-w-xl sm:rounded-2xl">
        <div className="border-b border-borda px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <h2 id="titulo-revisao" className="font-semibold">
              Revisar Outros
            </h2>
            <button type="button" onClick={aoFechar} disabled={salvando} aria-label="Fechar" className="rounded-lg p-1.5 text-suave hover:bg-elevada hover:text-texto">
              <X className="size-4" aria-hidden />
            </button>
          </div>
          <p className="mt-0.5 text-xs text-suave">
            {comSugestao.length} com sugestão · {semSugestao.length} ficam em Outros
            {analise.pesquisa_disponivel ? (analise.pesquisas_feitas ? ` · ${analise.pesquisas_feitas} pesquisa(s) na web` : "") : " · pesquisa na web não configurada"}
          </p>
          {analise.aviso && <p className="mt-1 text-xs text-poente">{analise.aviso}</p>}
        </div>

        <div className="overflow-y-auto px-4">
          {comSugestao.length > 0 && (
            <section aria-labelledby="titulo-com-sugestao">
              <div className="flex items-center justify-between gap-3 pt-3">
                <h3 id="titulo-com-sugestao" className="text-sm font-semibold">
                  Sugestões
                </h3>
                <button type="button" onClick={aprovarTodas} className="text-xs text-suave underline underline-offset-4 hover:text-texto">
                  Aprovar todas
                </button>
              </div>
              <ul className="divide-y divide-borda">
                {comSugestao.map((s) => (
                  <Linha key={s.transacao_id} s={s} escolha={escolhas[s.transacao_id]} categorias={categorias} aoMudar={(e) => mudar(s.transacao_id, e)} aoCriarCategoria={setCategorias} />
                ))}
              </ul>
            </section>
          )}
          {semSugestao.length > 0 && (
            <details className="border-t border-borda py-3" open={comSugestao.length === 0}>
              <summary className="cursor-pointer text-sm font-semibold">Ficam em Outros ({semSugestao.length})</summary>
              <ul className="divide-y divide-borda">
                {semSugestao.map((s) => (
                  <Linha key={s.transacao_id} s={s} escolha={escolhas[s.transacao_id]} categorias={categorias} aoMudar={(e) => mudar(s.transacao_id, e)} aoCriarCategoria={setCategorias} />
                ))}
              </ul>
            </details>
          )}
        </div>

        <div className="space-y-3 border-t border-borda px-4 py-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={lembrar} onChange={(e) => setLembrar(e.target.checked)} />
            Lembrar essas escolhas nas próximas importações
          </label>
          {erro && (
            <p role="alert" className="text-sm text-brasa">
              {erro}
            </p>
          )}
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={aoFechar} disabled={salvando} className="rounded-xl border border-borda px-4 py-2.5 text-sm hover:bg-elevada">
              Cancelar
            </button>
            <button type="button" onClick={salvar} disabled={!aprovadas.length || salvando} className="rounded-xl bg-destaque px-4 py-2.5 text-sm font-semibold text-sobre-destaque disabled:opacity-40">
              {salvando ? "Salvando…" : aprovadas.length ? `Salvar ${aprovadas.length} ${aprovadas.length === 1 ? "alteração" : "alterações"}` : "Aprove alguma sugestão"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function RevisarOutros({ categorias }: { categorias: Categorias }) {
  const [revisando, setRevisando] = useState(false);
  const [analise, setAnalise] = useState<AnaliseOutros | null>(null);
  const [aviso, setAviso] = useState<{ texto: string; loteId: number | null } | null>(null);

  async function revisar() {
    setRevisando(true);
    setAviso(null);
    const r = await analisarOutros();
    setRevisando(false);
    if (!r.ok) return setAviso({ texto: `Não deu para revisar agora: ${r.erro}.`, loteId: null });
    const a = r.dados;
    if (a.total_em_outros === 0) return setAviso({ texto: "Nada em Outros para revisar.", loteId: null });
    if (!a.ia_disponivel) return setAviso({ texto: "A revisão precisa da chave da Anthropic, que não está configurada.", loteId: null });
    if (a.sugestoes.length === 0) return setAviso({ texto: "Os gastos em Outros são entradas de dinheiro; não há o que revisar.", loteId: null });
    setAnalise(a);
  }

  async function desfazer(loteId: number) {
    const r = await desfazerLote(loteId);
    setAviso({
      texto: r.ok ? (r.dados.ja_desfeito ? "Já estava desfeito." : `Desfeito: ${r.dados.desfeitas} voltaram para Outros.`) : r.erro,
      loteId: null,
    });
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={revisar}
        disabled={revisando}
        aria-busy={revisando}
        className="inline-flex items-center gap-1.5 rounded-xl border border-borda px-3 py-1.5 text-sm font-medium hover:bg-elevada disabled:opacity-60"
      >
        <Sparkles className={`size-4 ${revisando ? "animate-pulse" : ""}`} aria-hidden />
        {revisando ? "Revisando…" : "Revisar Outros"}
      </button>
      {aviso && (
        <p role="status" className="flex items-center gap-2 text-right text-xs text-suave">
          {aviso.texto}
          {aviso.loteId && (
            <button type="button" onClick={() => desfazer(aviso.loteId!)} className="inline-flex items-center gap-0.5 font-medium text-texto underline underline-offset-2">
              <Undo2 className="size-3" aria-hidden />
              Desfazer
            </button>
          )}
        </p>
      )}
      {analise && (
        <Modal
          analise={analise}
          categorias={categorias}
          aoFechar={() => setAnalise(null)}
          aoSalvar={(texto, loteId) => {
            setAnalise(null);
            setAviso({ texto, loteId });
          }}
        />
      )}
    </div>
  );
}
