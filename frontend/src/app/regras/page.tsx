import { Suspense } from "react";

import { Regras } from "@/components/Regras";
import { buscarCategorias, buscarRegras } from "@/lib/api";
import { exigirUsuario } from "@/lib/sessao";

async function RegrasCarregadas() {
  await exigirUsuario("/regras");
  const [regras, categorias] = await Promise.all([buscarRegras(), buscarCategorias()]);
  return <Regras iniciais={regras} categorias={categorias} modoDemo={false} />;
}

export default function PaginaRegras() {
  return (
    <Suspense fallback={<main className="mx-auto w-full max-w-md flex-1 px-4 pt-6 text-suave">Carregando regras…</main>}>
      <RegrasCarregadas />
    </Suspense>
  );
}
