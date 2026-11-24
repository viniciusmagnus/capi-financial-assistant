import type { Categorias } from "@/lib/cofrinho";

export function OpcoesDeCategoria({ categorias, sentido }: { categorias: Categorias; sentido?: "despesa" | "receita" }) {
  return (
    <>
      {sentido !== "receita" && (
        <optgroup label="Gastos">
          {categorias.despesa.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </optgroup>
      )}
      {sentido !== "despesa" && (
        <optgroup label="Entradas">
          {categorias.receita.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </optgroup>
      )}
      <optgroup label="Entre suas contas">
        <option>{categorias.transferencia}</option>
      </optgroup>
    </>
  );
}
