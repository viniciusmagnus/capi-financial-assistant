"use client";

import { useEffect, useMemo, useState } from "react";

import { aplicarRevisao, previaDaRevisao } from "@/app/acoes";
import type { Previa } from "@/lib/revisao";

import { OPCOES_PADRAO } from "./Aprovacao";
import { Dialogo } from "./Dialogo";
import type { PropostaNaTela } from "./Proposta";

type Linha = { proposta: PropostaNaTela; previa: Previa | null; erro: string | null; chave: string; resultado: string | null };

export function AprovacaoEmLote({
  propostas,
  aoFechar,
  aoTerminar,
}: {
  propostas: PropostaNaTela[];
  aoFechar: () => void;
  aoTerminar: (aplicadas: string[]) => void;
}) {
  const [linhas, setLinhas] = useState<Linha[]>(() =>
    propostas.map((p) => ({ proposta: p, previa: null, erro: null, chave: crypto.randomUUID().replaceAll("-", ""), resultado: null })),
  );
  const [aplicando, setAplicando] = useState(false);
  const [terminou, setTerminou] = useState(false);

  useEffect(() => {
    let vivo = true;
    void Promise.all(propostas.map((p) => previaDaRevisao(p.conteudo, OPCOES_PADRAO))).then((respostas) => {
      if (!vivo) return;
      setLinhas((atuais) =>
        atuais.map((linha, n) => {
          const r = respostas[n];
          if (!r.ok) return { ...linha, erro: r.erro };
          if (r.dados.exige_confirmar_transferencia) return { ...linha, previa: r.dados, erro: "transferência interna: aprove sozinha, com a confirmação" };
          if (r.dados.afetadas.length === 0) return { ...linha, previa: r.dados, erro: "nada muda" };
          return { ...linha, previa: r.dados };
        }),
      );
    });
    return () => {
      vivo = false;
    };
  }, [propostas]);

  const prontas = useMemo(() => linhas.filter((l) => l.previa && !l.erro), [linhas]);
  const calculando = linhas.some((l) => !l.previa && !l.erro);

  async function aplicar() {
    setAplicando(true);
    const aplicadas: string[] = [];
    for (const linha of prontas) {
      const r = await aplicarRevisao(linha.proposta.conteudo, OPCOES_PADRAO, linha.previa!.assinatura, linha.chave, linha.proposta.id);
      setLinhas((atuais) =>
        atuais.map((l) => (l.proposta.chave === linha.proposta.chave ? { ...l, resultado: r.ok ? `${r.dados.alteradas} alterada(s)` : `não aplicada: ${r.erro}` } : l)),
      );
      if (r.ok) aplicadas.push(linha.proposta.chave);
    }
    setAplicando(false);
    setTerminou(true);
    aoTerminar(aplicadas);
  }

  return (
    <Dialogo titulo={`Aprovar ${propostas.length} propostas`} aoFechar={aoFechar} largo>
      <div className="space-y-3 text-sm">
        <p className="text-suave">
          Cada proposta é aplicada só nas transações dela, sem salvar regras. Para salvar uma regra ou aplicar em correspondências, aprove a proposta sozinha.
        </p>
        <ul className="divide-y divide-borda rounded-xl border border-borda">
          {linhas.map((l) => (
            <li key={l.proposta.chave} className="px-3 py-2">
              <p className="font-medium">
                {l.proposta.conteudo.estabelecimento ?? "Estabelecimento não muda"} → {l.proposta.conteudo.categoria ?? "categoria pendente"}
              </p>
              <p className="text-xs text-suave">
                {l.resultado ??
                  (l.erro ? `fica de fora: ${l.erro}` : l.previa ? `${l.previa.afetadas.length} mudam · ${l.previa.ignoradas.length} ficam como estão` : "calculando a prévia…")}
              </p>
            </li>
          ))}
        </ul>
        <div className="flex flex-col-reverse gap-2 border-t border-borda pt-4 sm:flex-row sm:justify-end">
          <button type="button" onClick={aoFechar} className="rounded-xl border border-borda px-4 py-2.5 hover:bg-elevada">
            {terminou ? "Fechar" : "Cancelar"}
          </button>
          {!terminou && (
            <button
              type="button"
              disabled={calculando || aplicando || prontas.length === 0}
              onClick={aplicar}
              className="rounded-xl bg-destaque px-4 py-2.5 font-semibold text-sobre-destaque disabled:opacity-40"
            >
              {aplicando ? "Aplicando…" : `Aprovar e aplicar ${prontas.length}`}
            </button>
          )}
        </div>
      </div>
    </Dialogo>
  );
}
