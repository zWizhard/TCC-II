import { useId, useMemo, useState } from "react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { formatarInteiro } from "@/lib/format";

import { LIMITE_TABELA } from "./search";

export type Ordenacao<Row> = {
  id: string;
  rotulo: string;
  comparar: (a: Row, b: Row) => number;
};

type TabelaPaginadaProps<Row> = {
  caption: string;
  /** Colunas sem `sortValue`: a ordem vale para todas as páginas e é escolhida no seletor. */
  columns: ReadonlyArray<DataTableColumn<Row>>;
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  /** A primeira é a ordem inicial. */
  ordenacoes: readonly [Ordenacao<Row>, ...Array<Ordenacao<Row>>];
  /** Nome das linhas no rodapé (ex.: "municípios"). */
  unidades: string;
};

/**
 * Alternativa em texto ao mapa: as mesmas unidades, ordenadas e paginadas no navegador. O mapa
 * pode ter milhares de unidades; a tabela mostra 25 por vez, sem nova consulta à API.
 */
export function TabelaPaginada<Row>({
  caption,
  columns,
  rows,
  rowKey,
  ordenacoes,
  unidades,
}: TabelaPaginadaProps<Row>) {
  const seletorId = useId();
  const [ordemId, setOrdemId] = useState(ordenacoes[0].id);
  const [pagina, setPagina] = useState(1);

  const ordem = ordenacoes.find((o) => o.id === ordemId) ?? ordenacoes[0];
  const ordenadas = useMemo(() => [...rows].sort(ordem.comparar), [rows, ordem]);
  const paginas = Math.max(1, Math.ceil(ordenadas.length / LIMITE_TABELA));
  const atual = Math.min(pagina, paginas);
  const primeira = (atual - 1) * LIMITE_TABELA;
  const visiveis = ordenadas.slice(primeira, primeira + LIMITE_TABELA);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <label
            htmlFor={seletorId}
            className="mb-1.5 block text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground"
          >
            Ordenar a tabela por
          </label>
          <select
            id={seletorId}
            value={ordem.id}
            onChange={(event) => {
              setOrdemId(event.target.value);
              setPagina(1);
            }}
            className="h-9 max-w-full rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground"
          >
            {ordenacoes.map((o) => (
              <option key={o.id} value={o.id}>
                {o.rotulo}
              </option>
            ))}
          </select>
        </div>
      </div>

      <DataTable
        className="mt-4"
        caption={caption}
        columns={columns}
        rows={visiveis}
        rowKey={rowKey}
      />

      <nav
        aria-label="Páginas da tabela do mapa"
        className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground"
      >
        <p role="status">
          {ordenadas.length === 0
            ? `Nenhum registro`
            : `${unidades} ${formatarInteiro(primeira + 1)}–${formatarInteiro(primeira + visiveis.length)} de ${formatarInteiro(ordenadas.length)} · página ${formatarInteiro(atual)} de ${formatarInteiro(paginas)}`}
        </p>
        <div className="flex gap-2">
          {(
            [
              ["Anterior", atual <= 1, atual - 1],
              ["Próxima", atual >= paginas, atual + 1],
            ] as const
          ).map(([rotulo, desabilitado, destino]) => (
            <button
              key={rotulo}
              type="button"
              disabled={desabilitado}
              onClick={() => setPagina(destino)}
              className="rounded-md border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              {rotulo}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}
