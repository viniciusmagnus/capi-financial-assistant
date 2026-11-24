export type Humor = "sem_teto" | "tranquila" | "de_olho" | "apertada" | "estourou";

export type GastoRecente = {
  id: number;
  data: string;
  descricao: string;
  valor_centavos: number;
  categoria: string;
};

export type TransacaoEncontrada = GastoRecente & {
  relevancia: number;
  encontrada_por: ("significado" | "palavra")[];
};

export type Fala = { texto: string; autor: "claude" | "roteiro" };

export type Cofrinho = {
  mes: string;
  teto_centavos: number | null;
  gasto_centavos: number;
  pode_gastar_centavos: number | null;
  dias_no_mes: number;
  dias_restantes: number;
  por_dia_centavos: number | null;
  humor: Humor;
  ultimos: GastoRecente[];
  fala: Fala;
  teto_origem?: "mes" | "renda" | null;
};

export const CATEGORIAS_DESPESA = [
  "Mercado",
  "Restaurantes e delivery",
  "Transporte",
  "Lazer",
  "Moradia",
  "Saúde",
  "Assinaturas",
  "Educação",
  "Vestuário",
  "Pets",
  "Impostos e taxas",
  "Presentes e doações",
  "Outros",
] as const;

export const CATEGORIAS_RECEITA = ["Salário", "Rendimentos", "Reembolsos", "Outras receitas"] as const;

export type Categoria = string;

export type Sentido = "despesa" | "receita";

export type Categorias = { despesa: string[]; receita: string[]; transferencia: string; criadas: string[] };

export const CATEGORIAS_PADRAO: Categorias = {
  despesa: [...CATEGORIAS_DESPESA],
  receita: [...CATEGORIAS_RECEITA],
  transferencia: "Transferência interna",
  criadas: [],
};

export const todasAsCategorias = (c: Categorias) => [...c.despesa, ...c.receita, c.transferencia];

export type Regra = { id: number; padrao: string; categoria: Categoria };

export type ResultadoCategorizacao = {
  por_regra: number;
  enviadas_ao_claude: number;
  pelo_claude: number;
  pendentes: number;
  ia_disponivel: boolean;
  motivo: string | null;
  para_revisar_na_importacao: number | null;
};

const meses = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric", timeZone: "UTC" });

export function nomeDoMes(mes: string) {
  const texto = meses.format(new Date(`${mes}-01T00:00:00Z`));
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function mesVizinho(mes: string, passo: number) {
  const [ano, numero] = mes.split("-").map(Number);
  const data = new Date(Date.UTC(ano, numero - 1 + passo, 1));
  return data.toISOString().slice(0, 7);
}

export type TokenMcp = { id: number; nome: string; prefixo: string; criado_em: string; ultimo_uso_em: string | null };

export type TokenMcpCriado = { id: number; nome: string; token: string };
