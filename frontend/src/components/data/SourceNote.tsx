import type { Metadados } from "@/lib/api/schemas";
import { formatarDataExtracao } from "@/lib/format";

type SourceNoteProps = {
  metadados: Pick<Metadados, "fonte" | "ano_censo" | "extraido_em" | "aviso">;
};

/** Fonte, ano de referência, data de extração e aviso — tudo vindo de `/api/v1/metadados`. */
export function SourceNote({ metadados }: SourceNoteProps) {
  return (
    <div className="text-xs leading-5 text-primary-foreground/70">
      <dl className="grid gap-x-10 gap-y-3 sm:grid-cols-3">
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[.12em] text-teal-light">
            Fonte
          </dt>
          <dd className="mt-1">{metadados.fonte}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[.12em] text-teal-light">
            Ano de referência
          </dt>
          <dd className="mt-1">{metadados.ano_censo}</dd>
        </div>
        <div>
          <dt className="text-[10px] font-bold uppercase tracking-[.12em] text-teal-light">
            Extração da cópia local
          </dt>
          <dd className="mt-1">
            {metadados.extraido_em ? (
              <time dateTime={metadados.extraido_em}>
                {formatarDataExtracao(metadados.extraido_em)}
              </time>
            ) : (
              formatarDataExtracao(metadados.extraido_em)
            )}
          </dd>
        </div>
      </dl>
      <p className="mt-5 border-t border-primary-foreground/10 pt-4">{metadados.aviso}</p>
    </div>
  );
}
