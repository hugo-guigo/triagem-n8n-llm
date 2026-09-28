-- Resumo do log de execuções (tabela execucoes).
-- Rodar: Get-Content consultas/resumo.sql | docker compose exec -T postgres psql -U admin -d clinica
-- (no Linux/macOS: docker compose exec -T postgres psql -U admin -d clinica < consultas/resumo.sql)

\echo '== Por destino (a última linha é o total)'
SELECT
    coalesce(destino, 'TOTAL')                                        AS destino,
    count(*)                                                          AS execucoes,
    round(avg(latencia_ms))                                           AS lat_media_ms,
    percentile_cont(0.5)  WITHIN GROUP (ORDER BY latencia_ms)::int    AS lat_p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latencia_ms)::int    AS lat_p95_ms,
    max(latencia_ms)                                                  AS lat_max_ms,
    round(avg(tokens_entrada))                                        AS tokens_in_medio,
    round(avg(tokens_saida))                                          AS tokens_out_medio,
    sum(coalesce(tokens_entrada, 0) + coalesce(tokens_saida, 0))      AS tokens_total,
    count(*) FILTER (WHERE erro IS NOT NULL)                          AS com_erro
FROM execucoes
GROUP BY ROLLUP (destino)
ORDER BY grouping(destino), count(*) DESC;

\echo '== Taxas'
SELECT
    count(*)                                                                    AS execucoes,
    round(100.0 * count(*) FILTER (WHERE handoff) / nullif(count(*), 0), 1)     AS pct_handoff,
    round(100.0 * count(*) FILTER (WHERE destino = 'erro') / nullif(count(*), 0), 1) AS pct_erro_banco,
    count(*) FILTER (WHERE erro LIKE 'erro na API do LLM%')                     AS falhas_llm_apos_retry,
    round(avg(latencia_llm_ms))                                                 AS lat_llm_media_ms
FROM execucoes;

\echo '== Por categoria (só execuções que passaram pelo LLM)'
SELECT
    categoria,
    count(*)                               AS execucoes,
    round(avg(confianca), 2)               AS confianca_media,
    count(*) FILTER (WHERE handoff)        AS handoffs
FROM execucoes
WHERE categoria IS NOT NULL
GROUP BY categoria
ORDER BY count(*) DESC;
