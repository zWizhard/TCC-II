import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";

import { Brand } from "./Brand";
import { Container } from "./Container";

const MAIN_ID = "conteudo";

const navLinkClass =
  "rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground data-[status=active]:bg-muted data-[status=active]:text-foreground";

type AppShellProps = {
  children: ReactNode;
  /** Rodapé da área de dados (fonte, extração, avisos). */
  footer?: ReactNode;
};

/** Moldura da área de dados (`/painel`): link de pular, marca, navegação e ano de referência. */
export function AppShell({ children, footer }: AppShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <a
        href={`#${MAIN_ID}`}
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary-foreground"
      >
        Pular para o conteúdo
      </a>
      <header className="border-b border-border/70 bg-background shadow-hairline">
        <Container className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-4">
          <Brand />
          <nav className="flex items-center gap-1" aria-label="Navegação principal">
            <Link to="/" className={navLinkClass} activeOptions={{ exact: true }}>
              Início
            </Link>
            <Link to="/painel" className={navLinkClass}>
              Visão Geral
            </Link>
          </nav>
          <p className="inline-flex items-center gap-2 rounded-full border border-teal/20 bg-teal-soft px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[.13em] text-teal-dark">
            <span className="size-1.5 rounded-full bg-teal" aria-hidden="true" />
            Censo da Educação Superior 2024
          </p>
        </Container>
      </header>
      <main id={MAIN_ID} tabIndex={-1} className="flex-1 outline-none">
        {children}
      </main>
      {footer}
    </div>
  );
}
