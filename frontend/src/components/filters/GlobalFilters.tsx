import { useId, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { ErrorState, LoadingState } from "@/components/data/DataState";
import { Skeleton } from "@/components/ui/skeleton";
import { municipiosQueryOptions } from "@/lib/api/queries";
import {
  categoriaSchema,
  organizacaoSchema,
  regiaoSchema,
  type DimensaoOferta,
  type Metadados,
  type Rede,
} from "@/lib/api/schemas";

import { SegmentedRadio } from "./SegmentedRadio";
import {
  alternarDimensao,
  contarFiltrosAtivos,
  dimensoesDaModalidade,
  dimensoesSelecionadas,
  FILTROS_LIMPOS,
  modalidadesDisponiveis,
  modalidadeSelecionada,
  MODALIDADE_PERSONALIZADA,
  MODALIDADE_TODAS,
  type FiltrosGlobais,
} from "./search";

type OpcaoRede = Rede | "todas";

const OPCOES_REDE: ReadonlyArray<{ valor: OpcaoRede; rotulo: string }> = [
  { valor: "todas", rotulo: "Todas" },
  { valor: "publica", rotulo: "Pública" },
  { valor: "privada", rotulo: "Privada" },
];

/** Estado das opções de filtro (`/api/v1/metadados`). */
export type FiltrosDisponiveis =
  | { tipo: "carregando" }
  | { tipo: "erro"; erro: unknown; onRetry: () => void }
  | { tipo: "sucesso"; metadados: Metadados };

type GlobalFiltersProps = {
  filtros: FiltrosGlobais;
  /** Recebe só o que mudou; quem chama grava na URL. */
  onChange: (alteracao: Partial<FiltrosGlobais>) => void;
  disponiveis: FiltrosDisponiveis;
};

const ROTULO =
  "mb-1.5 block text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground";
const SELECT =
  "h-9 w-full min-w-0 rounded-md border border-border bg-background px-3 text-xs font-medium text-foreground disabled:cursor-not-allowed disabled:opacity-60";

/**
 * Filtros globais. Principais: território (Região → UF → Município), Rede e Modalidade.
 * "Mais filtros": categoria administrativa, organização acadêmica e as dimensões de oferta
 * detalhadas. O ano não é filtro — a base tem só 2024. Todas as opções vêm da API.
 */
export function GlobalFilters({ filtros, onChange, disponiveis }: GlobalFiltersProps) {
  if (disponiveis.tipo === "carregando") {
    return (
      <LoadingState label="Carregando os filtros…">
        <Skeleton className="h-28 w-full" />
      </LoadingState>
    );
  }
  if (disponiveis.tipo === "erro") {
    return <ErrorState error={disponiveis.erro} onRetry={disponiveis.onRetry} />;
  }
  return <Filtros filtros={filtros} onChange={onChange} metadados={disponiveis.metadados} />;
}

function Filtros({
  filtros,
  onChange,
  metadados,
}: Omit<GlobalFiltersProps, "disponiveis"> & { metadados: Metadados }) {
  const { total, avancados } = contarFiltrosAtivos(filtros);
  // Abre sozinho quando a URL já chega com um filtro avançado ativo.
  const [maisFiltrosAberto, setMaisFiltrosAberto] = useState(avancados > 0);
  const dimensoes = metadados.dimensoes_oferta;
  const modalidade = modalidadeSelecionada(filtros, dimensoes);
  const opcoesModalidade = [
    { valor: MODALIDADE_TODAS, rotulo: "Todas" },
    // Rótulos literais de tp_modalidade_ensino.
    ...modalidadesDisponiveis(dimensoes).map((m) => ({ valor: m, rotulo: m })),
    // Só aparece quando as dimensões detalhadas não coincidem com uma modalidade.
    ...(modalidade === MODALIDADE_PERSONALIZADA
      ? [{ valor: MODALIDADE_PERSONALIZADA, rotulo: "Personalizada" }]
      : []),
  ];
  const categorias = metadados.categorias.filter((c) => !filtros.rede || c.rede === filtros.rede);

  return (
    <form
      aria-label="Filtros globais"
      onSubmit={(event) => event.preventDefault()}
      className="rounded-lg border border-border bg-card p-4 shadow-hairline sm:p-5"
    >
      <div className="grid gap-x-6 gap-y-5 lg:grid-cols-[auto_minmax(0,1fr)]">
        <div>
          <p className={ROTULO}>Ano de referência</p>
          <p className="py-1.5 text-sm font-semibold text-foreground">
            {metadados.ano_censo}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              único ano disponível
            </span>
          </p>
        </div>

        <Territorio filtros={filtros} onChange={onChange} metadados={metadados} />
      </div>

      <div className="mt-5 flex flex-wrap items-end gap-x-8 gap-y-5">
        <SegmentedRadio<OpcaoRede>
          legenda="Rede"
          opcoes={OPCOES_REDE}
          valor={filtros.rede ?? "todas"}
          onChange={(valor) => {
            const rede = valor === "todas" ? undefined : valor;
            // A categoria administrativa pertence a uma única rede: trocá-la invalida a escolha.
            const categoria = metadados.categorias.find((c) => c.slug === filtros.categoria);
            const incoerente = rede !== undefined && categoria && categoria.rede !== rede;
            onChange(incoerente ? { rede, categoria: undefined } : { rede });
          }}
        />
        <SegmentedRadio<string>
          legenda="Modalidade"
          opcoes={opcoesModalidade}
          valor={modalidade}
          onChange={(valor) => {
            if (valor === MODALIDADE_PERSONALIZADA) return;
            onChange({ dimensao: dimensoesDaModalidade(valor, dimensoes) });
          }}
        />
        {total > 0 && (
          <button
            type="button"
            onClick={() => onChange(FILTROS_LIMPOS)}
            className="h-9 rounded-md border border-border bg-background px-3 text-xs font-semibold text-foreground transition-colors hover:bg-muted"
          >
            Limpar filtros ({total})
          </button>
        )}
      </div>

      <details
        className="mt-5 border-t border-border pt-4"
        open={maisFiltrosAberto}
        onToggle={(event) => setMaisFiltrosAberto(event.currentTarget.open)}
      >
        <summary className="cursor-pointer rounded text-xs font-semibold text-foreground">
          Mais filtros
          {avancados > 0 ? ` (${avancados} ${avancados === 1 ? "ativo" : "ativos"})` : ""}
        </summary>
        <div className="mt-4 grid gap-x-6 gap-y-5 lg:grid-cols-2">
          <Campo rotulo="Categoria administrativa">
            {(id) => (
              <select
                id={id}
                className={SELECT}
                value={filtros.categoria ?? ""}
                onChange={(event) =>
                  onChange({
                    categoria: categoriaSchema
                      .optional()
                      .catch(undefined)
                      .parse(event.target.value),
                  })
                }
              >
                <option value="">Todas</option>
                {categorias.map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.rotulo}
                  </option>
                ))}
              </select>
            )}
          </Campo>
          <Campo rotulo="Organização acadêmica">
            {(id) => (
              <select
                id={id}
                className={SELECT}
                value={filtros.organizacao ?? ""}
                onChange={(event) =>
                  onChange({
                    organizacao: organizacaoSchema
                      .optional()
                      .catch(undefined)
                      .parse(event.target.value),
                  })
                }
              >
                <option value="">Todas</option>
                {metadados.organizacoes.map((o) => (
                  <option key={o.slug} value={o.slug}>
                    {o.rotulo}
                  </option>
                ))}
              </select>
            )}
          </Campo>
          <fieldset className="min-w-0 lg:col-span-2">
            <legend className={ROTULO}>Dimensão de oferta (detalhe da modalidade)</legend>
            <DimensoesCheckboxes filtros={filtros} dimensoes={dimensoes} onChange={onChange} />
          </fieldset>
        </div>
      </details>
    </form>
  );
}

