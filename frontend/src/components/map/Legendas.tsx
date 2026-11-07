import type { ReactNode } from "react";

import { Notes } from "@/components/data/Notes";
import type { Linha, RespostaCoropletico, RespostaIndicador } from "@/lib/api/schemas";
import { formatarDecimal, formatarInteiro, rotuloRecorte } from "@/lib/format";

import { RAMPA_CALOR } from "./estilo";
import {
  casasDasClasses,
  COR_HACHURA,
  COR_SEM_REGISTRO,
  coresDasClasses,
  faixaDaClasse,
  rotuloSemRegistro,
} from "./geo";

const TITULO = "text-[10px] font-semibold uppercase tracking-[.1em] text-muted-foreground";
const TEXTO = "text-xs leading-5 text-muted-foreground";

function Bloco({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div>
      <p className={TITULO}>{titulo}</p>
      <div className={`mt-1.5 ${TEXTO}`}>{children}</div>
    </div>
  );
}

function plural(quantidade: number, singular: string, pluralizado: string): string {
  return `${formatarInteiro(quantidade)} ${quantidade === 1 ? singular : pluralizado}`;
}

/**
 * Legenda do coroplético. Faixas, contagens e o valor do território são os que a API devolveu;
 * aqui só se escolhe a cor de cada classe e quantas casas decimais mostrar.
 */
export function LegendaCoropletico({
  dados,
  territorio,
}: {
  dados: RespostaCoropletico;
  territorio: string;
}) {
  const { indicador, geral } = dados;
  const cores = coresDasClasses(dados.classes);
  const casas = casasDasClasses(dados.classes);
  const unidade = dados.nivel === "uf" ? ["UF", "UFs"] : ["unidade", "unidades"];
  const [singular = "unidade", pluralizado = "unidades"] = unidade;

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-semibold leading-5 text-foreground">{indicador.nome}</p>
        <p className={TEXTO}>
          {indicador.codigo} · em {indicador.unidade}
        </p>
      </div>

      <ul aria-label="Classes do mapa" className="space-y-1.5">
        {dados.classes.map((classe, i) => (
          <li key={classe.indice} className="flex items-start gap-2 text-xs leading-5">
            <span
              aria-hidden="true"
              className="mt-0.5 size-4 shrink-0 rounded-sm border border-foreground/20"
              style={{ backgroundColor: cores[i] }}
            />
            <span className="min-w-0 text-foreground">
              <span className="tabular-nums">
                {faixaDaClasse(classe, (valor) => formatarDecimal(valor, casas))}
              </span>
              <span className="text-muted-foreground">
                {" "}
                · {plural(classe.unidades, singular, pluralizado)}
              </span>
            </span>
          </li>
        ))}
        <li className="flex items-start gap-2 text-xs leading-5">
          <span
            aria-hidden="true"
            className="mt-0.5 size-4 shrink-0 rounded-sm border border-foreground/20"
            style={{
              backgroundColor: COR_SEM_REGISTRO,
              backgroundImage: `repeating-linear-gradient(45deg, ${COR_HACHURA} 0 1px, transparent 1px 5px)`,
            }}
          />
          <span className="min-w-0 text-foreground">
            {rotuloSemRegistro(dados.filtros)} (cinza hachurado)
            <span className="text-muted-foreground">
              {" "}
              · {plural(dados.sem_registro, singular, pluralizado)} — ausência de registro, não zero
            </span>
          </span>
        </li>
      </ul>

      <Bloco titulo="Como as cores são definidas">
        {dados.metodo_classes === "quantis"
          ? "Quantis: cada cor reúne número parecido de unidades; os limites mudam com os filtros."
          : `Método de classes: ${dados.metodo_classes}.`}{" "}
        As faixas mostram o menor e o maior valor observados em cada classe.
      </Bloco>

      <Bloco titulo={`Valor em ${territorio}`}>
        {geral.numerador === null || geral.valor === null ? (
          <p className="font-semibold text-foreground">Sem registro de oferta neste recorte</p>
        ) : (
          <p>
            <span className="font-display text-xl font-semibold tabular-nums text-foreground">
              {formatarDecimal(geral.valor, casas)}
            </span>{" "}
            {indicador.unidade}
          </p>
        )}
        <p>
          {dados.numerador_nome}:{" "}
          <span className="tabular-nums text-foreground">
            {geral.numerador === null ? "sem registro" : formatarInteiro(geral.numerador)}
          </span>
        </p>
        <p>
          {dados.denominador_nome}:{" "}
          <span className="tabular-nums text-foreground">{formatarInteiro(geral.denominador)}</span>
        </p>
      </Bloco>

      <Bloco titulo="Recorte e anos">
        <p>
          Recorte territorial: <strong>{rotuloRecorte(dados.recorte)}</strong> (onde o curso é
          ofertado, incluindo polos de EAD).
        </p>
        <p>
          Censo da Educação Superior {dados.ano_censo} · população estimada de {dados.ano_populacao}
          .
        </p>
        <p>
          {plural(dados.unidades, singular, pluralizado)} no território ·{" "}
          {formatarInteiro(dados.com_registro)} com registro.
        </p>
      </Bloco>

      <Notes notas={dados.notas} />
      <Notes notas={indicador.limitacoes} />
    </div>
  );
}

