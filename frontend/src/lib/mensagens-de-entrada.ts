type ErroDeAutenticacao = { status?: number; code?: string; message?: string } | null | undefined;

const POR_CODIGO: Record<string, string> = {
  INVALID_EMAIL_OR_PASSWORD: "E-mail ou senha não conferem.",
  INVALID_EMAIL: "Esse e-mail não parece válido.",
  INVALID_PASSWORD: "A senha atual não confere.",
  PASSWORD_TOO_SHORT: "A senha precisa de pelo menos 12 caracteres.",
  PASSWORD_TOO_LONG: "A senha passou de 256 caracteres.",
  PASSWORD_COMPROMISED: "Essa senha já apareceu em vazamentos públicos. Escolha outra.",
  EMAIL_NOT_VERIFIED: "Falta confirmar o seu e-mail. Mandamos um link novo para a sua caixa de entrada.",
  INVALID_TOKEN: "Esse link não vale mais. Peça um novo.",
  TOKEN_EXPIRED: "Esse link venceu. Peça um novo.",
  CREDENTIAL_ACCOUNT_NOT_FOUND: "Esta conta entra com o Google. Para ter senha, use “Esqueci a senha”.",
  SESSION_NOT_FRESH: "Por segurança, saia e entre de novo antes de fazer isso.",
  INVALID_ORIGIN: "Pedido recusado: ele não veio do Capi.",
  CROSS_SITE_NAVIGATION_LOGIN_BLOCKED: "Pedido recusado: ele não veio do Capi.",
};

const DO_GOOGLE: Record<string, string> = {
  account_not_linked:
    "Já existe uma conta no Capi com esse e-mail. Entre com e-mail e senha e, em Conta, vincule o Google. Assim a gente sabe que as duas são suas.",
  "email_doesn't_match": "O Google escolhido tem outro e-mail. Vincule um Google com o mesmo e-mail da sua conta.",
  unable_to_link_account: "Não deu para vincular essa conta do Google.",
  account_already_linked_to_different_user: "Essa conta do Google já está ligada a outra pessoa no Capi.",
  access_denied: "O login com o Google foi cancelado.",
  state_mismatch: "O login com o Google expirou no meio do caminho. Tente de novo.",
  please_restart_the_process: "O login com o Google expirou no meio do caminho. Tente de novo.",
};

export function mensagemDeErro(erro: ErroDeAutenticacao, padrao = "Algo deu errado. Tente de novo em instantes."): string {
  if (!erro) return padrao;
  if (erro.status === 429) return "Muitas tentativas seguidas. Espere alguns minutos e tente de novo.";
  if (erro.code && POR_CODIGO[erro.code]) return POR_CODIGO[erro.code];
  return padrao;
}

export function mensagemDoGoogle(codigo: string | null): string | null {
  if (!codigo) return null;
  return DO_GOOGLE[codigo] ?? "O login com o Google não deu certo. Tente de novo.";
}

export function mensagemDoLink(codigo: string | null): string | null {
  if (!codigo) return null;
  if (codigo === "LINK_USADO") return "Esse link de confirmação já foi usado. Se o e-mail já está confirmado, é só entrar.";
  if (codigo === "TOKEN_EXPIRED") return "Esse link de confirmação venceu. Peça um novo abaixo.";
  return "Esse link de confirmação não vale. Peça um novo abaixo.";
}
