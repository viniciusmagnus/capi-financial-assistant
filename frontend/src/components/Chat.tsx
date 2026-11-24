"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { irParaEntrar } from "@/lib/sessao-cliente";

type Uso = { entrada: number; saida: number; cache_lido: number; cache_gravado: number };

type Evento =
  | { tipo: "texto"; texto: string }
  | { tipo: "ferramenta"; nome: string; entrada: Record<string, unknown> }
  | { tipo: "erro"; mensagem: string }
  | { tipo: "fim"; modelo?: string; uso?: Uso | null };

type Mensagem = {
  papel: "user" | "assistant";
  texto: string;
  ferramentas: string[];
  erro?: string;
  rodape?: string;
};

const NOMES: Record<string, string> = {
  gastos_por_categoria: "gastos por categoria",
  saldos: "saldos das contas",
  buscar_transacoes: "busca de transações",
  cofrinho_do_mes: "cofrinho do mês",
  recategorizar: "mudou uma categoria",
  criar_regra: "criou uma regra",
};

const SUGESTOES = [
  "Quanto ainda posso gastar este mês?",
  "Quanto gastei com comida fora em novembro?",
  "Quais foram meus maiores gastos do mês?",
  "Quanto tenho em cada conta?",
];

function rodape(evento: Extract<Evento, { tipo: "fim" }>) {
  if (!evento.uso) return evento.modelo;
  const { entrada, saida, cache_lido } = evento.uso;
  const mil = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1).replace(".", ",")} mil` : String(n));
  return `${evento.modelo} · ${mil(entrada + cache_lido)} tokens de entrada (${mil(cache_lido)} do cache) · ${mil(saida)} de saída`;
}

export function Chat() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [texto, setTexto] = useState("");
  const [respondendo, setRespondendo] = useState(false);
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fim.current?.scrollIntoView({ block: "end" });
  }, [mensagens]);

  function atualizarUltima(mudar: (m: Mensagem) => Mensagem) {
    setMensagens((atuais) => [...atuais.slice(0, -1), mudar(atuais[atuais.length - 1])]);
  }

  async function enviar(pergunta: string) {
    const limpa = pergunta.trim();
    if (!limpa || respondendo) return;
    const historico: Mensagem[] = [...mensagens.filter((m) => m.texto), { papel: "user", texto: limpa, ferramentas: [] }];
    setMensagens([...historico, { papel: "assistant", texto: "", ferramentas: [] }]);
    setTexto("");
    setRespondendo(true);

    try {
      const resposta = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensagens: historico.slice(-20).map(({ papel, texto }) => ({ papel, texto })) }),
      });
      if (resposta.status === 401) {
        irParaEntrar();
        return;
      }
      if (!resposta.body) throw new Error("sem corpo");
      const leitor = resposta.body.pipeThrough(new TextDecoderStream()).getReader();
      let sobra = "";
      for (;;) {
        const { value, done } = await leitor.read();
        if (done) break;
        sobra += value;
        const partes = sobra.split("\n");
        sobra = partes.pop() ?? "";
        for (const linha of partes) {
          if (!linha.trim()) continue;
          const evento = JSON.parse(linha) as Evento;
          if (evento.tipo === "texto") atualizarUltima((m) => ({ ...m, texto: m.texto + evento.texto }));
          if (evento.tipo === "ferramenta") atualizarUltima((m) => ({ ...m, ferramentas: [...m.ferramentas, NOMES[evento.nome] ?? evento.nome] }));
          if (evento.tipo === "erro") atualizarUltima((m) => ({ ...m, erro: evento.mensagem }));
          if (evento.tipo === "fim") atualizarUltima((m) => ({ ...m, rodape: rodape(evento) }));
        }
      }
    } catch {
      atualizarUltima((m) => ({ ...m, erro: "Não consegui falar com a API. Tenta de novo?" }));
    } finally {
      setRespondendo(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-4 pb-4 pt-6">
      <header className="flex items-center justify-between">
        <span />
        {mensagens.length > 0 && (
          <button type="button" onClick={() => setMensagens([])} disabled={respondendo} className="text-sm text-suave hover:underline disabled:opacity-40">
            nova conversa
          </button>
        )}
      </header>

      <div className="flex-1">
        {mensagens.length === 0 ? (
          <section className="mt-10">
            <h1 className="text-2xl font-semibold tracking-tight">Pergunte sobre o seu dinheiro</h1>
            <p className="mt-2 text-sm text-suave">
              O Claude responde consultando o seu ledger com as mesmas ferramentas do servidor MCP. Todo número vem de uma consulta, não de
              chute.
            </p>
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {SUGESTOES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => enviar(s)}
                  className="rounded-2xl border border-borda bg-superficie px-4 py-3 text-left text-sm hover:border-destaque"
                >
                  {s}
                </button>
              ))}
            </div>
          </section>
        ) : (
          <ol className="mt-6 space-y-5">
            {mensagens.map((m, i) =>
              m.papel === "user" ? (
                <li key={i} className="ml-auto max-w-[85%] rounded-2xl bg-destaque px-4 py-2.5 text-sobre-destaque">
                  {m.texto}
                </li>
              ) : (
                <li key={i} className="max-w-full">
                  {m.ferramentas.length > 0 && (
                    <div className="mb-2 flex flex-wrap gap-1">
                      {m.ferramentas.map((f, j) => (
                        <span key={j} className="rounded-full bg-trilho px-2 py-0.5 text-[11px] text-suave">
                          consultou {f}
                        </span>
                      ))}
                    </div>
                  )}
                  {m.texto ? (
                    <div className="resposta text-[15px] leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.texto}</ReactMarkdown>
                    </div>
                  ) : (
                    !m.erro && respondendo && i === mensagens.length - 1 && <p className="animate-pulse text-sm text-suave">pensando…</p>
                  )}
                  {m.erro && <p className="mt-2 text-sm text-[var(--humor-estourou)]">{m.erro}</p>}
                  {m.rodape && <p className="mt-2 text-[11px] text-suave">{m.rodape}</p>}
                </li>
              ),
            )}
          </ol>
        )}
        <div ref={fim} />
      </div>

      <form
        className="sticky bottom-0 mt-6 flex gap-2 bg-fundo pt-2"
        onSubmit={(e) => {
          e.preventDefault();
          enviar(texto);
        }}
      >
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          maxLength={4000}
          placeholder="Ex.: quanto gastei com mercado em outubro?"
          className="min-w-0 flex-1 rounded-xl border border-borda bg-superficie px-4 py-3 outline-none focus:border-destaque"
        />
        <button
          type="submit"
          disabled={!texto.trim() || respondendo}
          className="rounded-xl bg-destaque px-4 py-3 font-semibold text-sobre-destaque disabled:opacity-40"
        >
          Enviar
        </button>
      </form>
    </main>
  );
}
