import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";

export function FinalCTA() {
  return (
    <section className="px-5 pb-24 lg:px-8">
      <div className="mx-auto max-w-7xl overflow-hidden rounded-lg bg-primary px-6 py-14 text-primary-foreground sm:px-10 lg:flex lg:items-center lg:justify-between lg:px-14">
        <div>
          <h2 className="max-w-2xl font-display text-3xl font-semibold leading-tight sm:text-4xl">
            Explore a educação superior por meio dos dados.
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-primary-foreground/65">
            Descubra padrões, compare territórios e transforme grandes bases de dados em
            conhecimento.
          </p>
        </div>
        <div className="mt-8 flex shrink-0 flex-col gap-3 sm:flex-row lg:ml-10 lg:mt-0">
          <Link
            to="/painel"
            className="inline-flex items-center justify-center gap-2 rounded-md bg-primary-foreground px-5 py-3 text-sm font-semibold text-primary"
          >
            Explorar plataforma <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
          <a
            href="#metodologia"
            className="inline-flex items-center justify-center rounded-md border border-primary-foreground/20 px-5 py-3 text-sm font-semibold text-primary-foreground"
          >
            Conhecer metodologia
          </a>
        </div>
      </div>
    </section>
  );
}
