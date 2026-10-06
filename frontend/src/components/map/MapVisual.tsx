import { useId } from "react";
import { Layers3, Minus, Plus } from "lucide-react";

/**
 * Mapa ILUSTRATIVO da landing: desenho estático, sem dado estatístico e sem interação.
 * É aqui (components/map) que o mapa real em MapLibre GL JS entrará, consumindo a API por
 * nível/recorte/filtros. Até lá, os controles são apenas decoração e ficam inertes.
 */
type MapVisualProps = { compact?: boolean; tooltip?: boolean; className?: string };

const points: Array<[number, number, number]> = [
  [39, 26, 7],
  [48, 41, 11],
  [62, 48, 8],
  [55, 62, 13],
  [41, 66, 8],
  [66, 69, 6],
  [47, 78, 5],
  [73, 56, 4],
  [31, 46, 4],
];

export function MapVisual({ compact = false, tooltip = false, className = "" }: MapVisualProps) {
  // Há mais de um mapa por página: ids de <defs> precisam ser únicos.
  const uid = useId().replace(/:/g, "");
  const blurId = `map-blur-${uid}`;
  const gridId = `map-grid-${uid}`;

  return (
    <div
      className={`relative overflow-hidden bg-map ${className}`}
      aria-label="Mapa ilustrativo do Brasil, sem dados estatísticos reais"
      role="img"
    >
      <svg viewBox="0 0 640 500" className="h-full w-full" aria-hidden="true">
        <defs>
          <filter id={blurId}>
            <feGaussianBlur stdDeviation="22" />
          </filter>
          <pattern id={gridId} width="28" height="28" patternUnits="userSpaceOnUse">
            <path
              d="M 28 0 L 0 0 0 28"
              fill="none"
              stroke="currentColor"
              strokeOpacity=".07"
              strokeWidth="1"
            />
          </pattern>
        </defs>
        <rect width="640" height="500" fill={`url(#${gridId})`} className="text-primary" />
        <path
          d="M274 49 350 62 397 43 430 79 491 100 516 149 492 190 510 232 465 264 457 322 414 352 401 408 361 459 322 420 302 367 267 337 237 288 206 267 203 222 166 193 178 151 220 127 231 82Z"
          className="fill-mapland stroke-mapline"
          strokeWidth="2"
        />
        <path
          d="M232 83 278 136 345 126 397 44M278 136 260 216 207 222M278 136 352 202 424 175 491 101M260 216 336 275 352 202M336 275 310 349 401 408M336 275 425 280 465 264M425 280 414 352M310 349 237 288"
          className="fill-none stroke-mapline"
          strokeWidth="1"
          strokeDasharray="4 5"
          opacity=".75"
        />
        {points.slice(0, compact ? 7 : 9).map(([x, y, r], i) => (
          <g key={i}>
            <circle
              cx={`${x}%`}
              cy={`${y}%`}
              r={r * 3}
              className="fill-teal/15"
              filter={`url(#${blurId})`}
            />
            <circle cx={`${x}%`} cy={`${y}%`} r={r} className="fill-teal/20" />
            <circle
              cx={`${x}%`}
              cy={`${y}%`}
              r="3"
              className="fill-teal stroke-background"
              strokeWidth="2"
            />
          </g>
        ))}
      </svg>
      <div className="absolute bottom-4 left-4 flex items-center gap-2 rounded-md border border-border/80 bg-background/90 px-3 py-2 text-[11px] text-muted-foreground shadow-soft backdrop-blur">
        <span className="size-2 rounded-full bg-teal" />
        Concentração ilustrativa
      </div>
      {!compact && (
        <div
          inert
          aria-hidden="true"
          className="absolute right-4 top-4 flex flex-col overflow-hidden rounded-md border border-border bg-background shadow-soft"
        >
          <button
            type="button"
            tabIndex={-1}
            className="grid size-9 place-items-center text-muted-foreground"
          >
            <Plus className="size-4" />
          </button>
          <button
            type="button"
            tabIndex={-1}
            className="grid size-9 place-items-center border-t border-border text-muted-foreground"
          >
            <Minus className="size-4" />
          </button>
          <button
            type="button"
            tabIndex={-1}
            className="grid size-9 place-items-center border-t border-border text-muted-foreground"
          >
            <Layers3 className="size-4" />
          </button>
        </div>
      )}
      {tooltip && (
        <div className="absolute left-[46%] top-[50%] w-48 rounded-md border border-border bg-background p-3 shadow-panel">
          <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[.12em] text-teal-dark">
            <span className="size-1.5 rounded-full bg-teal" />
            Ponto ilustrativo
          </div>
          <p className="text-xs font-semibold text-foreground">Instituição de Ensino Superior</p>
          <p className="mt-1 text-[11px] text-muted-foreground">Goiânia • GO</p>
        </div>
      )}
    </div>
  );
}
