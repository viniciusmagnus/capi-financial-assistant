"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { nomeDoMes } from "@/lib/diagnostico";

export function AbasDeMes({ meses, atual }: { meses: string[]; atual: string }) {
  const trilho = useRef<HTMLElement>(null);
  const ativa = useRef<HTMLAnchorElement>(null);
  const [transborda, setTransborda] = useState(false);

  useEffect(() => {
    const nav = trilho.current;
    const aba = ativa.current;
    if (!nav) return;
    setTransborda(nav.scrollWidth > nav.clientWidth + 1);
    if (aba) nav.scrollLeft = aba.offsetLeft - (nav.clientWidth - aba.offsetWidth) / 2;
  }, [atual, meses.length]);

  return (
    <nav
      ref={trilho}
      aria-label="Mês"
      className={`relative flex gap-1 overflow-x-auto px-4 pt-5 [scrollbar-width:none] sm:px-0 ${
        transborda ? "[mask-image:linear-gradient(to_right,transparent,black_1.5rem,black_calc(100%-2.5rem),transparent)]" : ""
      }`}
    >
      {meses.map((mes) => (
        <Link
          key={mes}
          ref={mes === atual ? ativa : undefined}
          href={`/?mes=${mes}`}
          scroll={false}
          aria-current={mes === atual ? "page" : undefined}
          className="shrink-0 rounded-lg px-3 py-1.5 text-sm text-suave hover:bg-superficie hover:text-texto aria-[current=page]:bg-superficie aria-[current=page]:font-semibold aria-[current=page]:text-texto"
        >
          {nomeDoMes(mes)}
        </Link>
      ))}
    </nav>
  );
}
