import { ApiContratoError, ApiError, ApiIndisponivelError } from "@/lib/api/client";

export type DescricaoErro = { titulo: string; detalhe: string; codigo?: string };

/** Traduz um erro de consulta em texto para o usuário, distinguindo os três tipos de falha. */
export function descreverErro(erro: unknown): DescricaoErro {
  if (erro instanceof ApiIndisponivelError) {
    return {
      titulo: "API indisponível",
      detalhe:
        "Não foi possível conectar à API do Observatório. Verifique se ela está em execução e tente novamente.",
    };
  }
  if (erro instanceof ApiError) {
    return {
      titulo: "A API recusou a consulta",
      // Texto vindo do servidor: exibido como dado, nunca interpretado.
      detalhe: erro.mensagem,
      codigo: `${erro.codigo} · HTTP ${erro.status}`,
    };
  }
  if (erro instanceof ApiContratoError) {
    return {
      titulo: "Resposta fora do contrato",
      detalhe:
        "A API respondeu em um formato diferente do esperado. O valor não é exibido para evitar um número incorreto.",
    };
  }
  return { titulo: "Erro inesperado", detalhe: "Não foi possível carregar este bloco." };
}
