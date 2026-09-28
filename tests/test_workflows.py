"""Checagens estáticas dos workflows exportados. Não precisam de n8n, banco nem LLM."""
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVOS = sorted((RAIZ / "workflows").glob("*.json"))
WF = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in ARQUIVOS}
PRINCIPAL = WF["triagem_de_mensagens.json"]


def nos(wf):
    return {n["name"]: n for n in wf["nodes"]}


def test_existem_os_tres_workflows():
    assert set(WF) == {"triagem_de_mensagens.json", "tratamento_de_erros.json", "teste_de_erro.json"}


@pytest.mark.parametrize("nome", list(WF))
def test_conexoes_apontam_para_nos_que_existem(nome):
    wf = WF[nome]
    nomes = [n["name"] for n in wf["nodes"]]
    assert len(nomes) == len(set(nomes)), "nomes de nós repetidos"
    for origem, saidas in wf["connections"].items():
        assert origem in nomes, f"conexão sai de nó inexistente: {origem}"
        for saida in saidas["main"]:
            for destino in saida:
                assert destino["node"] in nomes, f"{origem} -> nó inexistente {destino['node']}"


@pytest.mark.parametrize("caminho", ARQUIVOS, ids=lambda p: p.name)
def test_nenhum_segredo_nem_dado_da_instancia(caminho):
    texto = caminho.read_text(encoding="utf-8")
    for proibido in ["gsk_", "Bearer ", "projectId", "@gmail", "\"shared\""]:
        assert proibido not in texto, f"{proibido!r} encontrado em {caminho.name}"
    for n in json.loads(texto)["nodes"]:
        for cred in n.get("credentials", {}).values():
            assert set(cred) == {"id", "name"}, "credencial deve ser só referência (id e nome)"


@pytest.mark.parametrize("nome", list(WF))
def test_sql_so_com_parametros(nome):
    """Nada de montar SQL com expressão do n8n: o texto do cliente entra só como parâmetro ($1, $2...)."""
    for n in WF[nome]["nodes"]:
        if n["type"] != "n8n-nodes-base.postgres":
            continue
        query = n["parameters"]["query"]
        assert "{{" not in query, f"{n['name']}: expressão dentro do SQL"
        if re.search(r"\$\d", query):
            assert n["parameters"]["options"].get("queryReplacement"), f"{n['name']}: $n sem parâmetros"


def test_chamada_ao_llm_tem_retry_e_saida_de_erro():
    http = nos(PRINCIPAL)["Classificar (Groq)"]
    assert http["retryOnFail"] is True and http["maxTries"] >= 2
    assert http["waitBetweenTries"] > 0
    assert http["onError"] == "continueErrorOutput"
    destinos = [d["node"] for d in PRINCIPAL["connections"]["Classificar (Groq)"]["main"][1]]
    assert destinos == ["Handoff por erro do LLM"]


def test_gravacoes_no_banco_desviam_o_erro_para_nao_confirmar():
    """Falha no INSERT tem de sair pela saída de erro (vira 503), nunca seguir como sucesso."""
    for nome in ["Buscar id_mensagem", "Gravar na fila de revisão", "Criar alerta", "Registrar no CRM"]:
        n = nos(PRINCIPAL)[nome]
        assert n["onError"] == "continueErrorOutput", nome
        assert not n.get("alwaysOutputData"), f"{nome}: alwaysOutputData manda item vazio pela saída de sucesso"


def test_uma_so_resposta_e_todas_passam_pelo_log():
    respostas = [n for n in PRINCIPAL["nodes"] if n["type"] == "n8n-nodes-base.respondToWebhook"]
    assert [n["name"] for n in respostas] == ["Responder"]
    assert PRINCIPAL["connections"]["Registrar execução"]["main"][0][0]["node"] == "Responder"


def test_workflow_de_erro_configurado():
    id_erros = WF["tratamento_de_erros.json"]["id"]
    assert PRINCIPAL["settings"]["errorWorkflow"] == id_erros
    assert WF["teste_de_erro.json"]["settings"]["errorWorkflow"] == id_erros
    tipos = [n["type"] for n in WF["tratamento_de_erros.json"]["nodes"]]
    assert "n8n-nodes-base.errorTrigger" in tipos


def test_saida_do_llm_presa_a_um_schema_strict():
    code = nos(PRINCIPAL)["Montar requisição"]["parameters"]["jsCode"]
    assert "type: 'json_schema'" in code and "strict: true" in code
    assert "additionalProperties: false" in code
