import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { Capivara } from "@/components/Capivara";

async function NaHoraDoPedido() {
  await connection();
  return null;
}

export default function NaoEncontrada() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
      <Capivara humor="de_olho" className="w-32 text-texto" />
      <p className="text-lg font-medium">Essa página não existe.</p>
      <p className="text-sm text-suave">Procurei até embaixo da cuia e nada.</p>
      <Link href="/" className="rounded-2xl bg-destaque px-5 py-3 font-semibold text-sobre-destaque">
        Voltar para o mês
      </Link>
      <Suspense>
        <NaHoraDoPedido />
      </Suspense>
    </main>
  );
}
