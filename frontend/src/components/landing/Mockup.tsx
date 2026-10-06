import type { ReactNode } from "react";

type MockupProps = {
  /** Alternativa textual: o que a ilustração representa. */
  description: string;
  children: ReactNode;
  className?: string;
};

/**
 * Moldura para as ilustrações da landing (painéis demonstrativos, sem dados e sem ação).
 * O conteúdo fica `inert`: fora da ordem de tabulação e da árvore de acessibilidade, para que
 * os "botões" desenhados não sejam anunciados como controles que não fazem nada. Quem usa
 * tecnologia assistiva recebe a descrição textual no lugar.
 */
export function Mockup({ description, children, className }: MockupProps) {
  return (
    <figure className={className}>
      <figcaption className="sr-only">{description}</figcaption>
      <div inert aria-hidden="true">
        {children}
      </div>
    </figure>
  );
}
