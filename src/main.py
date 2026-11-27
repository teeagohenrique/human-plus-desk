"""Roda o fluxo v2 (texto): máscara -> triagem -> percepção -> redator -> auditoria.

A IA só SUGERE: toda decisão fica como "pendente" até a analista agir no painel.

Uso:  python -m src.main                                          (demonstração, padrão regras)
      python src/main.py                                          (execução direta também funciona)
      python -m src.main --avaliar                                (avalia gabarito rascunho)
      python -m src.main --avaliar caminho.json --provider regras (avalia com provedor explícito)

GEMINI_API_KEY e GEMINI_MODEL podem vir do .env na raiz (ignorado pelo git).
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# Execução direta (python src/main.py) coloca src/ no sys.path, não a raiz.
# Em import normal (__package__ == "src") este bloco não roda.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import auditoria
from src.config import carregar_env
from src.llm import (
    obter_contador_fallback,
    obter_contador_triagem,
    resolver_provider,
    triagem_com_llm,
    usar_contadores,
    zerar_contadores,
)
from src.mascara import mascarar
from src.pipeline import processar_chamado

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data" / "chamados_simulados.json"
LOG = RAIZ / "data" / "auditoria.jsonl"

ORDEM = {"alta": 0, "media": 1, "baixa": 2}

logger = logging.getLogger(__name__)

def _carregar_env() -> None:
    """Wrapper mantido por compatibilidade; a lógica vive em `src.config`."""
    carregar_env(RAIZ / ".env")


def processar(
    chamado_id: str,
    texto: str,
    log: Path | None = LOG,
    provider: str | None = None,
) -> dict:
    resultado = processar_chamado(texto, provider=provider)
    if log is not None:
        m, t, p, r = resultado.mascara, resultado.triagem, resultado.palpites, resultado.rascunho
        auditoria.registrar(log, chamado_id, "mascara", {"tipos": m.tipos_encontrados, "texto": m.texto})
        auditoria.registrar(log, chamado_id, "triagem", t.model_dump())
        auditoria.registrar(log, chamado_id, "percepcao", {"palpites": [x.model_dump() for x in p]})
        auditoria.registrar(log, chamado_id, "redator", r.model_dump())
    return {"id": chamado_id, "mascara": resultado.mascara, "triagem": resultado.triagem,
            "palpites": resultado.palpites, "rascunho": resultado.rascunho}


def carregar(caminho: Path = DADOS) -> list[dict]:
    chamados: list[dict] = json.loads(Path(caminho).read_text(encoding="utf-8"))["chamados"]
    return chamados


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
    with usar_contadores():
        zerar_contadores()
        acertos_i = acertos_u = 0
        chamados = carregar(caminho)
        for c in chamados:
            m = mascarar(c["texto"])
            t = triagem_com_llm(
                m.texto,
                provider=provider,
                ner_disponivel=m.ner_disponivel,
            )
            g = c["gabarito"]
            ok_i, ok_u = t.intencao == g["intencao"], t.urgencia == g["urgencia"]
            acertos_i += ok_i
            acertos_u += ok_u
            if not (ok_i and ok_u):
                print(f'{c["id"]}: previsto {t.intencao}/{t.urgencia} | gabarito {g["intencao"]}/{g["urgencia"]}')
        n = len(chamados)
        origem = obter_contador_triagem()
        motivos = obter_contador_fallback()
        if n == 0:
            print("Origem: gemini=0 | regras=0 | fallback=0")
            print("Fallbacks: nenhum")
            print("Arquivo: (vazio) | Provider: (vazio) | Intenção: 0/0 (0%) | Urgência: 0/0 (0%)")
            return {"arquivo": Path(caminho).name, "provider": ativo, "n": 0,
                    "acertos_intencao": 0, "acertos_urgencia": 0,
                    "origem": origem, "fallback_motivos": motivos}
    print(f"Origem: gemini={origem['gemini']} | regras={origem['regras']} | fallback={origem['fallback']}")
    detalhes = ", ".join(f"{motivo}={qtd}" for motivo, qtd in motivos.items() if qtd) or "nenhum"
    print(f"Fallbacks: {detalhes}")
    print(f"Arquivo: {Path(caminho).name} | Provider: {ativo} | "
          f"Intenção: {acertos_i}/{n} ({acertos_i/n:.0%}) | "
          f"Urgência: {acertos_u}/{n} ({acertos_u/n:.0%})")
    return {"arquivo": Path(caminho).name, "provider": ativo, "n": n,
            "acertos_intencao": acertos_i, "acertos_urgencia": acertos_u,
            "origem": origem, "fallback_motivos": motivos}


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


def main(argv: list[str] | None = None) -> int:
    """Orquestra a CLI: carrega .env, interpreta os argumentos e executa a ação."""
    _carregar_env()
    args = _parse_args(argv)
    if args.avaliar is not None:
        avaliar(Path(args.avaliar), provider=args.provider)
    else:
        demonstrar(provider=args.provider)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.info("cli: interrompido pelo usuário")
        raise SystemExit(130) from None
    except Exception:
        logger.exception("cli: falha inesperada")
        raise SystemExit(1) from None
