import { useId, type ReactNode } from "react";

import { Panel } from "@/components/layout/Panel";
import { cn } from "@/lib/utils";

type ChartCardProps = {
  title: string;
  /** Linha de contexto sob o título (indicador, nível, recorte). */
  description?: ReactNode;
  /** Controles do bloco (seletores), alinhados à direita do título. */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

/** Moldura de um bloco de visualização do painel: título, contexto, controles e conteúdo. */
export function ChartCard({ title, description, actions, children, className }: ChartCardProps) {
  const tituloId = useId();
  return (
    <Panel className={cn("shadow-soft", className)}>
      <section aria-labelledby={tituloId}>
        <div className="flex flex-col gap-4 border-b border-border p-4 sm:p-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <h3 id={tituloId} className="font-display text-lg font-semibold text-foreground">
              {title}
            </h3>
            {description && (
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
            )}
          </div>
          {actions && <div className="flex flex-wrap items-end gap-3">{actions}</div>}
        </div>
        <div className="p-4 sm:p-5">{children}</div>
      </section>
    </Panel>
  );
}
