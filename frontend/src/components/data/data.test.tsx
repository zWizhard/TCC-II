import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiContratoError, ApiError, ApiIndisponivelError } from "@/lib/api/client";
import { formatarCompacto, formatarDataExtracao, formatarInteiro } from "@/lib/format";
import erro422 from "@/test/fixtures/erro-422.json";
import iesBrasil from "@/test/fixtures/ies-brasil.json";

import { DataState, type ConsultaLike } from "./DataState";
import { KpiCard, type KpiEstado } from "./KpiCard";

afterEach(cleanup);

describe("format", () => {
  it("formata inteiros no padrão brasileiro", () => {
    expect(formatarInteiro(1234567)).toBe("1.234.567");
    expect(formatarInteiro(0)).toBe("0");
    expect(formatarCompacto(4500000)).toMatch(/^4,5\smi$/);
  });

  it("formata a data de extração sem deslocar o dia pelo fuso", () => {
    expect(formatarDataExtracao("2026-01-01T00:05:00")).toBe("01/01/2026 às 00:05");
    expect(formatarDataExtracao("2026-12-31")).toBe("31/12/2026");
    expect(formatarDataExtracao(null)).toBe("não informada");
    expect(formatarDataExtracao("ontem")).toBe("ontem");
  });
});

function renderKpi(estado: KpiEstado) {
  const { indicador } = iesBrasil;
  return render(
    <KpiCard
      nome={indicador.nome}
      codigo={indicador.codigo}
      unidade={indicador.unidade}
      recorte="sede"
      limitacoes={indicador.limitacoes}
      estado={estado}
    />,
  );
}

describe("KpiCard", () => {
  it("sempre declara a ficha, o recorte territorial e as limitações", () => {
    renderKpi({ tipo: "carregando" });
    const cartao = screen.getByRole("article", { name: iesBrasil.indicador.nome });
    expect(within(cartao).getByText(iesBrasil.indicador.codigo)).toBeInTheDocument();
    expect(within(cartao).getByText("Sede da IES")).toBeInTheDocument();
    for (const limitacao of iesBrasil.indicador.limitacoes) {
      expect(within(cartao).getByText(limitacao)).toBeInTheDocument();
    }
  });

  it("carregando: anuncia o estado e não mostra número", () => {
    renderKpi({ tipo: "carregando" });
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByText(formatarInteiro(iesBrasil.total))).not.toBeInTheDocument();
  });

  it("sucesso: mostra o valor formatado, a parcela sem território e as notas", () => {
    renderKpi({
      tipo: "sucesso",
      valor: iesBrasil.total,
      valorSemTerritorio: 41,
      notas: ["Nota A"],
    });
    expect(screen.getByText(formatarInteiro(iesBrasil.total))).toBeInTheDocument();
    expect(screen.getByText(/Inclui 41 sem município identificado/)).toBeInTheDocument();
    expect(screen.getByText("Nota A")).toBeInTheDocument();
  });

  it("vazio: mostra a mensagem em vez de zero", () => {
    renderKpi({ tipo: "vazio", mensagem: "Nenhum registro para os filtros selecionados." });
    expect(screen.getByRole("status")).toHaveTextContent("Nenhum registro");
  });

  it("erro da API: mostra a mensagem e o código do envelope e permite tentar de novo", () => {
    const onRetry = vi.fn();
    renderKpi({
      tipo: "erro",
      erro: new ApiError(422, erro422.erro.codigo, erro422.erro.mensagem),
      onRetry,
    });
    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent(erro422.erro.mensagem);
    expect(alerta).toHaveTextContent(erro422.erro.codigo);
    within(alerta).getByRole("button", { name: "Tentar novamente" }).click();
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

function consulta<T>(parcial: Partial<ConsultaLike<T>>): ConsultaLike<T> {
  return {
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    refetch: () => undefined,
    ...parcial,
  };
}

describe("DataState", () => {
  it("carregando → status; sucesso → conteúdo; vazio → mensagem", () => {
    const { rerender } = render(
      <DataState query={consulta<string[]>({ isPending: true })} isEmpty={(d) => d.length === 0}>
        {(dados) => <p>{dados.join(",")}</p>}
      </DataState>,
    );
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");

    rerender(
      <DataState query={consulta({ data: ["a", "b"] })} isEmpty={(d) => d.length === 0}>
        {(dados) => <p>{dados.join(",")}</p>}
      </DataState>,
    );
    expect(screen.getByText("a,b")).toBeInTheDocument();

    rerender(
      <DataState
        query={consulta<string[]>({ data: [] })}
        isEmpty={(d) => d.length === 0}
        empty="Sem linhas."
      >
        {(dados) => <p>{dados.join(",")}</p>}
      </DataState>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Sem linhas.");
  });

  it("distingue API fora do ar de resposta fora do contrato", () => {
    const { rerender } = render(
      <DataState query={consulta<string>({ isError: true, error: new ApiIndisponivelError() })}>
        {(dados) => <p>{dados}</p>}
      </DataState>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("API indisponível");

    rerender(
      <DataState
        query={consulta<string>({ isError: true, error: new ApiContratoError("/x", "campo") })}
      >
        {(dados) => <p>{dados}</p>}
      </DataState>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Resposta fora do contrato");
  });
});
