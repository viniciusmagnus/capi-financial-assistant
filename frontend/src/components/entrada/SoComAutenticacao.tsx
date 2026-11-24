import { redirect } from "next/navigation";
import { connection } from "next/server";
import type { ReactNode } from "react";

import { autenticacaoConfigurada, googleConfigurado } from "@/lib/auth";

export async function SoComAutenticacao({ children }: { children: (google: boolean) => ReactNode }) {
  await connection();
  if (!autenticacaoConfigurada) redirect("/demonstracao");
  return children(googleConfigurado);
}
