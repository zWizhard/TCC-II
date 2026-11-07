# Tabelas do benchmark (geradas por `benchmark/relatorio.py`)

Não editar à mão. Unidade de análise: o caso (acerto = correto em todas as repetições). IC 95% de Wilson. Protocolo em [`PROTOCOLO.md`](PROTOCOLO.md); leitura e limitações em [`RESULTADOS.md`](RESULTADOS.md).

## Condição P — produção (como o sistema está)

`num_predict` = 1024; opções = `{'seed': 20241007}`; campos = `{}`; prazo = 120 s; temperatura 0; 3 repetição(ões).

### Funil de correção — casos corretos em todas as repetições (%; IC 95%)

| Modelo | JSON válido | Plano válido / SQL executável | Plano correto | SQL semanticamente correto | Resultado correto (sucesso) |
|---|---|---|---|---|---|
| gpt-oss:20b | 9/28 (32.1%; 17.9–50.7) | 7/28 (25.0%; 12.7–43.4) | 7/28 (25.0%; 12.7–43.4) | 7/28 (25.0%; 12.7–43.4) | 7/28 (25.0%; 12.7–43.4) |
| qwen2.5-coder:14b | 28/28 (100.0%; 87.9–100.0) | 2/28 (7.1%; 2.0–22.6) | 2/28 (7.1%; 2.0–22.6) | 2/28 (7.1%; 2.0–22.6) | 2/28 (7.1%; 2.0–22.6) |
| qwen3:8b | 24/28 (85.7%; 68.5–94.3) | 3/28 (10.7%; 3.7–27.2) | 3/28 (10.7%; 3.7–27.2) | 3/28 (10.7%; 3.7–27.2) | 3/28 (10.7%; 3.7–27.2) |

### Sucesso: todos os casos, sem os 4 de convenção implícita, e por execução

| Modelo | 28 casos | 24 casos (sem F4, G4, M1, M2) | Por execução (%) |
|---|---|---|---|
| gpt-oss:20b | 7/28 (25.0%; 12.7–43.4) | 7/24 (29.2%; 14.9–49.2) | 31.0 |
| qwen2.5-coder:14b | 2/28 (7.1%; 2.0–22.6) | 2/24 (8.3%; 2.3–25.8) | 7.1 |
| qwen3:8b | 3/28 (10.7%; 3.7–27.2) | 3/24 (12.5%; 4.3–31.0) | 14.3 |

### Desfechos (execuções) e estabilidade (casos)

| Modelo | Execuções | Respondida | Plano inválido | Não é um plano | Sem resposta no prazo | Paradas por `length` | Com raciocínio | Desfecho estável | Saída idêntica |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss:20b | 84 | 26 | 8 | 50 | 0 | 50 | 84 | 22/28 | 15/28 |
| qwen2.5-coder:14b | 84 | 6 | 78 | 0 | 0 | 0 | 0 | 28/28 | 28/28 |
| qwen3:8b | 84 | 12 | 64 | 8 | 0 | 8 | 84 | 23/28 | 4/28 |

### Latência e uso do hardware

| Modelo | Parâmetros | Quant. | Memória (GB) | Fração na GPU | Carga (s) | Mediana (s) | P90 (s) | Máx. (s) | Mediana dos acertos (s) | Tokens gerados (med.) | Tokens/s (med.) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss:20b | 20.9B | MXFP4 | 14.0 | 0.443 | 13.4 | 37.8 | 40.6 | 41.4 | 23.4 | 1024 | 28.8 |
| qwen2.5-coder:14b | 14.8B | Q4_K_M | 10.0 | 0.642 | 9.4 | 15.6 | 19.1 | 23.9 | 17.4 | 109 | 9.4 |
| qwen3:8b | 8.2B | Q4_K_M | 5.6 | 1.0 | 4.1 | 12.1 | 18.2 | 20.8 | 11.2 | 563 | 58.9 |

### Sucesso por categoria (casos corretos / casos)

| Categoria | n | gpt-oss:20b | qwen2.5-coder:14b | qwen3:8b |
|---|---|---|---|---|
| agregacao | 3 | 3/3 | 0/3 | 2/3 |
| comparacao | 3 | 0/3 | 0/3 | 0/3 |
| filtro_simples | 4 | 2/4 | 0/4 | 1/4 |
| group_by | 4 | 1/4 | 0/4 | 0/4 |
| having | 4 | 0/4 | 0/4 | 0/4 |
| multiplos_filtros | 4 | 0/4 | 0/4 | 0/4 |
| ranking | 4 | 0/4 | 2/4 | 0/4 |
| razao | 2 | 1/2 | 0/2 | 0/2 |

### Sucesso por caso (* = convenção implícita)

