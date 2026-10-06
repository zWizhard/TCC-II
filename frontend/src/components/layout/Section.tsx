import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type SectionHeaderProps = {
  eyebrow: string;
  title?: ReactNode;
  /** Texto de apoio abaixo do título. */
  children?: ReactNode;
  className?: string;
  titleClassName?: string;
  /** Nível do título; a landing usa h2, blocos internos do painel podem usar h3. */
  as?: "h1" | "h2" | "h3";
  titleId?: string;
};

/** Cabeçalho de seção: sobretítulo + título + texto, com as utilities de `styles.css`. */
export function SectionHeader({
  eyebrow,
  title,
  children,
  className,
  titleClassName,
  as: Title = "h2",
  titleId,
}: SectionHeaderProps) {
  return (
    <div className={className}>
      <p className="eyebrow">{eyebrow}</p>
      {title && (
        <Title id={titleId} className={cn("section-title", titleClassName)}>
          {title}
        </Title>
      )}
      {children && <p className="section-copy">{children}</p>}
    </div>
  );
}
