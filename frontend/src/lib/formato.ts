const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const porcento = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });
const dataCurta = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", timeZone: "UTC" });

export const formatarReais = (centavos: number) => reais.format(centavos / 100);
export const formatarPorcento = (fracao: number) => porcento.format(fracao);
export const formatarData = (iso: string) => dataCurta.format(new Date(`${iso}T00:00:00Z`));
