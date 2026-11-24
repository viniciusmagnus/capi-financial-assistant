import type { Humor } from "@/lib/cofrinho";

const PELO = "#a9774e";
const PELO_ESCURO = "#7f5636";
const FOCINHO = "#c79a71";
const TRACO = "#2b1d14";

function Olhos({ humor }: { humor: Humor }) {
  const props = { stroke: TRACO, strokeWidth: 3.2, strokeLinecap: "round" as const, fill: "none" };
  switch (humor) {
    case "tranquila":
      return (
        <g {...props}>
          <path d="M52 64 q7 6 14 0" />
          <path d="M94 64 q7 6 14 0" />
        </g>
      );
    case "de_olho":
      return (
        <g>
          <g {...props}>
            <path d="M51 61 h16" />
            <path d="M93 61 h16" />
            <path d="M93 51 l15 -4" />
          </g>
          <circle cx="63" cy="65" r="3.6" fill={TRACO} />
          <circle cx="105" cy="65" r="3.6" fill={TRACO} />
        </g>
      );
    case "apertada":
      return (
        <g>
          <circle cx="59" cy="63" r="3.8" fill={TRACO} />
          <circle cx="101" cy="63" r="3.8" fill={TRACO} />
          <g {...props}>
            <path d="M51 54 l14 3" />
            <path d="M109 54 l-14 3" />
          </g>
          <path d="M126 34 q6 10 0 14 q-6 -4 0 -14z" fill="#7cc3ea" />
        </g>
      );
    case "estourou":
      return (
        <g {...props}>
          <path d="M53 58 l11 11 M64 58 l-11 11" />
          <path d="M96 58 l11 11 M107 58 l-11 11" />
        </g>
      );
    default:
      return (
        <g>
          <circle cx="59" cy="64" r="3.6" fill={TRACO} />
          <circle cx="101" cy="64" r="3.6" fill={TRACO} />
          <text x="128" y="30" fontSize="22" fontWeight="700" fill={TRACO} opacity="0.7">
            ?
          </text>
        </g>
      );
  }
}

function Boca({ humor }: { humor: Humor }) {
  const props = { stroke: TRACO, strokeWidth: 2.6, strokeLinecap: "round" as const, fill: "none" };
  switch (humor) {
    case "tranquila":
      return <path d="M72 104 q8 6 16 0" {...props} />;
    case "de_olho":
      return <path d="M72 105 q9 0 16 -3" {...props} />;
    case "apertada":
      return <path d="M70 105 q4 -3 7 0 t7 0 t7 0" {...props} />;
    case "estourou":
      return <ellipse cx="80" cy="106" rx="6" ry="7" fill={TRACO} />;
    default:
      return <path d="M73 104 h14" {...props} />;
  }
}

export function Capivara({ humor, className }: { humor: Humor; className?: string }) {
  return (
    <svg viewBox="0 0 160 140" className={className} role="img" aria-label={`Capi, a capivara, está ${humor.replace("_", " ")}`}>
      <ellipse cx="80" cy="132" rx="46" ry="6" fill="currentColor" opacity="0.08" />
      <ellipse cx="46" cy="34" rx="10" ry="8" fill={PELO_ESCURO} />
      <ellipse cx="114" cy="34" rx="10" ry="8" fill={PELO_ESCURO} />
      <rect x="28" y="30" width="104" height="98" rx="44" fill={PELO} />
      <ellipse cx="80" cy="96" rx="36" ry="24" fill={FOCINHO} />
      <ellipse cx="71" cy="88" rx="3.4" ry="2.4" fill={TRACO} />
      <ellipse cx="89" cy="88" rx="3.4" ry="2.4" fill={TRACO} />
      {humor === "tranquila" && (
        <g>
          <circle cx="80" cy="22" r="11" fill="#f5a524" />
          <path d="M80 11 q6 -6 11 -3 q-5 4 -11 3z" fill="#4c9a4a" />
          <ellipse cx="44" cy="80" rx="7" ry="4" fill="#e58f86" opacity="0.55" />
          <ellipse cx="116" cy="80" rx="7" ry="4" fill="#e58f86" opacity="0.55" />
        </g>
      )}
      {humor === "estourou" && (
        <g fill="#e05656" opacity="0.6">
          <ellipse cx="44" cy="80" rx="8" ry="5" />
          <ellipse cx="116" cy="80" rx="8" ry="5" />
        </g>
      )}
      <Olhos humor={humor} />
      <Boca humor={humor} />
    </svg>
  );
}
