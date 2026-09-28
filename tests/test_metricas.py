import pytest

from metricas import aceita, matriz_confusao, media, percentil, taxa


def test_aceita_valor_ou_lista():
    assert aceita("crm", "crm")
    assert not aceita("crm", "alerta")
    assert aceita(["resposta", "revisao"], "revisao")
    assert not aceita(["resposta", "revisao"], None)


def test_percentil_igual_ao_percentile_cont():
    # percentile_cont(0.5) de 1,2,3,4 = 2.5; percentile_cont(0.95) = 3.85
    assert percentil([4, 1, 3, 2], 0.5) == pytest.approx(2.5)
    assert percentil([1, 2, 3, 4], 0.95) == pytest.approx(3.85)
    assert percentil([7], 0.95) == 7
    assert percentil([None, 5], 0.5) == 5
    assert percentil([], 0.5) is None


def test_media_e_taxa_ignoram_vazios():
    assert media([1, None, 3]) == 2
    assert media([]) is None
    assert taxa(3, 4) == 0.75
    assert taxa(0, 0) is None


def test_matriz_confusao_conta_pares():
    m = matriz_confusao([("duvida", "duvida"), ("duvida", "outro"), ("duvida", "duvida")])
    assert m == {("duvida", "duvida"): 2, ("duvida", "outro"): 1}
