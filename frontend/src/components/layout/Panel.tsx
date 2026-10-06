import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** "Card de painel": moldura elevada usada nos mockups da landing e nos blocos do painel. */
export function Panel({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card shadow-panel",
        className,
      )}
      {...props}
    />
  );
}

type PanelBlockProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Remove o padding do corpo (ex.: mapa que encosta nas bordas). */
  flush?: boolean;
  className?: string;
};

/** Bloco interno de um painel: título pequeno, subtítulo e conteúdo. */
export function PanelBlock({
  title,
  subtitle,
  children,
  flush = false,
  className,
}: PanelBlockProps) {
  const header = (
    <>
      <p className="text-xs font-semibold text-foreground">{title}</p>
      {subtitle && <p className="mt-1 text-[10px] text-muted-foreground">{subtitle}</p>}
    </>
  );
  if (flush) {
    return (
      <div className={cn("overflow-hidden rounded-md border border-border", className)}>
        <div className="p-4 pb-2">{header}</div>
        {children}
      </div>
    );
  }
  return (
    <div className={cn("rounded-md border border-border p-4", className)}>
      {header}
      {children}
    </div>
  );
}
