import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { FormularioCarregando } from "@/components/entrada/Carregando";
import { Verificacao } from "@/components/entrada/Formularios";
import { Moldura } from "@/components/entrada/Moldura";
import { SoComAutenticacao } from "@/components/entrada/SoComAutenticacao";

export const metadata: Metadata = { title: "Confirmar e-mail · Capi", referrer: "no-referrer" };

export default function VerificarEmail() {
  return (
    <Moldura
      titulo="Confirme o seu e-mail"
      subtitulo="É assim que a gente sabe que os extratos vão para a pessoa certa."
      rodape={
        <p>
          <Link href="/entrar" className="underline underline-offset-4 hover:text-texto">
            Voltar para entrar
          </Link>
        </p>
      }
    >
      <Suspense fallback={<FormularioCarregando />}>
        <SoComAutenticacao>{() => <Verificacao />}</SoComAutenticacao>
      </Suspense>
    </Moldura>
  );
}
