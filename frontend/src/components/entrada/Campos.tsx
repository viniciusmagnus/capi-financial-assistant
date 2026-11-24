"use client";

import { Eye, EyeOff } from "lucide-react";
import { useId, useState } from "react";

import { CLASSE_CAMPO } from "./Moldura";

export function Campo({
  rotulo,
  dica,
  ...props
}: { rotulo: string; dica?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {rotulo}
      </label>
      <input id={id} aria-describedby={dica ? `${id}-dica` : undefined} className={CLASSE_CAMPO} {...props} />
      {dica && (
        <p id={`${id}-dica`} className="mt-1.5 text-xs text-suave">
          {dica}
        </p>
      )}
    </div>
  );
}

export function CampoSenha({
  rotulo,
  dica,
  novaSenha,
  ...props
}: { rotulo: string; dica?: string; novaSenha?: boolean } & React.InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  const [visivel, setVisivel] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {rotulo}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visivel ? "text" : "password"}
          autoComplete={novaSenha ? "new-password" : "current-password"}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          aria-describedby={dica ? `${id}-dica` : undefined}
          className={`${CLASSE_CAMPO} pr-12`}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisivel((v) => !v)}
          aria-pressed={visivel}
          aria-label={visivel ? "Esconder a senha" : "Mostrar a senha"}
          className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-xl text-suave hover:text-texto"
        >
          {visivel ? <EyeOff className="size-5" aria-hidden /> : <Eye className="size-5" aria-hidden />}
        </button>
      </div>
      {dica && (
        <p id={`${id}-dica`} className="mt-1.5 text-xs text-suave">
          {dica}
        </p>
      )}
    </div>
  );
}
