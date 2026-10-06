import { createMemoryHistory, createRouter, RouterProvider } from "@tanstack/react-router";
import { render } from "@testing-library/react";

import { criarQueryClient } from "@/lib/api/queries";
import { routeTree } from "@/routeTree.gen";

/**
 * Monta a aplicação inteira (shell + rota) em um caminho, como o navegador faria.
 *
 * Dois cuidados, sem os quais nada chega ao DOM do jsdom:
 *  - o shell (`__root.tsx`) renderiza <html>/<head>/<body>, que não podem ser filhos do <div>
 *    padrão do testing-library — o contêiner é o próprio documento;
 *  - o roteador é carregado antes de montar; no jsdom ele não sai de `pending` sozinho.
 */
export async function renderRota(caminho: string) {
  const router = createRouter({
    routeTree,
    context: { queryClient: criarQueryClient() },
    history: createMemoryHistory({ initialEntries: [caminho] }),
  });
  await router.load();
  render(<RouterProvider router={router} />, { container: document });
  return router;
}
