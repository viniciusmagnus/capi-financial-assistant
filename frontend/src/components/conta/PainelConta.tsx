"use client";

import { Check, Copy, KeyRound, LoaderCircle, LogOut, MonitorSmartphone, Plug, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, type ReactNode, Suspense, useState, useTransition } from "react";

import { apagarTokenDoMcp, encerrarSessao, novoTokenDoMcp } from "@/app/acoes";
import { Campo, CampoSenha } from "@/components/entrada/Campos";
import { Aviso, CLASSE_BOTAO_SECUNDARIO } from "@/components/entrada/Moldura";
import { authCliente } from "@/lib/auth-cliente";
import type { TokenMcp } from "@/lib/cofrinho";
import { mensagemDeErro, mensagemDoGoogle } from "@/lib/mensagens-de-entrada";
import type { Usuario } from "@/lib/sessao";

export type SessaoListada = { id: string; aparelho: string; desde: string; ultimoUso: string; atual: boolean };

const DATA = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

function Secao({ icone, titulo, children }: { icone: ReactNode; titulo: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-borda bg-superficie p-5" aria-label={titulo}>
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        {icone}
        {titulo}
      </h2>
      <div className="mt-3 text-sm">{children}</div>
    </section>
  );
}

function RetornoDoGoogle() {
  const parametros = useSearchParams();
  const erro = mensagemDoGoogle(parametros.get("error"));
  if (erro) return <Aviso tipo="erro">{erro}</Aviso>;
  if (parametros.get("vinculado") === "google") return <Aviso tipo="ok">Google vinculado. Agora dá para entrar pelos dois jeitos.</Aviso>;
  return null;
}

function FormasDeEntrar({ temSenha, temGoogle, googleDisponivel, email }: { temSenha: boolean; temGoogle: boolean; googleDisponivel: boolean; email: string }) {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [linkEnviado, setLinkEnviado] = useState(false);

  async function vincularGoogle() {
    setOcupado(true);
    setErro(null);
    const { error } = await authCliente.linkSocial({ provider: "google", callbackURL: "/conta?vinculado=google", errorCallbackURL: "/conta" });
    if (error) {
      setErro(mensagemDeErro(error, "Não deu para abrir o Google agora."));
      setOcupado(false);
    }
  }

  async function criarSenha() {
    setOcupado(true);
    const { error } = await authCliente.requestPasswordReset({ email, redirectTo: "/redefinir-senha" });
    setOcupado(false);
    if (error) setErro(mensagemDeErro(error));
    else setLinkEnviado(true);
  }

  return (
    <>
      <Suspense>
        <RetornoDoGoogle />
      </Suspense>
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      <ul className="divide-y divide-borda">
        <li className="flex items-center justify-between gap-3 py-2.5">
          <span>E-mail e senha</span>
          {temSenha ? (
            <span className="text-correnteza">Ativo</span>
          ) : linkEnviado ? (
            <span className="text-suave">Link enviado para {email}</span>
          ) : (
            <button type="button" onClick={criarSenha} disabled={ocupado} className="rounded-lg border border-borda px-3 py-1.5 hover:bg-elevada">
              Criar senha por e-mail
            </button>
          )}
        </li>
        <li className="flex items-center justify-between gap-3 py-2.5">
          <span>Google</span>
          {temGoogle ? (
            <span className="text-correnteza">Vinculado</span>
          ) : googleDisponivel ? (
            <button type="button" onClick={vincularGoogle} disabled={ocupado} className="rounded-lg border border-borda px-3 py-1.5 hover:bg-elevada">
              Vincular Google
            </button>
          ) : (
            <span className="text-suave">Não configurado neste servidor</span>
          )}
        </li>
      </ul>
      {!temGoogle && googleDisponivel && (
        <p className="mt-2 text-xs text-suave">
          Para vincular, você já está dentro da conta e ainda confirma no Google com o mesmo e-mail. A gente nunca junta contas só porque o e-mail é
          igual.
        </p>
      )}
    </>
  );
}

