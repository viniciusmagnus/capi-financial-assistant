import {
  Car,
  CircleHelp,
  Gift,
  GraduationCap,
  HeartPulse,
  House,
  Landmark,
  type LucideIcon,
  PawPrint,
  Shapes,
  Shirt,
  ShoppingCart,
  Ticket,
  Tv,
  UtensilsCrossed,
} from "lucide-react";
import {
  type SimpleIcon,
  siAirbnb,
  siAliexpress,
  siApple,
  siBurgerking,
  siCarrefour,
  siClaude,
  siCoursera,
  siDuolingo,
  siGoogle,
  siHbomax,
  siIcloud,
  siIfood,
  siKfc,
  siMcdonalds,
  siNetflix,
  siPlaystation,
  siShell,
  siShopee,
  siSpotify,
  siStarbucks,
  siSteam,
  siUber,
  siUbereats,
  siUdemy,
  siYoutube,
} from "simple-icons";

const ICONES_DE_MARCA: Record<string, SimpleIcon> = {
  airbnb: siAirbnb,
  aliexpress: siAliexpress,
  apple: siApple,
  burgerking: siBurgerking,
  carrefour: siCarrefour,
  claude: siClaude,
  coursera: siCoursera,
  duolingo: siDuolingo,
  google: siGoogle,
  hbomax: siHbomax,
  icloud: siIcloud,
  ifood: siIfood,
  kfc: siKfc,
  mcdonalds: siMcdonalds,
  netflix: siNetflix,
  playstation: siPlaystation,
  shell: siShell,
  shopee: siShopee,
  spotify: siSpotify,
  starbucks: siStarbucks,
  steam: siSteam,
  uber: siUber,
  ubereats: siUbereats,
  udemy: siUdemy,
  youtube: siYoutube,
};

const ICONES_DE_CATEGORIA: Record<string, LucideIcon> = {
  Mercado: ShoppingCart,
  "Restaurantes e delivery": UtensilsCrossed,
  Transporte: Car,
  Lazer: Ticket,
  Moradia: House,
  Saúde: HeartPulse,
  Educação: GraduationCap,
  Assinaturas: Tv,
  Vestuário: Shirt,
  Pets: PawPrint,
  "Impostos e taxas": Landmark,
  "Presentes e doações": Gift,
  Outros: Shapes,
  "A classificar": CircleHelp,
};

function iniciais(nome: string) {
  const palavras = nome.replace(/[^\p{L}\p{N} ]/gu, "").split(/\s+/).filter(Boolean);
  if (palavras.length === 1) return palavras[0].slice(0, 2);
  return (palavras[0][0] + palavras[1][0]).toUpperCase();
}

export function IconeGasto({ marca, nome, categoria }: { marca: string | null; nome: string; categoria: string }) {
  const caixa = "flex size-9 shrink-0 items-center justify-center rounded-xl";
  const icone = marca ? ICONES_DE_MARCA[marca] : undefined;
  if (icone) {
    return (
      <span className={`${caixa} bg-white ring-1 ring-borda`} title={nome}>
        <svg viewBox="0 0 24 24" className="size-5" role="img" aria-label={`logo ${icone.title}`}>
          <path d={icone.path} fill={`#${icone.hex}`} />
        </svg>
      </span>
    );
  }
  if (marca) {
    return (
      <span className={`${caixa} bg-texto text-[11px] font-bold tracking-tight text-fundo`} aria-label={`marca ${nome}`} title={nome}>
        {iniciais(nome)}
      </span>
    );
  }
  const Icone = ICONES_DE_CATEGORIA[categoria] ?? Shapes;
  return (
    <span className={`${caixa} bg-trilho text-suave`} aria-hidden>
      <Icone className="size-[18px]" strokeWidth={1.8} />
    </span>
  );
}
