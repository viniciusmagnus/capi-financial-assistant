import type { Cofrinho, GastoRecente, Humor } from "./cofrinho";

const ROTEIRO: Record<Humor, string[]> = {
  sem_teto: [
    "Sem teto, tchê? Isso não é orçamento, é rodeio.",
    "Gastar sem teto é fazer churrasco sem saber quantos vêm.",
    "Me dá um teto pro mês. Ou pelo menos me deixa reclamar com propriedade.",
  ],
  tranquila: [
    "Bah, tudo em ordem. Tão em ordem que até o chimarrão tá desconfiado.",
    "Tu tá no ritmo. Vou lagartear no sol antes que tu invente moda.",
    "Vou tirar um cochilo. Me acorda se tu abrir o app de delivery.",
  ],
  de_olho: [
    "O mês ainda tá no chimarrão e teus gastos já tão no churrasco.",
    "Não tô julgando, tchê. Tô só anotando. Bem devagarinho.",
    "Teu cartão tá correndo mais que ônibus atrasado na Ipiranga.",
  ],
  apertada: [
    "Sobrou pouco pila e muito mês. Que emocionante, né?",
    "Daqui pra frente é cacetinho com margarina e olhe lá.",
    "Respira. Guarda o cartão. Isso, devagarinho, como quem não quer nada.",
  ],
  estourou: [
    "Barbaridade, passou do teto. Caíram os butiá do bolso aqui.",
    "Estourou. Vou ali lagartear e fingir que não vi.",
    "Parabéns, tu zerou o mês. Que orgulho. Que desgosto.",
  ],
};

function calcularHumor(teto: number | null, gasto: number, diasNoMes: number, restantes: number): Humor {
  if (teto === null) return "sem_teto";
  if (gasto > teto) return "estourou";
  const usado = gasto / teto;
  const decorrido = restantes ? (diasNoMes - restantes + 1) / diasNoMes : 1;
  if (usado >= 0.85 || usado > decorrido + 0.2) return "apertada";
  if (usado > decorrido + 0.05) return "de_olho";
  return "tranquila";
}

function montar(teto: number | null, gasto: number, ultimos: GastoRecente[]): Cofrinho {
  const diasNoMes = 30;
  const restantes = 12;
  const podeGastar = teto === null ? null : teto - gasto;
  const humor = calcularHumor(teto, gasto, diasNoMes, restantes);
  const opcoes = ROTEIRO[humor];
  return {
    mes: "2026-11",
    teto_centavos: teto,
    gasto_centavos: gasto,
    pode_gastar_centavos: podeGastar,
    dias_no_mes: diasNoMes,
    dias_restantes: restantes,
    por_dia_centavos: podeGastar === null ? null : Math.floor(Math.max(podeGastar, 0) / restantes),
    humor,
    ultimos: ultimos.slice(0, 5),
    fala: { texto: opcoes[gasto % opcoes.length], autor: "roteiro" },
  };
}

export const ULTIMOS: GastoRecente[] = [
  { id: 5, data: "2026-11-19", descricao: "IFD*BURGER DO BAIRRO", valor_centavos: -6_890, categoria: "Restaurantes e delivery" },
  { id: 4, data: "2026-11-18", descricao: "ZAFFARI CRISTAL", valor_centavos: -31_245, categoria: "Mercado" },
  { id: 3, data: "2026-11-17", descricao: "UBER *TRIP", valor_centavos: -2_310, categoria: "Transporte" },
  { id: 2, data: "2026-11-15", descricao: "CINEMA BOURBON", valor_centavos: -6_400, categoria: "Lazer" },
  { id: 1, data: "2026-11-14", descricao: "PAG*FARMACIA SAO JOAO", valor_centavos: -8_790, categoria: "Saúde" },
];

const gastoInicial = 145_350 + ULTIMOS.reduce((soma, g) => soma - g.valor_centavos, 0);

export const cofrinhoDemo = montar(300_000, gastoInicial, ULTIMOS);
