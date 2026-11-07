import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { respostaComposicaoSchema, respostaRazaoSchema } from "@/lib/api/schemas";
import { formatarInteiro, formatarPercentual, formatarRazao } from "@/lib/format";

import respostas from "./fixtures/matriculas.json";
import { renderRota } from "./render-rota";

// Respostas reais da API (scripts/dev/capturar_fixtures_frontend.py), por caminho + query.
// URL fora da fixture responde 404 sem envelope: o teste falha em vez de passar com dado inventado.
const mapa: Record<string, unknown> = respostas;

const TODAS = "dimensao=presencial&dimensao=ead_polo&dimensao=ead_nacional&dimensao=ead_exterior";
const COM_BASE = "dimensao=presencial&dimensao=ead_polo&dimensao=ead_exterior";

function composicao(caminho: string) {
  const corpo = mapa[`/api/v1/indicadores/${caminho}`];
  if (corpo === undefined) throw new Error(`fixture sem ${caminho}`);
  return respostaComposicaoSchema.parse(corpo);
}

function razao(caminho: string) {
  const corpo = mapa[`/api/v1/razoes/${caminho}`];
  if (corpo === undefined) throw new Error(`fixture sem ${caminho}`);
  return respostaRazaoSchema.parse(corpo);
}

function fetchDasFixtures() {
  return vi.fn(async (entrada: RequestInfo | URL) => {
    const url = new URL(String(entrada));
    const corpo = mapa[url.pathname + url.search];
    return corpo === undefined
      ? new Response(JSON.stringify({ detail: "fora da fixture" }), { status: 404 })
      : new Response(JSON.stringify(corpo), { status: 200 });
  });
}

/** Falha se alguma consulta saiu das respostas reais capturadas. */
function esperarSoConsultasReais(fetchMock: ReturnType<typeof fetchDasFixtures>) {
  const consultadas = fetchMock.mock.calls.map(([entrada]) => {
    const url = new URL(String(entrada));
    return url.pathname + url.search;
  });
  expect(consultadas.filter((c) => !(c in mapa))).toEqual([]);
}

