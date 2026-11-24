"use client";

import { CircleUserRound, ListChecks, MessageCircle, ScanSearch, Search, Sunset } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

const DESTINOS = [
  { href: "/", rotulo: "Mês", icone: Sunset },
  { href: "/chat", rotulo: "Chat", icone: MessageCircle },
  { href: "/busca", rotulo: "Busca", icone: Search },
  { href: "/revisao", rotulo: "Revisar", icone: ScanSearch },
  { href: "/regras", rotulo: "Regras", icone: ListChecks },
  { href: "/conta", rotulo: "Conta", icone: CircleUserRound },
];

const PUBLICAS = ["/entrar", "/cadastrar", "/verificar-email", "/recuperar-senha", "/redefinir-senha", "/demonstracao"];

function ativo(caminho: string, href: string) {
  return href === "/" ? caminho === "/" : caminho.startsWith(href);
}

export function Topo() {
  const caminho = usePathname();
  const publica = PUBLICAS.some((p) => caminho.startsWith(p));
  if (publica) {
    return (
      <header data-publica className="border-b border-borda bg-fundo">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-4">
          <Link href="/entrar" className="flex items-center gap-2" aria-label="Capi, assistente financeiro: entrar">
            <Image src="/capi.svg" alt="" width={32} height={32} unoptimized priority className="size-8" />
            <span className="largo text-xl font-bold">Capi</span>
            <span className="hidden text-sm text-suave sm:inline">assistente financeiro</span>
          </Link>
          {caminho.startsWith("/demonstracao") && (
            <nav aria-label="Acesso" className="flex gap-1 text-sm">
              <Link href="/entrar" className="rounded-lg px-3 py-2 text-suave hover:bg-superficie hover:text-texto">
                Entrar
              </Link>
              <Link href="/cadastrar" className="rounded-lg bg-destaque px-3 py-2 font-semibold text-sobre-destaque">
                Criar conta
              </Link>
            </nav>
          )}
        </div>
      </header>
    );
  }
  return (
    <>
      <header className="border-b border-borda bg-fundo">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2" aria-label="Capi, assistente financeiro: início">
            <Image src="/capi.svg" alt="" width={32} height={32} unoptimized priority className="size-8" />
            <span className="largo text-xl font-bold">Capi</span>
            <span className="text-sm text-suave">assistente financeiro</span>
          </Link>
          <nav aria-label="Principal" className="hidden gap-1 text-sm sm:flex">
            {DESTINOS.map(({ href, rotulo }) => (
              <Link
                key={href}
                href={href}
                aria-current={ativo(caminho, href) ? "page" : undefined}
                className="rounded-lg px-3 py-2 text-suave hover:bg-superficie hover:text-texto aria-[current=page]:text-texto aria-[current=page]:underline aria-[current=page]:decoration-poente aria-[current=page]:decoration-2 aria-[current=page]:underline-offset-8"
              >
                {rotulo}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <nav
        aria-label="Principal"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-borda bg-fundo/95 pb-[env(safe-area-inset-bottom)] backdrop-blur sm:hidden"
      >
        <ul className="grid grid-cols-6">
          {DESTINOS.map(({ href, rotulo, icone: Icone }) => (
            <li key={href}>
              <Link
                href={href}
                aria-current={ativo(caminho, href) ? "page" : undefined}
                className="flex flex-col items-center gap-0.5 py-2 text-[11px] text-suave aria-[current=page]:text-poente"
              >
                <Icone className="size-5" aria-hidden />
                {rotulo}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}
