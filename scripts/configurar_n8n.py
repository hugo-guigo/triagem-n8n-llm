"""Configura o n8n que o docker compose subiu: credenciais, workflows e publicação.

1. Cria as credenciais a partir do .env, dentro do container (a senha e a chave não aparecem na tela):
   - "Postgres clínica (app)", sempre
   - "Groq API" (header Authorization: Bearer ...), só se GROQ_API_KEY estiver no .env
2. Importa workflows/*.json e publica os três workflows.
3. Reinicia o n8n e espera o webhook de produção responder.

Uso: python scripts/configurar_n8n.py
"""
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:5678"
WORKFLOWS = [  # o de erros primeiro: os outros apontam para ele
    ("tratamento_de_erros.json", "TriagemErros0001"),
    ("teste_de_erro.json", "TriagemTesteErr1"),
    ("triagem_de_mensagens.json", "TriagemMsgs00001"),
]


def compose(*args: str, entrada: str | None = None) -> str:
    r = subprocess.run(["docker", "compose", *args], cwd=RAIZ, input=entrada, text=True,
                       encoding="utf-8", capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"falhou: docker compose {' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def ler_env() -> dict[str, str]:
    arquivo = RAIZ / ".env"
    if not arquivo.exists():
        raise SystemExit(".env não encontrado. Rode antes: python scripts/gerar_env.py")
    return dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", arquivo.read_text(encoding="utf-8"), re.M))


def credenciais(env: dict[str, str]) -> list[dict]:
    creds = [{"id": "PgClinicaApp0001", "name": "Postgres clínica (app)", "type": "postgres",
              "data": {"host": "postgres", "port": 5432, "database": "clinica", "user": "app",
                       "password": env["APP_DB_PASSWORD"], "ssl": "disable",
                       "allowUnauthorizedCerts": False, "sshTunnel": False, "maxConnections": 10}}]
    if env.get("GROQ_API_KEY", "").strip():
        creds.append({"id": "GroqApiKey000001", "name": "Groq API", "type": "httpHeaderAuth",
                      "data": {"name": "Authorization", "value": f"Bearer {env['GROQ_API_KEY'].strip()}"}})
    return creds


def esperar(url: str, pronto, limite_s: int = 120) -> None:
    fim = time.time() + limite_s
    while time.time() < fim:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if pronto(r.status, r.read().decode("utf-8", "replace")):
                    return
        except urllib.error.HTTPError as e:
            if pronto(e.code, e.read().decode("utf-8", "replace")):
                return
        except OSError:
            pass
        time.sleep(2)
    raise SystemExit(f"tempo esgotado esperando {url}")


def main() -> None:
    env = ler_env()
    esperar(f"{BASE}/healthz", lambda s, _: s == 200)

    creds = credenciais(env)
    # o JSON com segredos vai pelo stdin direto para um arquivo temporário no container e é apagado em seguida
    compose("exec", "-T", "n8n", "sh", "-c",
            "umask 077; cat > /tmp/cred.json && n8n import:credentials --input=/tmp/cred.json; "
            "s=$?; rm -f /tmp/cred.json; exit $s", entrada=json.dumps(creds))
    print("credenciais:", ", ".join(c["name"] for c in creds))
    if len(creds) == 1:
        print("  GROQ_API_KEY vazia no .env: se a credencial 'Groq API' ainda não existe no n8n, crie pela "
              "interface (Header Auth) ou ponha a chave no .env e rode de novo. Sem ela, mensagens "
              "válidas vão para a revisão humana por erro do LLM.")

    for arquivo, id_wf in WORKFLOWS:
        compose("exec", "-T", "n8n", "n8n", "import:workflow", f"--input=/workflows/{arquivo}")
        compose("exec", "-T", "n8n", "n8n", "publish:workflow", f"--id={id_wf}")
        print(f"importado e publicado: {arquivo}")

    compose("restart", "n8n")
    esperar(f"{BASE}/healthz", lambda s, _: s == 200)
    # o webhook só aceita POST; com o workflow ativo, um GET devolve 404 "Did you mean to make a POST request?"
    esperar(f"{BASE}/webhook/triagem", lambda s, corpo: "Did you mean to make a POST" in corpo)
    print(f"pronto: POST {BASE}/webhook/triagem")


if __name__ == "__main__":
    main()
