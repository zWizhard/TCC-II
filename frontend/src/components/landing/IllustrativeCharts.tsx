/**
 * Gráficos ILUSTRATIVOS da landing: formas sem rótulo e sem valor, apenas para sugerir o tipo
 * de visualização. Não representam dado do Censo. Os gráficos reais ficam em components/data.
 */

const COLUMN_HEIGHTS = [42, 68, 53, 82, 63];
const ROW_WIDTHS = [84, 61, 47, 33, 26];

/** Barras verticais sem escala. */
export function IllustrativeColumns() {
  return (
    <div className="flex h-44 items-end justify-around gap-4 border-b border-border px-3 pt-6">
      {COLUMN_HEIGHTS.map((h, i) => (
        <div key={i} className="flex h-full flex-1 items-end">
          <span className="w-full rounded-t-sm bg-primary/12" style={{ height: `${h}%` }}>
            <span className="block h-1.5 w-full rounded-full bg-teal" />
          </span>
        </div>
      ))}
    </div>
  );
}

/** Barras horizontais sem escala nem categoria nomeada. */
export function IllustrativeRows() {
  return (
    <div className="flex h-44 flex-col justify-around border-l border-border pt-6">
      {ROW_WIDTHS.map((w, i) => (
        <div key={i} className="flex items-center gap-3 pl-3">
          <span className="h-2 w-12 shrink-0 rounded-full bg-muted" />
          <span className="h-4 rounded-r-sm bg-primary/12" style={{ width: `${w}%` }}>
            <span className="ml-auto block h-full w-1.5 rounded-full bg-teal" />
          </span>
        </div>
      ))}
    </div>
  );
}
