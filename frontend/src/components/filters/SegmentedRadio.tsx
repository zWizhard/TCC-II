import { useId } from "react";

import { cn } from "@/lib/utils";

type Opcao<V extends string> = { valor: V; rotulo: string };

type SegmentedRadioProps<V extends string> = {
  legenda: string;
  opcoes: ReadonlyArray<Opcao<V>>;
  valor: V;
  onChange: (valor: V) => void;
  className?: string;
};

/**
 * Escolha única em formato de controle segmentado. São `<input type="radio">` nativos:
 * setas alternam, Tab entra e sai do grupo, e o leitor de tela anuncia grupo e posição.
 */
export function SegmentedRadio<V extends string>({
  legenda,
  opcoes,
  valor,
  onChange,
  className,
}: SegmentedRadioProps<V>) {
  const nome = useId();
  return (
    <fieldset className={cn("min-w-0", className)}>
      <legend className="mb-1.5 text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground">
        {legenda}
      </legend>
      <div className="inline-flex flex-wrap rounded-md bg-muted p-1">
        {opcoes.map((opcao) => (
          <label
            key={opcao.valor}
            className="cursor-pointer rounded px-3 py-1.5 text-xs font-medium text-muted-foreground has-checked:bg-background has-checked:text-foreground has-checked:shadow-hairline has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring"
          >
            <input
              type="radio"
              className="sr-only"
              name={nome}
              value={opcao.valor}
              checked={opcao.valor === valor}
              onChange={() => onChange(opcao.valor)}
            />
            {opcao.rotulo}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
