import { Suspense } from "react";

import { Chat } from "@/components/Chat";
import { exigirUsuario } from "@/lib/sessao";

async function ChatDoUsuario() {
  await exigirUsuario("/chat");
  return <Chat />;
}

export default function PaginaChat() {
  return (
    <Suspense fallback={<main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-6 text-suave">Abrindo o chat…</main>}>
      <ChatDoUsuario />
    </Suspense>
  );
}
