import { ArrowRight } from "lucide-react";

import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { methodology } from "@/data/landing";

export function Methodology() {
  return (
    <section id="metodologia" className="section-pad border-y border-border bg-section">
      <Container>
        <SectionHeader
          className="max-w-3xl"
          eyebrow="Metodologia de pesquisa"
          title="Da base de dados ao conhecimento"
        >
          A plataforma integra diferentes dimensões do Censo da Educação Superior, preservando a
          granularidade e a rastreabilidade dos indicadores utilizados.
        </SectionHeader>
        <ol className="mt-14 grid gap-0 lg:grid-cols-6">
          {methodology.map((step, i) => (
            <li
              key={step}
              className="relative flex gap-4 border-l border-border pb-8 pl-5 lg:block lg:border-l-0 lg:border-t lg:pb-0 lg:pl-0 lg:pt-6"
            >
              <span className="absolute -left-1.5 top-0 size-3 rounded-full border-2 border-section bg-primary lg:-top-1.5 lg:left-0" />
              <span className="text-[10px] font-bold text-teal-dark" aria-hidden="true">
                0{i + 1}
              </span>
              <p className="max-w-[150px] text-sm font-semibold leading-5 text-foreground lg:mt-2">
                {step}
              </p>
              {i < methodology.length - 1 && (
                <ArrowRight
                  className="absolute right-4 top-[-8px] hidden size-4 bg-section text-border lg:block"
                  aria-hidden="true"
                />
              )}
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}
