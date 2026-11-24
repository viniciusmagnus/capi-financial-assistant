export type Fonte = { id: string; titulo: string; url: string };

export type OrigemDaSugestao = "descricao" | "historico" | "pesquisa";

export type SugestaoDeGasto = {
  transacao_id: number;
  data: string;
  descricao: string;
  valor_centavos: number;
  conta: string;
  parcela: string | null;
  estabelecimento: string | null;
  categoria: string | null;
  justificativa: string;
  origem: OrigemDaSugestao | null;
  fontes: Fonte[];
};

export type AnaliseOutros = {
  sugestoes: SugestaoDeGasto[];
  total_em_outros: number;
  analisadas: number;
  ia_disponivel: boolean;
  pesquisa_disponivel: boolean;
  pesquisas_feitas: number;
  aviso: string | null;
};

export type Decisao = {
  transacao_id: number;
  categoria: string;
  estabelecimento: string | null;
  origem: "usuario" | "historico" | "pesquisa";
};

export type ResultadoConfirmacao = {
  lote_id: number | null;
  alteradas: number;
  ignoradas: { transacao_id: number; motivo: string }[];
  regras_salvas: string[];
  repetido: boolean;
};

export type ResultadoDesfazer = { lote_id: number; desfeitas: number; conflitos: number[]; ja_desfeito: boolean };

export type Resultado<T> = { ok: true; dados: T } | { ok: false; erro: string; status?: number };
