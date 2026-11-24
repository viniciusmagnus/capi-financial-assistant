import { ErroDaApi, SessaoExpirada, apiConfigurada, enviarExtrato } from "@/lib/api";
import { mesmaOrigem } from "@/lib/sessao";

const LIMITE = 5 * 1024 * 1024;

export async function POST(request: Request) {
  if (!apiConfigurada) {
    return Response.json({ erro: "A demonstração não importa arquivos. Crie uma conta para usar os seus." }, { status: 503 });
  }
  if (!mesmaOrigem(request)) {
    return Response.json({ erro: "Pedido recusado: veio de fora do Capi." }, { status: 403 });
  }
  let recebido: FormData;
  try {
    recebido = await request.formData();
  } catch {
    return Response.json({ erro: "Não recebi o arquivo. Tente de novo." }, { status: 400 });
  }
  const arquivo = recebido.get("arquivo");
  if (!(arquivo instanceof File) || arquivo.size === 0) {
    return Response.json({ erro: "O arquivo chegou vazio." }, { status: 400 });
  }
  if (arquivo.size > LIMITE) {
    return Response.json({ erro: "Passa de 5 MB. Exporte um período menor no banco." }, { status: 413 });
  }

  const envio = new FormData();
  envio.append("arquivo", arquivo, arquivo.name.slice(0, 200));
  try {
    return Response.json(await enviarExtrato(envio));
  } catch (erro) {
    if (erro instanceof SessaoExpirada) {
      return Response.json({ erro: "Sua sessão expirou. Entre de novo para continuar.", sessaoExpirada: true }, { status: 401 });
    }
    if (erro instanceof ErroDaApi) {
      const mensagem = erro.status === 422 ? `${erro.detalhe.charAt(0).toUpperCase()}${erro.detalhe.slice(1)}.` : erro.detalhe;
      return Response.json({ erro: mensagem }, { status: erro.status });
    }
    return Response.json({ erro: "Não consegui falar com a API. Ela está no ar?" }, { status: 502 });
  }
}
