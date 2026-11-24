import { SessaoExpirada, abrirChat, apiConfigurada } from "@/lib/api";
import { mesmaOrigem } from "@/lib/sessao";

const NDJSON = { "Content-Type": "application/x-ndjson; charset=utf-8", "Cache-Control": "no-store" };

function linhas(...eventos: object[]) {
  return eventos.map((e) => JSON.stringify(e)).join("\n") + "\n";
}

export async function POST(request: Request) {
  if (!apiConfigurada) {
    return new Response(linhas({ tipo: "erro", mensagem: "O chat só funciona com uma conta e a API ligada." }, { tipo: "fim" }), {
      status: 503,
      headers: NDJSON,
    });
  }
  if (!mesmaOrigem(request)) {
    return new Response(linhas({ tipo: "erro", mensagem: "Pedido recusado: veio de fora do Capi." }, { tipo: "fim" }), { status: 403, headers: NDJSON });
  }

  const corpo = await request.text();
  if (corpo.length > 200_000) return new Response("conversa grande demais", { status: 413 });

  let resposta: Response;
  try {
    resposta = await abrirChat(corpo);
  } catch (erro) {
    if (erro instanceof SessaoExpirada) {
      return new Response(linhas({ tipo: "erro", mensagem: "Sua sessão expirou. Entre de novo para continuar a conversa.", sessaoExpirada: true }, { tipo: "fim" }), {
        status: 401,
        headers: NDJSON,
      });
    }
    return new Response(linhas({ tipo: "erro", mensagem: "Não consegui falar com a API. Ela está no ar?" }, { tipo: "fim" }), { status: 502, headers: NDJSON });
  }
  if (!resposta.ok || !resposta.body) {
    const detalhe = await resposta.text().catch(() => "");
    return new Response(linhas({ tipo: "erro", mensagem: `A API respondeu ${resposta.status}. ${detalhe}`.trim() }, { tipo: "fim" }), {
      headers: NDJSON,
    });
  }
  return new Response(resposta.body, { headers: NDJSON });
}
