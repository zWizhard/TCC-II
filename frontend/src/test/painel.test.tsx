import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { respostaIndicadorSchema } from "@/lib/api/schemas";
import { formatarInteiro } from "@/lib/format";

import respostasReais from "./fixtures/painel-padrao.json";
import { renderRota } from "./render-rota";

// Respostas reais da API para as consultas padrão de /painel, indexadas por caminho + query.
// URL que não esteja aqui responde 404 sem envelope: se o cliente montar uma URL diferente da
// que a API de fato atendeu, o teste falha em vez de passar com dado inventado.
const respostas: Record<string, unknown> = respostasReais;

function resposta(caminho: string) {
  const corpo = respostas[caminho];
  if (corpo === undefined) throw new Error(`fixture sem ${caminho}`);
  return respostaIndicadorSchema.parse(corpo);
}

function fetchDasFixtures() {
  return vi.fn(async (entrada: RequestInfo | URL) => {
    const url = new URL(String(entrada));
    const corpo = respostas[url.pathname + url.search];
    return corpo === undefined
      ? new Response(JSON.stringify({ detail: "fora da fixture" }), { status: 404 })
      : new Response(JSON.stringify(corpo), { status: 200 });
  });
}

const renderPainel = () => renderRota("/painel");

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("rota /painel", () => {
  it("mostra os totais nacionais e a distribuição por região com os valores da API", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderPainel();

    const ies = resposta("/api/v1/indicadores/ies?nivel=brasil&recorte=sede");
    const cartaoIes = await screen.findByRole("article", { name: ies.indicador.nome });
    await within(cartaoIes).findByText(formatarInteiro(ies.total));
    expect(within(cartaoIes).getByText("Sede da IES")).toBeInTheDocument();
    expect(within(cartaoIes).getByText(/não se aplica a este indicador/)).toBeInTheDocument();

    // Um cartão por indicador do catálogo, cada um com o total da sua própria resposta.
    const catalogo = respostas["/api/v1/indicadores"] as Array<{ slug: string; nome: string }>;
    expect(await screen.findAllByRole("article")).toHaveLength(catalogo.length);
    const chavesBrasil = Object.keys(respostas).filter((c) => c.includes("nivel=brasil"));
    expect(chavesBrasil).toHaveLength(catalogo.length);
    for (const chave of chavesBrasil) {
      const dados = resposta(chave);
      const cartao = screen.getByRole("article", { name: dados.indicador.nome });
      await within(cartao).findByText(formatarInteiro(dados.total));
      expect(within(cartao).getByText(dados.indicador.codigo)).toBeInTheDocument();
    }

    // Distribuição: primeiro indicador do catálogo, por região, na tabela.
    const regiao = resposta("/api/v1/indicadores/ies?nivel=regiao&recorte=sede");
    const tabela = await screen.findByRole("table");
    for (const linha of regiao.linhas) {
      const celula = within(tabela).getByRole("rowheader", { name: linha.nome });
      expect(celula.closest("tr")).toHaveTextContent(formatarInteiro(linha.valor));
    }

    // Fonte e aviso de retrato transversal vêm dos metadados.
    const metadados = respostas["/api/v1/metadados"] as { fonte: string; aviso: string };
    expect(screen.getByText(metadados.fonte)).toBeInTheDocument();
    expect(screen.getByText(metadados.aviso)).toBeInTheDocument();

    // Nenhuma consulta caiu fora das respostas reais, e todas foram GET.
    for (const [entrada, opcoes] of fetchMock.mock.calls as unknown as Array<
      [string, RequestInit]
    >) {
      const url = new URL(entrada);
      expect(Object.keys(respostas)).toContain(url.pathname + url.search);
      expect(opcoes.method).toBe("GET");
    }
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("troca o nível para UF pela interface e grava a escolha na URL", async () => {
    vi.stubGlobal("fetch", fetchDasFixtures());
    const router = await renderPainel();

    fireEvent.click(await screen.findByRole("radio", { name: "UF" }));

    const uf = resposta("/api/v1/indicadores/ies?nivel=uf&recorte=sede");
    const primeira = uf.linhas[0];
    if (!primeira) throw new Error("fixture de UF sem linhas");
    const celula = await screen.findByRole("rowheader", { name: primeira.nome });
    expect(celula.closest("tr")).toHaveTextContent(formatarInteiro(primeira.valor));
    expect(within(screen.getByRole("table")).getAllByRole("rowheader")).toHaveLength(
      uf.linhas.length,
    );
    await waitFor(() => expect(router.state.location.search).toMatchObject({ nivel: "uf" }));
  });

  it("com a API fora do ar, avisa e não exibe número algum", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await renderPainel();

    const alertas = await screen.findAllByRole("alert", {}, { timeout: 5000 });
    expect(alertas[0]).toHaveTextContent("API indisponível");
    expect(screen.queryAllByRole("article")).toHaveLength(0);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