function TrocarSenha() {
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function trocar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = evento.currentTarget;
    const dados = new FormData(formulario);
    const nova = String(dados.get("nova") ?? "");
    if (nova !== String(dados.get("repetida") ?? "")) {
      setErro("As duas senhas novas não são iguais.");
      return;
    }
    setOcupado(true);
    setErro(null);
    const { error } = await authCliente.changePassword({ currentPassword: String(dados.get("atual") ?? ""), newPassword: nova, revokeOtherSessions: true });
    setOcupado(false);
    if (error) {
      setErro(mensagemDeErro(error));
      return;
    }
    formulario.reset();
    setOk(true);
  }

  return (
    <form onSubmit={trocar} className="space-y-3">
      {erro && <Aviso tipo="erro">{erro}</Aviso>}
      {ok && <Aviso tipo="ok">Senha trocada. Os outros aparelhos foram desconectados.</Aviso>}
      <CampoSenha rotulo="Senha atual" name="atual" required maxLength={256} />
      <CampoSenha rotulo="Senha nova" name="nova" novaSenha required minLength={12} maxLength={256} dica="Pelo menos 12 caracteres." />
      <CampoSenha rotulo="Repita a senha nova" name="repetida" novaSenha required minLength={12} maxLength={256} />
      <button type="submit" disabled={ocupado} aria-busy={ocupado} className={CLASSE_BOTAO_SECUNDARIO}>
        {ocupado ? "Trocando…" : "Trocar a senha"}
      </button>
    </form>
  );
}

function Aparelhos({ sessoes }: { sessoes: SessaoListada[] }) {
  const [pendente, iniciar] = useTransition();
  const [aviso, setAviso] = useState<string | null>(null);
  const outras = sessoes.filter((s) => !s.atual).length;

  function sairDosOutros() {
    iniciar(async () => {
      const { error } = await authCliente.revokeOtherSessions();
      setAviso(error ? mensagemDeErro(error) : "Pronto: só este aparelho continua conectado.");
      if (!error) location.reload();
    });
  }

  return (
    <>
      {aviso && <Aviso tipo="info">{aviso}</Aviso>}
      <ul className="divide-y divide-borda">
        {sessoes.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="truncate">
                {s.aparelho}
                {s.atual && <span className="ml-2 rounded-full bg-correnteza-fundo px-2 py-0.5 text-xs text-correnteza">este aparelho</span>}
              </p>
              <p className="text-xs text-suave">
                Desde {DATA.format(new Date(s.desde))} · último uso {DATA.format(new Date(s.ultimoUso))}
              </p>
            </div>
            {!s.atual && (
              <button
                type="button"
                disabled={pendente}
                onClick={() => iniciar(async () => void (await encerrarSessao(s.id)))}
                className="shrink-0 rounded-lg border border-borda px-3 py-1.5 hover:bg-elevada"
              >
                Encerrar
              </button>
            )}
          </li>
        ))}
      </ul>
      {outras > 0 && (
        <button type="button" onClick={sairDosOutros} disabled={pendente} className={`${CLASSE_BOTAO_SECUNDARIO} mt-3`}>
          Sair de todos os outros aparelhos
        </button>
      )}
    </>
  );
}

