import { Link } from "@tanstack/react-router";
import { ArrowDownRight, ArrowRight, CheckCircle2 } from "lucide-react";

import { Container } from "@/components/layout/Container";
import { Panel } from "@/components/layout/Panel";
import { MapVisual } from "@/components/map/MapVisual";
import { heroHighlights } from "@/data/landing";

import { Mockup } from "./Mockup";

export function Hero() {
  return (
    <section
      id="inicio"
      className="relative overflow-hidden border-b border-border bg-background pt-28 lg:pt-32"
    >
      <Container className="grid items-center gap-14 pb-20 pt-10 lg:grid-cols-[.9fr_1.1fr] lg:pb-24 lg:pt-16">
        <div className="relative z-10">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-teal/20 bg-teal-soft px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[.13em] text-teal-dark">
            <span className="size-1.5 rounded-full bg-teal" />
            Data Science • Educação • IA
          </div>
          <h1 className="max-w-2xl font-display text-4xl font-semibold leading-[1.08] text-foreground sm:text-5xl lg:text-[3.65rem]">
            Dados que revelam a realidade da educação superior brasileira.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground lg:text-lg lg:leading-8">
            Explore instituições, cursos, matrículas e padrões territoriais por meio de dados do
            Censo da Educação Superior, visualizações interativas e Inteligência Artificial.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              to="/painel"
              className="inline-flex items-center justify-center gap-2 rounded-md bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition-all hover:-translate-y-0.5 hover:bg-primary/92"
            >
              Explorar os dados <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
            <a
              href="#sobre"
              className="inline-flex items-center justify-center gap-2 rounded-md border border-border bg-background px-5 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-muted"
            >
              Conhecer o projeto <ArrowDownRight className="size-4" aria-hidden="true" />
            </a>
          </div>
          <div className="mt-9 flex flex-wrap gap-x-5 gap-y-2">
            {heroHighlights.map((x) => (
              <span
                key={x}
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
              >
                <CheckCircle2 className="size-3.5 text-teal" aria-hidden="true" />
                {x}
              </span>
            ))}
          </div>
        </div>
        <div className="relative min-w-0">
          <div className="absolute -inset-6 -z-10 bg-grid-fade" />
          <Mockup description="Ilustração de um mapa analítico da distribuição territorial das Instituições de Ensino Superior no Brasil, com alternância entre concentração, IES e municípios. Imagem conceitual, sem dados estatísticos reais.">
            <Panel>
              <div className="flex flex-col gap-4 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[.14em] text-teal-dark">
                    Mapa analítico
                  </p>
                  <p className="mt-1 text-sm font-semibold text-foreground">
                    Distribuição territorial
                  </p>
                </div>
                <div className="flex gap-2 text-[11px] text-muted-foreground">
                  <span className="rounded border border-border px-2 py-1">Censo 2024</span>
                  <span className="rounded border border-border px-2 py-1">Brasil</span>
                  <span className="hidden rounded border border-border px-2 py-1 sm:block">
                    Todas as IES
                  </span>
                </div>
              </div>
              <div className="border-b border-border px-4 py-3">
                <div className="inline-flex rounded-md bg-muted p-1">
                  {["Heatmap", "IES", "Municípios"].map((x, i) => (
                    <button
                      key={x}
                      type="button"
                      tabIndex={-1}
                      className={`rounded px-3 py-1.5 text-[11px] font-medium ${i === 0 ? "bg-background text-foreground shadow-hairline" : "text-muted-foreground"}`}
                    >
                      {x}
                    </button>
                  ))}
                </div>
              </div>
              <MapVisual className="aspect-[1.22/1] sm:aspect-[1.35/1]" tooltip />
            </Panel>
          </Mockup>
          <p className="mt-3 text-right text-[10px] text-muted-foreground">
            Visualização conceitual • sem dados estatísticos reais
          </p>
        </div>
      </Container>
    </section>
  );
}
