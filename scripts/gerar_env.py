"""Cria o .env a partir do .env.example, trocando cada senha por um valor aleatório.

Uso: python scripts/gerar_env.py
Não sobrescreve um .env que já existe.
"""
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
exemplo, destino = RAIZ / ".env.example", RAIZ / ".env"

if destino.exists():
    raise SystemExit(".env já existe; apague-o antes se quiser gerar outro.")

linhas = []
for linha in exemplo.read_text(encoding="utf-8").splitlines():
    chave, _, valor = linha.partition("=")
    if not linha.startswith("#") and valor.startswith("troque"):
        linha = f"{chave}={secrets.token_urlsafe(32)}"
    linhas.append(linha)

destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
print(f"Criado {destino}")
