import type { Metadata } from "next";
import { Suspense } from "react";

import { FormularioCarregando } from "@/components/entrada/Carregando";
import { FormRedefinir } from "@/components/entrada/Formularios";
import { Moldura } from "@/components/entrada/Moldura";
import { SoComAutenticacao } from "@/components/entrada/SoComAutenticacao";

export const metadata: Metadata = { title: "Senha nova · Capi", referrer: "no-referrer" };

export default function RedefinirSenha() {
  return (
    <Moldura titulo="Escolha uma senha nova" subtitulo="Depois de trocar, todas as sessões abertas são encerradas.">
      <Suspense fallback={<FormularioCarregando />}>
        <SoComAutenticacao>{() => <FormRedefinir />}</SoComAutenticacao>
      </Suspense>
    </Moldura>
  );
}
