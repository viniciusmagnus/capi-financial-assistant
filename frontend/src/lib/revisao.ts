import type { Regra } from "./cofrinho";

export type FiltroRevisao = { q?: string; inicio?: string; fim?: string; conta_id?: number };

export type ItemRevisao = {
  id: number;
  data: string;
  descricao: string;
  valor_centavos: number;
  conta_id: number;
  conta: string;
  categoria: string;
  estabelecimento: string;
  estabelecimento_confirmado: boolean;
  marca: string | null;
  forma_pagamento: string | null;
  parcela: string | null;
  categorizada_por: "regra" | "claude" | "usuario" | null;
};

export type PaginaRevisao = { itens: ItemRevisao[]; total: number; total_centavos: number; pagina: number; por_pagina: number };

export type GrupoRevisao = {
  chave: string;
  estabelecimento: string;
  marca: string | null;
  confirmado: boolean;
  quantidade: number;
  total_centavos: number;
  descricoes: string[];
  ids: number[];
};

export type ContaDeOrigem = { id: number; nome: string };

export type OrigemInformacao = "usuario" | "regra" | "historico" | "pesquisa" | "hipotese";

export type Evidencia = { origem: OrigemInformacao; texto: string; fontes: string[] };

export type RegraSugerida = { padrao: string; categoria: string | null; estabelecimento: string | null };

export type ConteudoProposta = {
  transacao_ids: number[];
  estabelecimento: string | null;
  categoria: string | null;
  motivo: string;
  evidencias: Evidencia[];
  incertezas: string[];
  regra: RegraSugerida | null;
};

export type OpcoesAplicacao = {
  alcance: "selecionadas" | "correspondencias";
  salvar_regra: boolean;
  substituir_manuais: boolean;
  confirmar_transferencia: boolean;
};

export type LinhaPrevia = {
  id: number;
  data: string;
  descricao: string;
  valor_centavos: number;
  categoria_atual: string;
  categoria_nova: string;
  estabelecimento_atual: string | null;
  estabelecimento_novo: string | null;
  categorizada_por: ItemRevisao["categorizada_por"];
  por: "selecao" | "regra";
  motivo: string | null;
};

export type Previa = {
  afetadas: LinhaPrevia[];
  ignoradas: LinhaPrevia[];
  manuais_preservadas: number;
  efeito_nos_gastos_centavos: number;
  regra: {
    padrao: string;
    categoria: string | null;
    estabelecimento: string | null;
    valida: boolean;
    erro: string | null;
    existente: Regra | null;
    casa_com_selecionadas: number;
    correspondencias_existentes: number;
  } | null;
  avisos: string[];
  exige_confirmar_transferencia: boolean;
  assinatura: string;
};

export type ResultadoLote = { lote_id: number; alteradas: number; regra: Regra | null; repetido: boolean };

export type ResultadoDesfazer = { lote_id: number; desfeitas: number; conflitos: number[]; ja_desfeito: boolean };

export type LoteResumo = { id: number; resumo: string; criado_em: string; desfeito_em: string | null; alteracoes: number; regra_id: number | null };

export type FonteDaConversa = { id: string; titulo: string; url: string; termo: string };

export type PesquisaFeita = { termo: string; cidade: string | null; consultas: string[]; fontes: string[]; resumo: string; recusada: string | null };

export type PropostaSalva = { id: number; status: "pendente" | "aplicada" | "rejeitada"; conteudo: ConteudoProposta };

export type RespostaRevisao = {
  conversa_id: number;
  resposta: string;
  propostas: PropostaSalva[];
  descartadas: string[];
  pesquisas: PesquisaFeita[];
  fontes: FonteDaConversa[];
  pesquisa_disponivel: boolean;
  ia_disponivel: boolean;
};

export type ConversaCriada = { id: number; pesquisa_disponivel: boolean; ia_disponivel: boolean };

export type Resultado<T> = { ok: true; dados: T } | { ok: false; erro: string; status?: number };

export const ROTULO_ORIGEM: Record<OrigemInformacao, string> = {
  usuario: "Você disse",
  regra: "Regra existente",
  historico: "Seu histórico",
  pesquisa: "Pesquisa na web",
  hipotese: "Hipótese do Claude",
};
