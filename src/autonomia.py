"""Portão de autonomia: a IA só age sozinha num contexto ESTREITO depois de provar
taxa de erro <= 1% (com 95% de confiança) E o gestor aprovar. Tudo começa DESLIGADO.

Regras fixas (decisão do projeto, não configurável):
- O ENVIO DE RESPOSTAS AO CLIENTE é sempre da analista. Nunca entra neste portão.
- Só conta como evidência o que um HUMANO confirmou (decisões automáticas não entram).
- Contextos aprovados continuam sendo verificados por amostra; um erro suspende o contexto.
- O gestor pode revogar a qualquer momento. Tudo vai para a auditoria.

Limite superior de erro: Clopper-Pearson unilateral (cálculo estatístico padrão; os números
de corte vêm da conversa com a pessoa dona do projeto, não de pesquisa externa).
Aviso: a urgência NÃO vem pré-selecionada na interface — a analista escolhe
explicitamente. Eventos com `urgencia_automatica` não entram como evidência.
"""
from __future__ import annotations

import json
import zlib
from datetime import UTC, datetime
from math import comb
from pathlib import Path

from src import auditoria

ERRO_MAX = 0.01
ALFA = 0.05                 # 95% de confiança
AMOSTRA_VERIFICACAO = 10    # contexto autônomo: 1 em cada 10 chamados ainda vai para a analista
ACOES_PROIBIDAS = ("enviar_resposta", "enviar_ao_cliente")
ACAO_PERMITIDA = "urgencia"
LIMITE_BUSCA = 5000


def contexto_de(intencao: str, urgencia_ia: str) -> str:
    return f"{ACAO_PERMITIDA}:{intencao}:{urgencia_ia}"


def limite_superior_erro(n: int, k: int, alfa: float = ALFA) -> float:
    """Limite superior unilateral (1-alfa) da taxa de erro com k erros em n casos."""
    if n <= 0 or k >= n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        cdf = sum(comb(n, i) * m**i * (1 - m) ** (n - i) for i in range(k + 1))
        if cdf > alfa:
            lo = m
        else:
            hi = m
    return hi


def casos_necessarios(k: int, erro_max: float = ERRO_MAX) -> int | None:
    """Menor n (com k erros) que prova erro <= erro_max. None se passar do limite de busca."""
    n = k + 1
    while n <= LIMITE_BUSCA:
        if limite_superior_erro(n, k) <= erro_max:
            return n
        n += 1
    return None


def carregar_config(caminho: Path) -> dict:
    caminho = Path(caminho)
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return {"aprovados": [], "suspensos": []}


def _salvar(caminho: Path, cfg: dict) -> None:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _eventos_humanos(eventos: list[dict]) -> list[dict]:
    return [e for e in eventos
            if e["agente"] == "analista" and e["saida"].get("urgencia_analista")
            and not e["saida"].get("urgencia_automatica")]


def _ctx(e: dict) -> str:
    return contexto_de(e["saida"]["intencao"], e["saida"]["urgencia"])


def evidencia(eventos: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for e in _eventos_humanos(eventos):
        c = out.setdefault(_ctx(e), {"n": 0, "erros": 0})
        c["n"] += 1
        c["erros"] += e["saida"]["urgencia_analista"] != e["saida"]["urgencia"]
    return out


def autonomos(config: dict) -> set[str]:
    return {a["contexto"] for a in config["aprovados"]} - {s["contexto"] for s in config["suspensos"]}


def status(eventos: list[dict], config: dict) -> list[dict]:
    ativos, suspensos = autonomos(config), {s["contexto"] for s in config["suspensos"]}
    linhas = []
    for ctx, ev in sorted(evidencia(eventos).items()):
        n, k = ev["n"], ev["erros"]
        lim = limite_superior_erro(n, k)
        if ctx in ativos:
            estado = "autonomo"
        elif ctx in suspensos:
            estado = "suspenso"
        elif lim <= ERRO_MAX:
            estado = "elegivel"
        else:
            estado = "bloqueado"
        nec = casos_necessarios(k)
        linhas.append({"contexto": ctx, "n": n, "erros": k, "limite_erro": lim,
                       "faltam": None if nec is None else max(0, nec - n), "estado": estado})
    return linhas


def aprovar_autonomia(caminho: Path, contexto: str, gestor: str, eventos: list[dict],
                      log: Path | None = None) -> dict:
    """O gestor aprova. O portão recalcula a evidência e NÃO confia na tela."""
    acao = contexto.split(":")[0]
    if acao in ACOES_PROIBIDAS or acao != ACAO_PERMITIDA:
        raise ValueError(f"ação não pode ser autônoma: {acao}")
    cfg = carregar_config(caminho)
    linha = next((item for item in status(eventos, cfg) if item["contexto"] == contexto), None)
    prova = linha is not None and linha["limite_erro"] <= ERRO_MAX
    if not prova or linha["estado"] == "autonomo":
        raise ValueError("contexto não prova erro <= 1% (ou já é autônomo): autonomia negada")
    cfg["suspensos"] = [s for s in cfg["suspensos"] if s["contexto"] != contexto]
    cfg["aprovados"] = [a for a in cfg["aprovados"] if a["contexto"] != contexto]
    cfg["aprovados"].append({"contexto": contexto, "gestor": gestor, "quando": _agora(),
                             "n": linha["n"], "erros": linha["erros"]})
    _salvar(caminho, cfg)
    if log is not None:
        auditoria.registrar(log, "-", "gestor", {"acao": "aprovar_autonomia", "contexto": contexto,
                                                 "gestor": gestor, "n": linha["n"], "erros": linha["erros"]},
                            decisao="aprovou")
    return cfg


def revogar_autonomia(caminho: Path, contexto: str, gestor: str, log: Path | None = None) -> dict:
    cfg = carregar_config(caminho)
    cfg["aprovados"] = [a for a in cfg["aprovados"] if a["contexto"] != contexto]
    _salvar(caminho, cfg)
    if log is not None:
        auditoria.registrar(log, "-", "gestor", {"acao": "revogar_autonomia", "contexto": contexto,
                                                 "gestor": gestor}, decisao="rejeitou")
    return cfg


def reavaliar(caminho: Path, eventos: list[dict], log: Path | None = None) -> list[str]:
    """Suspende contextos aprovados em que um humano discordou DEPOIS da aprovação."""
    cfg = carregar_config(caminho)
    suspensos_agora = []
    for ap in cfg["aprovados"]:
        ctx = ap["contexto"]
        if ctx in {s["contexto"] for s in cfg["suspensos"]}:
            continue
        erro = any(_ctx(e) == ctx and e["quando"] > ap["quando"]
                   and e["saida"]["urgencia_analista"] != e["saida"]["urgencia"]
                   for e in _eventos_humanos(eventos))
        if erro:
            cfg["suspensos"].append({"contexto": ctx, "motivo": "discordância humana após aprovação",
                                     "quando": _agora()})
            suspensos_agora.append(ctx)
            if log is not None:
                auditoria.registrar(log, "-", "sistema", {"acao": "suspender_autonomia", "contexto": ctx},
                                    decisao="rejeitou")
    if suspensos_agora:
        _salvar(caminho, cfg)
    return suspensos_agora


def deve_perguntar(contexto: str, chamado_id: str, config: dict) -> bool:
    """Contexto não autônomo: sempre pergunta. Autônomo: só 1 em AMOSTRA_VERIFICACAO (verificação)."""
    if contexto not in autonomos(config):
        return True
    return zlib.crc32(chamado_id.encode("utf-8")) % AMOSTRA_VERIFICACAO == 0
