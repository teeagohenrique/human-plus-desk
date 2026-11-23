"""Roda o fluxo v2 (texto): máscara -> triagem -> percepção -> redator -> auditoria.

A IA só SUGERE: toda decisão fica como "pendente" até a analista agir no painel.

Uso:  python -m src.main                                          (demonstração, padrão regras)
      python -m src.main --avaliar                                (avalia gabarito rascunho)
      python -m src.main --avaliar caminho.json --provider regras (avalia com provedor explícito)
"""
import argparse
import json
from pathlib import Path

from src import auditoria
from src.llm import rascunho_com_llm, resolver_provider, triagem_com_llm
from src.mascara import mascarar
from src.percepcao import perceber

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data" / "chamados_simulados.json"
LOG = RAIZ / "data" / "auditoria.jsonl"

ORDEM = {"alta": 0, "media": 1, "baixa": 2}


def processar(
    chamado_id: str,
    texto: str,
    log: Path | None = LOG,
    provider: str | None = None,
) -> dict:
    m = mascarar(texto)
    t = triagem_com_llm(m.texto, provider=provider)
    p = perceber(m.texto, t)
    leitura_inicial = p[0].leituras[0] if p else None
    r = rascunho_com_llm(m.texto, t, palpites=p, leitura=leitura_inicial, provider=provider)
    if log is not None:
        auditoria.registrar(log, chamado_id, "mascara", {"tipos": m.tipos_encontrados, "texto": m.texto})
        auditoria.registrar(log, chamado_id, "triagem", t.model_dump())
        auditoria.registrar(log, chamado_id, "percepcao", {"palpites": [x.model_dump() for x in p]})
        auditoria.registrar(log, chamado_id, "redator", r.model_dump())
    return {"id": chamado_id, "mascara": m, "triagem": t, "palpites": p, "rascunho": r}


def carregar(caminho: Path = DADOS) -> list[dict]:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))["chamados"]


def demonstrar(provider: str | None = None) -> None:
    ativo = resolver_provider(provider)
    resultados = [processar(c["id"], c["texto"], provider=provider) for c in carregar()]
    resultados.sort(key=lambda x: ORDEM[x["triagem"].urgencia])  # fila: mais urgentes primeiro
    for x in resultados:
        t = x["triagem"]
        print(f"\n=== {x['id']} | urgência {t.urgencia.upper()} ({t.pontuacao_urgencia} pts) | "
              f"{t.intencao} (confiança {t.confianca}) | provider={ativo}")
        print("  texto mascarado:", x["mascara"].texto)
        for mo in t.motivos_urgencia:
            print(f'  porquê [{mo.sinal}]: "{mo.trecho}"')
        for pa in x["palpites"]:
            print(f'  palpite [{pa.tipo} | {pa.confianca}]: {pa.hipotese}')
        print("  rascunho (SUGESTÃO, a analista decide):", x["rascunho"].texto)
        print("  guardrail:", "ok" if x["rascunho"].passou_guardrail else x["rascunho"].feedback_guardrail)
    print(f"\nLog gravado em {LOG}")


def avaliar(caminho: Path = DADOS, provider: str | None = None) -> dict:
    ativo = resolver_provider(provider)
    acertos_i = acertos_u = 0
    chamados = carregar(caminho)
    for c in chamados:
        t = triagem_com_llm(mascarar(c["texto"]).texto, provider=provider)
        g = c["gabarito"]
        ok_i, ok_u = t.intencao == g["intencao"], t.urgencia == g["urgencia"]
        acertos_i += ok_i
        acertos_u += ok_u
        if not (ok_i and ok_u):
            print(f'{c["id"]}: previsto {t.intencao}/{t.urgencia} | gabarito {g["intencao"]}/{g["urgencia"]}')
    n = len(chamados)
    print(f"Arquivo: {Path(caminho).name} | Provider: {ativo} | "
          f"Intenção: {acertos_i}/{n} ({acertos_i/n:.0%}) | "
          f"Urgência: {acertos_u}/{n} ({acertos_u/n:.0%})")
    return {"arquivo": Path(caminho).name, "provider": ativo, "n": n,
            "acertos_intencao": acertos_i, "acertos_urgencia": acertos_u}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Human + Desk CLI")
    parser.add_argument(
        "--avaliar",
        nargs="?",
        const=str(DADOS),
        default=None,
        help="Compara com o gabarito do arquivo JSON (padrão: data/chamados_simulados.json)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="Adaptador de IA: regras (padrão) ou gemini",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    if args.avaliar is not None:
        avaliar(Path(args.avaliar), provider=args.provider)
    else:
        demonstrar(provider=args.provider)