| Caso | Categoria | gpt-oss:20b | qwen2.5-coder:14b | qwen3:8b |
|---|---|---|---|---|
| A1 | agregacao | ✓ | ✗ | ✓ |
| A2 | agregacao | ✓ | ✗ | ✗ |
| A3 | agregacao | ✓ | ✗ | ✓ |
| C1 | comparacao | ✗ | ✗ | ✗ |
| C2 | comparacao | ✗ | ✗ | ✗ |
| C3 | comparacao | ✗ | ✗ | ✗ |
| F1 | filtro_simples | ✓ | ✗ | ✓ |
| F2 | filtro_simples | ✗ | ✗ | ✗ |
| F3 | filtro_simples | ✓ | ✗ | ✗ |
| F4* | filtro_simples | ✗ | ✗ | ✗ |
| G1 | group_by | ✗ | ✗ | ✗ |
| G2 | group_by | ✗ | ✗ | ✗ |
| G3 | group_by | ✓ | ✗ | ✗ |
| G4* | group_by | ✗ | ✗ | ✗ |
| H1 | having | ✗ | ✗ | ✗ |
| H2 | having | ✗ | ✗ | ✗ |
| H3 | having | ✗ | ✗ | ✗ |
| H4 | having | ✗ | ✗ | ✗ |
| M1* | multiplos_filtros | ✗ | ✗ | ✗ |
| M2* | multiplos_filtros | ✗ | ✗ | ✗ |
| M3 | multiplos_filtros | ✗ | ✗ | ✗ |
| M4 | multiplos_filtros | ✗ | ✗ | ✗ |
| R1 | ranking | ✗ | ✓ | ✗ |
| R2 | ranking | ✗ | ✗ | ✗ |
| R3 | ranking | ✗ | ✗ | ✗ |
| R4 | ranking | ✗ | ✓ | ✗ |
| Z1 | razao | ✓ | ✗ | ✗ |
| Z2 | razao | ✗ | ✗ | ✗ |

**gpt-oss:20b** — motivos de rejeição do plano (execuções): `intencao_incoerente` 6, `visualizacao_incompativel` 4, `dimensao_de_oferta_ausente` 1, `dimensao_de_oferta_nao_declarada` 1, `limite_diverge_do_contexto` 1. Campos divergentes da referência: `intent` 6, `dimensao_de_oferta` 1, `limit` 1.

**qwen2.5-coder:14b** — motivos de rejeição do plano (execuções): `limite_diverge_do_contexto` 63, `visualizacao_incompativel` 24, `agrupamento_invalido` 21, `agrupamento_fora_do_contexto` 21, `limiar_do_contexto_omitido` 15, `intencao_incoerente` 12. Campos divergentes da referência: `limit` 69, `group_by` 24, `having` 15, `intent` 9, `filters` 6, `dimensao_de_oferta` 3.

**qwen3:8b** — motivos de rejeição do plano (execuções): `filtro_diverge_do_contexto` 38, `filtro_invalido` 30, `dimensao_inexistente` 29, `intencao_incoerente` 21, `agrupamento_fora_do_contexto` 19, `ordenacao_diverge_do_contexto` 18. Campos divergentes da referência: `filters` 48, `intent` 39, `order_by` 18, `group_by` 18, `having` 12, `metrics` 3.

### Comparação entre modelos

Q de Cochran (global): Q = 4.67, gl = 2, p = 0.0970.

| Modelo A | Modelo B | Só A acerta | Só B acerta | p (McNemar) | p (Holm) |
|---|---|---|---|---|---|
| gpt-oss:20b | qwen2.5-coder:14b | 7 | 2 | 0.1797 | 0.3750 |
| gpt-oss:20b | qwen3:8b | 4 | 0 | 0.1250 | 0.3750 |
| qwen2.5-coder:14b | qwen3:8b | 2 | 3 | 1.0000 | 1.0000 |

## Bloco de sistema (sem LLM)

Idêntico nas 3 rodadas: sim. Situação exata: 10/12. (A abstenção é condição de entrada no bloco, não resultado.)

| Caso | Categoria | Pergunta | Situação ideal | Situação obtida | Exata |
|---|---|---|---|---|---|
| J1 | join | matrículas por 100 mil habitantes por UF | nao_suportada | nao_suportada | ✓ |
| J2 | join | Quantas matrículas presenciais e quantos docentes há por UF? | nao_suportada | requer_esclarecimento | ✗ |
| J3 | join | docentes por matrícula por UF | recusada | recusada | ✓ |
| T1 | evolucao_temporal | crescimento das matrículas presenciais entre 2020 e 2024 | recusada | recusada | ✓ |
| T2 | evolucao_temporal | matrículas presenciais em 2019 | recusada | recusada | ✓ |
| T3 | evolucao_temporal | Como evoluíram as matrículas presenciais? | recusada | nao_mapeada | ✗ |
| B1 | ambiguidade | Quantas universidades existem no Brasil? | requer_esclarecimento | requer_esclarecimento | ✓ |
| B2 | ambiguidade | Quantas IES públicas existem? | requer_esclarecimento | requer_esclarecimento | ✓ |
| B3 | ambiguidade | Quantas matrículas EAD existem? | requer_esclarecimento | requer_esclarecimento | ✓ |
| B4 | ambiguidade | matrículas presenciais em São Paulo | requer_esclarecimento | requer_esclarecimento | ✓ |
| B5 | ambiguidade | Quantas matrículas existem no Brasil? | requer_esclarecimento | requer_esclarecimento | ✓ |
| X1 | fora_de_escopo | taxa de evasão dos cursos presenciais | recusada | recusada | ✓ |
