"use client";

import { useId } from "react";

import { formatarReais } from "@/lib/formato";

export function CampoReais({
  centavos,
  onChange,
  rotulo,
  dica,
  grande = true,
}: {
  centavos: number;
  onChange: (centavos: number) => void;
  rotulo: string;
  dica?: string;
  grande?: boolean;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="text-sm text-suave">
        {rotulo}
      </label>
      <input
        id={id}
        inputMode="numeric"
        autoComplete="off"
        aria-describedby={dica ? `${id}-dica` : undefined}
        className={`mt-1 w-full rounded-xl border border-borda bg-fundo px-4 font-semibold tabular-nums outline-none focus:border-destaque ${grande ? "py-3 text-3xl" : "py-2.5 text-lg"}`}
        value={formatarReais(centavos)}
        onChange={(e) => onChange(Math.min(Number(e.target.value.replace(/\D/g, "") || "0"), 99_999_999_999))}
      />
      {dica && (
        <p id={`${id}-dica`} className="mt-1 text-xs text-suave">
          {dica}
        </p>
      )}
    </div>
  );
}
