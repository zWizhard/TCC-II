import { Brand } from "./Brand";
import { Container } from "./Container";

/** Rodapé da landing. */
export function Footer() {
  return (
    <footer className="bg-ai text-primary-foreground">
      <Container className="py-12">
        <div className="flex flex-col justify-between gap-10 border-b border-primary-foreground/10 pb-10 md:flex-row">
          <div>
            <Brand inverse href="#inicio" />
            <p className="mt-5 max-w-sm text-xs leading-5 text-primary-foreground/50">
              Projeto acadêmico desenvolvido para fins de pesquisa e análise de dados.
            </p>
          </div>
          <nav
            className="flex flex-wrap gap-x-8 gap-y-3 text-xs text-primary-foreground/60"
            aria-label="Navegação do rodapé"
          >
            <a href="#sobre" className="hover:text-primary-foreground">
              Projeto
            </a>
            <a href="#metodologia" className="hover:text-primary-foreground">
              Metodologia
            </a>
            <a href="#plataforma" className="hover:text-primary-foreground">
              Dados
            </a>
            <a href="#sobre" className="hover:text-primary-foreground">
              Sobre
            </a>
          </nav>
        </div>
        <div className="flex flex-col justify-between gap-2 pt-6 text-[10px] text-primary-foreground/60 sm:flex-row">
          <p>Fonte dos dados: INEP — Censo da Educação Superior</p>
          <p>Referência visual • TCC-II • 2026</p>
        </div>
      </Container>
    </footer>
  );
}
