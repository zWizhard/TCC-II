import { Focus } from "lucide-react";

import { Container } from "@/components/layout/Container";
import { Panel } from "@/components/layout/Panel";
import { SectionHeader } from "@/components/layout/Section";
import { MapVisual } from "@/components/map/MapVisual";
import { mapHighlights, mapModes } from "@/data/landing";

import { Mockup } from "./Mockup";

export function MapSection() {
  return (
    <section className="section-pad bg-background">
      <Container className="grid items-center gap-12 lg:grid-cols-[.72fr_1.28fr]">
        <div>
          <SectionHeader
            eyebrow="Inteligência territorial"
            title="Explore a educação superior pelo território"
          >
            Alterne entre camadas para investigar concentrações, localizar instituições e
            compreender diferenças municipais em múltiplas escalas.
          </SectionHeader>
          {/* Lista descritiva das camadas previstas — não são controles. */}
          <ul className="mt-8 space-y-2">
            {mapModes.map(({ icon: Icon, title, text }, i) => (
              <li
                key={title}
                className={`flex w-full items-center gap-4 rounded-md border p-4 text-left ${i === 0 ? "border-primary/20 bg-primary/5" : "border-transparent"}`}
              >
                <span
                  className={`grid size-9 shrink-0 place-items-center rounded ${i === 0 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}
                >
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                <span>
                  <strong className="block text-sm text-foreground">{title}</strong>
                  <span className="text-xs leading-5 text-muted-foreground">{text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="min-w-0">
          <Mockup description="Ilustração da camada territorial de concentração sobre o mapa do Brasil. Representação conceitual, sem dados estatísticos reais.">
            <Panel>
              <div className="flex items-center justify-between border-b border-border p-4">
                <div>
                  <p className="text-xs font-semibold">Camada territorial</p>
                  <p className="text-[10px] text-muted-foreground">Representação ilustrativa</p>
                </div>
                <span className="flex items-center gap-1.5 rounded-full bg-teal-soft px-3 py-1 text-[10px] font-semibold text-teal-dark">
                  <span className="size-1.5 rounded-full bg-teal" />
                  Concentração
                </span>
              </div>
              <MapVisual className="aspect-[1.35/1]" />
            </Panel>
          </Mockup>
          <div className="mt-4 flex flex-wrap gap-2">
            {mapHighlights.map((x) => (
              <span
                key={x}
                className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-[10px] font-medium text-muted-foreground"
              >
                <Focus className="size-3 text-teal" aria-hidden="true" />
                {x}
              </span>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}
