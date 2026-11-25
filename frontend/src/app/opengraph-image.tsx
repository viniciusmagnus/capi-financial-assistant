import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { ImageResponse } from "next/og";

export const alt = "Capi, a capivara que cuida das suas finanças, ao pôr do sol";
export const size = { width: 1200, height: 627 };
export const contentType = "image/png";

const FAMILIA = "Archivo";

async function fonte(peso: 400 | 800) {
  try {
    const css = await fetch(`https://fonts.googleapis.com/css2?family=${FAMILIA}:wght@${peso}`).then((r) => r.text());
    const url = css.match(/src: url\((.+?)\) format\('(?:opentype|truetype)'\)/)?.[1];
    if (!url) return null;
    const dados = await fetch(url).then((r) => r.arrayBuffer());
    return { name: FAMILIA, data: dados, weight: peso, style: "normal" as const };
  } catch {
    return null;
  }
}

export default async function Image() {
  const [mascote, regular, forte] = await Promise.all([
    readFile(join(process.cwd(), "public", "capi.svg"), "utf8"),
    fonte(400),
    fonte(800),
  ]);
  const fontes = [regular, forte].filter((f) => f !== null);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 88px",
          background: "linear-gradient(160deg, #0f2726 0%, #0a1c1b 55%, #0a1c1b 100%)",
          fontFamily: fontes.length ? FAMILIA : undefined,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", width: 640 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, color: "#ff7a3d", fontSize: 30, fontWeight: 800, letterSpacing: 2 }}>
            CAPI
            <div style={{ display: "flex", width: 56, height: 4, borderRadius: 2, background: "#ff7a3d" }} />
            <span style={{ color: "#9fbab4", fontWeight: 400, letterSpacing: 0, fontSize: 26 }}>assistente financeiro</span>
          </div>
          <div style={{ display: "flex", marginTop: 28, color: "#f3ebe1", fontSize: 76, fontWeight: 800, lineHeight: 1.04 }}>
            Para onde foi o seu mês?
          </div>
          <div style={{ display: "flex", marginTop: 28, color: "#9fbab4", fontSize: 32, lineHeight: 1.35 }}>
            Solte o extrato e a fatura: a Capi categoriza os gastos, vigia o teto e responde no chat.
          </div>
          <div style={{ display: "flex", marginTop: 40, color: "#5fd4c4", fontSize: 24 }}>Claude · RAG · MCP</div>
        </div>
        <div
          style={{
            display: "flex",
            borderRadius: 72,
            boxShadow: "0 30px 80px rgba(255, 122, 61, 0.28)",
          }}
        >
          <img src={`data:image/svg+xml;base64,${Buffer.from(mascote).toString("base64")}`} width={380} height={380} alt="" />
        </div>
      </div>
    ),
    { ...size, fonts: fontes },
  );
}
