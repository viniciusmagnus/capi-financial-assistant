"use client";

import { Check, CircleAlert, FileUp, LoaderCircle, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { categorizarImportacoes } from "@/app/acoes";
import type { ResultadoCategorizacao } from "@/lib/cofrinho";
import { type ResultadoImportacao, formatarDiaMes } from "@/lib/diagnostico";
import { irParaEntrar } from "@/lib/sessao-cliente";

const LIMITE = 5 * 1024 * 1024;
const MAXIMO = 12;
const ACEITOS = /\.(ofx|qfx|csv|pdf)$/i;

type Estado = "fila" | "enviando" | "lendo" | "ok" | "erro";
type Item = { id: string; nome: string; estado: Estado; progresso: number; resultado?: ResultadoImportacao; erro?: string };
type Fase = "ocioso" | "importando" | "categorizando" | "pronto";

function enviar(arquivo: File, aoProgredir: (fracao: number) => void, aoTerminarEnvio: () => void) {
  return new Promise<ResultadoImportacao>((resolve, reject) => {
    const formulario = new FormData();
    formulario.append("arquivo", arquivo);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/importar");
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => e.lengthComputable && aoProgredir(e.loaded / e.total);
    xhr.upload.onload = aoTerminarEnvio;
    xhr.onerror = () => reject(new Error("A conexão caiu durante o envio."));
    xhr.onload = () => {
      if (xhr.status === 401) irParaEntrar();
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as ResultadoImportacao);
      else reject(new Error((xhr.response as { erro?: string } | null)?.erro ?? `Falha no envio (${xhr.status}).`));
    };
    xhr.send(formulario);
  });
}

function nomeDaConta(r: ResultadoImportacao) {
  const nome = r.conta.split(":").slice(1).join(":");
  return /cart|conta/i.test(nome) ? nome : `${r.cartao_de_credito ? "cartão" : "conta"} ${nome}`;
}

