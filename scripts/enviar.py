"""Envia uma mensagem de teste ao webhook e mostra o status HTTP e a resposta.

Uso:
  python scripts/enviar.py exemplos/valida.json
  python scripts/enviar.py exemplos/valida.json --url http://127.0.0.1:5678/webhook-test/triagem

Sem dependências: só a biblioteca padrão.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 127.0.0.1 e não localhost: no Windows, localhost tenta IPv6 (::1) primeiro e perde ~2 s até cair no IPv4
URL_PADRAO = "http://127.0.0.1:5678/webhook/triagem"


def enviar(corpo: bytes, url: str = URL_PADRAO, timeout: float = 60) -> tuple[int, str, float]:
    """POST no webhook. Devolve (status HTTP, corpo da resposta, latência em ms)."""
    req = urllib.request.Request(
        url, data=corpo, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, texto = resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:  # 4xx e 5xx também têm corpo
        status, texto = err.code, err.read().decode("utf-8")
    return status, texto, (time.perf_counter() - t0) * 1000


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arquivo", type=Path, help="arquivo com o corpo do POST (enviado como está)")
    p.add_argument("--url", default=URL_PADRAO)
    args = p.parse_args()

    status, texto, ms = enviar(args.arquivo.read_bytes(), args.url)
    print(f"HTTP {status} em {ms:.0f} ms")
    try:
        print(json.dumps(json.loads(texto), ensure_ascii=False, indent=2))
    except json.JSONDecodeError:
        print(texto or "(corpo vazio)")
    sys.exit(0 if status < 500 else 1)


if __name__ == "__main__":
    main()
