"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { aplicarRevisao, previaDaRevisao } from "@/app/acoes";
import { formatarData, formatarReais } from "@/lib/formato";
import type { ConteudoProposta, OpcoesAplicacao, Previa, ResultadoLote } from "@/lib/revisao";

import { Dialogo } from "./Dialogo";

export const OPCOES_PADRAO: OpcoesAplicacao = { alcance: "selecionadas", salvar_regra: false, substituir_manuais: false, confirmar_transferencia: false };

function novaChave() {
  return crypto.randomUUID().replaceAll("-", "");
}

export function TabelaDaPrevia({ linhas, comMotivo = false }: { linhas: Previa["afetadas"]; comMotivo?: boolean }) {
  return (
    <ul className="divide-y divide-borda rounded-xl border border-borda text-sm">
      {linhas.map((l) => (
        <li key={l.id} className="grid gap-0.5 px-3 py-2">
          <div className="flex justify-between gap-3">
            <span className="min-w-0 truncate" title={l.descricao}>
              {l.descricao}
            </span>
            <span className="shrink-0 tabular-nums">{formatarReais(l.valor_centavos)}</span>
          </div>
          <div className="flex flex-wrap gap-x-3 text-xs text-suave">
            <span>{formatarData(l.data)}</span>
            {comMotivo ? (
              <span>{l.motivo}</span>
            ) : (
              <>
                <span>
                  {l.categoria_atual === l.categoria_nova ? l.categoria_atual : `${l.categoria_atual} → ${l.categoria_nova}`}
                </span>
                {l.estabelecimento_novo && l.estabelecimento_novo !== l.estabelecimento_atual && <span>estabelecimento: {l.estabelecimento_novo}</span>}
                {l.por === "regra" && <span className="text-poente">pela regra</span>}
              </>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Aprovacao({
  conteudo,
  propostaId,
  aoFechar,
  aoAplicar,
}: {
  conteudo: ConteudoProposta;
  propostaId: number | null;
  aoFechar: () => void;
  aoAplicar: (resultado: ResultadoLote) => void;
}) {
  const [opcoes, setOpcoes] = useState<OpcoesAplicacao>(OPCOES_PADRAO);
  const [previa, setPrevia] = useState<Previa | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [aplicando, setAplicando] = useState(false);
  const [verIgnoradas, setVerIgnoradas] = useState(false);
  const [versao, setVersao] = useState(0);
  const chave = useMemo(() => (previa ? novaChave() : ""), [previa]);

  useEffect(() => {
    let vivo = true;
    void previaDaRevisao(conteudo, opcoes).then((r) => {
      if (!vivo) return;
      setCarregando(false);
      if (r.ok) {
        setPrevia(r.dados);
        setErro(null);
      } else {
        setPrevia(null);
        setErro(r.erro);
      }
    });
    return () => {
      vivo = false;
    };
  }, [conteudo, opcoes, versao]);

  function recalcular() {
    setPrevia(null);
    setCarregando(true);
    setVersao((v) => v + 1);
  }

  function mudar(parcial: Partial<OpcoesAplicacao>) {
    setPrevia(null);
    setCarregando(true);
    setOpcoes((atual) => ({ ...atual, ...parcial }));
  }

  async function aplicar() {
    if (!previa || aplicando) return;
    setAplicando(true);
    setErro(null);
    const r = await aplicarRevisao(conteudo, opcoes, previa.assinatura, chave, propostaId);
    setAplicando(false);
    if (r.ok) {
      aoAplicar(r.dados);
      return;
    }
    if (r.status === 409) recalcular();
    setErro(r.erro);
  }

  const regraValida = Boolean(previa?.regra?.valida);
  const podeAplicar =
    previa !== null &&
    !carregando &&
    !aplicando &&
    (!previa.exige_confirmar_transferencia || opcoes.confirmar_transferencia) &&
    (previa.afetadas.length > 0 || opcoes.salvar_regra);

  return (
    <Dialogo titulo="Revisar antes de aplicar" aoFechar={aoFechar} largo>
      <div className="space-y-4 text-sm">
        <div className="rounded-xl bg-superficie p-3">
          <p className="font-medium">
            {conteudo.estabelecimento ? `Estabelecimento: ${conteudo.estabelecimento}` : "Estabelecimento: fica como está"}
          </p>
          <p className="text-suave">{conteudo.categoria ? `Categoria: ${conteudo.categoria}` : "Categoria: fica como está (pendente)"}</p>
          <p className="mt-1 text-xs text-suave">Você selecionou {conteudo.transacao_ids.length} transação(ões).</p>
        </div>

        <fieldset className="space-y-2">
          <legend className="mb-1 font-medium">Onde aplicar</legend>
          <label className="flex items-start gap-2">
            <input type="radio" name="alcance" checked={opcoes.alcance === "selecionadas"} onChange={() => mudar({ alcance: "selecionadas" })} className="mt-1" />
            <span>Só nas transações selecionadas</span>
          </label>
          <label className={`flex items-start gap-2 ${conteudo.regra ? "" : "opacity-50"}`}>
            <input
              type="radio"
              name="alcance"
              disabled={!conteudo.regra || (previa !== null && !regraValida)}
              checked={opcoes.alcance === "correspondencias"}
              onChange={() => mudar({ alcance: "correspondencias" })}
              className="mt-1"
            />
            <span>
              Também nas transações que já existem e casam com a regra{conteudo.regra ? ` ${conteudo.regra.padrao.toUpperCase()}` : ""}
              {previa?.regra && previa.regra.valida && <span className="text-suave"> ({previa.regra.correspondencias_existentes} no total)</span>}
            </span>
          </label>
          {conteudo.regra && (
            <label className={`flex items-start gap-2 ${previa !== null && !regraValida ? "opacity-50" : ""}`}>
              <input
                type="checkbox"
                disabled={previa !== null && !regraValida}
                checked={opcoes.salvar_regra}
                onChange={(e) => mudar({ salvar_regra: e.target.checked })}
                className="mt-1"
              />
              <span>
                Salvar a regra <strong>{conteudo.regra.padrao.toUpperCase()}</strong> para as próximas importações
                <span className="block text-xs text-suave">
                  {conteudo.regra.categoria ? `vira ${conteudo.regra.categoria}` : "não muda a categoria"}
                  {conteudo.regra.estabelecimento ? ` · estabelecimento ${conteudo.regra.estabelecimento}` : ""}
                </span>
              </span>
            </label>
          )}
          {previa?.regra?.erro && <p className="text-xs text-brasa">A regra não pode ser usada: {previa.regra.erro}.</p>}
          {previa?.regra?.existente && regraValida && (
            <p className="text-xs text-suave">
              Já existe a regra {previa.regra.existente.padrao} → {previa.regra.existente.categoria ?? "sem categoria"}; salvar substitui.
            </p>
          )}
          {(previa?.manuais_preservadas ?? 0) > 0 || opcoes.substituir_manuais ? (
            <label className="flex items-start gap-2">
              <input type="checkbox" checked={opcoes.substituir_manuais} onChange={(e) => mudar({ substituir_manuais: e.target.checked })} className="mt-1" />
              <span>Substituir também as que você classificou à mão antes</span>
            </label>
          ) : null}
          {previa?.exige_confirmar_transferencia && (
            <label className="flex items-start gap-2 rounded-xl border border-poente/40 bg-destaque-fundo p-2">
              <input
                type="checkbox"
                checked={opcoes.confirmar_transferencia}
                onChange={(e) => mudar({ confirmar_transferencia: e.target.checked })}
                className="mt-1"
              />
              <span>Confirmo que esse dinheiro foi para outra conta minha, e por isso não é gasto.</span>
            </label>
          )}
        </fieldset>

        {carregando && <p aria-live="polite" className="text-suave">Calculando a prévia…</p>}
        {erro && (
          <p role="alert" className="rounded-xl bg-brasa/10 px-3 py-2 text-brasa">
            {erro.charAt(0).toUpperCase() + erro.slice(1)}.
          </p>
        )}

        {previa && (
          <>
            {previa.avisos.length > 0 && (
              <ul className="space-y-1">
                {previa.avisos.map((a) => (
                  <li key={a} className="flex gap-2 text-suave">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-poente" aria-hidden />
                    {a}
                  </li>
                ))}
              </ul>
            )}
            <p className="font-medium" aria-live="polite">
              {previa.afetadas.length} transação(ões) vão mudar
              {previa.efeito_nos_gastos_centavos !== 0 && (
                <span className="font-normal text-suave">
                  {" "}
                  · total de gastos {previa.efeito_nos_gastos_centavos < 0 ? "cai" : "sobe"} {formatarReais(Math.abs(previa.efeito_nos_gastos_centavos))}
                </span>
              )}
            </p>
            {previa.afetadas.length > 0 && (
              <div className="max-h-64 overflow-y-auto">
                <TabelaDaPrevia linhas={previa.afetadas} />
              </div>
            )}
            {previa.ignoradas.length > 0 && (
              <div>
                <button type="button" onClick={() => setVerIgnoradas((v) => !v)} className="text-suave underline underline-offset-4" aria-expanded={verIgnoradas}>
                  {previa.ignoradas.length} ficam como estão
                </button>
                {verIgnoradas && (
                  <div className="mt-2 max-h-48 overflow-y-auto">
                    <TabelaDaPrevia linhas={previa.ignoradas} comMotivo />
                  </div>
                )}
              </div>
            )}
          </>
        )}

        <div className="flex flex-col-reverse gap-2 border-t border-borda pt-4 sm:flex-row sm:justify-end">
          <button type="button" onClick={aoFechar} className="rounded-xl border border-borda px-4 py-2.5 hover:bg-elevada">
            Cancelar
          </button>
          <button
            type="button"
            onClick={aplicar}
            disabled={!podeAplicar}
            className="rounded-xl bg-destaque px-4 py-2.5 font-semibold text-sobre-destaque disabled:opacity-40"
          >
            {aplicando ? "Aplicando…" : previa ? `Aprovar e aplicar${previa.afetadas.length ? ` (${previa.afetadas.length})` : ""}` : "Aprovar e aplicar"}
          </button>
        </div>
      </div>
    </Dialogo>
  );
}
