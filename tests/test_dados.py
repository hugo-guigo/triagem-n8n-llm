"""O conjunto de avaliação é válido e não vaza os exemplos few-shot do prompt."""
import json
import re
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CASOS = json.loads((RAIZ / "dados" / "mensagens_teste.json").read_text(encoding="utf-8"))["casos"]
CATEGORIAS = {"agendamento", "cancelamento", "reclamacao", "duvida", "outro"}
DESTINOS = {"crm", "alerta", "revisao", "resposta", "invalido"}


def como_lista(v):
    return v if isinstance(v, list) else [v]


def test_tamanho_e_ids_unicos():
    assert 20 <= len(CASOS) <= 40
    ids = [c["id"] for c in CASOS]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[A-Za-z0-9_-]+", i) for i in ids)


def test_rotulos_validos():
    for c in CASOS:
        esp = c["esperado"]
        assert set(como_lista(esp["destino"])) <= DESTINOS, c["id"]
        if esp.get("categoria") is not None:
            assert set(como_lista(esp["categoria"])) <= CATEGORIAS, c["id"]
        if esp["destino"] == "invalido":
            assert "corpo" in c and esp.get("http") == 400, c["id"]
        else:
            assert {"nome", "canal", "texto"} <= set(c), c["id"]


def test_cobre_todas_as_categorias_ambiguos_e_invalidos():
    cats = Counter(cat for c in CASOS for cat in como_lista(c["esperado"].get("categoria")) if cat)
    assert set(cats) == CATEGORIAS
    assert sum(1 for c in CASOS if c["esperado"].get("categoria") is None and c["esperado"]["destino"] == "revisao") >= 2
    assert sum(1 for c in CASOS if c["esperado"]["destino"] == "invalido") >= 2


def test_nenhum_caso_repete_os_exemplos_do_prompt():
    """Se o teste tiver os exemplos few-shot, a acurácia sai inflada (vazamento)."""
    wf = json.loads((RAIZ / "workflows" / "triagem_de_mensagens.json").read_text(encoding="utf-8"))
    code = next(n for n in wf["nodes"] if n["name"] == "Montar requisição")["parameters"]["jsCode"]
    bloco = code[code.index("const EXEMPLOS"):code.index("];", code.index("const EXEMPLOS"))]
    exemplos = re.findall(r"\['\w+', '[^']*', '([^']*)'", bloco)
    assert len(exemplos) >= 4, "não achei os exemplos few-shot no prompt"
    normaliza = lambda t: re.sub(r"\W+", " ", t.lower()).strip()
    testes = {normaliza(c.get("texto", "")) for c in CASOS}
    for ex in exemplos:
        assert normaliza(ex) not in testes, f"exemplo do prompt aparece no teste: {ex}"
