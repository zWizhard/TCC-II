import { createRouter } from "@tanstack/react-router";

import { criarQueryClient } from "./lib/api/queries";
import { routeTree } from "./routeTree.gen";

export const getRouter = () => {
  const queryClient = criarQueryClient();

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};
