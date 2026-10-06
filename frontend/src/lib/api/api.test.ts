import { afterEach, describe, expect, it, vi } from "vitest";

import erro422 from "@/test/fixtures/erro-422.json";
import health from "@/test/fixtures/health.json";
import iesBrasil from "@/test/fixtures/ies-brasil.json";
import iesUfPublica from "@/test/fixtures/ies-uf-publica.json";
import indicadores from "@/test/fixtures/indicadores.json";
import matriculasBrasil from "@/test/fixtures/matriculas-brasil.json";
import matriculasRegiao from "@/test/fixtures/matriculas-regiao.json";
import metadados from "@/test/fixtures/metadados.json";

import {
  ApiContratoError,
  ApiError,
  ApiIndisponivelError,
  API_BASE_URL_PADRAO,
  consultarIndicador,
  montarParametrosIndicador,
  obterMetadados,
} from "./client";
import { resolverDimensoes } from "./dimensoes";
import {
  catalogoSchema,
  DIMENSOES,
  envelopeErroSchema,
  metadadosSchema,
  respostaIndicadorSchema,
  saudeSchema,
  type IndicadorInfo,
} from "./schemas";

// As fixtures são respostas reais da API (capturadas em 2026-10-06), não exemplos escritos à mão.
const catalogo = catalogoSchema.parse(indicadores);

function indicador(slug: string): IndicadorInfo {
  const encontrado = catalogo.find((i) => i.slug === slug);
  if (!encontrado) throw new Error(`fixture sem o indicador ${slug}`);
  return encontrado;
}

function responder(corpo: unknown, status = 200) {
  return vi.fn(async () => new Response(JSON.stringify(corpo), { status }));
}

