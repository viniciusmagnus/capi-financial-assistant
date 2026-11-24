import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { FormularioCarregando } from "@/components/entrada/Carregando";
import { FormCadastro } from "@/components/entrada/Formularios";
import { Moldura } from "@/components/entrada/Moldura";
import { SoComAutenticacao } from "@/components/entrada/SoComAutenticacao";

export const metadata: Metadata = { title: "Criar conta · Capi" };

export default function Cadastrar() {
  return (
    <Moldura
      titulo="Criar conta"
      subtitulo="A Capi só abre os números depois que você confirma o e-mail."
      rodape={
        <p>
          Já tem conta?{" "}
          <Link href="/entrar" className="font-semibold text-texto underline underline-offset-4">
            Entrar
          </Link>
        </p>
      }
    >
      <Suspense fallback={<FormularioCarregando />}>
        <SoComAutenticacao>{(google) => <FormCadastro google={google} />}</SoComAutenticacao>
      </Suspense>
    </Moldura>
  );
}
