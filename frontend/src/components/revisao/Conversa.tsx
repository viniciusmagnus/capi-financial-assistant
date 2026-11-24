"use client";

import { Globe, SendHorizonal } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { abrirConversaDeRevisao, conversarSobreRevisao } from "@/app/acoes";
import type { FonteDaConversa, PesquisaFeita, PropostaSalva } from "@/lib/revisao";

const SUGESTOES = [
  "Tenta descobrir quais são esses estabelecimentos.",
  "Lords ZS é a loja de ternos; classifica como vestuário.",
  "Gianluca - Bom Fim é a sorveteria.",
  "Essas descrições diferentes são compras na Amazon.",
  "Quero padronizar os lançamentos descritos apenas como PIX enviado.",
];

const LIMITE = 300;

type Mensagem = { papel: "usuario" | "assistente"; texto: string; pesquisas?: PesquisaFeita[]; descartadas?: string[]; selecionadas?: number };

export function Conversa({
  selecao,
  aoReceberPropostas,
  aoReceberFontes,
}: {
  selecao: number[];
  aoReceberPropostas: (propostas: PropostaSalva[]) => void;
  aoReceberFontes: (fontes: FonteDaConversa[]) => void;
}) {
  const [conversaId, setConversaId] = useState<number | null>(null);
  const [disponivel, setDisponivel] = useState<{ ia: boolean; pesquisa: boolean } | null>(null);
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar() {
    const limpo = texto.trim();
    if (!limpo || enviando) return;
    if (selecao.length === 0) {
      setErro("Selecione na lista as transações sobre as quais quer conversar.");
      return;
    }
    if (selecao.length > LIMITE) {
      setErro(`Para conversar, selecione até ${LIMITE} transações (um grupo, por exemplo).`);
      return;
    }
    setErro(null);
    setEnviando(true);
    let id = conversaId;
    if (id === null) {
      const aberta = await abrirConversaDeRevisao();
      if (!aberta.ok) {
        setEnviando(false);
        setErro(aberta.erro);
        return;
      }
      id = aberta.dados.id;
      setConversaId(id);
      setDisponivel({ ia: aberta.dados.ia_disponivel, pesquisa: aberta.dados.pesquisa_disponivel });
    }
    setMensagens((atual) => [...atual, { papel: "usuario", texto: limpo, selecionadas: selecao.length }]);
    setTexto("");
    const r = await conversarSobreRevisao(id, limpo, selecao);
    setEnviando(false);
    if (!r.ok) {
      setErro(r.erro.charAt(0).toUpperCase() + r.erro.slice(1) + ".");
      return;
    }
    setDisponivel({ ia: r.dados.ia_disponivel, pesquisa: r.dados.pesquisa_disponivel });
    setMensagens((atual) => [...atual, { papel: "assistente", texto: r.dados.resposta, pesquisas: r.dados.pesquisas, descartadas: r.dados.descartadas }]);
    aoReceberFontes(r.dados.fontes);
    if (r.dados.propostas.length) aoReceberPropostas(r.dados.propostas);
  }

  return (
    <section aria-labelledby="titulo-conversa" className="rounded-2xl border border-borda bg-superficie p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="titulo-conversa" className="font-semibold">
          Conversar com o Claude
        </h2>
        {disponivel && (
          <span className={`inline-flex items-center gap-1 text-xs ${disponivel.pesquisa ? "text-correnteza" : "text-suave"}`}>
            <Globe className="size-3.5" aria-hidden />
            {disponivel.pesquisa ? "pesquisa na web ligada" : "sem pesquisa na web"}
          </span>
        )}
      </div>
      <p className="mt-1 text-xs text-suave">
        O Claude vê só as {selecao.length || "0"} transações selecionadas, suas categorias e regras. Ele sugere; nada muda sem a sua aprovação.
      </p>

      {mensagens.length > 0 && (
        <ol className="mt-3 max-h-[28rem] space-y-3 overflow-y-auto" aria-live="polite">
          {mensagens.map((m, n) => (
            <li key={n} className={m.papel === "usuario" ? "ml-6 rounded-xl bg-elevada px-3 py-2 text-sm" : "mr-2 text-sm"}>
              {m.papel === "usuario" && <span className="block text-[11px] text-suave">você · {m.selecionadas} selecionada(s)</span>}
              {m.papel === "assistente" ? (
                <div className="resposta leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>
                    {m.texto}
                  </ReactMarkdown>
                </div>
              ) : (
                <p className="whitespace-pre-line">{m.texto}</p>
              )}
              {m.pesquisas?.map((p, i) => (
                <p key={i} className="mt-1 flex gap-1 text-xs text-suave">
                  <Globe className="mt-0.5 size-3 shrink-0" aria-hidden />
                  {p.recusada && !p.consultas.length ? (
                    <span>
                      Pesquisa de &quot;{p.termo}&quot; não feita: {p.recusada}
                    </span>
                  ) : (
                    <span>
                      Pesquisou &quot;{p.termo}&quot;{p.cidade ? ` em ${p.cidade}` : ""}
                      {p.consultas.length ? ` (busca enviada: ${p.consultas.map((c) => `“${c}”`).join(", ")})` : ""}
                      {p.fontes.length ? ` · fontes ${p.fontes.join(", ")}` : " · nenhuma fonte"}
                      {p.recusada ? ` · erro: ${p.recusada}` : ""}
                    </span>
                  )}
                </p>
              ))}
              {m.descartadas && m.descartadas.length > 0 && (
                <details className="mt-1 text-xs text-suave">
                  <summary>{m.descartadas.length} sugestão(ões) descartada(s) na validação</summary>
                  <ul className="list-disc pl-4">
                    {m.descartadas.map((d) => (
                      <li key={d}>{d}</li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          ))}
          {enviando && <li className="text-sm text-suave">Pensando…</li>}
        </ol>
      )}

      <div className="mt-3 flex flex-wrap gap-1.5">
        {SUGESTOES.map((s) => (
          <button key={s} type="button" onClick={() => setTexto(s)} className="rounded-full border border-borda px-2.5 py-1 text-xs text-suave hover:bg-elevada hover:text-texto">
            {s}
          </button>
        ))}
      </div>

      <form
        className="mt-3 flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void enviar();
        }}
      >
        <label className="min-w-0 flex-1">
          <span className="sr-only">Mensagem para o Claude</span>
          <textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void enviar();
              }
            }}
            rows={2}
            maxLength={2000}
            placeholder="Conte o que você sabe ou peça para pesquisar"
            className="w-full resize-none rounded-xl border border-borda bg-fundo px-3 py-2 text-sm outline-none focus:border-poente"
          />
        </label>
        <button type="submit" disabled={enviando || !texto.trim()} aria-label="Enviar" className="rounded-xl bg-destaque p-2.5 text-sobre-destaque disabled:opacity-40">
          <SendHorizonal className="size-4" aria-hidden />
        </button>
      </form>
      {erro && (
        <p role="alert" className="mt-2 text-sm text-brasa">
          {erro}
        </p>
      )}
    </section>
  );
}
