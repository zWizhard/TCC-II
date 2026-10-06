import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export type DataTableColumn<Row> = {
  id: string;
  header: string;
  cell: (row: Row) => ReactNode;
  /** Valor usado na ordenação. Sem ele, a coluna não é ordenável. */
  sortValue?: (row: Row) => string | number;
  align?: "left" | "right";
  /** Marca a célula como cabeçalho da linha (`<th scope="row">`). */
  rowHeader?: boolean;
};

export type DataTableSort = { columnId: string; direction: "asc" | "desc" };

type DataTableProps<Row> = {
  /** Legenda da tabela: o que os dados representam. */
  caption: string;
  columns: ReadonlyArray<DataTableColumn<Row>>;
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  /** Ordenação inicial. Sem ela, mantém a ordem recebida. */
  initialSort?: DataTableSort;
  className?: string;
};

const collator = new Intl.Collator("pt-BR", { sensitivity: "base", numeric: true });

function compare(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return collator.compare(String(a), String(b));
}

/** Tabela ordenável por clique ou teclado nos cabeçalhos, com `aria-sort`. */
export function DataTable<Row>({
  caption,
  columns,
  rows,
  rowKey,
  initialSort,
  className,
}: DataTableProps<Row>) {
  const [sort, setSort] = useState<DataTableSort | undefined>(initialSort);

  const sorted = useMemo(() => {
    const column = sort && columns.find((c) => c.id === sort.columnId);
    const sortValue = column?.sortValue;
    if (!sort || !sortValue) return [...rows];
    const factor = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => factor * compare(sortValue(a), sortValue(b)));
  }, [rows, columns, sort]);

  const toggle = (column: DataTableColumn<Row>) => {
    setSort((current) => {
      if (current?.columnId === column.id) {
        return { columnId: column.id, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      // Texto começa em ordem alfabética; número começa do maior para o menor.
      const sample = rows[0] !== undefined ? column.sortValue?.(rows[0]) : undefined;
      return { columnId: column.id, direction: typeof sample === "number" ? "desc" : "asc" };
    });
  };

  return (
    <Table className={className}>
      <TableCaption className="mt-3 text-left text-xs">{caption}</TableCaption>
      <TableHeader>
        <TableRow>
          {columns.map((column) => {
            const active = sort?.columnId === column.id;
            const direction = active ? sort.direction : undefined;
            const Icon =
              direction === "asc" ? ArrowUp : direction === "desc" ? ArrowDown : ArrowUpDown;
            return (
              <TableHead
                key={column.id}
                scope="col"
                aria-sort={
                  !column.sortValue
                    ? undefined
                    : direction === "asc"
                      ? "ascending"
                      : direction === "desc"
                        ? "descending"
                        : "none"
                }
                className={cn("h-10 px-3", column.align === "right" && "text-right")}
              >
                {column.sortValue ? (
                  <button
                    type="button"
                    onClick={() => toggle(column)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded text-xs font-semibold text-muted-foreground hover:text-foreground",
                      active && "text-foreground",
                    )}
                  >
                    {column.header}
                    <Icon className="size-3.5" aria-hidden="true" />
                    <span className="sr-only">
                      {direction === "asc"
                        ? "(ordem crescente; ativar para inverter)"
                        : direction === "desc"
                          ? "(ordem decrescente; ativar para inverter)"
                          : "(ativar para ordenar)"}
                    </span>
                  </button>
                ) : (
                  <span className="text-xs font-semibold">{column.header}</span>
                )}
              </TableHead>
            );
          })}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((row) => (
          <TableRow key={rowKey(row)}>
            {columns.map((column) =>
              column.rowHeader ? (
                <th
                  key={column.id}
                  scope="row"
                  className="px-3 py-2 text-left text-sm font-medium text-foreground"
                >
                  {column.cell(row)}
                </th>
              ) : (
                <TableCell
                  key={column.id}
                  className={cn(
                    "px-3 py-2 text-sm",
                    column.align === "right" && "text-right tabular-nums",
                  )}
                >
                  {column.cell(row)}
                </TableCell>
              ),
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
