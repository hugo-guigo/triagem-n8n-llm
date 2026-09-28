"""Avalia o fluxo de ponta a ponta: dispara o conjunto de teste no webhook e compara com o esperado.

Cada rodada usa ids novos (prefixo avAAAAMMDDhhmmss), então dá para rodar de novo sem esbarrar
na checagem de duplicata. Categoria, destino, latência e tokens vêm do log do próprio fluxo
(tabela execucoes), que é a fonte de verdade da observabilidade.

Uso (com os containers rodando):
  python scripts/avaliar.py                  # 8 s entre chamadas ao LLM (limite grátis do Groq)
  python scripts/avaliar.py --intervalo 0    # sem pausa (vai bater no limite de taxa)

Gera resultados/avaliacao.md (resumo) e resultados/avaliacao.csv (caso a caso).
"""
import argparse
import csv
import io
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enviar import URL_PADRAO, enviar  # noqa: E402
from metricas import aceita, matriz_confusao, media, percentil, taxa  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CATEGORIAS = ["agendamento", "cancelamento", "reclamacao", "duvida", "outro"]


def corpo_do_caso(caso: dict, id_mensagem: str) -> dict:
    if "corpo" in caso:  # casos inválidos trazem o corpo pronto
        return {"id_mensagem": id_mensagem, **caso["corpo"]}
    return {"id_mensagem": id_mensagem, "nome": caso["nome"], "canal": caso["canal"], "texto": caso["texto"]}


def ler_log(prefixo: str) -> dict[str, dict]:
    """Linhas de execucoes desta rodada, por id_mensagem. Fica a PRIMEIRA execução de cada id:
    o reenvio do teste de idempotência gera uma segunda linha (duplicada) que não entra na nota."""
    sql = ("SELECT id_mensagem, destino, categoria, urgencia, confianca, handoff, erro, modelo, "
           "latencia_llm_ms, latencia_ms, tokens_entrada, tokens_saida FROM execucoes "
           f"WHERE id_mensagem LIKE '{prefixo}-%' ORDER BY id")
    saida = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "admin", "-d", "clinica", "--csv", "-c", sql],
        cwd=RAIZ, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    linhas = {}
    for r in csv.DictReader(io.StringIO(saida)):
        for k in ["confianca"]:
            r[k] = float(r[k]) if r[k] else None
        for k in ["latencia_llm_ms", "latencia_ms", "tokens_entrada", "tokens_saida"]:
            r[k] = int(r[k]) if r[k] else None
        r["handoff"] = r["handoff"] == "t"
        linhas.setdefault(r["id_mensagem"], r)
    return linhas


def fmt(x, casas=0, sufixo=""):
    if x is None:
        return "n/d"
    return f"{x:.{casas}f}{sufixo}" if casas else f"{round(x)}{sufixo}"


