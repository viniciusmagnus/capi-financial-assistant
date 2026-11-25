import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";
import { connection } from "next/server";
import { Topo } from "@/components/Topo";

import "./globals.css";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  axes: ["wdth"],
});

const titulo = "Capi, assistente financeiro";
const descricao =
  "Solte o extrato e a fatura e veja para onde foi o seu mês. A Capi categoriza os gastos, vigia o teto do mês e responde no chat.";

export async function generateMetadata(): Promise<Metadata> {
  await connection();
  return {
    metadataBase: new URL(process.env.BETTER_AUTH_URL ?? "http://localhost:3100"),
    title: titulo,
    description: descricao,
    icons: { icon: { url: "/capi.svg", type: "image/svg+xml" } },
    openGraph: {
      type: "website",
      locale: "pt_BR",
      siteName: "Capi",
      url: "/",
      title: titulo,
      description: descricao,
    },
    twitter: { card: "summary_large_image", title: titulo, description: descricao },
  };
}

export const viewport: Viewport = {
  themeColor: "#0a1c1b",
  colorScheme: "dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${archivo.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col pb-16 sm:pb-0 has-[header[data-publica]]:pb-0">
        <Topo />
        {children}
      </body>
    </html>
  );
}
