"use client";

import { X } from "lucide-react";
import { type ReactNode, type RefObject, Suspense, use, useEffect, useRef, useState, useTransition } from "react";

import { anotarGasto, definirTeto, salvarRenda, voltarAoSalario } from "@/app/acoes";
import { CampoReais } from "@/components/CampoReais";
import { Capivara } from "@/components/Capivara";
import type { Categorias, Cofrinho, Fala } from "@/lib/cofrinho";
import { type Diagnostico, type Renda, formatarDiaMes, nomeDoMes } from "@/lib/diagnostico";
import { formatarPorcento, formatarReais } from "@/lib/formato";

const ARCO = { x: 12, largura: 76, altura: 76 };
const DURACAO = 1800;

function posicaoNoArco(p: number) {
  const angulo = Math.PI * (1 - p);
  return {
    x: ARCO.x + ARCO.largura / 2 + (ARCO.largura / 2) * Math.cos(angulo),
    y: 100 - ARCO.altura * Math.sin(angulo),
  };
}

function useSubida(alvo: number) {
  const [p, setP] = useState(0);
  useEffect(() => {
    let quadro = 0;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      quadro = requestAnimationFrame(() => setP(alvo));
      return () => cancelAnimationFrame(quadro);
    }
    const inicio = performance.now();
    const passo = (agora: number) => {
      const t = Math.min((agora - inicio) / DURACAO, 1);
      setP(alvo * (1 - Math.pow(2, -10 * t)));
      if (t < 1) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [alvo]);
  return p;
}

function Folha({ refDialogo, titulo, children }: { refDialogo: RefObject<HTMLDialogElement | null>; titulo: string; children: ReactNode }) {
  return (
    <dialog
      ref={refDialogo}
      aria-label={titulo}
      className="m-auto mb-0 w-full max-w-md rounded-t-2xl border border-borda bg-superficie p-0 text-texto backdrop:bg-black/60 sm:mb-auto sm:rounded-2xl"
      onClick={(e) => e.target === e.currentTarget && e.currentTarget.close()}
    >
      <div className="p-5">
        <div className="flex items-center justify-between">
          <h2 className="largo text-lg font-bold">{titulo}</h2>
          <button type="button" onClick={() => refDialogo.current?.close()} className="rounded-lg p-1.5 text-suave hover:bg-elevada hover:text-texto" aria-label="Fechar">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}

function EditorDeRenda({ renda, aoFechar, className }: { renda: Renda | null; aoFechar: () => void; className?: string }) {
  const [valor, setValor] = useState(renda?.valor_centavos ?? 0);
  const [variavel, setVariavel] = useState(renda?.variavel ?? false);
  const [tocou, setTocou] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [pendente, iniciar] = useTransition();

  return (
    <form
      className={className ?? "space-y-3 border-t border-borda px-4 py-4 sm:px-6"}
      onSubmit={(e) => {
        e.preventDefault();
        setTocou(true);
        setErro(null);
        iniciar(async () => {
          try {
            await salvarRenda(valor, variavel);
            aoFechar();
          } catch {
            setErro("Não consegui salvar a renda. Tenta de novo?");
          }
        });
      }}
    >
      <div className="flex rounded-xl border border-borda p-1 text-sm" role="radiogroup" aria-label="Como é a sua renda">
        {[
          { variavel: false, rotulo: "Salário fixo" },
          { variavel: true, rotulo: "Média (renda varia)" },
        ].map((opcao) => (
          <button
            key={opcao.rotulo}
            type="button"
            role="radio"
            aria-checked={variavel === opcao.variavel}
            onClick={() => setVariavel(opcao.variavel)}
            className="flex-1 rounded-lg px-3 py-2 text-suave aria-checked:bg-elevada aria-checked:font-semibold aria-checked:text-texto"
          >
            {opcao.rotulo}
          </button>
        ))}
      </div>
      <CampoReais
        rotulo={variavel ? "Média do que entra por mês, nos últimos 3 a 6 meses" : "Salário por mês, depois dos descontos"}
        centavos={valor}
        grande={false}
        onChange={(c) => {
          setValor(c);
          setTocou(true);
        }}
        dica="Esse valor vira o teto padrão de todo mês: o sol se põe quando os gastos chegam nele. Dá para usar um teto diferente em um mês específico."
      />
      {tocou && valor === 0 && (
        <p className="text-sm text-suave" role="status">
          Renda zero vale. O mês mostra como os gastos se dividem, sem percentuais da renda e sem teto padrão.
        </p>
      )}
      {erro && (
        <p className="text-sm text-brasa" role="alert">
          {erro}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={pendente} className="rounded-xl bg-destaque px-4 py-2.5 font-semibold text-sobre-destaque disabled:opacity-50">
          {pendente ? "Salvando…" : "Salvar renda"}
        </button>
        {renda && (
          <button type="button" onClick={aoFechar} className="rounded-xl border border-borda px-4 py-2.5 font-medium hover:bg-elevada">
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}

function Numero({ rotulo, valor, detalhe, cor }: { rotulo: string; valor: string; detalhe?: ReactNode; cor?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-suave">{rotulo}</dt>
      <dd className={`largo mt-0.5 truncate text-base font-semibold sm:text-xl ${cor ?? ""}`}>{valor}</dd>
      {detalhe && <dd className="mt-0.5 text-xs text-suave">{detalhe}</dd>}
    </div>
  );
}

function FalaDaCapi({ promessa }: { promessa: Promise<Fala> }) {
  return use(promessa).texto;
}

function Pensando() {
  return (
    <span className="inline-flex translate-y-[-2px] gap-1 align-middle" role="img" aria-label="Capi tá pensando">
      {[0, 150, 300].map((atraso) => (
        <span key={atraso} className="size-1.5 animate-pulse rounded-full bg-current motion-reduce:animate-none" style={{ animationDelay: `${atraso}ms` }} />
      ))}
    </span>
  );
}

export function PrimeiraRenda() {
  return (
    <section aria-labelledby="titulo-renda" className="overflow-hidden bg-agua sm:rounded-2xl">
      <div
        className="h-24 sm:h-28"
        style={{ background: "linear-gradient(to bottom, var(--ceu-alto) 0%, var(--ceu-meio) 45%, var(--ceu-baixo) 82%, var(--horizonte) 100%)" }}
        aria-hidden
      />
      <div className="border-t px-4 py-5 sm:px-6" style={{ borderColor: "color-mix(in srgb, var(--horizonte) 60%, transparent)" }}>
        <h2 id="titulo-renda" className="largo text-2xl font-bold">
          Quanto você recebe por mês?
        </h2>
        <p className="mt-1 text-sm text-suave">É o primeiro passo: sem isso não dá para saber quanto do mês já foi.</p>
        <EditorDeRenda renda={null} aoFechar={() => undefined} className="mt-4 space-y-3" />
      </div>
    </section>
  );
}

export function Ceu({
  diagnostico: d,
  cofrinho,
  fala = null,
  categorias,
  modoDemo,
  semDados,
}: {
  diagnostico: Diagnostico;
  cofrinho: Cofrinho | null;
  fala?: Promise<Fala> | null;
  categorias: Categorias;
  modoDemo: boolean;
  semDados: boolean;
}) {
  const renda = d.renda;
  const teto = cofrinho?.teto_centavos ?? null;
  const gasto = d.totais.gastos_centavos;
  const limite = teto ?? (renda && renda.valor_centavos > 0 ? renda.valor_centavos : null);
  const fracao = limite ? gasto / limite : 0;
  const passou = limite !== null && fracao > 1;
  const p = useSubida(semDados ? 0 : Math.min(fracao, 0.97));
  const forca = Math.min(p / 0.97, 1);
  const sol = posicaoNoArco(p);
  const tamanho = 36 + (passou ? 52 : 40) * forca;
  const corDoSol = passou
    ? `color-mix(in oklab, var(--poente) ${Math.round((1 - forca) * 100)}%, var(--brasa))`
    : `color-mix(in oklab, var(--sol-meio) ${Math.round((1 - forca) * 100)}%, var(--poente))`;

  const [editando, setEditando] = useState(false);
  const doSalario = cofrinho?.teto_origem === "renda";
  const [pendente, iniciar] = useTransition();
  const [erro, setErro] = useState<string | null>(null);
  const folhaGasto = useRef<HTMLDialogElement>(null);
  const folhaTeto = useRef<HTMLDialogElement>(null);
  const [valor, setValor] = useState(0);
  const [categoria, setCategoria] = useState(categorias.despesa.includes("Mercado") ? "Mercado" : (categorias.despesa[0] ?? "Outros"));
  const [descricao, setDescricao] = useState("");
  const [novoTeto, setNovoTeto] = useState(teto ?? 0);

  function executar(acao: () => Promise<void>, folha: RefObject<HTMLDialogElement | null>) {
    setErro(null);
    iniciar(async () => {
      try {
        await acao();
        folha.current?.close();
      } catch {
        setErro("Não consegui salvar. Tenta de novo?");
      }
    });
  }

  const mes = nomeDoMes(d.mes).split(" ")[0].toLowerCase();
  const periodo = d.periodo.inicio && d.periodo.fim && d.periodo.parcial ? `extrato de ${formatarDiaMes(d.periodo.inicio)} a ${formatarDiaMes(d.periodo.fim)}` : null;
  const pode = cofrinho?.pode_gastar_centavos ?? null;

  let linhaDoTeto: ReactNode;
  if (semDados) linhaDoTeto = "Solte o extrato e a fatura logo acima e o sol começa a andar.";
  else if (teto !== null && pode !== null)
    linhaDoTeto =
      pode >= 0 ? (
        <>
          Pode gastar <strong className="font-semibold text-texto">{formatarReais(pode)}</strong> {doSalario ? "do seu salário" : "do teto deste mês"} de{" "}
          {formatarReais(teto)}
          {cofrinho && cofrinho.dias_restantes > 0 && cofrinho.por_dia_centavos !== null && cofrinho.por_dia_centavos > 0 && ` · ${formatarReais(cofrinho.por_dia_centavos)}/dia`}
        </>
      ) : (
        <>
          Passou {doSalario ? "do seu salário" : "do teto deste mês"} de {formatarReais(teto)} em{" "}
          <strong className="font-semibold text-brasa">{formatarReais(-pode)}</strong>
        </>
      );
  else if (limite !== null) linhaDoTeto = `O sol se põe quando os gastos chegam à renda de ${formatarReais(limite)}.`;
  else linhaDoTeto = "Com renda zero não há teto padrão. Defina um teto para este mês e o sol começa a andar.";

  return (
    <section aria-labelledby="titulo-mes" className="overflow-hidden bg-agua sm:rounded-2xl">
      <div
        className="relative h-56 overflow-hidden sm:h-64"
        style={{
          background: passou
            ? "linear-gradient(to bottom, var(--ceu-brasa-alto) 0%, var(--ceu-brasa-meio) 45%, var(--ceu-brasa-baixo) 82%, var(--horizonte-brasa) 100%)"
            : "linear-gradient(to bottom, var(--ceu-alto) 0%, var(--ceu-meio) 45%, var(--ceu-baixo) 82%, var(--horizonte) 100%)",
        }}
      >
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(circle at ${sol.x}% ${sol.y}%, color-mix(in srgb, var(--sol) ${Math.round(10 + 40 * forca)}%, transparent) 0%, transparent ${30 + 25 * forca}%)`,
          }}
          aria-hidden
        />
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 size-full" aria-hidden>
          <path
            d={`M ${ARCO.x} 100 A ${ARCO.largura / 2} ${ARCO.altura} 0 0 1 ${ARCO.x + ARCO.largura} 100`}
            pathLength={100}
            fill="none"
            stroke="var(--texto)"
            strokeOpacity={0.22}
            strokeWidth={1.5}
            strokeDasharray="1 2.5"
            vectorEffect="non-scaling-stroke"
          />
          {p > 0.005 && (
            <path
              d={`M ${ARCO.x} 100 A ${ARCO.largura / 2} ${ARCO.altura} 0 0 1 ${sol.x.toFixed(3)} ${sol.y.toFixed(3)}`}
              fill="none"
              stroke={passou ? "var(--brasa)" : "var(--sol)"}
              strokeOpacity={0.6}
              strokeWidth={2}
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>
        {limite !== null && !semDados && (
          <div
            className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full"
            style={{
              left: `${sol.x}%`,
              top: `${sol.y}%`,
              width: tamanho,
              height: tamanho,
              background: `radial-gradient(circle at 50% 45%, var(--sol-claro) 0%, ${corDoSol} 70%)`,
              boxShadow: `0 4px ${18 + 50 * forca}px ${4 + 16 * forca}px color-mix(in srgb, ${passou ? "var(--brasa)" : "var(--sol)"} ${Math.round(20 + 45 * forca)}%, transparent)`,
            }}
            aria-hidden
          />
        )}
        <div className="absolute inset-x-0 -bottom-7 flex justify-center" aria-hidden>
          <Capivara humor={cofrinho?.humor ?? "tranquila"} className="w-20 sm:w-24" />
        </div>
        <p className="relative px-4 pt-3 text-xs font-medium text-texto/85 sm:px-6 sm:pt-4">
          {nomeDoMes(d.mes)}
          {periodo && ` · ${periodo}`}
        </p>
      </div>

      <div
        className="relative border-t px-4 pb-5 pt-4 text-center sm:px-6"
        style={{
          borderColor: passou ? "var(--horizonte-brasa)" : "color-mix(in srgb, var(--horizonte) 60%, transparent)",
          background: "linear-gradient(to bottom, var(--agua-clara), var(--agua) 60%)",
        }}
      >
        {cofrinho && !semDados && (
          <div className="relative mx-auto mb-4 max-w-[22rem] rounded-2xl bg-balao px-4 py-2.5 text-sm text-balao-texto">
            <span className="absolute -top-1.5 left-1/2 size-3 -translate-x-1/2 rotate-45 bg-balao" aria-hidden />
            <p aria-live="polite">
              <span className="font-semibold">Capi: </span>
              {fala ? (
                <Suspense fallback={<Pensando />}>
                  <FalaDaCapi promessa={fala} />
                </Suspense>
              ) : (
                cofrinho.fala.texto
              )}
            </p>
          </div>
        )}
        <h2 id="titulo-mes" className="text-sm text-suave">
          Gastos de {mes}
        </h2>
        <p className="largo mt-0.5 text-4xl font-bold sm:text-5xl">{formatarReais(semDados ? 0 : gasto)}</p>
        <p className="mx-auto mt-1 max-w-[34ch] text-sm text-suave">{linhaDoTeto}</p>

        {!semDados && (
          <div className="mx-auto mt-4 grid max-w-sm grid-cols-[1fr_auto] gap-2">
            <button
              type="button"
              disabled={modoDemo}
              onClick={() => folhaGasto.current?.showModal()}
              className="rounded-xl bg-destaque px-4 py-3 font-semibold text-sobre-destaque disabled:opacity-50"
            >
              + Anotar gasto
            </button>
            <button
              type="button"
              disabled={modoDemo}
              onClick={() => {
                setNovoTeto(teto ?? 0);
                folhaTeto.current?.showModal();
              }}
              className="rounded-xl border border-borda px-4 py-3 font-medium hover:bg-elevada disabled:opacity-50"
            >
              Teto do mês
            </button>
          </div>
        )}
        {modoDemo && <p className="mt-2 text-xs text-suave">Na demonstração não dá para anotar gastos nem mudar o teto.</p>}
      </div>

      <dl className="grid grid-cols-3 gap-3 border-t border-borda px-4 py-4 sm:px-6">
        <Numero
          rotulo="Renda mensal"
          valor={formatarReais(renda?.valor_centavos ?? 0)}
          detalhe={
            modoDemo ? (
              "fictícia"
            ) : (
              <button type="button" onClick={() => setEditando(!editando)} className="underline decoration-borda underline-offset-2 hover:text-texto">
                {renda ? (editando ? "fechar" : "alterar") : "informar"}
              </button>
            )
          }
          cor="text-correnteza"
        />
        <Numero
          rotulo="Da renda já foi"
          valor={d.comprometimento !== null ? formatarPorcento(d.comprometimento) : gasto === 0 ? formatarPorcento(0) : "sem renda"}
          cor={d.comprometimento !== null && d.comprometimento > 1 ? "text-brasa" : undefined}
        />
        <Numero
          rotulo="Renda − gastos"
          valor={d.diferenca_centavos !== null ? formatarReais(d.diferenca_centavos) : gasto === 0 ? formatarReais(0) : "sem renda"}
          detalhe="não é o saldo da conta"
          cor={d.diferenca_centavos !== null && d.diferenca_centavos < 0 ? "text-brasa" : undefined}
        />
      </dl>
      {editando && !modoDemo && <EditorDeRenda renda={renda} aoFechar={() => setEditando(false)} />}

      <Folha refDialogo={folhaGasto} titulo="Anotar gasto">
        <form
          className="mt-4 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (valor <= 0) return;
            executar(async () => {
              await anotarGasto(valor, categoria, descricao);
              setValor(0);
              setDescricao("");
            }, folhaGasto);
          }}
        >
          <CampoReais rotulo="Quanto" centavos={valor} onChange={setValor} />
          <fieldset>
            <legend className="text-sm text-suave">Com o quê</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {categorias.despesa.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCategoria(c)}
                  aria-pressed={categoria === c}
                  className="rounded-lg border border-borda px-3 py-1.5 text-sm aria-pressed:border-poente aria-pressed:bg-destaque-fundo aria-pressed:text-poente"
                >
                  {c}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="block">
            <span className="text-sm text-suave">Descrição (opcional)</span>
            <input
              value={descricao}
              maxLength={200}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder={categoria}
              className="mt-1 w-full rounded-xl border border-borda bg-fundo px-4 py-2.5 outline-none focus:border-poente"
            />
          </label>
          {erro && <p className="text-sm text-brasa">{erro}</p>}
          <button type="submit" disabled={valor <= 0 || pendente} className="w-full rounded-xl bg-destaque px-4 py-3 font-semibold text-sobre-destaque disabled:opacity-50">
            {pendente ? "Anotando…" : "Anotar"}
          </button>
        </form>
      </Folha>

      <Folha refDialogo={folhaTeto} titulo={`Teto de ${mes}`}>
        <form
          className="mt-4 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (novoTeto <= 0) return;
            executar(() => definirTeto(d.mes, novoTeto), folhaTeto);
          }}
        >
          <p className="text-sm text-suave">
            {doSalario
              ? `Hoje o teto de ${mes} é o seu salário (${formatarReais(teto ?? 0)}). Mude só se quiser um limite diferente neste mês.`
              : renda && renda.valor_centavos > 0
                ? `Este mês tem um teto próprio. Os outros meses continuam usando o seu salário (${formatarReais(renda.valor_centavos)}).`
                : "Sem renda informada, o teto vale só para este mês."}
          </p>
          <CampoReais rotulo={`Teto de ${mes}`} centavos={novoTeto} onChange={setNovoTeto} dica="O sol se põe quando os gastos chegam aqui." />
          {erro && <p className="text-sm text-brasa">{erro}</p>}
          <button type="submit" disabled={novoTeto <= 0 || pendente} className="w-full rounded-xl bg-destaque px-4 py-3 font-semibold text-sobre-destaque disabled:opacity-50">
            {pendente ? "Salvando…" : `Usar este teto em ${mes}`}
          </button>
          {cofrinho?.teto_origem === "mes" && renda && renda.valor_centavos > 0 && (
            <button
              type="button"
              disabled={pendente}
              onClick={() => executar(() => voltarAoSalario(d.mes), folhaTeto)}
              className="w-full rounded-xl border border-borda px-4 py-3 font-medium hover:bg-elevada disabled:opacity-50"
            >
              Voltar ao salário ({formatarReais(renda.valor_centavos)})
            </button>
          )}
        </form>
      </Folha>
    </section>
  );
}
