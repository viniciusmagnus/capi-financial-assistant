import { CircleAlert, Info } from "lucide-react";

import { type Diagnostico, formatarDiaMes } from "@/lib/diagnostico";
import { formatarReais } from "@/lib/formato";

function tipoDaConta(c: Diagnostico["contas"][number]) {
  if (c.anotada_a_mao) return "anotada à mão";
  return c.tipo === "passivo" ? "cartão" : "conta";
}

function Observacoes({ diagnostico: d }: { diagnostico: Diagnostico }) {
  if (d.avisos.length === 0) return null;
  return (
    <details className="mt-6 text-sm">
      <summary className="cursor-pointer text-suave hover:text-texto">Observações sobre os números ({d.avisos.length})</summary>
      <ul className="mt-3 space-y-2.5">
        {d.avisos.map((a) => (
          <li key={a.tipo} className="flex gap-2.5">
            {a.nivel === "atencao" ? (
              <CircleAlert className="mt-0.5 size-4 shrink-0 text-sol" aria-label="atenção" />
            ) : (
              <Info className="mt-0.5 size-4 shrink-0 text-suave" aria-label="informação" />
            )}
            <span className="text-suave">{a.texto}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function ContasDoMes({ diagnostico: d }: { diagnostico: Diagnostico }) {
  const fora = d.totais;
  const temFora = fora.entradas.length > 0 || fora.estornos_centavos > 0 || fora.transferencias_saida_centavos > 0;

  return (
    <section aria-labelledby="titulo-contas">
      <h2 id="titulo-contas" className="largo text-2xl font-bold">
        De onde vieram os números
      </h2>
      <div className="mt-4 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="text-xs font-semibold text-suave">Contas consideradas</h3>
          <ul className="mt-2 divide-y divide-borda border-y border-borda text-sm">
            {d.contas.map((c) => (
              <li key={`${c.tipo}-${c.nome}`} className="flex flex-wrap justify-between gap-x-3 py-2">
                <span>
                  {c.nome} <span className="text-suave">· {tipoDaConta(c)}</span>
                </span>
                <span className="text-suave">
                  {c.inicio && c.fim ? `${formatarDiaMes(c.inicio)} a ${formatarDiaMes(c.fim)}${c.cobre_o_mes ? " · mês inteiro" : ""}` : "sem extrato no mês"}
                </span>
              </li>
            ))}
            {d.contas.length === 0 && <li className="py-2 text-suave">Nenhuma conta com movimento neste mês.</li>}
          </ul>
        </div>

        {temFora && (
          <div>
            <h3 className="text-xs font-semibold text-suave">Fora dos gastos</h3>
            <ul className="mt-2 divide-y divide-borda border-y border-borda text-sm">
              {fora.entradas.map((e) => (
                <li key={e.categoria} className="flex justify-between gap-3 py-2">
                  <span>
                    Entrada: {e.categoria === "A classificar" ? "sem categoria" : e.categoria} <span className="text-suave">({e.quantidade})</span>
                  </span>
                  <span className="text-correnteza">{formatarReais(e.total_centavos)}</span>
                </li>
              ))}
              {fora.estornos_centavos > 0 && (
                <li className="flex justify-between gap-3 py-2">
                  <span>Estornos e reembolsos</span>
                  <span>{formatarReais(fora.estornos_centavos)}</span>
                </li>
              )}
              {fora.transferencias_saida_centavos > 0 && (
                <li className="flex justify-between gap-3 py-2">
                  <span>Transferências e pagamento de fatura</span>
                  <span>{formatarReais(fora.transferencias_saida_centavos)}</span>
                </li>
              )}
            </ul>
            <p className="mt-2 text-xs text-suave">Entrada no extrato não substitui a renda informada: nem todo dinheiro que entra é salário.</p>
          </div>
        )}
      </div>
      <Observacoes diagnostico={d} />
    </section>
  );
}
