import Link from "next/link";

import { GraficoGastos } from "@/components/diagnostico/GraficoGastos";
import { InsightsCapi } from "@/components/diagnostico/InsightsCapi";
import { Simulador } from "@/components/diagnostico/Simulador";
import { AbasDeMes } from "@/components/inicio/AbasDeMes";
import { Ceu, PrimeiraRenda } from "@/components/inicio/Ceu";
import { ContasDoMes } from "@/components/inicio/DetalhesDoMes";
import { GastosDoMes } from "@/components/inicio/GastosDoMes";
import { Importador } from "@/components/inicio/Importador";
import type { Categorias, Cofrinho, Fala } from "@/lib/cofrinho";
import type { Diagnostico } from "@/lib/diagnostico";

export function Painel({
  diagnostico: d,
  cofrinho,
  fala = null,
  categorias,
  modoDemo,
}: {
  diagnostico: Diagnostico;
  cofrinho: Cofrinho | null;
  fala?: Promise<Fala> | null;
  categorias: Categorias;
  modoDemo: boolean;
}) {
  const semDados = d.meses_disponiveis.length === 0;
  const semRenda = !modoDemo && d.renda === null;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 pb-12 sm:px-4 sm:pt-6">
      {modoDemo && (
        <p className="bg-destaque-fundo px-4 py-2 text-sm sm:rounded-xl">
          <strong className="font-semibold text-poente">Demonstração com dados fictícios.</strong> Nada aqui é de uma pessoa real nem é salvo. Para
          usar os seus extratos,{" "}
          <Link href="/cadastrar" className="font-semibold underline underline-offset-4">
            crie uma conta
          </Link>{" "}
          ou{" "}
          <Link href="/entrar" className="underline underline-offset-4">
            entre
          </Link>
          .
        </p>
      )}

      {semRenda ? (
        <div className="mt-4">
          <PrimeiraRenda />
        </div>
      ) : (
        <>
          <div className="px-4 pt-4 sm:px-0">
            <Importador modoDemo={modoDemo} destaque={semDados} />
          </div>

          {!semDados && <AbasDeMes meses={d.meses_disponiveis} atual={d.mes} />}

          <div className="mt-4">
            <Ceu
              key={`${d.mes}-${d.totais.gastos_centavos}-${cofrinho?.teto_centavos}-${d.renda?.valor_centavos}`}
              diagnostico={d}
              cofrinho={cofrinho}
              fala={fala}
              categorias={categorias}
              modoDemo={modoDemo}
              semDados={semDados}
            />
          </div>

          {!semDados && (
            <div className="mt-8 space-y-14 px-4 sm:px-0">
              <GastosDoMes key={d.mes} diagnostico={d} categorias={categorias} modoDemo={modoDemo} />
              <GraficoGastos key={`grafico-${d.mes}`} diagnostico={d} categorias={categorias} modoDemo={modoDemo} />
              <InsightsCapi diagnostico={d} />
              <Simulador key={`${d.mes}-${d.renda?.valor_centavos}`} diagnostico={d} modoDemo={modoDemo} />
              <ContasDoMes diagnostico={d} />
            </div>
          )}
        </>
      )}
    </main>
  );
}
