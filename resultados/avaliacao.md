# Avaliação do fluxo (28/09/2026 20:12)

Rodada `av20260928200833`, 30 mensagens fictícias de `dados/mensagens_teste.json`, modelo `openai/gpt-oss-20b` pelo Groq (plano grátis), 8 s entre chamadas.

| Métrica | Resultado |
|---|---|
| Categoria correta (casos não ambíguos que passaram pelo LLM) | 24/24 (100.0%) |
| Destino correto (CRM, alerta, revisão, resposta, 400) | 29/30 (96.7%) |
| Mandadas para revisão humana (handoff) | 5 (4 esperadas) |
| Falhas do LLM depois do retry | 0 |
| Reenvio do mesmo id_mensagem | devolveu duplicada, sem chamar o LLM (81 ms) |
| Latência de ponta a ponta com LLM (média / p50 / p95 / máx.) | 637 / 563 / 1371 / 1594 ms |
| Tokens por mensagem (entrada / saída, média) | 992 / 67 |
| Tokens na rodada | 28595 |
| Confiança média quando acertou / quando errou | 0.88 / n/d |

## Matriz de confusão da categoria (linha = esperada, coluna = obtida)

| esperada \ obtida | agendamento | cancelamento | reclamacao | duvida | outro |
|---|---|---|---|---|---|
| agendamento | 5 | · | · | · | · |
| cancelamento | · | 4 | · | · | · |
| reclamacao | · | · | 7 | · | · |
| duvida | · | · | · | 5 | · |
| outro | · | · | · | · | 3 |

## Casos que erraram

- **o2** "Somos uma agência de marketing digital e queremos apresentar nossos serviços para a sua cl": esperado outro -> resposta, obtido outro -> revisao (confiança 0.4)
