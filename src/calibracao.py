"""Calibração: aprende com o que a analista JÁ faz (zero trabalho extra).

Aprende só de duas coisas: qual leitura a Marina escolheu (ou se escreveu a dela)
e se aprovou/editou/rejeitou. Edição NÃO conta como erro de classificação.

Regras (valores iniciais, a ajustar com a equipe; não vêm de pesquisa):
- Poucos dados: não mexe em nada ("Informação insuficiente").
- Reordenar leituras por intenção: só com >= MIN_POR_INTENCAO respostas naquela intenção.
- Propor REDUÇÃO da lista: só com >= MIN_DECISOES respostas, no máximo 1 leitura por vez,
  nunca abaixo de MIN_ATIVAS, e NUNCA se a analista escreve a própria leitura em
  mais de LIMIAR_LIVRE dos casos (sinal de que a lista não cobre a realidade).
- A redução só vale depois que o GESTOR aprova (`aprovar_reducao`), e fica na auditoria.
"""
import json
from pathlib import Path

from pydantic import BaseModel

from src import auditoria
from src.percepcao import LEITURAS

MIN_DECISOES = 30
MIN_POR_INTENCAO = 10
LIMIAR_RARA = 0.05
LIMIAR_LIVRE = 0.20
MIN_ATIVAS = 3


class Proposta(BaseModel):
    leitura: str
    motivo: str


def carregar_config(caminho: Path) -> dict:
    caminho = Path(caminho)
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {"ativas": list(LEITURAS), "aprovacoes": []}


def _respostas(eventos: list[dict]) -> list[dict]:
    """Decisões da analista em que havia leituras para escolher."""
    return [e for e in eventos
            if e["agente"] == "analista" and not e["saida"].get("sem_palpites", False)]


def avaliar(eventos: list[dict], ativas: list[str]) -> dict:
    resp = _respostas(eventos)
    n = len(resp)
    cont = {k: 0 for k in ativas}
    for e in resp:
        k = e["saida"].get("leitura")
        if k in cont:
            cont[k] += 1
    livres = sum(1 for e in resp if e["saida"].get("leitura_livre"))
    return {
        "respostas": n,
        "suficiente": n >= MIN_DECISOES,
        "faltam": max(0, MIN_DECISOES - n),
        "uso": {k: (v / n if n else 0.0) for k, v in cont.items()},
        "contagem": cont,
        "share_livre": livres / n if n else 0.0,
        "livres": livres,
    }


def propor_reducao(eventos: list[dict], config: dict) -> tuple[list[Proposta], str]:
    """Devolve (propostas, explicação). Nunca altera nada: só propõe."""
    ativas = config["ativas"]
    a = avaliar(eventos, ativas)
    if not a["suficiente"]:
        return [], f"Informação insuficiente: {a['respostas']} de {MIN_DECISOES} respostas. Faltam {a['faltam']}."
    if a["share_livre"] > LIMIAR_LIVRE:
        return [], (f"A analista escreveu a própria leitura em {a['share_livre']:.0%} dos casos "
                    f"(limite {LIMIAR_LIVRE:.0%}). A lista pode não cobrir a realidade: não reduzir.")
    if len(ativas) <= MIN_ATIVAS:
        return [], f"A lista já está no mínimo ({MIN_ATIVAS} leituras)."
    rara = min(ativas, key=lambda k: a["uso"][k])
    if a["uso"][rara] < LIMIAR_RARA:
        return [Proposta(leitura=rara, motivo=(
            f"Escolhida em {a['uso'][rara]:.0%} de {a['respostas']} respostas (limite {LIMIAR_RARA:.0%})."))], \
            "Há uma leitura candidata a sair. Precisa da aprovação do gestor."
    return [], "Nenhuma leitura abaixo do limite de uso. Nada a propor."


def aprovar_reducao(caminho_config: Path, leitura: str, gestor: str, log: Path | None = None) -> dict:
    cfg = carregar_config(caminho_config)
    if leitura not in cfg["ativas"]:
        raise ValueError(f"leitura não está ativa: {leitura}")
    if len(cfg["ativas"]) <= MIN_ATIVAS:
        raise ValueError(f"a lista não pode ficar abaixo de {MIN_ATIVAS} leituras")
    cfg["ativas"].remove(leitura)
    cfg["aprovacoes"].append({"leitura_removida": leitura, "gestor": gestor})
    caminho_config = Path(caminho_config)
    caminho_config.parent.mkdir(parents=True, exist_ok=True)
    caminho_config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    if log is not None:
        auditoria.registrar(log, "-", "gestor", {"acao": "remover_leitura", "leitura": leitura, "gestor": gestor},
                            decisao="aprovou")
    return cfg


def reordenar(leituras: list[str], intencao: str, eventos: list[dict], ativas: list[str]) -> list[str]:
    """Filtra pelas leituras ativas e, com dados suficientes NA INTENÇÃO, põe as mais escolhidas antes."""
    base = [k for k in leituras if k in ativas]
    resp = [e for e in _respostas(eventos) if e["saida"].get("intencao") == intencao]
    if len(resp) < MIN_POR_INTENCAO:
        return base  # poucos dados: mantém a ordem original
    cont = {k: sum(1 for e in resp if e["saida"].get("leitura") == k) for k in base}
    return sorted(base, key=lambda k: -cont[k])  # sorted é estável: empate mantém a ordem original
