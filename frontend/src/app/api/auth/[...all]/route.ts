import { toNextJsHandler } from "better-auth/next-js";

import { auth, autenticacaoConfigurada } from "@/lib/auth";

const handler = toNextJsHandler(auth);

function semAutenticacao() {
  return Response.json({ message: "Autenticação não configurada neste ambiente." }, { status: 503 });
}

export async function GET(request: Request) {
  return autenticacaoConfigurada ? handler.GET(request) : semAutenticacao();
}

export async function POST(request: Request) {
  return autenticacaoConfigurada ? handler.POST(request) : semAutenticacao();
}
