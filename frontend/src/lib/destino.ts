const PAGINAS_DE_ENTRADA = ["/entrar", "/cadastrar", "/verificar-email", "/recuperar-senha", "/redefinir-senha"];

export function destinoSeguro(valor: unknown, padrao = "/"): string {
  if (typeof valor !== "string" || valor.length === 0 || valor.length > 512) return padrao;
  if (!valor.startsWith("/") || valor.startsWith("//") || valor.includes("\\")) return padrao;
  if (/[\u0000-\u001f\u007f]/.test(valor)) return padrao;
  let url: URL;
  try {
    url = new URL(valor, "http://capi.interno");
  } catch {
    return padrao;
  }
  if (url.origin !== "http://capi.interno") return padrao;
  try {
    if (/[\u0000-\u001f\u007f]/.test(decodeURIComponent(url.pathname + url.search))) return padrao;
  } catch {
    return padrao;
  }
  if (PAGINAS_DE_ENTRADA.some((p) => url.pathname === p || url.pathname.startsWith(`${p}/`))) return padrao;
  if (url.pathname.startsWith("/api/")) return padrao;
  return `${url.pathname}${url.search}`;
}

export function paginaDeEntrada(volta: string, extras: Record<string, string> = {}): string {
  const parametros = new URLSearchParams(extras);
  const seguro = destinoSeguro(volta);
  if (seguro !== "/") parametros.set("volta", seguro);
  const consulta = parametros.toString();
  return consulta ? `/entrar?${consulta}` : "/entrar";
}
