"""Exporta os workflows do n8n para workflows/<nome>.json, sem metadados da instância.

O export do n8n traz datas, ids de versão e o projeto do dono (com nome e email da conta).
Nada disso importa para quem vai importar o workflow, e só geraria diffs e dados pessoais
no repositório. Este script mantém só o que define o workflow.

Uso (com os containers rodando): python scripts/exportar_workflows.py
"""
import json
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "workflows"
BRUTO = "_export_bruto.json"
CAMPOS = ["id", "name", "nodes", "connections", "settings", "pinData"]


def nome_arquivo(nome: str) -> str:
    """'Triagem de mensagens' -> 'triagem_de_mensagens.json'"""
    ascii_ = nome.lower().encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_).strip("_") + ".json"


def main() -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "n8n", "n8n", "export:workflow",
         "--all", "--pretty", f"--output=/workflows/{BRUTO}"],
        cwd=RAIZ, check=True,
    )
    bruto = PASTA / BRUTO
    try:
        for wf in json.loads(bruto.read_text(encoding="utf-8")):
            limpo = {k: wf[k] for k in CAMPOS if k in wf}
            limpo["active"] = False  # quem importar publica quando tiver as credenciais
            destino = PASTA / nome_arquivo(wf["name"])
            destino.write_text(json.dumps(limpo, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
            print(f"{wf['name']} -> {destino.relative_to(RAIZ)}")
    finally:
        bruto.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