function urlChamada(mock: ReturnType<typeof vi.fn>): URL {
  return new URL(String(mock.mock.calls[0]?.[0]));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("contrato (zod) contra as respostas reais", () => {
  it("aceita todas as fixtures capturadas da API", () => {
    expect(saudeSchema.safeParse(health).success).toBe(true);
    expect(metadadosSchema.safeParse(metadados).success).toBe(true);
    expect(catalogoSchema.safeParse(indicadores).success).toBe(true);
    for (const resposta of [iesBrasil, iesUfPublica, matriculasBrasil, matriculasRegiao]) {
      expect(respostaIndicadorSchema.safeParse(resposta).success).toBe(true);
    }
    expect(envelopeErroSchema.safeParse(erro422).success).toBe(true);
  });

  it("recusa resposta de indicador sem o recorte territorial", () => {
    const { recorte: _recorte, ...semRecorte } = iesBrasil;
    expect(respostaIndicadorSchema.safeParse(semRecorte).success).toBe(false);
  });

  it("as dimensões do frontend são as mesmas que a API publica", () => {
    expect(metadados.dimensoes_oferta.map((d) => d.slug).sort()).toEqual([...DIMENSOES].sort());
  });
});

describe("resolverDimensoes", () => {
  it("não se aplica a indicador que não exige dimensão", () => {
    expect(resolverDimensoes(indicador("ies"), "uf", [...DIMENSOES])).toEqual({
      aplicavel: false,
      efetivas: [],
      excluidas: [],
      consultavel: true,
    });
  });

  it("no nível brasil mantém todas as dimensões selecionadas", () => {
    const r = resolverDimensoes(indicador("vagas"), "brasil", [...DIMENSOES]);
    expect(r.efetivas).toEqual([...DIMENSOES]);
    expect(r.excluidas).toEqual([]);
  });

  it("em nível territorial corta as dimensões que o catálogo não admite e as declara", () => {
    const vagas = indicador("vagas");
    const r = resolverDimensoes(vagas, "uf", [...DIMENSOES]);
    expect(r.efetivas).toEqual(vagas.dimensoes_territoriais);
    expect([...r.efetivas, ...r.excluidas].sort()).toEqual([...DIMENSOES].sort());
    expect(r.consultavel).toBe(true);
  });

  it("não é consultável quando nenhuma dimensão selecionada é admitida", () => {
    const r = resolverDimensoes(indicador("vagas"), "uf", ["ead_nacional"]);
    expect(r.efetivas).toEqual([]);
    expect(r.consultavel).toBe(false);
    expect(resolverDimensoes(indicador("matriculas"), "brasil", []).consultavel).toBe(false);
  });
});

describe("montarParametrosIndicador", () => {
  it("usa sempre o recorte do catálogo e não envia dimensão a indicador de IES", () => {
    const ies = indicador("ies");
    const p = montarParametrosIndicador(ies, { nivel: "uf", dimensoes: [...DIMENSOES] });
    expect(p.get("recorte")).toBe(ies.recorte);
    expect(p.get("nivel")).toBe("uf");
    expect(p.has("dimensao")).toBe(false);
  });

  it("envia só as dimensões efetivas, a rede e ignora uf fora do nível municipal", () => {
    const matriculas = indicador("matriculas");
    const p = montarParametrosIndicador(matriculas, {
      nivel: "regiao",
      dimensoes: [...DIMENSOES],
      rede: "publica",
      uf: "GO",
    });
    expect(p.getAll("dimensao").sort()).toEqual([...matriculas.dimensoes_territoriais].sort());
    expect(p.get("rede")).toBe("publica");
    expect(p.has("uf")).toBe(false);

    const municipal = montarParametrosIndicador(matriculas, {
      nivel: "municipio",
      dimensoes: ["presencial"],
      uf: "GO",
    });
    expect(municipal.get("uf")).toBe("GO");
  });
});

describe("cliente HTTP", () => {
  it("consulta a URL padrão da API e devolve a resposta validada", async () => {
    const fetchMock = responder(matriculasRegiao);
    vi.stubGlobal("fetch", fetchMock);

    const dados = await consultarIndicador(indicador("matriculas"), {
      nivel: "regiao",
      dimensoes: ["presencial", "ead_polo"],
    });

    const url = urlChamada(fetchMock);
    expect(url.origin).toBe(API_BASE_URL_PADRAO);
    expect(url.pathname).toBe("/api/v1/indicadores/matriculas");
    expect(url.searchParams.get("recorte")).toBe("oferta");
    expect(dados.total).toBe(matriculasRegiao.total);
    expect(dados.linhas).toHaveLength(matriculasRegiao.linhas.length);
  });

  it("converte o envelope de erro da API em ApiError", async () => {
    vi.stubGlobal("fetch", responder(erro422, 422));

    const erro = await consultarIndicador(indicador("vagas"), {
      nivel: "brasil",
      dimensoes: ["ead_polo"],
    }).catch((e: unknown) => e);

    expect(erro).toBeInstanceOf(ApiError);
    expect(erro).toMatchObject({
      status: 422,
      codigo: erro422.erro.codigo,
      mensagem: erro422.erro.mensagem,
    });
  });

  it("acusa resposta fora do contrato em vez de entregar dado malformado", async () => {
    vi.stubGlobal("fetch", responder({ ...metadados, dimensoes_oferta: "todas" }));
    await expect(obterMetadados()).rejects.toBeInstanceOf(ApiContratoError);
  });

  it("acusa erro HTTP sem envelope como quebra de contrato", async () => {
    vi.stubGlobal("fetch", responder({ detail: "Not Found" }, 404));
    await expect(obterMetadados()).rejects.toBeInstanceOf(ApiContratoError);
  });

  it("distingue API fora do ar de erro da API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await expect(obterMetadados()).rejects.toBeInstanceOf(ApiIndisponivelError);
  });

  it("repassa o cancelamento sem tratá-lo como API fora do ar", async () => {
    const controle = new AbortController();
    controle.abort();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new DOMException("cancelada", "AbortError");
      }),
    );
    const erro = await obterMetadados({ signal: controle.signal }).catch((e: unknown) => e);
    expect(erro).not.toBeInstanceOf(ApiIndisponivelError);
    expect(erro).toMatchObject({ name: "AbortError" });
  });
});
