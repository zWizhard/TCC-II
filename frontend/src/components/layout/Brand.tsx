import { Link } from "@tanstack/react-router";
import { BarChart3 } from "lucide-react";

type BrandProps = {
  inverse?: boolean;
  /** Âncora na própria página (landing). Sem ela, a marca leva à rota inicial. */
  href?: string;
};

const ARIA_LABEL = "Observatório Inteligente da Educação Superior — início";

export function Brand({ inverse = false, href }: BrandProps) {
  const className = `group inline-flex items-center gap-3 ${inverse ? "text-primary-foreground" : "text-foreground"}`;
  const content = (
    <>
      <span
        className={`grid size-10 place-items-center rounded-md border ${inverse ? "border-primary-foreground/20 bg-primary-foreground/10" : "border-primary/15 bg-primary/5"}`}
      >
        <BarChart3
          className={`size-5 ${inverse ? "text-primary-foreground" : "text-primary"}`}
          strokeWidth={1.8}
          aria-hidden="true"
        />
      </span>
      <span className="leading-tight">
        <strong className="block font-display text-[15px] font-semibold">
          Observatório Inteligente
        </strong>
        <span
          className={`block text-xs ${inverse ? "text-primary-foreground/65" : "text-muted-foreground"}`}
        >
          da Educação Superior
        </span>
      </span>
    </>
  );

  if (href) {
    return (
      <a href={href} className={className} aria-label={ARIA_LABEL}>
        {content}
      </a>
    );
  }
  return (
    <Link to="/" className={className} aria-label={ARIA_LABEL}>
      {content}
    </Link>
  );
}
