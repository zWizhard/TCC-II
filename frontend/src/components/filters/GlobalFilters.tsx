import { ErrorState, LoadingState } from "@/components/data/DataState";
import { Skeleton } from "@/components/ui/skeleton";
import type { DimensaoOferta, Rede } from "@/lib/api/schemas";

import { SegmentedRadio } from "./SegmentedRadio";
import { alternarDimensao, dimensoesSelecionadas, type FiltrosGlobais } from "./search";

type OpcaoRede = Rede | "todas";

const OPCOES_REDE: ReadonlyArray<{ valor: OpcaoRede; rotulo: string }> = [
  { valor: "todas", rotulo: "Todas" },
  { valor: "publica", rotulo: "Pública" },
  { valor: "privada", rotulo: "Privada" },
];

/** Estado do catálogo de dimensões (`/api/v1/metadados`). */
export type DimensoesDisponiveis =
  | { tipo: "carregando" }
  | { tipo: "erro"; erro: unknown; onRetry: () => void }
  | { tipo: "sucesso"; dimensoes: readonly DimensaoOferta[]; anoCenso: string };

type GlobalFiltersProps = {
  filtros: FiltrosGlobais;
  /** Recebe só o que mudou; quem chama grava na URL. */
  onChange: (alteracao: Partial<FiltrosGlobais>) => void;
  disponiveis: DimensoesDisponiveis;
};

/**
 * Filtros globais: Rede e Dimensão de oferta. O ano não é filtro — a base tem só 2024.
 * Região/UF/Município entram com o mapa (a API só filtra por UF no nível municipal).
 */
export function GlobalFilters({ filtros, onChange, disponiveis }: GlobalFiltersProps) {
  return (
    <form
      aria-label="Filtros globais"
      onSubmit={(event) => event.preventDefault()}
      className="grid gap-x-8 gap-y-5 rounded-lg border border-border bg-card p-4 shadow-hairline sm:p-5 lg:grid-cols-[auto_auto_1fr]"
    >
      <div>
        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground">
          Ano de referência
        </p>
        <p className="py-1.5 text-sm font-semibold text-foreground">
          {disponiveis.tipo === "sucesso" ? disponiveis.anoCenso : "2024"}
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            único ano disponível
          </span>
        </p>
      </div>

      <SegmentedRadio<OpcaoRede>
        legenda="Rede"
        opcoes={OPCOES_REDE}
        valor={filtros.rede ?? "todas"}
        onChange={(valor) => onChange({ rede: valor === "todas" ? undefined : valor })}
      />

      <fieldset className="min-w-0">
        <legend className="mb-1.5 text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground">
          Dimensão de oferta
        </legend>
        {disponiveis.tipo === "carregando" && (
          <LoadingState label="Carregando dimensões de oferta…">
            <Skeleton className="h-16 w-full" />
          </LoadingState>
        )}
        {disponiveis.tipo === "erro" && (
          <ErrorState compact error={disponiveis.erro} onRetry={disponiveis.onRetry} />
        )}
        {disponiveis.tipo === "sucesso" && (
          <DimensoesCheckboxes
            filtros={filtros}
            dimensoes={disponiveis.dimensoes}
            onChange={onChange}
          />
        )}
      </fieldset>
    </form>
  );
}

function DimensoesCheckboxes({
  filtros,
  dimensoes,
  onChange,
}: {
  filtros: FiltrosGlobais;
  dimensoes: readonly DimensaoOferta[];
  onChange: (alteracao: Partial<FiltrosGlobais>) => void;
}) {
  const slugs = dimensoes.map((d) => d.slug);
  const selecionadas = new Set(dimensoesSelecionadas(filtros, slugs));
  return (
    <>
      <ul className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
        {dimensoes.map((dimensao) => (
          <li key={dimensao.slug}>
            <label className="flex cursor-pointer items-start gap-2 text-xs leading-5 text-foreground">
              <input
                type="checkbox"
                className="mt-1 size-3.5 shrink-0 accent-primary"
                checked={selecionadas.has(dimensao.slug)}
                onChange={() =>
                  onChange({ dimensao: alternarDimensao(filtros, slugs, dimensao.slug) })
                }
              />
              <span>
                {/* Rótulo literal de tp_dimensao no Censo, sem agrupar nem renomear. */}
                {dimensao.rotulo}
                {!dimensao.territorializavel && (
                  <span className="block text-[11px] leading-4 text-muted-foreground">
                    Sem território: só entra nos totais do Brasil.
                  </span>
                )}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
        Vale apenas para os indicadores que exigem dimensão de oferta; nos demais, o cartão informa
        que o filtro não se aplica.
      </p>
    </>
  );
}