/** Legenda do modo de pontos: o que é um ponto, o que é um agrupamento e o que não aparece. */
export function LegendaPontos({ dados, maximo }: { dados: RespostaIndicador; maximo: number }) {
  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-semibold leading-5 text-foreground">Municípios de sede de IES</p>
        <p className={TEXTO}>
          {dados.indicador.codigo} · {dados.indicador.nome} · Recorte territorial:{" "}
          <strong>{rotuloRecorte(dados.recorte)}</strong>
        </p>
      </div>

      <ul aria-label="Símbolos do mapa" className="space-y-2.5">
        <li className="flex items-start gap-2.5 text-xs leading-5">
          <span
            aria-hidden="true"
            className="mt-0.5 size-4 shrink-0 rounded-full border border-white bg-[#0f766e]"
          />
          <span className="text-foreground">
            Cada ponto é um <strong>município de sede</strong>, não uma instituição. A área do
            círculo é proporcional ao número de IES com sede nele (de 1 a {formatarInteiro(maximo)}{" "}
            neste recorte).
          </span>
        </li>
        <li className="flex items-start gap-2.5 text-xs leading-5">
          <span
            aria-hidden="true"
            className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border border-white bg-[#134e4a] text-[9px] font-semibold text-white"
          >
            n
          </span>
          <span className="text-foreground">
            Círculo escuro com número: municípios de sede próximos, agrupados. O número é a{" "}
            <strong>soma das IES</strong> desses municípios, não a quantidade de municípios. Clique
            para aproximar.
          </span>
        </li>
      </ul>

      <Bloco titulo="Neste recorte">
        <p>
          <span className="font-display text-xl font-semibold tabular-nums text-foreground">
            {formatarInteiro(dados.total)}
          </span>{" "}
          {dados.indicador.unidade} em{" "}
          <span className="tabular-nums text-foreground">{formatarInteiro(dados.unidades)}</span>{" "}
          municípios de sede.
        </p>
      </Bloco>

      <Bloco titulo="O que a posição significa">
        A posição é a coordenada de referência do município, não o endereço da instituição: a base
        não tem coordenada por IES. Todas as IES de um município ficam no mesmo ponto. Campi fora da
        sede e polos de EAD não aparecem neste modo.
      </Bloco>

      <Notes notas={dados.notas} />
      <Notes notas={dados.indicador.limitacoes} />
    </div>
  );
}

/** Legenda do mapa de calor: define a intensidade e diz o que ela não é. */
export function LegendaCalor({
  dados,
  maior,
}: {
  dados: RespostaIndicador;
  /** Município de maior valor na resposta: a referência (peso 1) do mapa. */
  maior: Linha | undefined;
}) {
  const { indicador } = dados;
  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-semibold leading-5 text-foreground">
          Concentração de {indicador.nome.toLowerCase()}
        </p>
        <p className={TEXTO}>
          {indicador.codigo} · Recorte territorial: <strong>{rotuloRecorte(dados.recorte)}</strong>
        </p>
      </div>

      <div>
        <div
          aria-hidden="true"
          className="h-3 w-full rounded-sm border border-foreground/20"
          style={{
            backgroundImage: `linear-gradient(to right, rgba(254,230,206,0), ${RAMPA_CALOR.join(", ")})`,
          }}
        />
        <p className="mt-1 flex justify-between text-[11px] text-muted-foreground">
          <span>menor intensidade</span>
          <span>maior intensidade</span>
        </p>
      </div>

      <Bloco titulo="O que a intensidade mostra">
        A soma de {indicador.unidade} dos municípios próximos, com peso decrescente pela distância.
        É densidade relativa dentro deste recorte: soma peso e proximidade e muda com o zoom, por
        isso não tem unidade e não permite ler o número de um município.
      </Bloco>

      <Bloco titulo="Volume absoluto">
        O mapa mostra volume absoluto, não normalizado por população: acompanha onde há mais gente.
        Não é valor por habitante nem valor por área.
      </Bloco>

      <Bloco titulo="Referência do peso">
        {maior ? (
          <>
            O peso de cada município é o valor dele em relação ao maior da resposta atual:{" "}
            <strong className="text-foreground">
              {maior.nome}
              {maior.uf ? ` – ${maior.uf}` : ""}
            </strong>
            , com{" "}
            <span className="tabular-nums text-foreground">{formatarInteiro(maior.valor)}</span>{" "}
            {indicador.unidade}. Com outros filtros a referência muda: mapas com filtros diferentes
            não são comparáveis.
          </>
        ) : (
          "Sem município com valor neste recorte."
        )}
      </Bloco>

      <Bloco titulo="Posição">
        Cada município entra na sua coordenada de referência. Ao aproximar, os municípios aparecem
        como pontos: passe o cursor para ver o valor exato, ou consulte a tabela.
      </Bloco>

      <Notes notas={dados.notas} />
      <Notes notas={indicador.limitacoes} />
    </div>
  );
}
