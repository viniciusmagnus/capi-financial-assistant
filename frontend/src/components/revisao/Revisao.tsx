"use client";

import { ChevronDown, ChevronRight, Undo2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { agruparRevisao, desfazerLote, idsDoFiltroDaRevisao, itensDaRevisao, listarRevisao, lotesDaRevisao, rejeitarProposta } from "@/app/acoes";
import type { Categorias } from "@/lib/cofrinho";
import { formatarData, formatarReais } from "@/lib/formato";
import type {
  ConteudoProposta,
  ContaDeOrigem,
  FiltroRevisao,
  FonteDaConversa,
  GrupoRevisao,
  ItemRevisao,
  LoteResumo,
  PaginaRevisao,
  PropostaSalva,
  ResultadoLote,
} from "@/lib/revisao";

import { Aprovacao } from "./Aprovacao";
import { AprovacaoEmLote } from "./AprovacaoEmLote";
import { Conversa } from "./Conversa";
import { CartaoDeProposta, EditorDeClassificacao, type PropostaNaTela } from "./Proposta";

type Alcance = { tipo: "manual" } | { tipo: "filtro"; descricao: string };
type Janela =
  | { tipo: "aprovar"; proposta: PropostaNaTela }
  | { tipo: "editar"; proposta: PropostaNaTela }
  | { tipo: "manual"; ids: number[] }
  | { tipo: "lote"; propostas: PropostaNaTela[] }
  | null;

const CHAVE_MANUAL = "manual";

function descreverFiltro(f: FiltroRevisao, contas: ContaDeOrigem[]) {
  const partes = [];
  if (f.q) partes.push(`busca “${f.q}”`);
  if (f.inicio || f.fim) partes.push(`de ${f.inicio ? formatarData(f.inicio) : "o início"} a ${f.fim ? formatarData(f.fim) : "hoje"}`);
  if (f.conta_id) partes.push(`conta ${contas.find((c) => c.id === f.conta_id)?.nome ?? f.conta_id}`);
  return partes.length ? partes.join(", ") : "todo o “Outros”";
}

function Etiqueta({ children }: { children: React.ReactNode }) {
  return <span className="rounded-md bg-elevada px-1.5 py-0.5 text-[11px] text-suave">{children}</span>;
}

function LinhaDaTransacao({ item, marcada, aoMarcar }: { item: ItemRevisao; marcada: boolean; aoMarcar: (v: boolean) => void }) {
  return (
    <li>
      <label className="flex cursor-pointer items-start gap-3 px-3 py-2.5 hover:bg-elevada/50">
        <input type="checkbox" checked={marcada} onChange={(e) => aoMarcar(e.target.checked)} className="mt-1" />
        <span className="min-w-0 flex-1">
          <span className="flex justify-between gap-3">
            <span className="min-w-0 truncate font-medium" title={item.descricao}>
              {item.descricao}
            </span>
            <span className="shrink-0 tabular-nums">{formatarReais(item.valor_centavos)}</span>
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-suave">
            <span>{formatarData(item.data)}</span>
            <span>·</span>
            <span>{item.conta}</span>
            <span>·</span>
            <span title={item.estabelecimento_confirmado ? "Estabelecimento confirmado por você ou por regra" : "Estabelecimento identificado pelo app, ainda não confirmado"}>
              {item.estabelecimento}
              {item.estabelecimento_confirmado ? " ✓" : "?"}
            </span>
            {item.forma_pagamento && <Etiqueta>{item.forma_pagamento}</Etiqueta>}
            {item.parcela && <Etiqueta>{item.parcela === "parcelada" ? "parcelada" : `parcela ${item.parcela}`}</Etiqueta>}
            {item.categorizada_por === "usuario" && <Etiqueta>classificada por você</Etiqueta>}
          </span>
        </span>
      </label>
    </li>
  );
}

export function Revisao({
  inicial,
  contas,
  categorias,
  lotesIniciais,
}: {
  inicial: PaginaRevisao;
  contas: ContaDeOrigem[];
  categorias: Categorias;
  lotesIniciais: LoteResumo[];
}) {
  const [rascunho, setRascunho] = useState<FiltroRevisao>({});
  const [filtro, setFiltro] = useState<FiltroRevisao>({});
  const [modo, setModo] = useState<"lista" | "grupos">("lista");
  const [pagina, setPagina] = useState(inicial);
  const [grupos, setGrupos] = useState<GrupoRevisao[] | null>(null);
  const [abertos, setAbertos] = useState<Record<string, ItemRevisao[] | "carregando">>({});
  const [selecao, setSelecao] = useState<Set<number>>(new Set());
  const [alcance, setAlcance] = useState<Alcance>({ tipo: "manual" });
  const [conhecidos, setConhecidos] = useState<Map<number, ItemRevisao>>(() => new Map(inicial.itens.map((i) => [i.id, i])));
  const [propostas, setPropostas] = useState<PropostaNaTela[]>([]);
  const [marcadas, setMarcadas] = useState<Set<string>>(new Set());
  const [fontes, setFontes] = useState<Map<string, FonteDaConversa>>(new Map());
  const [lotes, setLotes] = useState(lotesIniciais);
  const [janela, setJanela] = useState<Janela>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  const conhecer = useCallback((itens: ItemRevisao[]) => {
    setConhecidos((atual) => {
      const novo = new Map(atual);
      for (const i of itens) novo.set(i.id, i);
      return novo;
    });
  }, []);

  const recarregar = useCallback(
    async (f: FiltroRevisao, numero: number, comGrupos: boolean) => {
      setCarregando(true);
      const [lista, agrupados, historico] = await Promise.all([
        listarRevisao(f, numero),
        comGrupos ? agruparRevisao(f) : Promise.resolve(null),
        lotesDaRevisao(),
      ]);
      setCarregando(false);
      if (lista.ok) {
        setPagina(lista.dados);
        conhecer(lista.dados.itens);
      } else setAviso(lista.erro);
      if (agrupados?.ok) setGrupos(agrupados.dados);
      if (historico.ok) setLotes(historico.dados);
      setAbertos({});
    },
    [conhecer],
  );

  useEffect(() => {
    if (modo === "grupos" && grupos === null) {
      void agruparRevisao(filtro).then((r) => r.ok && setGrupos(r.dados));
    }
  }, [modo, grupos, filtro]);

  const faltando = useMemo(
    () => [...new Set(propostas.flatMap((p) => p.conteudo.transacao_ids))].filter((id) => !conhecidos.has(id)).slice(0, 300),
    [propostas, conhecidos],
  );
  useEffect(() => {
    if (faltando.length) void itensDaRevisao(faltando).then((r) => r.ok && conhecer(r.dados));
  }, [faltando, conhecer]);

  function aplicarFiltro(novo: FiltroRevisao) {
    setFiltro(novo);
    setGrupos(null);
    setAlcance({ tipo: "manual" });
    void recarregar(novo, 1, modo === "grupos");
  }

  function marcar(ids: number[], valor: boolean) {
    setAlcance({ tipo: "manual" });
    setSelecao((atual) => {
      const nova = new Set(atual);
      for (const id of ids) {
        if (valor) nova.add(id);
        else nova.delete(id);
      }
      return nova;
    });
  }

  async function selecionarTudoDoFiltro() {
    const r = await idsDoFiltroDaRevisao(filtro);
    if (!r.ok) {
      setAviso(r.erro);
      return;
    }
    setSelecao(new Set(r.dados));
    setAlcance({ tipo: "filtro", descricao: descreverFiltro(filtro, contas) });
  }

  async function abrirGrupo(grupo: GrupoRevisao) {
    if (abertos[grupo.chave]) {
      setAbertos((atual) => {
        const resto = { ...atual };
        delete resto[grupo.chave];
        return resto;
      });
      return;
    }
    setAbertos((a) => ({ ...a, [grupo.chave]: "carregando" }));
    const r = await itensDaRevisao(grupo.ids.slice(0, 300));
    if (r.ok) {
      conhecer(r.dados);
      setAbertos((a) => ({ ...a, [grupo.chave]: r.dados }));
    }
  }

  function receberPropostas(novas: PropostaSalva[]) {
    setPropostas((atual) => [
      ...novas.map((p) => ({ chave: `p${p.id}`, id: p.id, status: p.status, conteudo: p.conteudo, editada: false })),
      ...atual,
    ]);
  }

  function receberFontes(lista: FonteDaConversa[]) {
    setFontes(new Map(lista.map((f) => [f.id, f])));
  }

  function aposAplicar(resultado: ResultadoLote, chaves: string[]) {
    setPropostas((atual) => atual.map((p) => (chaves.includes(p.chave) ? { ...p, status: "aplicada" } : p)));
    setMarcadas(new Set());
    setSelecao(new Set());
    setAlcance({ tipo: "manual" });
    setJanela(null);
    setAviso(
      resultado.repetido
        ? "Essa aprovação já tinha sido aplicada; nada foi feito de novo."
        : `${resultado.alteradas} transação(ões) atualizada(s)${resultado.regra ? `; regra ${resultado.regra.padrao} salva` : ""}.`,
    );
    void recarregar(filtro, pagina.pagina, modo === "grupos");
  }

  async function rejeitar(proposta: PropostaNaTela) {
    if (proposta.id !== null) {
      const r = await rejeitarProposta(proposta.id);
      if (!r.ok) {
        setAviso(r.erro);
        return;
      }
    }
    setPropostas((atual) => atual.map((p) => (p.chave === proposta.chave ? { ...p, status: "rejeitada" } : p)));
  }

  async function desfazer(lote: LoteResumo) {
    const r = await desfazerLote(lote.id);
    if (!r.ok) {
      setAviso(r.erro);
      return;
    }
    setAviso(
      r.dados.ja_desfeito
        ? "Esse lote já tinha sido desfeito."
        : `${r.dados.desfeitas} transação(ões) voltaram ao que eram${r.dados.conflitos.length ? `; ${r.dados.conflitos.length} mudaram depois e ficaram como estão` : ""}.`,
    );
    void recarregar(filtro, pagina.pagina, modo === "grupos");
  }

  const ids = [...selecao];
  const naPagina = pagina.itens.map((i) => i.id);
  const paginaToda = naPagina.length > 0 && naPagina.every((id) => selecao.has(id));
  const paginas = Math.max(1, Math.ceil(pagina.total / pagina.por_pagina));
  const pendentes = propostas.filter((p) => p.status === "pendente");
  const marcadasLista = pendentes.filter((p) => marcadas.has(p.chave));

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-6 sm:pb-10">
      <h1 className="largo text-2xl font-bold">Revisar “Outros”</h1>
      <p className="mt-2 max-w-2xl text-sm text-suave">
        Ensine o Capi a ler descrições confusas. Selecione transações, conte o que você sabe ou peça uma pesquisa, e aprove as propostas. As aprovadas podem virar regras para as próximas importações.
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="min-w-0 space-y-4">
          <form
            className="grid grid-cols-2 gap-2 rounded-2xl border border-borda bg-superficie p-3 sm:grid-cols-[1fr_1fr_1fr_auto]"
            onSubmit={(e) => {
              e.preventDefault();
              aplicarFiltro(rascunho);
            }}
          >
            <label className="col-span-2 block sm:col-span-4">
              <span className="sr-only">Buscar na descrição</span>
              <input
                value={rascunho.q ?? ""}
                onChange={(e) => setRascunho((r) => ({ ...r, q: e.target.value }))}
                maxLength={100}
                placeholder="Buscar na descrição"
                className="w-full rounded-xl border border-borda bg-fundo px-3 py-2 text-sm outline-none focus:border-poente"
              />
            </label>
            <label className="block">
              <span className="sr-only">De</span>
              <input type="date" value={rascunho.inicio ?? ""} onChange={(e) => setRascunho((r) => ({ ...r, inicio: e.target.value || undefined }))} className="w-full rounded-xl border border-borda bg-fundo px-3 py-2 text-sm" />
            </label>
            <label className="block">
              <span className="sr-only">Até</span>
              <input type="date" value={rascunho.fim ?? ""} onChange={(e) => setRascunho((r) => ({ ...r, fim: e.target.value || undefined }))} className="w-full rounded-xl border border-borda bg-fundo px-3 py-2 text-sm" />
            </label>
            <label className="col-span-2 block sm:col-span-1">
              <span className="sr-only">Conta</span>
              <select
                value={rascunho.conta_id ?? ""}
                onChange={(e) => setRascunho((r) => ({ ...r, conta_id: e.target.value ? Number(e.target.value) : undefined }))}
                className="w-full rounded-xl border border-borda bg-fundo px-3 py-2 text-sm"
              >
                <option value="">Todas as contas</option>
                {contas.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" className="col-span-2 rounded-xl bg-destaque px-4 py-2 text-sm font-semibold text-sobre-destaque sm:col-span-1">
              Filtrar
            </button>
          </form>

          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <p aria-live="polite">
              <strong>{pagina.total}</strong> em “Outros” · {formatarReais(pagina.total_centavos)}
              {carregando && <span className="text-suave"> · atualizando…</span>}
            </p>
            <div className="flex rounded-xl border border-borda p-1" role="group" aria-label="Como ver">
              {(["lista", "grupos"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={modo === m}
                  onClick={() => setModo(m)}
                  className="rounded-lg px-3 py-1 text-suave aria-pressed:bg-elevada aria-pressed:font-semibold aria-pressed:text-texto"
                >
                  {m === "lista" ? "Lista" : "Agrupadas"}
                </button>
              ))}
            </div>
          </div>

          <div className="sticky top-0 z-20 flex flex-wrap items-center gap-2 rounded-xl border border-borda bg-fundo/95 px-3 py-2 text-sm backdrop-blur">
            <span aria-live="polite">
              {selecao.size === 0 ? (
                "Nenhuma selecionada"
              ) : alcance.tipo === "filtro" ? (
                <>
                  <strong>{selecao.size}</strong> selecionadas: todas do filtro ({alcance.descricao})
                </>
              ) : (
                <>
                  <strong>{selecao.size}</strong> selecionada(s) individualmente
                </>
              )}
            </span>
            <span className="ml-auto flex flex-wrap gap-2">
              {pagina.total > 0 && (
                <button type="button" onClick={selecionarTudoDoFiltro} className="rounded-lg border border-borda px-2.5 py-1 hover:bg-elevada">
                  Selecionar todas as {pagina.total} do filtro
                </button>
              )}
              {selecao.size > 0 && (
                <>
                  <button type="button" onClick={() => setJanela({ tipo: "manual", ids })} className="rounded-lg border border-borda px-2.5 py-1 hover:bg-elevada">
                    Classificar à mão
                  </button>
                  <button type="button" onClick={() => marcar(ids, false)} className="rounded-lg px-2.5 py-1 text-suave hover:bg-elevada">
                    Limpar
                  </button>
                </>
              )}
            </span>
          </div>

          {aviso && (
            <p className="rounded-xl bg-superficie px-3 py-2 text-sm" role="status">
              {aviso.charAt(0).toUpperCase() + aviso.slice(1)}
            </p>
          )}

          {modo === "lista" ? (
            <>
              <div className="rounded-2xl border border-borda bg-superficie">
                {naPagina.length > 0 && (
                  <label className="flex items-center gap-3 border-b border-borda px-3 py-2 text-sm text-suave">
                    <input type="checkbox" checked={paginaToda} onChange={(e) => marcar(naPagina, e.target.checked)} />
                    Selecionar as {naPagina.length} desta página
                  </label>
                )}
                <ul className="divide-y divide-borda text-sm">
                  {pagina.itens.map((item) => (
                    <LinhaDaTransacao key={item.id} item={item} marcada={selecao.has(item.id)} aoMarcar={(v) => marcar([item.id], v)} />
                  ))}
                  {pagina.itens.length === 0 && <li className="px-3 py-6 text-center text-suave">Nada em “Outros” com esse filtro. 🎉</li>}
                </ul>
              </div>
              {paginas > 1 && (
                <nav aria-label="Páginas" className="flex items-center justify-between text-sm">
                  <button
                    type="button"
                    disabled={pagina.pagina <= 1 || carregando}
                    onClick={() => recarregar(filtro, pagina.pagina - 1, false)}
                    className="rounded-lg border border-borda px-3 py-1.5 disabled:opacity-40"
                  >
                    Anterior
                  </button>
                  <span className="text-suave">
                    Página {pagina.pagina} de {paginas}
                  </span>
                  <button
                    type="button"
                    disabled={pagina.pagina >= paginas || carregando}
                    onClick={() => recarregar(filtro, pagina.pagina + 1, false)}
                    className="rounded-lg border border-borda px-3 py-1.5 disabled:opacity-40"
                  >
                    Próxima
                  </button>
                </nav>
              )}
            </>
          ) : (
            <ul className="space-y-2 text-sm">
              {grupos === null && <li className="text-suave">Agrupando…</li>}
              {grupos?.map((g) => {
                const todos = g.ids.every((id) => selecao.has(id));
                const alguns = !todos && g.ids.some((id) => selecao.has(id));
                const aberto = abertos[g.chave];
                return (
                  <li key={g.chave} className="rounded-2xl border border-borda bg-superficie">
                    <div className="flex items-start gap-3 px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={todos}
                        ref={(el) => {
                          if (el) el.indeterminate = alguns;
                        }}
                        onChange={(e) => marcar(g.ids, e.target.checked)}
                        aria-label={`Selecionar as ${g.quantidade} de ${g.estabelecimento}`}
                        className="mt-1"
                      />
                      <button type="button" onClick={() => abrirGrupo(g)} aria-expanded={Boolean(aberto)} className="min-w-0 flex-1 text-left">
                        <span className="flex justify-between gap-3">
                          <span className="flex min-w-0 items-center gap-1 font-medium">
                            {aberto ? <ChevronDown className="size-4 shrink-0" aria-hidden /> : <ChevronRight className="size-4 shrink-0" aria-hidden />}
                            <span className="truncate">
                              {g.estabelecimento}
                              {g.confirmado ? " ✓" : ""}
                            </span>
                          </span>
                          <span className="shrink-0 tabular-nums">
                            {g.quantidade}× · {formatarReais(g.total_centavos)}
                          </span>
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-suave">{g.descricoes.join(" · ")}</span>
                      </button>
                    </div>
                    {aberto === "carregando" && <p className="px-3 pb-2 text-xs text-suave">Carregando…</p>}
                    {Array.isArray(aberto) && (
                      <ul className="divide-y divide-borda border-t border-borda">
                        {aberto.map((item) => (
                          <LinhaDaTransacao key={item.id} item={item} marcada={selecao.has(item.id)} aoMarcar={(v) => marcar([item.id], v)} />
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
              {grupos?.length === 0 && <li className="text-suave">Nada em “Outros” com esse filtro.</li>}
            </ul>
          )}

          <section aria-labelledby="titulo-historico" className="rounded-2xl border border-borda bg-superficie p-3 text-sm">
            <h2 id="titulo-historico" className="font-semibold">
              Alterações aprovadas
            </h2>
            {lotes.length === 0 ? (
              <p className="mt-1 text-suave">Nada aplicado ainda.</p>
            ) : (
              <ul className="mt-2 divide-y divide-borda">
                {lotes.map((l) => (
                  <li key={l.id} className="flex items-center justify-between gap-3 py-2">
                    <span className="min-w-0">
                      <span className={`block truncate ${l.desfeito_em ? "text-suave line-through" : ""}`}>{l.resumo}</span>
                      <span className="text-xs text-suave">
                        {new Date(l.criado_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })} · {l.alteracoes} alteração(ões)
                        {l.regra_id ? " · com regra" : ""}
                        {l.desfeito_em ? " · desfeito" : ""}
                      </span>
                    </span>
                    {!l.desfeito_em && (
                      <button type="button" onClick={() => desfazer(l)} className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-borda px-2.5 py-1 hover:bg-elevada">
                        <Undo2 className="size-3.5" aria-hidden />
                        Desfazer
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <aside className="min-w-0 space-y-4 lg:sticky lg:top-4 lg:self-start">
          <Conversa selecao={ids} aoReceberPropostas={receberPropostas} aoReceberFontes={receberFontes} />

          {propostas.length > 0 && (
            <section aria-labelledby="titulo-propostas" className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h2 id="titulo-propostas" className="font-semibold">
                  Propostas ({pendentes.length} pendente{pendentes.length === 1 ? "" : "s"})
                </h2>
                {marcadasLista.length > 1 && (
                  <button type="button" onClick={() => setJanela({ tipo: "lote", propostas: marcadasLista })} className="rounded-lg bg-destaque px-3 py-1.5 text-sm font-semibold text-sobre-destaque">
                    Aprovar {marcadasLista.length} marcadas
                  </button>
                )}
              </div>
              {fontes.size > 0 && (
                <details className="rounded-xl border border-borda px-3 py-2 text-xs">
                  <summary className="cursor-pointer text-suave">Fontes consultadas ({fontes.size})</summary>
                  <ul className="mt-1 space-y-0.5">
                    {[...fontes.values()].map((f) => (
                      <li key={f.id}>
                        [{f.id}]{" "}
                        <a href={f.url} target="_blank" rel="noopener noreferrer nofollow" className="text-correnteza underline underline-offset-2">
                          {f.titulo}
                        </a>{" "}
                        <span className="text-suave">· pesquisa “{f.termo}”</span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              {propostas.map((p) => (
                <CartaoDeProposta
                  key={p.chave}
                  proposta={p}
                  itens={conhecidos}
                  fontes={fontes}
                  marcada={marcadas.has(p.chave)}
                  aoMarcar={(v) =>
                    setMarcadas((atual) => {
                      const nova = new Set(atual);
                      if (v) nova.add(p.chave);
                      else nova.delete(p.chave);
                      return nova;
                    })
                  }
                  aoAprovar={() => setJanela({ tipo: "aprovar", proposta: p })}
                  aoEditar={() => setJanela({ tipo: "editar", proposta: p })}
                  aoRejeitar={() => rejeitar(p)}
                  ocupado={janela !== null}
                />
              ))}
            </section>
          )}
        </aside>
      </div>

      {janela?.tipo === "aprovar" && (
        <Aprovacao
          conteudo={janela.proposta.conteudo}
          propostaId={janela.proposta.id}
          aoFechar={() => setJanela(null)}
          aoAplicar={(r) => aposAplicar(r, [janela.proposta.chave])}
        />
      )}
      {janela?.tipo === "editar" && (
        <EditorDeClassificacao
          titulo="Editar proposta"
          inicial={janela.proposta.conteudo}
          itens={conhecidos}
          categorias={categorias}
          aoFechar={() => setJanela(null)}
          aoSalvar={(conteudo: ConteudoProposta) => {
            const editada = { ...janela.proposta, conteudo, editada: true };
            setPropostas((atual) => atual.map((p) => (p.chave === editada.chave ? editada : p)));
            setJanela({ tipo: "aprovar", proposta: editada });
          }}
        />
      )}
      {janela?.tipo === "manual" && (
        <EditorDeClassificacao
          titulo={`Classificar ${janela.ids.length} transação(ões) à mão`}
          inicial={{ transacao_ids: janela.ids, estabelecimento: null, categoria: null, motivo: "", evidencias: [{ origem: "usuario", texto: "Classificação manual.", fontes: [] }], incertezas: [], regra: null }}
          itens={conhecidos}
          categorias={categorias}
          aoFechar={() => setJanela(null)}
          aoSalvar={(conteudo) => setJanela({ tipo: "aprovar", proposta: { chave: `${CHAVE_MANUAL}-${Date.now()}`, id: null, status: "pendente", conteudo, editada: true } })}
        />
      )}
      {janela?.tipo === "lote" && (
        <AprovacaoEmLote
          propostas={janela.propostas}
          aoFechar={() => setJanela(null)}
          aoTerminar={(chaves) => {
            setPropostas((atual) => atual.map((p) => (chaves.includes(p.chave) ? { ...p, status: "aplicada" } : p)));
            setMarcadas(new Set());
            setSelecao(new Set());
            void recarregar(filtro, 1, modo === "grupos");
          }}
        />
      )}
    </main>
  );
}
