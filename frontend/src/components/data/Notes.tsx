import { Info } from "lucide-react";

import { cn } from "@/lib/utils";

type NotesProps = {
  /** Ressalvas devolvidas pela API (`notas`). Texto exibido como dado. */
  notas: readonly string[];
  className?: string;
};

/** Ressalvas que acompanham um número. Não renderiza nada quando não há nota. */
export function Notes({ notas, className }: NotesProps) {
  if (notas.length === 0) return null;
  return (
    <ul className={cn("space-y-1.5", className)} aria-label="Ressalvas">
      {notas.map((nota) => (
        <li
          key={nota}
          className="flex gap-2 rounded-md bg-demo px-2.5 py-2 text-[11px] leading-4 text-demo-foreground"
        >
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>{nota}</span>
        </li>
      ))}
    </ul>
  );
}
