import { useId } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import type { Recorte } from "@/lib/api/schemas";
import { formatarInteiro, rotuloRecorte } from "@/lib/format";

import { EmptyState, ErrorState, LoadingState } from "./DataState";
import { Notes } from "./Notes";

export type KpiEstado =
  | { tipo: "carregando" }
  | { tipo: "erro"; erro: unknown; onRetry?: (() => void) | undefined }
  | { tipo: "vazio"; mensagem: string }
  | {
      tipo: "sucesso";
      valor: number;
      /** Parcela sem município identificado; no nível Brasil está incluída no valor. */
      valorSemTerritorio: number | null;
      /** Ressalvas da resposta, dependentes dos filtros. */
      notas: readonly string[];
    };

export type KpiCardProps = {
  nome: string;
  /** Código da ficha metodológica, ex.: IND-D-03. */
  codigo: string;
  unidade: string;
  /** Recorte territorial do indicador — sempre exibido (ADR-0004). */
  recorte: Recorte;
  /** Limitações fixas do indicador, vindas do catálogo. */
  limitacoes: readonly string[];
  /** Como os filtros globais se aplicam a este indicador (ex.: "não se aplica"). */
  contexto?: ReadonlyArray<{ rotulo: string; valor: string }>;
  estado: KpiEstado;
};

/** Cartão de um indicador agregado: valor, unidade, ficha, recorte e ressalvas. */
export function KpiCard({
  nome,
  codigo,
  unidade,
  recorte,
  limitacoes,
  contexto = [],
  estado,
}: KpiCardProps) {
  const tituloId = useId();

  return (
    <article
      aria-labelledby={tituloId}
      className="flex min-w-0 flex-col rounded-md border border-border bg-card p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-[.12em] text-teal-dark">
          {codigo}
        </span>
        <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
          <span className="sr-only">Recorte territorial: </span>
          {rotuloRecorte(recorte)}
        </span>
      </div>
      <h3 id={tituloId} className="mt-3 text-sm font-semibold leading-5 text-foreground">
        {nome}
      </h3>

      <div className="mt-3">
        {estado.tipo === "carregando" && (
          <LoadingState label={`Carregando ${nome}…`}>
            <Skeleton className="h-9 w-32" />
            <Skeleton className="mt-2 h-3 w-20" />
          </LoadingState>
        )}
        {estado.tipo === "erro" && (
          <ErrorState compact error={estado.erro} onRetry={estado.onRetry} />
        )}
        {estado.tipo === "vazio" && <EmptyState className="p-3">{estado.mensagem}</EmptyState>}
        {estado.tipo === "sucesso" && (
          <>
            <p className="break-words font-display text-3xl font-semibold leading-none tabular-nums text-foreground">
              {formatarInteiro(estado.valor)}
            </p>
            <p className="mt-1.5 text-xs text-muted-foreground">{unidade}</p>
            {estado.valorSemTerritorio !== null && estado.valorSemTerritorio > 0 && (
              <p className="mt-3 text-[11px] leading-4 text-muted-foreground">
                Inclui {formatarInteiro(estado.valorSemTerritorio)} sem município identificado.
              </p>
            )}
            <Notes notas={estado.notas} className="mt-3" />
          </>
        )}
      </div>

      {contexto.length > 0 && (
        <dl className="mt-4 space-y-1 border-t border-border pt-3 text-[11px] leading-4 text-muted-foreground">
          {contexto.map(({ rotulo, valor }) => (
            <div key={rotulo} className="flex flex-wrap gap-x-1">
              <dt className="font-semibold">{rotulo}:</dt>
              <dd>{valor}</dd>
            </div>
          ))}
        </dl>
      )}

      {limitacoes.length > 0 && (
        <details className="mt-3 text-[11px] leading-4 text-muted-foreground">
          <summary className="cursor-pointer rounded font-semibold text-foreground">
            Limitações ({limitacoes.length})
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {limitacoes.map((limitacao) => (
              <li key={limitacao}>{limitacao}</li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}
