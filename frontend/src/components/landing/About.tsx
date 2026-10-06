import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { aboutFields } from "@/data/landing";

export function About() {
  return (
    <section id="sobre" className="section-pad bg-background">
      <Container className="grid gap-12 lg:grid-cols-[1fr_.9fr]">
        <SectionHeader
          eyebrow="Sobre o projeto"
          title="Pesquisa aplicada à compreensão da educação brasileira"
        >
          Este projeto é desenvolvido como Trabalho de Conclusão de Curso na área de Data Science e
          investiga formas de integrar, visualizar e explorar dados da Educação Superior brasileira
          por meio de tecnologias modernas de análise de dados.
        </SectionHeader>
        <dl className="grid gap-px overflow-hidden rounded-lg border border-border bg-border sm:grid-cols-2">
          {aboutFields.map((x) => (
            <div key={x} className="bg-section p-5">
              <dt className="text-[10px] font-bold uppercase tracking-[.12em] text-muted-foreground">
                {x}
              </dt>
              <dd>
                <div className="mt-4 h-2 w-2/3 rounded-full bg-border" aria-hidden="true" />
                <p className="mt-3 text-[10px] text-muted-foreground">Informação a definir</p>
              </dd>
            </div>
          ))}
        </dl>
      </Container>
    </section>
  );
}