function Linha({ item }: { item: Item }) {
  const r = item.resultado;
  return (
    <li className="flex items-start gap-3 py-2.5 text-sm">
      <span className="mt-0.5 shrink-0" aria-hidden>
        {item.estado === "ok" ? (
          <Check className="size-4 text-correnteza" />
        ) : item.estado === "erro" ? (
          <CircleAlert className="size-4 text-brasa" />
        ) : item.estado === "fila" ? (
          <span className="block size-4 rounded-full border border-borda" />
        ) : (
          <LoaderCircle className="size-4 animate-spin text-sol" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium">{item.nome}</p>
        <p className={item.estado === "erro" ? "text-brasa" : "text-suave"}>
          {item.estado === "fila" && "na fila"}
          {item.estado === "enviando" && `enviando · ${Math.round(item.progresso * 100)}%`}
          {item.estado === "lendo" && "lendo e descartando repetidas"}
          {item.estado === "erro" && item.erro}
          {item.estado === "ok" && r && (
            <>
              {nomeDaConta(r)} · {r.formato.toUpperCase()}
              {r.inicio && r.fim && ` · ${formatarDiaMes(r.inicio)} a ${formatarDiaMes(r.fim)}`} · {r.novas} {r.novas === 1 ? "nova" : "novas"}
              {r.duplicadas > 0 && `, ${r.duplicadas} já estavam aqui`}
            </>
          )}
        </p>
      </div>
    </li>
  );
}

export function Importador({ modoDemo, destaque }: { modoDemo: boolean; destaque: boolean }) {
  const router = useRouter();
  const idEntrada = useId();
  const entrada = useRef<HTMLInputElement>(null);
  const [itens, setItens] = useState<Item[]>([]);
  const [fase, setFase] = useState<Fase>("ocioso");
  const [arrastando, setArrastando] = useState(false);
  const [categorizacao, setCategorizacao] = useState<ResultadoCategorizacao | null | undefined>(undefined);
  const [aviso, setAviso] = useState<string | null>(null);
  const [detalhes, setDetalhes] = useState(false);
  const ocupado = fase === "importando" || fase === "categorizando";

  const atualizar = (id: string, mudanca: Partial<Item>) => setItens((atuais) => atuais.map((i) => (i.id === id ? { ...i, ...mudanca } : i)));

  const importar = useCallback(
    async (lista: FileList | File[] | null) => {
      const arquivos = Array.from(lista ?? []);
      if (arquivos.length === 0 || ocupado) return;
      setAviso(null);
      if (modoDemo) {
        setAviso("A demonstração não recebe arquivos, para não misturar dados reais com fictícios. Crie uma conta para usar os seus.");
        return;
      }
      const novos: Item[] = arquivos.slice(0, MAXIMO).map((arquivo, i) => ({
        id: `${Date.now()}-${i}`,
        nome: arquivo.name,
        progresso: 0,
        estado: !ACEITOS.test(arquivo.name) ? "erro" : arquivo.size > LIMITE ? "erro" : "fila",
        erro: !ACEITOS.test(arquivo.name)
          ? "Formato não aceito: use OFX, CSV ou o PDF da fatura."
          : arquivo.size > LIMITE
            ? "Passa de 5 MB. Exporte um período menor."
            : undefined,
      }));
      if (arquivos.length > MAXIMO) setAviso(`Importei os ${MAXIMO} primeiros. Solte o resto em seguida.`);
      setItens(novos);
      setDetalhes(false);
      setCategorizacao(undefined);
      setFase("importando");

      const importados: ResultadoImportacao[] = [];
      for (const [i, item] of novos.entries()) {
        if (item.estado === "erro") continue;
        atualizar(item.id, { estado: "enviando" });
        try {
          const resultado = await enviar(
            arquivos[i],
            (fracao) => atualizar(item.id, { progresso: fracao }),
            () => atualizar(item.id, { estado: "lendo" }),
          );
          importados.push(resultado);
          atualizar(item.id, { estado: "ok", resultado });
        } catch (e) {
          atualizar(item.id, { estado: "erro", erro: e instanceof Error ? e.message : "Não consegui importar." });
        }
      }

      if (importados.length === 0) {
        setFase("pronto");
        return;
      }
      setFase("categorizando");
      try {
        setCategorizacao(await categorizarImportacoes(importados.map((r) => r.importacao_id)));
      } catch {
        setCategorizacao(null);
      }
      setFase("pronto");
      const ultimoMes = importados.reduce<string | null>((maior, r) => {
        const mes = r.fim?.slice(0, 7) ?? null;
        return mes && (!maior || mes > maior) ? mes : maior;
      }, null);
      router.push(ultimoMes ? `/?mes=${ultimoMes}` : "/", { scroll: false });
      router.refresh();
    },
    [modoDemo, ocupado, router],
  );

  useEffect(() => {
    let profundidade = 0;
    const temArquivos = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");
    const entrou = (e: DragEvent) => {
      if (!temArquivos(e)) return;
      profundidade += 1;
      setArrastando(true);
    };
    const saiu = (e: DragEvent) => {
      if (!temArquivos(e)) return;
      profundidade = Math.max(0, profundidade - 1);
      if (profundidade === 0) setArrastando(false);
    };
    const sobre = (e: DragEvent) => temArquivos(e) && e.preventDefault();
    const soltou = (e: DragEvent) => {
      if (!temArquivos(e)) return;
      e.preventDefault();
      profundidade = 0;
      setArrastando(false);
      void importar(e.dataTransfer?.files ?? null);
    };
    window.addEventListener("dragenter", entrou);
    window.addEventListener("dragleave", saiu);
    window.addEventListener("dragover", sobre);
    window.addEventListener("drop", soltou);
    return () => {
      window.removeEventListener("dragenter", entrou);
      window.removeEventListener("dragleave", saiu);
      window.removeEventListener("dragover", sobre);
      window.removeEventListener("drop", soltou);
    };
  }, [importar]);

  const ok = itens.filter((i) => i.estado === "ok" && i.resultado).map((i) => i.resultado!);
  const novas = ok.reduce((s, r) => s + r.novas, 0);
  const repetidas = ok.reduce((s, r) => s + r.duplicadas, 0);
  const revisar = categorizacao?.para_revisar_na_importacao ?? ok.reduce((s, r) => s + r.para_revisar, 0);
  const recusados = itens.filter((i) => i.estado === "erro").length;
  const visiveis = fase !== "pronto" || detalhes ? itens : itens.filter((i) => i.estado === "erro");

  return (
    <section aria-label="Importar arquivos" className={destaque ? "py-2" : ""}>
      <div
        className={`flex flex-col gap-3 rounded-2xl border px-4 py-3 transition-colors sm:flex-row sm:items-center sm:px-5 ${
          destaque ? "border-poente/60 bg-destaque-fundo py-5" : "border-borda bg-superficie"
        }`}
      >
        <FileUp className={`hidden shrink-0 sm:block ${destaque ? "size-7 text-poente" : "size-5 text-suave"}`} aria-hidden />
        <div className="min-w-0 flex-1">
          <p className={destaque ? "largo text-xl font-bold" : "font-semibold"}>
            {destaque ? "Solte aqui o extrato da conta e a fatura do cartão" : "Solte extrato e fatura em qualquer lugar da tela"}
          </p>
          <p className="text-sm text-suave">OFX, CSV ou o PDF da fatura · vários de uma vez · conta e cartão são reconhecidos sozinhos</p>
        </div>
        <label
          htmlFor={idEntrada}
          className={`inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 rounded-xl px-4 py-2.5 font-semibold focus-within:outline-2 focus-within:outline-sol ${
            ocupado ? "pointer-events-none opacity-50" : ""
          } ${destaque ? "bg-destaque text-sobre-destaque" : "border border-borda hover:bg-elevada"}`}
        >
          {ocupado ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <FileUp className="size-4" aria-hidden />}
          {ocupado ? "Importando…" : "Escolher arquivos"}
        </label>
        <input
          ref={entrada}
          id={idEntrada}
          type="file"
          multiple
          accept=".ofx,.qfx,.csv,.pdf"
          className="sr-only"
          disabled={ocupado}
          onChange={(e) => {
            void importar(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {destaque && itens.length === 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-suave hover:text-texto">Onde achar esses arquivos</summary>
          <ul className="mt-2 space-y-1.5 text-suave">
            <li>
              <strong className="font-medium text-texto">Fatura do Nubank:</strong> no app, Cartão › Faturas › escolha a fatura › Exportar. Chega por
              e-mail em CSV e PDF; pode soltar os dois, a mesma compra não conta duas vezes.
            </li>
            <li>
              <strong className="font-medium text-texto">Conta:</strong> extrato em OFX (às vezes chamado de Money ou Quicken) ou CSV, de preferência
              do mês inteiro.
            </li>
            <li>Pagamento de fatura e transferências entre suas contas ficam fora dos gastos.</li>
          </ul>
        </details>
      )}

      {aviso && (
        <p className="mt-3 text-sm text-sol" role="status">
          {aviso}
        </p>
      )}

      {itens.length > 0 && (
        <div className="mt-3 rounded-2xl border border-borda px-4 sm:px-5" aria-live="polite">
          {visiveis.length > 0 && (
            <ul className="divide-y divide-borda border-b border-borda">
              {visiveis.map((item) => (
                <Linha key={item.id} item={item} />
              ))}
            </ul>
          )}
          <div className="flex items-start gap-3 py-3 text-sm">
            <p className="min-w-0 flex-1">
              {fase === "importando" && "Importando um arquivo por vez…"}
              {fase === "categorizando" && "Categorizando: suas regras primeiro, depois a IA…"}
              {fase === "pronto" &&
                (ok.length === 0
                  ? "Nenhum arquivo entrou."
                  : `${novas} ${novas === 1 ? "transação nova" : "transações novas"}${repetidas ? `, ${repetidas} repetidas ignoradas` : ""}${
                      recusados ? `, ${recusados} ${recusados === 1 ? "arquivo recusado" : "arquivos recusados"}` : ""
                    }${revisar ? `, ${revisar} para revisar no gráfico` : ""}. O mês abaixo já está atualizado.`)}
              {fase === "pronto" && categorizacao && !categorizacao.ia_disponivel && (
                <span className="mt-1 block text-suave">
                  A IA não rodou ({categorizacao.motivo}); o que suas regras não cobriram aparece como “A classificar”.
                </span>
              )}
              {fase === "pronto" && categorizacao === null && (
                <span className="mt-1 block text-suave">A categorização falhou; os arquivos estão salvos e aparecem como “A classificar”.</span>
              )}
              {fase === "pronto" && ok.length > 0 && (
                <button
                  type="button"
                  onClick={() => setDetalhes(!detalhes)}
                  aria-expanded={detalhes}
                  className="mt-1 block text-suave underline decoration-borda underline-offset-2 hover:text-texto"
                >
                  {detalhes ? "esconder arquivos" : `ver ${ok.length === 1 ? "o arquivo importado" : `os ${ok.length} arquivos importados`}`}
                </button>
              )}
            </p>
            {fase === "pronto" && (
              <button type="button" onClick={() => setItens([])} aria-label="Fechar resumo da importação" className="rounded-lg p-1 text-suave hover:bg-elevada hover:text-texto">
                <X className="size-4" aria-hidden />
              </button>
            )}
          </div>
        </div>
      )}

      {arrastando && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-fundo/80 p-6 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-3xl border-2 border-dashed border-poente bg-destaque-fundo px-6 py-10 text-center">
            <FileUp className="mx-auto size-10 text-poente" aria-hidden />
            <p className="largo mt-3 text-2xl font-bold">Solte para importar</p>
            <p className="mt-1 text-sm text-suave">Conta e cartão, OFX, CSV ou PDF</p>
          </div>
        </div>
      )}
    </section>
  );
}