def pct(x):
    return "n/d" if x is None else f"{100 * x:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=URL_PADRAO)
    ap.add_argument("--intervalo", type=float, default=8.0, help="segundos entre chamadas que usam o LLM")
    ap.add_argument("--dados", type=Path, default=RAIZ / "dados" / "mensagens_teste.json")
    args = ap.parse_args()

    casos = json.loads(args.dados.read_text(encoding="utf-8"))["casos"]
    prefixo = "av" + datetime.now().strftime("%Y%m%d%H%M%S")
    print(f"Rodada {prefixo}: {len(casos)} casos")

    respostas = {}
    chamou_llm = False
    for caso in casos:
        idm = f"{prefixo}-{caso['id']}"
        usa_llm = caso["esperado"]["destino"] != "invalido"
        if usa_llm and chamou_llm:
            time.sleep(args.intervalo)
        chamou_llm = chamou_llm or usa_llm
        status, texto, ms = enviar(json.dumps(corpo_do_caso(caso, idm)).encode(), args.url, timeout=120)
        try:
            corpo = json.loads(texto)
        except json.JSONDecodeError:
            corpo = {}
        respostas[idm] = {"http": status, "ms_cliente": ms, "corpo": corpo}
        print(f"  {caso['id']:<3} HTTP {status} {ms:6.0f} ms  destino={corpo.get('destino', '-')}")

    # idempotência: reenviar o primeiro caso válido tem de voltar "duplicada", sem chamar o LLM
    primeiro = next(c for c in casos if "corpo" not in c)
    st, texto, ms_dup = enviar(json.dumps(corpo_do_caso(primeiro, f"{prefixo}-{primeiro['id']}")).encode(), args.url)
    idempotente = st == 200 and json.loads(texto).get("status") == "duplicada"
    print(f"  reenvio de {primeiro['id']}: {'duplicada (ok)' if idempotente else 'FALHOU'} em {ms_dup:.0f} ms")

    time.sleep(1)  # dá tempo do último INSERT no log
    log = ler_log(prefixo)

    linhas = []
    for caso in casos:
        idm = f"{prefixo}-{caso['id']}"
        esp, r, lg = caso["esperado"], respostas[idm], log.get(idm, {})
        destino = lg.get("destino") or r["corpo"].get("destino")
        categoria = lg.get("categoria") or None
        linhas.append({
            "caso": caso["id"], "texto": caso.get("texto", json.dumps(caso.get("corpo"), ensure_ascii=False)),
            "categoria_esperada": esp.get("categoria"), "categoria_obtida": categoria,
            "acertou_categoria": None if not esp.get("categoria") else aceita(esp["categoria"], categoria),
            "destino_esperado": esp["destino"], "destino_obtido": destino,
            "acertou_destino": aceita(esp["destino"], destino),
            "http": r["http"], "confianca": lg.get("confianca"), "urgencia": lg.get("urgencia"),
            "erro": lg.get("erro"), "latencia_ms": lg.get("latencia_ms"), "latencia_llm_ms": lg.get("latencia_llm_ms"),
            "tokens_entrada": lg.get("tokens_entrada"), "tokens_saida": lg.get("tokens_saida"), "modelo": lg.get("modelo"),
            "nota": caso.get("nota", ""),
        })

    com_cat = [l for l in linhas if l["acertou_categoria"] is not None]
    acertos_cat = sum(l["acertou_categoria"] for l in com_cat)
    acertos_dest = sum(l["acertou_destino"] for l in linhas)
    llm = [l for l in linhas if l["latencia_llm_ms"] is not None]
    handoffs = [l for l in linhas if l["destino_obtido"] == "revisao"]
    falhas_llm = [l for l in linhas if (l["erro"] or "").startswith("erro na API do LLM")]
    conf_certo = media([l["confianca"] for l in com_cat if l["acertou_categoria"]])
    conf_errado = media([l["confianca"] for l in com_cat if not l["acertou_categoria"]])
    lat = [l["latencia_ms"] for l in llm]
    tin = [l["tokens_entrada"] for l in llm]
    tout = [l["tokens_saida"] for l in llm]

    def primeira(c):  # para a matriz, uma categoria esperada aceita vira a que o modelo deu, se estiver na lista
        e = c["categoria_esperada"]
        return (c["categoria_obtida"] if isinstance(e, list) and c["categoria_obtida"] in e else
                (e[0] if isinstance(e, list) else e))
    matriz = matriz_confusao([(primeira(l), l["categoria_obtida"] or "(sem)") for l in com_cat])

    md = [
        f"# Avaliação do fluxo ({datetime.now():%d/%m/%Y %H:%M})",
        "",
        f"Rodada `{prefixo}`, {len(casos)} mensagens fictícias de `dados/mensagens_teste.json`, "
        f"modelo `{next((l['modelo'] for l in llm if l['modelo']), 'n/d')}` pelo Groq (plano grátis), "
        f"{args.intervalo:g} s entre chamadas.",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| Categoria correta (casos não ambíguos que passaram pelo LLM) | {acertos_cat}/{len(com_cat)} ({pct(taxa(acertos_cat, len(com_cat)))}) |",
        f"| Destino correto (CRM, alerta, revisão, resposta, 400) | {acertos_dest}/{len(linhas)} ({pct(taxa(acertos_dest, len(linhas)))}) |",
        f"| Mandadas para revisão humana (handoff) | {len(handoffs)} ({sum(1 for l in handoffs if aceita(l['destino_esperado'], 'revisao'))} esperadas) |",
        f"| Falhas do LLM depois do retry | {len(falhas_llm)} |",
        f"| Reenvio do mesmo id_mensagem | {'devolveu duplicada, sem chamar o LLM' if idempotente else 'NÃO devolveu duplicada'} ({ms_dup:.0f} ms) |",
        f"| Latência de ponta a ponta com LLM (média / p50 / p95 / máx.) | {fmt(media(lat))} / {fmt(percentil(lat, .5))} / {fmt(percentil(lat, .95))} / {fmt(max(lat) if lat else None)} ms |",
        f"| Tokens por mensagem (entrada / saída, média) | {fmt(media(tin))} / {fmt(media(tout))} |",
        f"| Tokens na rodada | {sum(x or 0 for x in tin) + sum(x or 0 for x in tout)} |",
        f"| Confiança média quando acertou / quando errou | {fmt(conf_certo, 2)} / {fmt(conf_errado, 2)} |",
        "",
        "## Matriz de confusão da categoria (linha = esperada, coluna = obtida)",
        "",
        "| esperada \\ obtida | " + " | ".join(CATEGORIAS) + " |",
        "|---|" + "---|" * len(CATEGORIAS),
    ]
    for e in CATEGORIAS:
        md.append(f"| {e} | " + " | ".join(str(matriz.get((e, o), 0) or "·") for o in CATEGORIAS) + " |")
    erradas = [l for l in linhas if not l["acertou_destino"] or l["acertou_categoria"] is False]
    md += ["", "## Casos que erraram", ""]
    if not erradas:
        md.append("Nenhum.")
    for l in erradas:
        md.append(f"- **{l['caso']}** \"{l['texto'][:90]}\": esperado {l['categoria_esperada']} -> {l['destino_esperado']}, "
                  f"obtido {l['categoria_obtida']} -> {l['destino_obtido']} (confiança {l['confianca']})")

    pasta = RAIZ / "resultados"
    pasta.mkdir(exist_ok=True)
    (pasta / "avaliacao.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    with open(pasta / "avaliacao.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        for l in linhas:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v) for k, v in l.items()})
    print()
    print("\n".join(md))


if __name__ == "__main__":
    main()
