import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { FormularioCarregando } from "@/components/entrada/Carregando";
import { FormRecuperar } from "@/components/entrada/Formularios";
import { Moldura } from "@/components/entrada/Moldura";
import { SoComAutenticacao } from "@/components/entrada/SoComAutenticacao";

export const metadata: Metadata = { title: "Recuperar senha · Capi" };

export default function RecuperarSenha() {
  return (
    <Moldura
      titulo="Esqueceu a senha?"
      subtitulo="Acontece nas melhores famílias. Mandamos um link para você escolher outra."
      rodape={
        <p>
          <Link href="/entrar" className="underline underline-offset-4 hover:text-texto">
            Voltar para entrar
          </Link>
        </p>
      }
    >
      <Suspense fallback={<FormularioCarregando />}>
        <SoComAutenticacao>{() => <FormRecuperar />}</SoComAutenticacao>
      </Suspense>
    </Moldura>
  );
}
