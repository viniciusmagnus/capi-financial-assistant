"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

export function Dialogo({ titulo, aoFechar, children, largo = false }: { titulo: string; aoFechar: () => void; children: ReactNode; largo?: boolean }) {
  const caixa = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const anterior = document.activeElement as HTMLElement | null;
    caixa.current?.focus();
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") aoFechar();
    };
    document.addEventListener("keydown", aoTeclar);
    const rolagem = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = rolagem;
      anterior?.focus?.();
    };
  }, [aoFechar]);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}>
      <div
        ref={caixa}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        tabIndex={-1}
        className={`flex max-h-[92dvh] w-full flex-col rounded-t-2xl border border-borda bg-fundo outline-none sm:rounded-2xl ${largo ? "sm:max-w-3xl" : "sm:max-w-xl"}`}
      >
        <div className="flex items-center justify-between gap-3 border-b border-borda px-4 py-3">
          <h2 className="font-semibold">{titulo}</h2>
          <button type="button" onClick={aoFechar} aria-label="Fechar" className="rounded-lg p-1.5 text-suave hover:bg-elevada hover:text-texto">
            <X className="size-4" aria-hidden />
          </button>
        </div>
        <div className="overflow-y-auto px-4 py-4">{children}</div>
      </div>
    </div>
  );
}
