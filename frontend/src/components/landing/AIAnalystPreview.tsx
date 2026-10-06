import {
  ArrowRight,
  Bot,
  Check,
  CornerDownLeft,
  Map as MapIcon,
  Sparkles,
  UserRound,
} from "lucide-react";

import { Container } from "@/components/layout/Container";
import { aiSuggestions } from "@/data/landing";

import { Mockup } from "./Mockup";

export function AIAnalystPreview() {
  return (
    <section className="section-pad bg-ai text-primary-foreground">
      <Container className="grid items-center gap-12 lg:grid-cols-[.8fr_1.2fr]">
        <div>
          <p className="mb-4 text-[11px] font-semibold uppercase tracking-[.16em] text-teal-light">
            Analista IA
          </p>
          <h2 className="font-display text-3xl font-semibold leading-tight sm:text-4xl">
            Pergunte aos dados em linguagem natural.
          </h2>
          <p className="mt-5 max-w-lg text-sm leading-7 text-primary-foreground/68 lg:text-base">
            O Analista IA permitirá transformar perguntas em consultas analíticas, auxiliando na
            exploração dos dados da Educação Superior.
          </p>
          <ul className="mt-8 space-y-2">
            {aiSuggestions.map((x) => (
              <li key={x} className="flex items-center gap-2 text-xs text-primary-foreground/65">
                <ArrowRight className="size-3.5 text-teal-light" aria-hidden="true" />
                {x}
              </li>
            ))}
          </ul>
        </div>
        <Mockup
          className="min-w-0"
          description="Ilustração de uma conversa com o Analista IA: uma pergunta em linguagem natural sobre municípios e a indicação de que a resposta será apresentada em ranking, tabela e mapa. Demonstração visual, sem integração ativa e sem dados reais."
        >
          <div className="overflow-hidden rounded-lg border border-primary-foreground/12 bg-ai-panel shadow-panel">
            <div className="flex items-center gap-3 border-b border-primary-foreground/10 p-4">
              <span className="grid size-8 place-items-center rounded bg-teal text-teal-foreground">
                <Sparkles className="size-4" />
              </span>
              <div>
                <p className="text-xs font-semibold">Analista IA</p>
                <p className="text-[10px] text-primary-foreground/50">
                  Demonstração visual • sem integração ativa
                </p>
              </div>
            </div>
            <div className="space-y-4 p-4 sm:p-6">
              <div className="ml-auto flex max-w-[85%] gap-3 rounded-md bg-primary-foreground/8 p-3">
                <UserRound className="mt-0.5 size-4 shrink-0 text-teal-light" />
                <p className="text-xs leading-5 text-primary-foreground/85">
                  Quais municípios possuem mais de 20 universidades?
                </p>
              </div>
              <div className="mr-auto max-w-[92%]">
                <div className="flex items-center gap-2 text-[10px] text-teal-light">
                  <Bot className="size-3.5" />
                  <span>Interpretando sua pergunta...</span>
                </div>
                <div className="mt-3 rounded-md border border-primary-foreground/10 bg-primary-foreground/5 p-4">
                  <p className="flex items-center gap-2 text-xs font-semibold">
                    <Check className="size-3.5 text-teal-light" />
                    Consulta concluída
                  </p>
                  <p className="mt-2 text-[11px] leading-5 text-primary-foreground/58">
                    Os municípios que atendem ao critério serão apresentados em ranking, tabela e
                    mapa.
                  </p>
                  <div className="mt-4 grid grid-cols-[1.1fr_.9fr] gap-3">
                    <div className="flex h-24 items-end gap-2 rounded border border-primary-foreground/8 p-3">
                      {[35, 64, 47, 78, 55].map((h, i) => (
                        <span
                          key={i}
                          className="flex-1 rounded-t-sm bg-teal/55"
                          style={{ height: `${h}%` }}
                        />
                      ))}
                    </div>
                    <div className="relative grid h-24 place-items-center overflow-hidden rounded border border-primary-foreground/8">
                      <MapIcon className="size-12 text-primary-foreground/12" />
                      <span className="absolute size-2 rounded-full bg-teal-light shadow-teal" />
                    </div>
                  </div>
                  <button
                    type="button"
                    tabIndex={-1}
                    className="mt-4 inline-flex items-center gap-2 text-[11px] font-semibold text-teal-light"
                  >
                    Visualizar consulta <ArrowRight className="size-3.5" />
                  </button>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-md border border-primary-foreground/12 px-3 py-2.5 text-[10px] text-primary-foreground/35">
                <span>Faça uma pergunta sobre os dados...</span>
                <CornerDownLeft className="size-3.5" />
              </div>
            </div>
          </div>
        </Mockup>
      </Container>
    </section>
  );
}
