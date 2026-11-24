import { Suspense } from "react";

import { Painel } from "@/components/inicio/Painel";
import { buscarCategorias, buscarCofrinho, buscarDiagnostico, buscarFala } from "@/lib/api";
import { exigirUsuario } from "@/lib/sessao";

async function MesCarregado({ searchParams }: { searchParams: PageProps<"/">["searchParams"] }) {
  const { mes } = await searchParams;
  const mesPedido = typeof mes === "string" ? mes : undefined;
  await exigirUsuario(mesPedido ? `/?mes=${encodeURIComponent(mesPedido)}` : "/");
  const [diagnostico, categorias] = await Promise.all([buscarDiagnostico(mesPedido), buscarCategorias()]);
  const cofrinho = await buscarCofrinho(diagnostico.mes.slice(0, 7)).catch(() => null);
  const fala = cofrinho && cofrinho.fala.autor === "roteiro" ? buscarFala(cofrinho.mes).catch(() => cofrinho.fala) : null;
  return <Painel diagnostico={diagnostico} cofrinho={cofrinho} fala={fala} categorias={categorias} modoDemo={false} />;
}

function CarregandoMes() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 sm:px-4 sm:pt-6" aria-busy>
      <div className="mx-4 mt-4 h-16 rounded-2xl border border-borda bg-superficie sm:mx-0" />
      <div
        className="mt-9 h-64 sm:h-80 sm:rounded-2xl"
        style={{ background: "linear-gradient(to bottom, var(--ceu-alto) 0%, var(--ceu-meio) 40%, var(--agua) 64%)" }}
      >
        <p className="px-4 pt-4 text-sm text-texto/85 sm:px-6">Montando o mês…</p>
      </div>
    </main>
  );
}

export default function Inicio({ searchParams }: PageProps<"/">) {
  return (
    <Suspense fallback={<CarregandoMes />}>
      <MesCarregado searchParams={searchParams} />
    </Suspense>
  );
}
