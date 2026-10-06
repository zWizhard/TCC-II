import { ArrowRight } from "lucide-react";

import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { resources } from "@/data/landing";

export function Features() {
  return (
    <section id="recursos" className="section-pad bg-background">
      <Container>
        <SectionHeader
          className="max-w-2xl"
          eyebrow="Recursos"
          title="Uma plataforma, múltiplas camadas de análise"
        />
        <div className="mt-12 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {resources.map(({ icon: Icon, title, text }) => (
            <article key={title} className="group border-t border-border pt-5">
              <div className="flex items-start justify-between">
                <span className="grid size-9 place-items-center rounded bg-muted text-primary transition-colors group-hover:bg-teal-soft group-hover:text-teal-dark">
                  <Icon className="size-4.5" strokeWidth={1.7} aria-hidden="true" />
                </span>
                <ArrowRight
                  className="size-4 text-border transition-all group-hover:translate-x-1 group-hover:text-teal"
                  aria-hidden="true"
                />
              </div>
              <h3 className="mt-5 font-display text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p>
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}
