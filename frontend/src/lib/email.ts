import "server-only";

import nodemailer, { type Transporter } from "nodemailer";

const REMETENTE = process.env.EMAIL_REMETENTE ?? "Capi <nao-responda@capi.localhost>";

type Mensagem = { assunto: string; titulo: string; paragrafos: string[]; botao?: { rotulo: string; url: string }; rodape: string };

let transporte: Transporter | null = null;

function obterTransporte(): Transporter {
  if (!process.env.SMTP_URL) {
    throw new Error("SMTP_URL não configurada: sem ela o Capi não consegue mandar e-mails de verificação e de senha.");
  }
  transporte ??= nodemailer.createTransport(process.env.SMTP_URL);
  return transporte;
}

function escapar(texto: string) {
  return texto.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

function primeiroNome(nome: string) {
  return nome.trim().split(/\s+/)[0] || "oi";
}

function html({ titulo, paragrafos, botao, rodape }: Mensagem) {
  const corpo = paragrafos.map((p) => `<p style="margin:0 0 14px;line-height:1.5">${escapar(p)}</p>`).join("");
  const acao = botao
    ? `<p style="margin:22px 0"><a href="${escapar(botao.url)}" style="background:#ff7a3d;color:#1a0f0a;padding:12px 18px;border-radius:12px;font-weight:700;text-decoration:none;display:inline-block">${escapar(botao.rotulo)}</a></p>
<p style="margin:0 0 14px;font-size:13px;color:#56706b;line-height:1.5">Se o botão não abrir, copie este endereço no navegador:<br><span style="word-break:break-all">${escapar(botao.url)}</span></p>`
    : "";
  return `<!doctype html><html lang="pt-BR"><body style="margin:0;background:#f3ebe1;font-family:Arial,Helvetica,sans-serif;color:#0a1c1b">
<div style="max-width:520px;margin:0 auto;padding:28px 20px">
<p style="margin:0 0 18px;font-weight:700;font-size:20px">Capi</p>
<h1 style="font-size:20px;margin:0 0 16px">${escapar(titulo)}</h1>
${corpo}${acao}
<p style="margin:24px 0 0;font-size:13px;color:#56706b;line-height:1.5">${escapar(rodape)}</p>
</div></body></html>`;
}

function texto({ titulo, paragrafos, botao, rodape }: Mensagem) {
  return [titulo, "", ...paragrafos, ...(botao ? ["", `${botao.rotulo}: ${botao.url}`] : []), "", rodape].join("\n");
}

async function enviar(para: string, mensagem: Mensagem) {
  await obterTransporte().sendMail({ from: REMETENTE, to: para, subject: mensagem.assunto, text: texto(mensagem), html: html(mensagem) });
}

export async function emailVerificacao(para: string, nome: string, url: string) {
  await enviar(para, {
    assunto: "Confirme seu e-mail no Capi",
    titulo: `Bah, ${primeiroNome(nome)}, falta só confirmar o e-mail`,
    paragrafos: [
      "Seus extratos e faturas só abrem depois que a gente tem certeza de que este e-mail é seu.",
      "O link vale por 24 horas e funciona uma vez só.",
    ],
    botao: { rotulo: "Confirmar meu e-mail", url },
    rodape: "Não criou conta no Capi? Pode ignorar este e-mail: sem a confirmação, ninguém entra com ele.",
  });
}

export async function emailRecuperacao(para: string, nome: string, url: string) {
  await enviar(para, {
    assunto: "Trocar a senha do Capi",
    titulo: `${primeiroNome(nome)}, pediram para trocar a sua senha`,
    paragrafos: [
      "Use o botão abaixo para escolher uma senha nova. O link vale por 30 minutos e funciona uma vez só.",
      "Quando a senha for trocada, todas as sessões abertas são encerradas, inclusive em outros aparelhos.",
    ],
    botao: { rotulo: "Escolher senha nova", url },
    rodape: "Não foi você? Ignore este e-mail: sua senha continua a mesma.",
  });
}

export async function emailContaExistente(para: string, nome: string, urlEntrar: string, urlRecuperar: string) {
  await enviar(para, {
    assunto: "Tentaram criar uma conta com o seu e-mail",
    titulo: `${primeiroNome(nome)}, você já tem conta no Capi`,
    paragrafos: [
      "Alguém tentou criar uma conta nova com este e-mail. Como ele já está cadastrado, nada foi criado.",
      `Se foi você, é só entrar em ${urlEntrar}. Esqueceu a senha? Troque em ${urlRecuperar}.`,
    ],
    rodape: "Não foi você? Não precisa fazer nada: a sua conta continua do jeito que estava.",
  });
}

export async function emailSenhaTrocada(para: string, nome: string) {
  await enviar(para, {
    assunto: "Sua senha do Capi foi trocada",
    titulo: `${primeiroNome(nome)}, a senha foi trocada`,
    paragrafos: ["A senha da sua conta acabou de ser trocada e todas as sessões abertas foram encerradas."],
    rodape: "Não foi você? Peça uma senha nova em recuperar senha agora mesmo e confira o acesso ao seu e-mail.",
  });
}
