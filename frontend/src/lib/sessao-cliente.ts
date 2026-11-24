import { paginaDeEntrada } from "./destino";

export function irParaEntrar() {
  window.location.assign(paginaDeEntrada(`${window.location.pathname}${window.location.search}`, { expirou: "1" }));
}
