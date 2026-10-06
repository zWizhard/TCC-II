import type { ReactNode } from "react";
import { AlertTriangle, Inbox, RotateCw } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { descreverErro } from "./descrever-erro";
import { cn } from "@/lib/utils";

type LoadingStateProps = {
  /** Texto lido por leitores de tela enquanto o esqueleto é exibido. */
  label?: string;
  children?: ReactNode;
  className?: string;
};

export function LoadingState({
  label = "Carregando dados…",
  children,
  className,
}: LoadingStateProps) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className={className}>
      <span className="sr-only">{label}</span>
      {children ?? <Skeleton className="h-24 w-full" />}
    </div>
  );
}

type ErrorStateProps = {
  error: unknown;
  onRetry?: (() => void) | undefined;
  compact?: boolean;
  className?: string;
};

export function ErrorState({ error, onRetry, compact = false, className }: ErrorStateProps) {
  const { titulo, detalhe, codigo } = descreverErro(error);
  return (
    <div
      role="alert"
      className={cn(
        "rounded-md border border-destructive/30 bg-destructive/5 text-left",
        compact ? "p-3" : "p-4",
        className,
      )}
    >
      <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <AlertTriangle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
        {titulo}
      </p>
      <p className="mt-1.5 break-words text-xs leading-5 text-muted-foreground">{detalhe}</p>
      {codigo && <p className="mt-1 text-[11px] text-muted-foreground">Código: {codigo}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-muted"
        >
          <RotateCw className="size-3.5" aria-hidden="true" />
          Tentar novamente
        </button>
      )}
    </div>
  );
}

type EmptyStateProps = { children: ReactNode; className?: string };

export function EmptyState({ children, className }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        "flex items-start gap-2 rounded-md border border-dashed border-border bg-section/60 p-4 text-xs leading-5 text-muted-foreground",
        className,
      )}
    >
      <Inbox className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p>{children}</p>
    </div>
  );
}

/** Subconjunto do resultado de `useQuery` que o DataState precisa. */
export type ConsultaLike<T> = {
  data: T | undefined;
  error: unknown;
  isPending: boolean;
  isError: boolean;
  refetch: () => unknown;
};

type DataStateProps<T> = {
  query: ConsultaLike<T>;
  /** Esqueleto específico do bloco. */
  loading?: ReactNode;
  loadingLabel?: string;
  isEmpty?: (data: T) => boolean;
  empty?: ReactNode;
  children: (data: T) => ReactNode;
};

/**
 * Trata os quatro estados de um bloco com dados da API: carregando, erro, vazio e sucesso.
 * Nenhum bloco do painel renderiza dado sem passar por aqui (ou pelos estados acima).
 */
export function DataState<T>({
  query,
  loading,
  loadingLabel,
  isEmpty,
  empty = "Nenhum registro para os filtros selecionados.",
  children,
}: DataStateProps<T>) {
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (query.isPending || query.data === undefined) {
    return (
      <LoadingState {...(loadingLabel ? { label: loadingLabel } : {})}>{loading}</LoadingState>
    );
  }
  if (isEmpty?.(query.data)) {
    return <EmptyState>{empty}</EmptyState>;
  }
  return <>{children(query.data)}</>;
}
