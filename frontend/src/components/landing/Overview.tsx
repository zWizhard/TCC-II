import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { overviewCards } from "@/data/landing";

export function Overview() {
  return (
    <section className="section-pad bg-background">
      <Container>
        <SectionHeader
          className="max-w-3xl"
          eyebrow="O observatório"
          title="Um novo olhar sobre a educação superior"
        >
          Informações disponíveis em grandes bases públicas podem se transformar em conhecimento
          acessível por meio da integração, da análise estatística e da visualização.
        </SectionHeader>
        <div className="mt-12 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
          {overviewCards.map(({ icon: Icon, title, text }) => (
            <article key={title} className="bg-card p-6 transition-colors hover:bg-section">
              <span className="grid size-10 place-items-center rounded-md bg-teal-soft text-teal-dark">
                <Icon className="size-5" strokeWidth={1.7} aria-hidden="true" />
              </span>
              <h3 className="mt-5 font-display text-lg font-semibold text-foreground">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p>
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}
