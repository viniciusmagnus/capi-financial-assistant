import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { FormularioCarregando } from "@/components/entrada/Carregando";
import { FormEntrar } from "@/components/entrada/Formularios";
import { Moldura } from "@/components/entrada/Moldura";
import { SoComAutenticacao } from "@/components/entrada/SoComAutenticacao";

export const metadata: Metadata = { title: "Entrar · Capi" };

export default function Entrar() {
  return (
    <Moldura
      titulo="Entrar no Capi"
      subtitulo="Seus extratos e faturas ficam só com você."
      rodape={
        <>
          <p>
            Ainda não tem conta?{" "}
            <Link href="/cadastrar" className="font-semibold text-texto underline underline-offset-4">
              Criar conta
            </Link>
          </p>
          <p>
            Só quer ver como funciona?{" "}
            <Link href="/demonstracao" className="underline underline-offset-4 hover:text-texto">
              Abrir a demonstração
            </Link>
          </p>
        </>
      }
    >
      <Suspense fallback={<FormularioCarregando />}>
        <SoComAutenticacao>{(google) => <FormEntrar google={google} />}</SoComAutenticacao>
      </Suspense>
    </Moldura>
  );
}
