import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/** Largura e respiro lateral padrão de toda a aplicação. */
export function Container({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("mx-auto max-w-7xl px-5 lg:px-8", className)} {...props} />;
}
