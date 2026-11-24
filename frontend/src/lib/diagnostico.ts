export type Renda = { valor_centavos: number; variavel: boolean; atualizada_em: string };

export type Base = "mes_completo" | "projecao" | "periodo";

export type Linha = {
  chave: string;
  nome: string;
  marca: string | null;
  categoria: string;
  total_centavos: number;
  quantidade: number;
  pct_gastos: number;
  pct_renda: number | null;
};

export type TransacaoDiagnostico = {
  id: number;
  data: string;
  descricao: string;
  valor_centavos: number;
  categoria: string;
  estabelecimento: string;
  conta: string;
  revisar: boolean;
  confianca: string | null;
};

export type Aviso = { tipo: string; nivel: "info" | "atencao"; texto: string };

export type Recomendacao = {
  id: string;
  tipo: string;
  alvo_tipo: "categoria" | "estabelecimento";
  alvo_chave: string;
  alvo_nome: string;
  titulo: string;
  fato: string;
  consequencia: string;
  acao: string;
  reducao: number;
  economia_centavos: number;
  base: Base;
  calculo: string;
  capi: string;
};

export type Diagnostico = {
  mes: string;
  meses_disponiveis: string[];
  renda: Renda | null;
  renda_referencia_centavos: number | null;
  periodo: {
    inicio: string | null;
    fim: string | null;
    dias_cobertos: number;
    dias_no_mes: number;
    parcial: boolean;
    descricao: string;
  };
  contas: {
    nome: string;
    tipo: "ativo" | "passivo";
    inicio: string | null;
    fim: string | null;
    cobre_o_mes: boolean;
    anotada_a_mao: boolean;
  }[];
  totais: {
    gastos_centavos: number;
    quantidade_gastos: number;
    sem_categoria_centavos: number;
    sem_categoria_quantidade: number;
    para_revisar: number;
    estornos_centavos: number;
    entradas: { categoria: string; total_centavos: number; quantidade: number }[];
    transferencias_saida_centavos: number;
    transferencias_entrada_centavos: number;
  };
  comprometimento: number | null;
  diferenca_centavos: number | null;
  projecao: {
    fator: number;
    dias_base: number;
    gastos_centavos: number;
    comprometimento: number | null;
    diferenca_centavos: number | null;
  } | null;
  base: Base;
  fator_base: number;
  categorias: Linha[];
  estabelecimentos: Linha[];
  transacoes: TransacaoDiagnostico[];
  avisos: Aviso[];
  recomendacoes: Recomendacao[];
  economia_combinada_centavos: number;
};

export type ResultadoImportacao = {
  importacao_id: number;
  conta: string;
  banco: string | null;
  formato: "ofx" | "csv" | "pdf";
  cartao_de_credito: boolean;
  inicio: string | null;
  fim: string | null;
  no_arquivo: number;
  novas: number;
  duplicadas: number;
  categorizadas_por_regra: number;
  para_revisar: number;
};

export type Agrupamento = "categoria" | "estabelecimento";

export const chaveDoCorte = (tipo: Agrupamento, chave: string) => `${tipo}|${chave}`;

export type Simulacao = {
  economia_centavos: number;
  gastos_centavos: number;
  renda_centavos: number | null;
  comprometimento: number | null;
  diferenca_centavos: number | null;
  rotulo: string;
};

export function baseDoMes(d: Diagnostico) {
  const gastos = d.base === "projecao" && d.projecao ? d.projecao.gastos_centavos : d.totais.gastos_centavos;
  const renda = d.base === "periodo" ? d.renda_referencia_centavos : (d.renda?.valor_centavos ?? null);
  const rotulo =
    d.base === "mes_completo"
      ? "no mês"
      : d.base === "projecao"
        ? `por mês, projetado pelos ${d.periodo.dias_cobertos} dias do extrato`
        : `nos ${d.periodo.dias_cobertos} dias do extrato`;
  return { gastos, renda, rotulo };
}

export function simular(d: Diagnostico, cortes: Record<string, number>): Simulacao {
  const maiorCorte = new Map<number, number>();
  for (const t of d.transacoes) {
    if (t.valor_centavos <= 0) continue;
    const fracao = Math.max(
      cortes[chaveDoCorte("categoria", t.categoria)] ?? 0,
      cortes[chaveDoCorte("estabelecimento", t.estabelecimento)] ?? 0,
    );
    if (fracao > 0) maiorCorte.set(t.id, fracao);
  }
  const valores = new Map(d.transacoes.map((t) => [t.id, t.valor_centavos]));
  let soma = 0;
  for (const [id, fracao] of maiorCorte) soma += (valores.get(id) ?? 0) * fracao;
  const economia = Math.round(soma * d.fator_base);

  const { gastos, renda, rotulo } = baseDoMes(d);
  const novos = gastos - economia;
  return {
    economia_centavos: economia,
    gastos_centavos: novos,
    renda_centavos: renda,
    comprometimento: renda ? novos / renda : null,
    diferenca_centavos: renda === null ? null : renda - novos,
    rotulo,
  };
}

const meses = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric", timeZone: "UTC" });
const diaMes = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", timeZone: "UTC" });

export function nomeDoMes(mes: string) {
  const texto = meses.format(new Date(`${mes}-01T00:00:00Z`));
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export const formatarDiaMes = (iso: string) => diaMes.format(new Date(`${iso}T00:00:00Z`));

export function mesAtual() {
  const partes = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit" }).formatToParts(
    new Date(),
  );
  const ano = partes.find((p) => p.type === "year")?.value;
  const mes = partes.find((p) => p.type === "month")?.value;
  return `${ano}-${mes}`;
}
