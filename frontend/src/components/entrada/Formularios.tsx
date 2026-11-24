"use client";

import { LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";

import { authCliente } from "@/lib/auth-cliente";
import { destinoSeguro } from "@/lib/destino";
import { mensagemDeErro, mensagemDoGoogle, mensagemDoLink } from "@/lib/mensagens-de-entrada";
import { Campo, CampoSenha } from "./Campos";
import { Aviso, CLASSE_BOTAO, CLASSE_BOTAO_SECUNDARIO } from "./Moldura";

const MINIMO = 12;
const MAXIMO = 256;

function Enviar({ ocupado, rotulo, rotuloOcupado }: { ocupado: boolean; rotulo: string; rotuloOcupado: string }) {
  return (
    <button type="submit" disabled={ocupado} aria-busy={ocupado} className={CLASSE_BOTAO}>
      {ocupado && <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" aria-hidden />}
      {ocupado ? rotuloOcupado : rotulo}
    </button>
  );
}

function texto(form: FormData, campo: string) {
  return String(form.get(campo) ?? "");
}

function useEnvio() {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  async function executar(evento: FormEvent<HTMLFormElement>, acao: (form: FormData) => Promise<void>) {
    evento.preventDefault();
    if (ocupado) return;
    setOcupado(true);
    setErro(null);
    try {
      await acao(new FormData(evento.currentTarget));
    } catch {
      setErro("Não consegui falar com o servidor. Confira a conexão e tente de novo.");
    } finally {
      setOcupado(false);
    }
  }
  return { ocupado, erro, setErro, executar };
}

function Separador() {
  return (
    <div className="my-5 flex items-center gap-3 text-xs text-suave" aria-hidden>
      <span className="h-px flex-1 bg-borda" />
      ou
      <span className="h-px flex-1 bg-borda" />
    </div>
  );
}

export function BotaoGoogle({ volta, rotulo = "Entrar com o Google" }: { volta: string; rotulo?: string }) {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  async function entrar() {
    setOcupado(true);
    setErro(null);
    const { error } = await authCliente.signIn.social({
      provider: "google",
      callbackURL: volta,
      errorCallbackURL: "/entrar",
      newUserCallbackURL: "/",
    });
    if (error) {
      setErro(mensagemDeErro(error, "Não deu para abrir o Google agora."));
      setOcupado(false);
    }
  }
  return (
    <>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <button type="button" onClick={entrar} disabled={ocupado} aria-busy={ocupado} className={CLASSE_BOTAO_SECUNDARIO}>
        {ocupado ? <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" aria-hidden /> : <LogoGoogle />}
        {ocupado ? "Abrindo o Google…" : rotulo}
      </button>
    </>
  );
}

function LogoGoogle() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
      <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.5a5.6 5.6 0 0 1-2.4 3.6v3h3.9c2.3-2.1 3.5-5.2 3.5-8.7z" />
      <path fill="#34A853" d="M12 24c3.2 0 6-1.1 7.9-2.9l-3.9-3c-1.1.7-2.4 1.2-4 1.2-3.1 0-5.7-2.1-6.6-4.9h-4v3.1A12 12 0 0 0 12 24z" />
      <path fill="#FBBC05" d="M5.4 14.4a7.2 7.2 0 0 1 0-4.7V6.6h-4a12 12 0 0 0 0 10.8l4-3z" />
      <path fill="#EA4335" d="M12 4.8c1.7 0 3.3.6 4.5 1.8l3.4-3.4A12 12 0 0 0 1.4 6.6l4 3.1C6.3 6.9 8.9 4.8 12 4.8z" />
    </svg>
  );
}

export function FormEntrar({ google }: { google: boolean }) {
  const parametros = useSearchParams();
  const router = useRouter();
  const volta = destinoSeguro(parametros.get("volta"));
  const { ocupado, erro, setErro, executar } = useEnvio();
  const [info, setInfo] = useState<string | null>(null);
  const erroDoGoogle = mensagemDoGoogle(parametros.get("error"));

  async function entrar(form: FormData) {
    setInfo(null);
    const { error } = await authCliente.signIn.email({ email: texto(form, "email").trim(), password: texto(form, "senha"), rememberMe: true });
    if (error) {
      if (error.code === "EMAIL_NOT_VERIFIED") setInfo(mensagemDeErro(error));
      else setErro(mensagemDeErro(error));
      return;
    }
    router.replace(volta);
    router.refresh();
  }

  return (
    <>
      {parametros.get("expirou") === "1" && <Aviso tipo="info">Sua sessão expirou. Entre de novo para continuar de onde parou.</Aviso>}
      {parametros.get("saiu") === "1" && <Aviso tipo="ok">Você saiu. Até a próxima!</Aviso>}
      {parametros.get("senha") === "trocada" && <Aviso tipo="ok">Senha trocada. Por segurança, todas as sessões foram encerradas: entre com a senha nova.</Aviso>}
      {erroDoGoogle && <Aviso tipo="erro">{erroDoGoogle}</Aviso>}
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {info && <Aviso tipo="info">{info}</Aviso>}
      <form onSubmit={(e) => executar(e, entrar)} className="space-y-4">
        <Campo rotulo="E-mail" name="email" type="email" autoComplete="email" inputMode="email" autoCapitalize="none" required maxLength={254} />
        <CampoSenha rotulo="Senha" name="senha" required maxLength={MAXIMO} />
        <div className="text-right text-sm">
          <Link href="/recuperar-senha" className="text-suave underline underline-offset-4 hover:text-texto">
            Esqueci a senha
          </Link>
        </div>
        <Enviar ocupado={ocupado} rotulo="Entrar" rotuloOcupado="Entrando…" />
      </form>
      {google && (
        <>
          <Separador />
          <BotaoGoogle volta={volta} />
        </>
      )}
    </>
  );
}

export function FormCadastro({ google }: { google: boolean }) {
  const { ocupado, erro, setErro, executar } = useEnvio();
  const [enviado, setEnviado] = useState(false);
  const [senha, setSenha] = useState("");

  async function cadastrar(form: FormData) {
    const { error } = await authCliente.signUp.email({
      name: texto(form, "nome").trim(),
      email: texto(form, "email").trim(),
      password: texto(form, "senha"),
      callbackURL: "/verificar-email?confirmado=1",
    });
    if (error) {
      setErro(mensagemDeErro(error, "Não deu para criar a conta agora. Tente de novo em instantes."));
      return;
    }
    setEnviado(true);
  }

  if (enviado) {
    return (
      <Aviso tipo="ok">
        <p className="font-semibold">Confira o seu e-mail.</p>
        <p className="mt-1">
          Se o endereço puder ser usado, chega um link de confirmação em instantes. Ele vale por 24 horas e funciona uma vez só. Sem confirmar, os
          dados financeiros não abrem.
        </p>
        <p className="mt-2">
          Não chegou? Veja o spam ou <Link href="/verificar-email" className="underline underline-offset-4">peça outro link</Link>.
        </p>
      </Aviso>
    );
  }

  const faltam = Math.max(MINIMO - senha.length, 0);
  return (
    <>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={(e) => executar(e, cadastrar)} className="space-y-4">
        <Campo rotulo="Como a Capi te chama?" name="nome" autoComplete="name" required minLength={1} maxLength={80} />
        <Campo rotulo="E-mail" name="email" type="email" autoComplete="email" inputMode="email" autoCapitalize="none" required maxLength={254} />
        <CampoSenha
          rotulo="Senha"
          name="senha"
          novaSenha
          required
          minLength={MINIMO}
          maxLength={MAXIMO}
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          dica={faltam > 0 ? `Pelo menos ${MINIMO} caracteres (faltam ${faltam}). Uma frase longa vale mais que símbolos.` : "Tamanho bom. Pode colar do gerenciador de senhas."}
        />
        <Enviar ocupado={ocupado} rotulo="Criar conta" rotuloOcupado="Criando…" />
      </form>
      {google && (
        <>
          <Separador />
          <BotaoGoogle volta="/" rotulo="Criar conta com o Google" />
        </>
      )}
    </>
  );
}

export function FormRecuperar() {
  const { ocupado, erro, setErro, executar } = useEnvio();
  const [enviado, setEnviado] = useState(false);

  async function pedir(form: FormData) {
    const { error } = await authCliente.requestPasswordReset({ email: texto(form, "email").trim(), redirectTo: "/redefinir-senha" });
    if (error && error.status === 429) {
      setErro(mensagemDeErro(error));
      return;
    }
    setEnviado(true);
  }

  if (enviado) {
    return (
      <Aviso tipo="ok">
        Se houver uma conta com esse e-mail, mandamos um link para trocar a senha. Ele vale por 30 minutos e funciona uma vez só.
      </Aviso>
    );
  }
  return (
    <>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={(e) => executar(e, pedir)} className="space-y-4">
        <Campo rotulo="E-mail da conta" name="email" type="email" autoComplete="email" inputMode="email" autoCapitalize="none" required maxLength={254} />
        <Enviar ocupado={ocupado} rotulo="Mandar link" rotuloOcupado="Mandando…" />
      </form>
    </>
  );
}

export function FormRedefinir() {
  const parametros = useSearchParams();
  const router = useRouter();
  const token = parametros.get("token");
  const { ocupado, erro, setErro, executar } = useEnvio();

  if (!token || parametros.get("error")) {
    return (
      <Aviso tipo="erro">
        Esse link não vale mais: ele vence em 30 minutos e funciona uma vez só.{" "}
        <Link href="/recuperar-senha" className="underline underline-offset-4">
          Peça um novo
        </Link>
        .
      </Aviso>
    );
  }

  async function trocar(form: FormData) {
    const senha = texto(form, "senha");
    if (senha !== texto(form, "confirmacao")) {
      setErro("As duas senhas não são iguais.");
      return;
    }
    const { error } = await authCliente.resetPassword({ newPassword: senha, token: token as string });
    if (error) {
      setErro(mensagemDeErro(error));
      return;
    }
    router.replace("/entrar?senha=trocada");
  }

  return (
    <>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <form onSubmit={(e) => executar(e, trocar)} className="space-y-4">
        <CampoSenha rotulo="Senha nova" name="senha" novaSenha required minLength={MINIMO} maxLength={MAXIMO} dica={`Pelo menos ${MINIMO} caracteres.`} />
        <CampoSenha rotulo="Repita a senha nova" name="confirmacao" novaSenha required minLength={MINIMO} maxLength={MAXIMO} />
        <Enviar ocupado={ocupado} rotulo="Trocar a senha" rotuloOcupado="Trocando…" />
      </form>
    </>
  );
}

export function Verificacao() {
  const parametros = useSearchParams();
  const erroDoLink = mensagemDoLink(parametros.get("error"));
  const confirmado = parametros.get("confirmado") === "1" && !erroDoLink;
  const { ocupado, erro, setErro, executar } = useEnvio();
  const [enviado, setEnviado] = useState(false);

  async function reenviar(form: FormData) {
    const { error } = await authCliente.sendVerificationEmail({ email: texto(form, "email").trim(), callbackURL: "/verificar-email?confirmado=1" });
    if (error && error.status === 429) {
      setErro(mensagemDeErro(error));
      return;
    }
    setEnviado(true);
  }

  if (confirmado) {
    return (
      <>
        <Aviso tipo="ok">E-mail confirmado. Agora é só entrar com a sua senha.</Aviso>
        <Link href="/entrar" className={CLASSE_BOTAO}>
          Entrar
        </Link>
      </>
    );
  }

  let topo: ReactNode = <p className="mb-4 text-sm text-suave">Mandamos um link para o seu e-mail. Não chegou? Veja o spam ou peça outro aqui.</p>;
  if (erroDoLink) topo = <Aviso tipo="erro">{erroDoLink}</Aviso>;
  return (
    <>
      {topo}
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {enviado ? (
        <Aviso tipo="ok">Se esse e-mail tiver uma conta ainda sem confirmação, um link novo chega em instantes.</Aviso>
      ) : (
        <form onSubmit={(e) => executar(e, reenviar)} className="space-y-4">
          <Campo rotulo="E-mail da conta" name="email" type="email" autoComplete="email" inputMode="email" autoCapitalize="none" required maxLength={254} />
          <Enviar ocupado={ocupado} rotulo="Mandar outro link" rotuloOcupado="Mandando…" />
        </form>
      )}
    </>
  );
}
