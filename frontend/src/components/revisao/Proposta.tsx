"use client";

import { ExternalLink } from "lucide-react";
import { useState } from "react";

import { OpcoesDeCategoria } from "@/components/OpcoesDeCategoria";
import type { Categorias } from "@/lib/cofrinho";
import { formatarReais } from "@/lib/formato";
import { ROTULO_ORIGEM, type ConteudoProposta, type FonteDaConversa, type ItemRevisao } from "@/lib/revisao";

import { Dialogo } from "./Dialogo";

export type PropostaNaTela = {
  chave: string;
  id: number | null;
  status: "pendente" | "aplicada" | "rejeitada";
  conteudo: ConteudoProposta;
  editada: boolean;
};

const COR_ORIGEM: Record<string, string> = {
  usuario: "bg-entrada/15 text-entrada",
  pesquisa: "bg-correnteza-fundo text-correnteza",
  historico: "bg-elevada text-texto",
  regra: "bg-elevada text-texto",
  hipotese: "bg-destaque-fundo text-poente",
};

export function CartaoDeProposta({
  proposta,
  itens,
  fontes,
  marcada,
  aoMarcar,
  aoAprovar,
  aoEditar,
  aoRejeitar,
  ocupado,
}: {
  proposta: PropostaNaTela;
  itens: Map<number, ItemRevisao>;
  fontes: Map<string, FonteDaConversa>;
  marcada: boolean;
  aoMarcar: (marcada: boolean) => void;
  aoAprovar: () => void;
  aoEditar: () => void;
  aoRejeitar: () => void;
  ocupado: boolean;
}) {
  const { conteudo } = proposta;
  const [aberta, setAberta] = useState(false);
  const conhecidas = conteudo.transacao_ids.map((id) => itens.get(id)).filter((i): i is ItemRevisao => Boolean(i));
  const atuais = [...new Set(conhecidas.map((i) => i.categoria))];
  const total = conhecidas.reduce((soma, i) => soma + i.valor_centavos, 0);
  const pendente = proposta.status === "pendente";

  return (
    <article className={`rounded-2xl border border-borda bg-superficie p-3 text-sm ${pendente ? "" : "opacity-70"}`} aria-label={`Proposta ${conteudo.estabelecimento ?? ""}`}>
      <div className="flex items-start gap-2">
        {pendente && (
          <input
            type="checkbox"
            checked={marcada}
            onChange={(e) => aoMarcar(e.target.checked)}
            aria-label="Incluir esta proposta na aprovação em conjunto"
            className="mt-1"
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{conteudo.estabelecimento ?? "Estabelecimento não muda"}</h3>
            {proposta.editada && <span className="rounded-md bg-elevada px-1.5 py-0.5 text-[11px]">editada por você</span>}
            {!pendente && (
              <span className="rounded-md bg-elevada px-1.5 py-0.5 text-[11px]">{proposta.status === "aplicada" ? "aplicada" : "rejeitada"}</span>
            )}
          </div>
          <p className="mt-0.5">
            <span className="text-suave">{atuais.join(", ") || "categoria atual"}</span> →{" "}
            {conteudo.categoria ? <strong>{conteudo.categoria}</strong> : <span className="text-suave">categoria fica pendente</span>}
          </p>
          <button type="button" onClick={() => setAberta((v) => !v)} aria-expanded={aberta} className="mt-1 text-xs text-suave underline underline-offset-4">
            {conteudo.transacao_ids.length} transação(ões){conhecidas.length === conteudo.transacao_ids.length ? ` · ${formatarReais(total)}` : ""}
          </button>
          {aberta && (
            <ul className="mt-1 max-h-40 space-y-0.5 overflow-y-auto text-xs text-suave">
              {conteudo.transacao_ids.map((id) => {
                const item = itens.get(id);
                return <li key={id}>{item ? `${item.descricao} · ${formatarReais(item.valor_centavos)}${item.parcela ? ` · parcela ${item.parcela}` : ""}` : `transação ${id}`}</li>;
              })}
            </ul>
          )}
          {conteudo.motivo && <p className="mt-2">{conteudo.motivo}</p>}
          {conteudo.evidencias.length > 0 && (
            <ul className="mt-2 space-y-1.5">
              {conteudo.evidencias.map((e, n) => (
                <li key={n}>
                  <span className={`mr-1.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium ${COR_ORIGEM[e.origem]}`}>{ROTULO_ORIGEM[e.origem]}</span>
                  {e.texto}
                  {e.fontes.length > 0 && (
                    <span className="mt-0.5 flex flex-wrap gap-x-2 text-xs">
                      {e.fontes.map((id) => {
                        const fonte = fontes.get(id);
                        return fonte ? (
                          <a key={id} href={fonte.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-0.5 text-correnteza underline underline-offset-2">
                            [{id}] {fonte.titulo.slice(0, 50)}
                            <ExternalLink className="size-3" aria-hidden />
                          </a>
                        ) : null;
                      })}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {conteudo.incertezas.length > 0 && (
            <div className="mt-2 rounded-lg bg-destaque-fundo px-2 py-1.5 text-xs text-poente">
              <p className="font-medium">Incertezas</p>
              <ul className="list-disc pl-4">
                {conteudo.incertezas.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
            </div>
          )}
          {conteudo.regra && (
            <p className="mt-2 text-xs text-suave">
              Regra sugerida: <strong className="text-texto">{conteudo.regra.padrao.toUpperCase()}</strong>
              {conteudo.regra.categoria ? ` → ${conteudo.regra.categoria}` : " (só estabelecimento)"}
              {conteudo.regra.estabelecimento ? ` · ${conteudo.regra.estabelecimento}` : ""}
            </p>
          )}
          {pendente && (
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" disabled={ocupado} onClick={aoAprovar} className="rounded-lg bg-destaque px-3 py-1.5 font-semibold text-sobre-destaque disabled:opacity-40">
                Revisar e aprovar
              </button>
              <button type="button" disabled={ocupado} onClick={aoEditar} className="rounded-lg border border-borda px-3 py-1.5 hover:bg-elevada disabled:opacity-40">
                Editar
              </button>
              <button type="button" disabled={ocupado} onClick={aoRejeitar} className="rounded-lg px-3 py-1.5 text-suave hover:bg-elevada hover:text-texto disabled:opacity-40">
                Rejeitar
              </button>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

export function EditorDeClassificacao({
  titulo,
  inicial,
  itens,
  categorias,
  aoSalvar,
  aoFechar,
}: {
  titulo: string;
  inicial: ConteudoProposta;
  itens: Map<number, ItemRevisao>;
  categorias: Categorias;
  aoSalvar: (conteudo: ConteudoProposta) => void;
  aoFechar: () => void;
}) {
  const [ids, setIds] = useState(inicial.transacao_ids);
  const [estabelecimento, setEstabelecimento] = useState(inicial.estabelecimento ?? "");
  const [categoria, setCategoria] = useState(inicial.categoria ?? "");
  const [motivo, setMotivo] = useState(inicial.motivo);
  const [comRegra, setComRegra] = useState(Boolean(inicial.regra));
  const [padrao, setPadrao] = useState(inicial.regra?.padrao ?? "");
  const [regraCategoria, setRegraCategoria] = useState(inicial.regra?.categoria ?? "");
  const [regraEstabelecimento, setRegraEstabelecimento] = useState(inicial.regra?.estabelecimento ?? "");
  const vazio = !estabelecimento.trim() && !categoria;

  function salvar() {
    const evidencias = inicial.evidencias.some((e) => e.origem === "usuario")
      ? inicial.evidencias
      : [...inicial.evidencias, { origem: "usuario" as const, texto: "Ajustado por você na revisão.", fontes: [] }];
    aoSalvar({
      transacao_ids: ids,
      estabelecimento: estabelecimento.trim() || null,
      categoria: categoria || null,
      motivo: motivo.trim(),
      evidencias,
      incertezas: inicial.incertezas,
      regra:
        comRegra && padrao.trim().length >= 3
          ? { padrao: padrao.trim(), categoria: regraCategoria || null, estabelecimento: regraEstabelecimento.trim() || null }
          : null,
    });
  }

  return (
    <Dialogo titulo={titulo} aoFechar={aoFechar} largo>
      <form
        className="space-y-4 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          if (!vazio && ids.length) salvar();
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="text-suave">Estabelecimento</span>
            <input
              value={estabelecimento}
              onChange={(e) => setEstabelecimento(e.target.value)}
              maxLength={80}
              placeholder="ex.: Lords ZS"
              className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2 outline-none focus:border-poente"
            />
            <span className="mt-1 block text-xs text-suave">A descrição original do extrato não muda.</span>
          </label>
          <label className="block">
            <span className="text-suave">Categoria</span>
            <select value={categoria} onChange={(e) => setCategoria(e.target.value)} className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2 outline-none focus:border-poente">
              <option value="">Manter a atual (pendente)</option>
              <OpcoesDeCategoria categorias={categorias} />
            </select>
          </label>
        </div>

        <fieldset>
          <legend className="text-suave">Transações ({ids.length})</legend>
          <ul className="mt-1 max-h-44 space-y-1 overflow-y-auto rounded-xl border border-borda p-2">
            {inicial.transacao_ids.map((id) => {
              const item = itens.get(id);
              return (
                <li key={id}>
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={ids.includes(id)} onChange={(e) => setIds((atual) => (e.target.checked ? [...atual, id] : atual.filter((x) => x !== id)))} />
                    <span className="min-w-0 truncate">{item ? `${item.descricao} · ${formatarReais(item.valor_centavos)}` : `transação ${id}`}</span>
                  </label>
                </li>
              );
            })}
          </ul>
        </fieldset>

        <label className="block">
          <span className="text-suave">Motivo (opcional)</span>
          <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={600} rows={2} className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2 outline-none focus:border-poente" />
        </label>

        <fieldset className="rounded-xl border border-borda p-3">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={comRegra} onChange={(e) => setComRegra(e.target.checked)} />
            <span>Sugerir uma regra para as próximas importações</span>
          </label>
          {comRegra && (
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <label className="block">
                <span className="text-suave">Se a descrição tiver</span>
                <input value={padrao} onChange={(e) => setPadrao(e.target.value)} maxLength={120} placeholder="ex.: LORDS ZS" className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2 uppercase outline-none focus:border-poente" />
              </label>
              <label className="block">
                <span className="text-suave">vira</span>
                <select value={regraCategoria} onChange={(e) => setRegraCategoria(e.target.value)} className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2 outline-none focus:border-poente">
                  <option value="">Não muda a categoria</option>
                  <OpcoesDeCategoria categorias={categorias} />
                </select>
              </label>
              <label className="block">
                <span className="text-suave">Estabelecimento</span>
                <input value={regraEstabelecimento} onChange={(e) => setRegraEstabelecimento(e.target.value)} maxLength={80} className="mt-1 w-full rounded-xl border border-borda bg-fundo px-3 py-2 outline-none focus:border-poente" />
              </label>
              <p className="text-xs text-suave sm:col-span-3">Use o nome de quem recebe. Padrões como &quot;PIX ENVIADO&quot; ou &quot;PARCELA&quot; são recusados por pegar gastos demais.</p>
            </div>
          )}
        </fieldset>

        <p className="text-xs text-suave">Salvar não altera nada: a próxima tela mostra a prévia e pede a sua aprovação.</p>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={aoFechar} className="rounded-xl border border-borda px-4 py-2.5 hover:bg-elevada">
            Cancelar
          </button>
          <button type="submit" disabled={vazio || ids.length === 0} className="rounded-xl bg-destaque px-4 py-2.5 font-semibold text-sobre-destaque disabled:opacity-40">
            Continuar para a prévia
          </button>
        </div>
      </form>
    </Dialogo>
  );
}
