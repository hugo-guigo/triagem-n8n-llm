"""Funções puras de métrica usadas pela avaliação. Sem rede e sem banco: testáveis no CI."""
from collections import Counter


def aceita(esperado, obtido) -> bool:
    """O esperado pode ser um valor ou uma lista de valores aceitáveis."""
    if isinstance(esperado, list):
        return obtido in esperado
    return obtido == esperado


def percentil(valores: list[float], p: float) -> float | None:
    """Percentil com interpolação linear (o mesmo critério do percentile_cont do Postgres)."""
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    pos = (len(v) - 1) * p
    base = int(pos)
    if base + 1 >= len(v):
        return float(v[-1])
    return v[base] + (v[base + 1] - v[base]) * (pos - base)


def media(valores: list[float]) -> float | None:
    v = [x for x in valores if x is not None]
    return sum(v) / len(v) if v else None


def taxa(acertos: int, total: int) -> float | None:
    return acertos / total if total else None


def matriz_confusao(pares: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    """pares = [(esperado, obtido), ...] -> contagem de cada combinação."""
    return dict(Counter(pares))
