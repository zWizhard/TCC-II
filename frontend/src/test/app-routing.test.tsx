import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderRota } from "./render-rota";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App routing", () => {
  it("renderiza a landing em português, sem consultar a API", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await renderRota("/");

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("lang", "pt-BR");
    // A landing é ilustrativa e precisa funcionar com a API fora do ar.
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("renderiza a página de rota inexistente", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);

    await renderRota("/this-route-does-not-exist");

    expect(
      await screen.findByRole("heading", { name: "Página não encontrada" }),
    ).toBeInTheDocument();
  });
});
