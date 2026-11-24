import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";
import { Topo } from "@/components/Topo";

import "./globals.css";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  axes: ["wdth"],
});

export const metadata: Metadata = {
  title: "Capi, assistente financeiro",
  description: "Solte o extrato e a fatura e veja para onde foi o seu mês.",
  icons: { icon: { url: "/capi.svg", type: "image/svg+xml" } },
};

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
