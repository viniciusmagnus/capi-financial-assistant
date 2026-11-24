import Image from "next/image";
import type { ReactNode } from "react";

export function Moldura({ titulo, subtitulo, children, rodape }: { titulo: string; subtitulo?: ReactNode; children: ReactNode; rodape?: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-md flex-1 px-4 pb-14 pt-6 sm:pt-12">
      <section aria-labelledby="titulo-entrada" className="overflow-hidden rounded-2xl border border-borda bg-superficie">
        <div
          className="relative h-20"
          style={{ background: "linear-gradient(to bottom, var(--ceu-alto) 0%, var(--ceu-meio) 45%, var(--ceu-baixo) 82%, var(--horizonte) 100%)" }}
          aria-hidden
        >
          <Image src="/capi.svg" alt="" width={48} height={48} unoptimized className="absolute -bottom-6 left-5 size-12 rounded-xl ring-4 ring-superficie" />
        </div>
        <div className="px-5 pb-6 pt-9">
          <h1 id="titulo-entrada" className="largo text-2xl font-bold">
            {titulo}
          </h1>
          {subtitulo && <div className="mt-1.5 text-sm text-suave">{subtitulo}</div>}
          <div className="mt-5">{children}</div>
        </div>
      </section>
      {rodape && <div className="mt-5 space-y-2 text-center text-sm text-suave">{rodape}</div>}
    </main>
  );
}

export function Aviso({ tipo, children }: { tipo: "erro" | "ok" | "info"; children: ReactNode }) {
  const cor = tipo === "erro" ? "border-brasa/50 text-texto" : tipo === "ok" ? "border-correnteza/50 text-texto" : "border-sol/40 text-texto";
  return (
    <div role={tipo === "erro" ? "alert" : "status"} className={`mb-4 rounded-xl border bg-fundo px-3.5 py-3 text-sm ${cor}`}>
      {children}
    </div>
  );
}

export const CLASSE_CAMPO =
  "w-full rounded-xl border border-borda bg-fundo px-3.5 py-3 text-base text-texto placeholder:text-suave/60 outline-none focus:border-destaque aria-[invalid=true]:border-brasa";

export const CLASSE_BOTAO =
  "flex w-full items-center justify-center gap-2 rounded-xl bg-destaque px-4 py-3 font-semibold text-sobre-destaque disabled:cursor-wait disabled:opacity-60";

export const CLASSE_BOTAO_SECUNDARIO =
  "flex w-full items-center justify-center gap-2 rounded-xl border border-borda px-4 py-3 font-semibold text-texto hover:bg-elevada disabled:cursor-wait disabled:opacity-60";
