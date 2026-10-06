import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { formatarCompacto, formatarInteiro } from "@/lib/format";

export type RankingItem = { chave: string; rotulo: string; valor: number };

type RankingBarChartProps = {
  itens: readonly RankingItem[];
  /** Unidade do valor (ex.: "matrículas"), usada na dica e na legenda acessível. */
  unidade: string;
  /** Descrição textual do gráfico. Os mesmos dados devem estar em uma tabela próxima. */
  descricao: string;
};

const ALTURA_BARRA = 26;
const ALTURA_EIXO = 44;

/**
 * Barras horizontais, uma por unidade territorial, na ordem recebida.
 * Só desenha os valores devolvidos pela API — não calcula participação nem razão.
 */
export function RankingBarChart({ itens, unidade, descricao }: RankingBarChartProps) {
  const config = { valor: { label: unidade, color: "var(--primary)" } } satisfies ChartConfig;
  const larguraRotulo = Math.min(
    150,
    Math.max(48, ...itens.map((item) => item.rotulo.length * 6.5 + 12)),
  );

  return (
    <div role="img" aria-label={descricao}>
      <ChartContainer
        config={config}
        className="aspect-auto w-full"
        style={{ height: itens.length * ALTURA_BARRA + ALTURA_EIXO }}
        aria-hidden="true"
      >
        <BarChart
          data={[...itens]}
          layout="vertical"
          margin={{ top: 4, right: 16, bottom: 0, left: 0 }}
          barCategoryGap={5}
          accessibilityLayer={false}
        >
          <CartesianGrid horizontal={false} />
          <XAxis
            type="number"
            tickLine={false}
            axisLine={false}
            tickFormatter={(valor: number) => formatarCompacto(valor)}
          />
          <YAxis
            type="category"
            dataKey="rotulo"
            width={larguraRotulo}
            tickLine={false}
            axisLine={false}
            interval={0}
          />
          <ChartTooltip
            cursor={{ fill: "var(--muted)" }}
            content={
              <ChartTooltipContent
                formatter={(valor) => (
                  <span className="font-medium tabular-nums text-foreground">
                    {formatarInteiro(Number(valor))} {unidade}
                  </span>
                )}
              />
            }
          />
          <Bar
            dataKey="valor"
            fill="var(--color-valor)"
            radius={[0, 3, 3, 0]}
            isAnimationActive={false}
          />
        </BarChart>
      </ChartContainer>
    </div>
  );
}
