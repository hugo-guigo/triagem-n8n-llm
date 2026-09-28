"""Testes de ponta a ponta no n8n de verdade, pelos caminhos que NÃO chamam o LLM.

Precisam dos containers rodando e do configurar_n8n.py já executado. Não gastam cota do Groq.
Rodar: RODAR_INTEGRACAO=1 pytest -m integracao   (PowerShell: $env:RODAR_INTEGRACAO=1; pytest -m integracao)
"""
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from enviar import enviar

RAIZ = Path(__file__).resolve().parent.parent
pytestmark = [
    pytest.mark.integracao,
    pytest.mark.skipif(os.environ.get("RODAR_INTEGRACAO") != "1", reason="defina RODAR_INTEGRACAO=1"),
]


def psql(sql: str) -> str:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "admin", "-d", "clinica", "-At", "-c", sql],
        cwd=RAIZ, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def novo_id() -> str:
    return "it-" + uuid.uuid4().hex[:12]


def log_de(id_mensagem: str) -> str:
    for _ in range(10):  # o log é gravado logo antes da resposta; a espera é só margem
        linha = psql(f"SELECT destino || '|' || coalesce(erro, '') FROM execucoes WHERE id_mensagem = '{id_mensagem}'")
        if linha:
            return linha
        time.sleep(0.5)
    return ""


def post(corpo: dict):
    status, texto, _ = enviar(json.dumps(corpo).encode())
    return status, json.loads(texto)


def test_entrada_invalida_responde_400_e_vai_para_o_log():
    idm = novo_id()
    status, r = post({"id_mensagem": idm, "nome": "Teste", "canal": "telegram", "texto": "oi"})
    assert status == 400
    assert r["status"] == "erro" and any("canal inválido" in e for e in r["erros"])
    assert log_de(idm).startswith("invalido|")


def test_id_ja_gravado_volta_duplicada_sem_chamar_o_llm():
    idm = novo_id()
    psql(f"INSERT INTO solicitacoes (id_mensagem, nome, canal, tipo, resumo) "
         f"VALUES ('{idm}', 'Teste', 'site', 'agendamento', 'gravado pelo teste')")
    status, r = post({"id_mensagem": idm, "nome": "Teste", "canal": "site", "texto": "Quero marcar pilates."})
    assert status == 200
    assert r["status"] == "duplicada" and r["destino"] == "crm"
    assert log_de(idm).startswith("duplicada|")


def test_banco_fora_responde_503_e_nao_confirma():
    """Sem permissão de leitura, a consulta de duplicata falha antes do LLM: tem de dar 503."""
    idm = novo_id()
    psql("REVOKE SELECT ON solicitacoes FROM app")
    try:
        status, r = post({"id_mensagem": idm, "nome": "Teste", "canal": "site", "texto": "Quero marcar pilates."})
    finally:
        psql("GRANT SELECT ON solicitacoes TO app")
    assert status == 503 and r["status"] == "erro"
    assert log_de(idm).startswith("erro|Buscar id_mensagem: permission denied")
    assert psql(f"SELECT count(*) FROM solicitacoes WHERE id_mensagem = '{idm}'") == "0"


def test_error_trigger_registra_falha_nao_tratada():
    antes = int(psql("SELECT count(*) FROM falhas"))
    enviar(b"{}", "http://127.0.0.1:5678/webhook/teste-erro")
    for _ in range(20):
        if int(psql("SELECT count(*) FROM falhas")) > antes:
            break
        time.sleep(0.5)
    ultima = psql("SELECT workflow || '|' || no || '|' || mensagem FROM falhas ORDER BY id DESC LIMIT 1")
    assert ultima.startswith("Teste de erro|Falhar de propósito|falha simulada")
