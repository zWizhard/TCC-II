import { BarChart3, ChevronDown, SlidersHorizontal } from "lucide-react";

import { Container } from "@/components/layout/Container";
import { Panel, PanelBlock } from "@/components/layout/Panel";
import { MapVisual } from "@/components/map/MapVisual";
import { dashboardFilters, dashboardKpis, dashboardTabs } from "@/data/landing";

import { IllustrativeColumns, IllustrativeRows } from "./IllustrativeCharts";
import { Mockup } from "./Mockup";

function FilterLabel({ name, value }: { name: string; value: string }) {
  return (
    <span className="min-w-0">
      <small className="block text-[9px] font-semibold uppercase tracking-[.1em] text-muted-foreground">
        {name}
      </small>
      <span className="block truncate text-xs font-medium text-foreground">{value}</span>
    </span>
  );
}

const filterBoxClass =
  "flex min-w-0 items-center justify-between gap-3 rounded-md border border-border bg-background px-3 py-2 text-left";

/** Seção "Prévia da plataforma": painel demonstrativo, sem dados e sem interação. */
export function DashboardPreview() {
  return (
    <section id="plataforma" className="section-pad bg-section">
      <Container>
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="eyebrow">Prévia da plataforma</p>
            <h2 className="section-title max-w-3xl">Explore os dados de diferentes perspectivas</h2>
          </div>
          <p className="max-w-sm text-sm leading-6 text-muted-foreground">
            Uma visão integrada para navegar entre indicadores, territórios e recortes acadêmicos.
          </p>
        </div>
        <Mockup
          className="mt-12"
          description="Ilustração do painel do Observatório em ambiente demonstrativo: abas de navegação, ano de referência 2024, filtros de região, UF e município, cartões de indicadores e três visualizações (barras por região, barras por categoria administrativa e mapa). Não contém dados reais."
        >
          <Panel>
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="grid size-7 place-items-center rounded bg-primary text-primary-foreground">
                  <BarChart3 className="size-3.5" />
                </span>
                <span className="text-xs font-semibold">Observatório</span>
              </div>
              <span className="rounded bg-demo px-2 py-1 text-[9px] font-bold uppercase tracking-[.12em] text-demo-foreground">
                Ambiente demonstrativo
              </span>
            </div>
            <div className="scrollbar-none overflow-x-auto border-b border-border">
              <div className="flex min-w-max px-3">
                {dashboardTabs.map((tab, i) => (
                  <button
                    key={tab}
                    type="button"
                    tabIndex={-1}
                    className={`relative px-4 py-3 text-[11px] font-medium ${i === 0 ? "text-primary" : "text-muted-foreground"}`}
                  >
                    {tab}
                    {i === 0 && <span className="absolute inset-x-3 bottom-0 h-0.5 bg-primary" />}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid gap-3 border-b border-border bg-section/60 p-4 sm:grid-cols-2 lg:grid-cols-[repeat(4,1fr)_auto]">
              {/* 2024 é o único ano da base: informação fixa, não um filtro. */}
              <div className={filterBoxClass}>
                <FilterLabel name="Ano de referência" value="2024" />
              </div>
              {dashboardFilters.map(([name, value]) => (
                <button key={name} type="button" tabIndex={-1} className={filterBoxClass}>
                  <FilterLabel name={name} value={value} />
                  <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
                </button>
              ))}
              <button
                type="button"
                tabIndex={-1}
                className="inline-flex items-center justify-center gap-2 rounded-md border border-border bg-background px-4 py-2 text-xs font-semibold text-foreground"
              >
                <SlidersHorizontal className="size-3.5" />
                Mais filtros
              </button>
            </div>
            <div className="p-4 sm:p-6">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {dashboardKpis.map((k) => (
                  <div key={k} className="rounded-md border border-border p-4">
                    <p className="text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground">
                      {k}
                    </p>
                    <div className="mt-3 h-7 w-20 animate-pulse rounded bg-muted" />
                    <p className="mt-2 text-[10px] text-muted-foreground">
                      Dados carregados dinamicamente
                    </p>
                  </div>
                ))}
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-[1.25fr_.8fr_.9fr]">
                <PanelBlock title="Matrículas por região" subtitle="Estrutura demonstrativa">
                  <IllustrativeRows />
                </PanelBlock>
                <PanelBlock title="Categoria administrativa" subtitle="Estrutura demonstrativa">
                  <IllustrativeColumns />
                </PanelBlock>
                <PanelBlock
                  title="Distribuição territorial"
                  subtitle="Visualização conceitual"
                  flush
                >
                  <MapVisual compact className="h-48" />
                </PanelBlock>
              </div>
            </div>
          </Panel>
        </Mockup>
      </Container>
    </section>
  );
}