function TokensDoMcp({ tokens, urlDoMcp }: { tokens: TokenMcp[]; urlDoMcp: string }) {
  const [pendente, iniciar] = useTransition();
  const [criado, setCriado] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);

  function criar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    const formulario = evento.currentTarget;
    const nome = String(new FormData(formulario).get("nome") ?? "");
    iniciar(async () => {
      const resultado = await novoTokenDoMcp(nome);
      if (!resultado.ok) {
        setErro(resultado.erro);
        return;
      }
      setErro(null);
      setCopiado(false);
      setCriado(resultado.token);
      formulario.reset();
    });
  }

  const comando = criado ? `claude mcp add --transport http capi ${urlDoMcp} --header "Authorization: Bearer ${criado}"` : "";

  return (
    <>
      <p className="text-suave">
        Cada token dá ao Claude Desktop ou ao Claude Code acesso só aos seus dados, pelas mesmas ferramentas do chat. Guarde-o como uma senha.
      </p>
      {erro && (
        <div className="mt-3">
          <Aviso tipo="erro">{erro}</Aviso>
        </div>
      )}
      {criado && (
        <div className="mt-3 rounded-xl border border-sol/40 bg-fundo p-3">
          <p className="font-semibold">Copie agora: este token não aparece de novo.</p>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all text-xs text-suave">{comando}</pre>
          <button
            type="button"
            onClick={async () => {
              await navigator.clipboard.writeText(comando);
              setCopiado(true);
            }}
            className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-borda px-3 py-1.5 hover:bg-elevada"
          >
            {copiado ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
            {copiado ? "Copiado" : "Copiar comando"}
          </button>
        </div>
      )}
      {tokens.length > 0 && (
        <ul className="mt-3 divide-y divide-borda">
          {tokens.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate">{t.nome}</p>
                <p className="text-xs text-suave">
                  {t.prefixo}… · {t.ultimo_uso_em ? `usado em ${DATA.format(new Date(t.ultimo_uso_em))}` : "nunca usado"}
                </p>
              </div>
              <button
                type="button"
                disabled={pendente}
                onClick={() => iniciar(() => apagarTokenDoMcp(t.id))}
                className="shrink-0 rounded-lg border border-borda px-3 py-1.5 hover:bg-elevada"
              >
                Revogar
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={criar} className="mt-3 flex items-end gap-2">
        <div className="min-w-0 flex-1">
          <Campo rotulo="Nome do token" name="nome" placeholder="ex.: Claude no notebook" maxLength={60} required />
        </div>
        <button type="submit" disabled={pendente} className="rounded-xl bg-destaque px-4 py-3 font-semibold text-sobre-destaque disabled:opacity-60">
          Criar
        </button>
      </form>
    </>
  );
}

export function PainelConta({
  usuario,
  temSenha,
  temGoogle,
  googleDisponivel,
  sessoes,
  tokens,
  urlDoMcp,
}: {
  usuario: Usuario;
  temSenha: boolean;
  temGoogle: boolean;
  googleDisponivel: boolean;
  sessoes: SessaoListada[];
  tokens: TokenMcp[];
  urlDoMcp: string;
}) {
  const router = useRouter();
  const [saindo, setSaindo] = useState(false);

  async function sair() {
    setSaindo(true);
    await authCliente.signOut();
    router.replace("/entrar?saiu=1");
    router.refresh();
  }

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 space-y-4 px-4 pb-14 pt-6">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="largo text-2xl font-bold">Conta</h1>
          <p className="truncate text-sm text-suave">
            {usuario.nome} · {usuario.email}
          </p>
        </div>
        <button type="button" onClick={sair} disabled={saindo} className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-borda px-3 py-2 text-sm hover:bg-elevada">
          {saindo ? <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" aria-hidden /> : <LogOut className="size-4" aria-hidden />}
          Sair
        </button>
      </header>
      <Secao icone={<ShieldCheck className="size-5 text-correnteza" aria-hidden />} titulo="Formas de entrar">
        <FormasDeEntrar temSenha={temSenha} temGoogle={temGoogle} googleDisponivel={googleDisponivel} email={usuario.email} />
      </Secao>
      {temSenha && (
        <Secao icone={<KeyRound className="size-5 text-sol" aria-hidden />} titulo="Senha">
          <TrocarSenha />
        </Secao>
      )}
      <Secao icone={<MonitorSmartphone className="size-5 text-suave" aria-hidden />} titulo="Aparelhos conectados">
        <Aparelhos sessoes={sessoes} />
      </Secao>
      <Secao icone={<Plug className="size-5 text-poente" aria-hidden />} titulo="Claude (MCP)">
        <TokensDoMcp tokens={tokens} urlDoMcp={urlDoMcp} />
      </Secao>
      <p className="px-1 text-xs text-suave">
        Sessões duram 7 dias sem uso e se renovam enquanto você usa o Capi. Trocar a senha encerra todas.
      </p>
    </main>
  );
}
