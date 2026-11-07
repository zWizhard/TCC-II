import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";

import { Comparacao } from "@/components/comparar/Comparacao";
import { validarCompararSearch, type CompararSearch } from "@/components/comparar/search";
import { DataState } from "@/components/data/DataState";
import { SourceNote } from "@/components/data/SourceNote";
import { AppShell } from "@/components/layout/AppShell";
import { Container } from "@/components/layout/Container";
import { SectionHeader } from "@/components/layout/Section";
import { Skeleton } from "@/components/ui/skeleton";
import { metadadosQueryOptions } from "@/lib/api/queries";

export const Route = createFileRoute("/comparar")({
  validateSearch: validarCompararSearch,
  head: () => ({
    meta: [
      { title: "Comparações — Observatório Inteligente da Educação Superior" },
      {
        name: "description",
        content:
          "Regiões, UFs ou municípios lado a lado no Censo da Educação Superior 2024: valores absolutos e valores relativos, com as mesmas definições, o mesmo ano e os mesmos filtros.",
      },
    ],
  }),
  component: Comparar,
});

function Comparar() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const metadados = useQuery(metadadosQueryOptions());

  // `replace`: montar a comparação não empilha uma entrada de histórico por unidade.
  const atualizar = (alteracao: Partial<CompararSearch>) =>
    void navigate({ search: (atual) => ({ ...atual, ...alteracao }), replace: true });

  return (
    <AppShell
      footer={
        metadados.data && (
          <footer className="bg-ai text-primary-foreground">
            <Container className="py-10">
              <SourceNote metadados={metadados.data} />
            </Container>
          </footer>
        )
      }
    >
      <Container className="py-10 lg:py-14">
        <SectionHeader as="h1" eyebrow="Comparações" title="Unidades lado a lado">
          Regiões, UFs ou municípios comparados pelos mesmos indicadores do Censo 2024. Os valores
          absolutos e os relativos ficam em blocos separados, porque respondem a perguntas
          diferentes: quanto há em cada unidade, e quanto há em relação ao seu tamanho.
        </SectionHeader>

        <div className="mt-8">
          <DataState
            query={metadados}
            loadingLabel="Carregando as opções de comparação…"
            loading={<Skeleton className="h-96 w-full" />}
          >
            {(meta) => <Comparacao metadados={meta} search={search} onChange={atualizar} />}
          </DataState>
        </div>

        <section aria-labelledby="titulo-leitura" className="mt-12">
          <SectionHeader
            as="h2"
            eyebrow="Como ler"
            title="O que torna as colunas comparáveis"
            titleId="titulo-leitura"
            titleClassName="text-2xl"
          />
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
            <li>
              <strong className="text-foreground">Mesmo nível.</strong> Região com região, UF com
              UF, município com município. Trocar de nível zera a seleção.
            </li>
            <li>
              <strong className="text-foreground">Sem classificação.</strong> As colunas ficam na
              ordem em que você escolheu as unidades. Entre as UFs, a ordem por matrículas e a ordem
              por matrículas por 100 mil habitantes quase não coincidem: São Paulo é a 1ª em
              matrículas e a 8ª na razão; o Distrito Federal, a 1ª na razão e a 12ª em matrículas.
            </li>
            <li>
              <strong className="text-foreground">Cada linha declara o seu recorte.</strong>{" "}
              Instituições e docentes são contados na sede da IES; cursos e matrículas, no local de
              oferta. A comparação é entre unidades, dentro de uma linha — linhas de recortes
              diferentes não se dividem uma pela outra.
            </li>
            <li>
              <strong className="text-foreground">Ausência não é zero.</strong> Um traço indica
              unidade sem registro para aquela linha ou razão com denominador zero.
            </li>
            <li>
              <strong className="text-foreground">Diferença não é explicação.</strong> A tabela
              descreve; não diz por que as unidades diferem. Várias proporções mudam muito com a
              rede — use o filtro para comparar a rede pública ou a privada isoladamente.
            </li>
            <li>
              <strong className="text-foreground">Um único ano.</strong> A base tem só 2024: não há
              comparação entre anos.
            </li>
          </ul>
        </section>
      </Container>
    </AppShell>
  );
}
