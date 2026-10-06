import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { technology } from "@/data/landing";

export function Technology() {
  return (
    <section className="bg-background py-16">
      <Container>
        <SectionHeader eyebrow="Construído para explorar dados públicos" />
        <div className="mt-7 grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
          {technology.map(({ icon: Icon, label, text }) => (
            <div key={label} className="bg-card p-5">
              <Icon className="size-4.5 text-teal" aria-hidden="true" />
              <p className="mt-4 text-[10px] font-bold uppercase tracking-[.12em] text-muted-foreground">
                {label}
              </p>
              <p className="mt-1.5 text-sm font-medium leading-5 text-foreground">{text}</p>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