/** Cada grupo aparece na tabela com numerador, denominador e o valor calculado pela API. */
async function esperarRazao(nomeDaTabela: RegExp, dados: ReturnType<typeof razao>) {
  const formatar = dados.indicador.percentual ? formatarPercentual : formatarRazao;
  const tabela = await screen.findByRole("table", { name: nomeDaTabela });
  expect(within(tabela).getAllByRole("rowheader")).toHaveLength(dados.linhas.length);
  for (const linha of dados.linhas) {
    const tr = within(tabela).getByRole("rowheader", { name: linha.nome }).closest("tr");
    expect(tr).toHaveTextContent(formatarInteiro(linha.numerador));
    expect(tr).toHaveTextContent(formatarInteiro(linha.denominador));
    expect(tr).toHaveTextContent(linha.valor === null ? "não se aplica" : formatar(linha.valor));
  }
  return tabela;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("rota /matriculas", () => {
  it("mostra o perfil e as razões com os valores calculados pela API", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/matriculas");

    // Perfil: partição na ordem natural devolvida pela API (faixa etária não é ordenada por valor).
    const faixas = composicao(`matriculas/composicao?por=faixa_etaria&recorte=oferta&${TODAS}`);
    const tabelaFaixas = await screen.findByRole("table", { name: /Matrículas por faixa etária/ });
    expect(
      within(tabelaFaixas)
        .getAllByRole("rowheader")
        .map((th) => th.textContent),
    ).toEqual(faixas.linhas.map((linha) => linha.nome));
    const sexo = composicao(`matriculas/composicao?por=sexo&recorte=oferta&${TODAS}`);
    const tabelaSexo = await screen.findByRole("table", { name: /Matrículas por sexo/ });
    for (const linha of sexo.linhas) {
      const tr = within(tabelaSexo).getByRole("rowheader", { name: linha.nome }).closest("tr");
      expect(tr).toHaveTextContent(formatarPercentual(linha.participacao));
    }
    expect(screen.getAllByText(/composição conforme IND-R-07/)).toHaveLength(5);
    // O tipo de vaga só existe para ingressantes.
    expect(screen.queryByRole("table", { name: /por tipo de vaga/ })).not.toBeInTheDocument();

    // Participações (IND-R-08/09): só dimensões em que a base existe.
    const financiamento = razao(
      `financiamento?recorte=oferta&${COM_BASE}&base=matriculas&por=rede`,
    );
    await esperarRazao(/Matrículas com financiamento estudantil por rede/, financiamento);
    expect(screen.getAllByText(formatarPercentual(financiamento.geral.valor)).length).toBe(1);
    await esperarRazao(
      /Matrículas com reserva de vagas por rede/,
      razao(`reserva_vagas?recorte=oferta&${COM_BASE}&base=matriculas&por=rede`),
    );

    // Razões por vaga: presencial e EAD nacional em cartões separados, nunca somados.
    const ingressos = razao("ingressantes_por_vaga?recorte=oferta&dimensao=presencial&por=rede");
    await esperarRazao(/Ingressantes por vaga ofertada \(presencial\) por rede/, ingressos);
    expect(screen.getByText(formatarRazao(ingressos.geral.valor))).toBeInTheDocument();
    const presencial = razao("inscricoes_por_vaga?recorte=oferta&dimensao=presencial&por=rede");
    const nacional = razao("inscricoes_por_vaga?recorte=oferta&dimensao=ead_nacional&por=rede");
    await esperarRazao(/Inscrições por vaga ofertada \(presencial\) por rede/, presencial);
    await esperarRazao(
      /Inscrições por vaga ofertada \(EAD, só no nível Brasil\) por rede/,
      nacional,
    );
    expect(presencial.geral.valor).not.toBe(nacional.geral.valor);

    // A recusa da razão entre concluintes e ingressantes está escrita na página.
    expect(screen.getByText(/essa conta não é feita\s+aqui \(IND-Q-01\)/)).toBeInTheDocument();
    // As ressalvas de leitura vêm do catálogo da API.
    expect(screen.getByText(/Não é taxa de ocupação/)).toBeInTheDocument();

    esperarSoConsultasReais(fetchMock);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("troca a base para ingressantes e grava na URL", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderRota("/matriculas");

    fireEvent.click(await screen.findByRole("radio", { name: "Ingressantes" }));
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ base: "ingressantes" }),
    );
    const tipos = composicao(`ingressantes/composicao?por=tipo_ingresso&recorte=oferta&${TODAS}`);
    const tabela = await screen.findByRole("table", { name: /Ingressantes por tipo de vaga/ });
    expect(within(tabela).getAllByRole("rowheader")).toHaveLength(tipos.linhas.length);
    for (const nota of tipos.notas) expect(screen.getByText(nota)).toBeInTheDocument();

    await esperarRazao(
      /Ingressantes com financiamento estudantil por rede/,
      razao(`financiamento?recorte=oferta&${COM_BASE}&base=ingressantes&por=rede`),
    );
    esperarSoConsultasReais(fetchMock);
  });

  it("compara por UF só onde a dimensão tem território", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    const router = await renderRota("/matriculas");

    fireEvent.change(await screen.findByRole("combobox", { name: "Comparar por" }), {
      target: { value: "uf" },
    });
    await waitFor(() => expect(router.state.location.search).toMatchObject({ comparar: "uf" }));

    const ingressos = razao("ingressantes_por_vaga?recorte=oferta&dimensao=presencial&por=uf");
    expect(ingressos.linhas).toHaveLength(27);
    await esperarRazao(/Ingressantes por vaga ofertada \(presencial\) por uf/, ingressos);
    // Por território, a participação deixa de fora as dimensões sem município — e a API avisa.
    const financiamento = razao(
      "financiamento?recorte=oferta&dimensao=presencial&dimensao=ead_polo&base=matriculas&por=uf",
    );
    await esperarRazao(/Matrículas com financiamento estudantil por uf/, financiamento);
    for (const nota of financiamento.notas) {
      expect(screen.getAllByText(nota).length).toBeGreaterThan(0);
    }
    // A dimensão EAD sem território mantém o valor do Brasil e explica a ausência da comparação.
    expect(screen.getByText(/não há comparação por território/)).toBeInTheDocument();
    expect(
      screen.queryByRole("table", { name: /EAD, só no nível Brasil/ }),
    ).not.toBeInTheDocument();
    esperarSoConsultasReais(fetchMock);
  });

  it("em um município, bloqueia perfil e participações e mantém as razões por vaga", async () => {
    const fetchMock = fetchDasFixtures();
    vi.stubGlobal("fetch", fetchMock);
    await renderRota("/matriculas?uf=DF&municipio=5300108");

    expect(await screen.findByRole("heading", { name: "Brasília (DF)" })).toBeInTheDocument();
    await esperarRazao(
      /Ingressantes por vaga ofertada \(presencial\) por rede/,
      razao(
        "ingressantes_por_vaga?recorte=oferta&dimensao=presencial&por=rede&uf=DF&municipio=5300108",
      ),
    );
    // 5 perfis + 2 participações + o aviso na lista de limites.
    expect(screen.getAllByText(/piso\s+de\s+supressão/).length).toBeGreaterThanOrEqual(8);
    expect(screen.queryByRole("table", { name: /por sexo/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("table", { name: /financiamento/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/EAD, só no nível Brasil/)).not.toBeInTheDocument();
    esperarSoConsultasReais(fetchMock);
  });

  it("com a API fora do ar, avisa e não exibe número algum", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await renderRota("/matriculas");

    const alertas = await screen.findAllByRole("alert", {}, { timeout: 5000 });
    expect(alertas[0]).toHaveTextContent("API indisponível");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