function Territorio({
  filtros,
  onChange,
  metadados,
}: Omit<GlobalFiltersProps, "disponiveis"> & { metadados: Metadados }) {
  const ufSelecionada = metadados.ufs.find((u) => u.sigla === filtros.uf);
  // A região exibida é a da UF, quando há UF: a URL pode trazer um par incoerente.
  const regiao = ufSelecionada?.regiao ?? filtros.regiao;
  const ufs = metadados.ufs
    .filter((u) => !regiao || u.regiao === regiao)
    .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  const municipios = useQuery(municipiosQueryOptions(ufSelecionada?.sigla));

  return (
    <fieldset className="min-w-0">
      <legend className="sr-only">Território</legend>
      <div className="grid gap-x-4 gap-y-4 sm:grid-cols-3">
        <Campo rotulo="Região">
          {(id) => (
            <select
              id={id}
              className={SELECT}
              value={regiao ?? ""}
              onChange={(event) =>
                onChange({
                  regiao: regiaoSchema.optional().catch(undefined).parse(event.target.value),
                  uf: undefined,
                  municipio: undefined,
                })
              }
            >
              <option value="">Brasil (todas)</option>
              {metadados.regioes.map((r) => (
                <option key={r.slug} value={r.slug}>
                  {r.nome}
                </option>
              ))}
            </select>
          )}
        </Campo>
        <Campo rotulo="UF">
          {(id) => (
            <select
              id={id}
              className={SELECT}
              value={ufSelecionada?.sigla ?? ""}
              onChange={(event) => {
                const escolhida = metadados.ufs.find((u) => u.sigla === event.target.value);
                onChange({
                  uf: escolhida?.sigla,
                  // Mantém a região coerente com a UF escolhida.
                  regiao: escolhida?.regiao ?? regiao,
                  municipio: undefined,
                });
              }}
            >
              <option value="">Todas</option>
              {ufs.map((u) => (
                <option key={u.sigla} value={u.sigla}>
                  {u.nome} ({u.sigla})
                </option>
              ))}
            </select>
          )}
        </Campo>
        <Campo rotulo="Município">
          {(id) => (
            <>
              <select
                id={id}
                className={SELECT}
                disabled={!ufSelecionada || !municipios.data}
                value={municipios.data && filtros.municipio ? String(filtros.municipio) : ""}
                onChange={(event) =>
                  onChange({
                    municipio: event.target.value ? Number(event.target.value) : undefined,
                  })
                }
              >
                <option value="">
                  {!ufSelecionada
                    ? "Escolha uma UF"
                    : municipios.isPending
                      ? "Carregando…"
                      : `Todos (${municipios.data?.municipios.length ?? 0} com registro)`}
                </option>
                {municipios.data?.municipios.map((m) => (
                  <option key={m.codigo} value={m.codigo}>
                    {m.nome}
                    {m.sede ? "" : " — sem sede de IES"}
                  </option>
                ))}
              </select>
              {municipios.isError && (
                <ErrorState
                  compact
                  className="mt-2"
                  error={municipios.error}
                  onRetry={() => void municipios.refetch()}
                />
              )}
            </>
          )}
        </Campo>
      </div>
      <p className="mt-2 text-[11px] leading-4 text-muted-foreground">
        A lista de municípios traz só os que aparecem no Censo, como sede de IES ou como local de
        oferta de curso (incluindo polos de EAD).
      </p>
    </fieldset>
  );
}

function Campo({ rotulo, children }: { rotulo: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="min-w-0">
      <label htmlFor={id} className={ROTULO}>
        {rotulo}
      </label>
      {children(id)}
    </div>
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
