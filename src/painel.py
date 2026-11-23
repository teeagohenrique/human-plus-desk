"""Lógica do painel (sem Streamlit, para poder testar e trocar a tela depois).

Fluxo: montar_fila -> analista decide -> registrar_decisao (auditoria) -> metricas.
A IA só sugere; nada é "enviado": a decisão da analista é apenas registrada.
"""
import json
import random
import re
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel

from src import auditoria, llm
from src.mascara import mascarar
from src.percepcao import LEITURAS, Historico, Palpite, perceber
from src.redator import _PLACEHOLDER, Rascunho
from src.triagem import Triagem

ORDEM_URGENCIA = {"alta": 0, "media": 1, "baixa": 2}
DECISOES = ("aprovou", "editou", "rejeitou")
ORIGENS = ("gemini", "regras", "fallback")
# Valor inicial do projeto (não vem de pesquisa): abaixo desta semelhança com a
# sugestão, a resposta é tratada como própria. A equipe pode recalibrar.
LIMIAR_ADAPTACAO = 0.45


class ItemFila(BaseModel):
    id: str
    texto_mascarado: str
    triagem: Triagem
    palpites: list[Palpite]
    rascunho: Rascunho
    origem_triagem: str = "regras"
    origem_rascunho: str = "regras"
    leitura_inicial: str | None = None
    provider_rascunho: str = "regras"


def carregar_historico(caminho: Path) -> dict[str, list[Historico]]:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))["historicos"]
    return {k: [Historico(**h) for h in v] for k, v in dados.items()}


def montar_fila(
    chamados: list[dict],
    historicos: dict[str, list[Historico]],
    provider: str | None = None,
    model: str | None = None,
    ao_avancar: Callable[[int, int, str], None] | None = None,
) -> list[ItemFila]:
    """Monta a fila já mascarada, com triagem e rascunho do provedor escolhido."""
    itens = []
    total_etapas = len(chamados) * 2
    etapa = 0
    for c in chamados:
        m = mascarar(c["texto"])
        t, origem_t = llm.triagem_com_origem(m.texto, provider=provider, model=model)
        etapa += 1
        if ao_avancar is not None:
            ao_avancar(etapa, total_etapas, f"{c['id']}:triagem")
        palpites = perceber(m.texto, t, historicos.get(c["id"], []))
        leitura_inicial = palpites[0].leituras[0] if palpites else None
        r, origem_r = llm.rascunho_com_origem(
            m.texto, t, palpites=palpites, leitura=leitura_inicial,
            provider=provider, model=model,
        )
        etapa += 1
        if ao_avancar is not None:
            ao_avancar(etapa, total_etapas, f"{c['id']}:rascunho")
        itens.append(ItemFila(
            id=c["id"], texto_mascarado=m.texto, triagem=t,
            palpites=palpites, rascunho=r,
            origem_triagem=origem_t, origem_rascunho=origem_r,
            leitura_inicial=leitura_inicial,
            provider_rascunho=llm.resolver_provider(provider),
        ))
    # Mais urgentes primeiro; dentro da urgência, maior pontuação primeiro.
    itens.sort(key=lambda i: (ORDEM_URGENCIA[i.triagem.urgencia], -i.triagem.pontuacao_urgencia, i.id))
    return itens


def rascunho_adaptado(
    item: ItemFila,
    leitura: str | None,
    provider: str | None = None,
    model: str | None = None,
    cache: dict | None = None,
) -> tuple[Rascunho, str]:
    """Rascunho reagindo à leitura escolhida, com cache para não repetir chamadas.

    O Streamlit reexecuta o script a cada interação; sem o cache, trocar a leitura
    ou aprovar um item geraria novas requisições à API. Na leitura inicial, o
    rascunho já foi gerado por `montar_fila` e é reaproveitado — isso evita uma
    segunda chamada por chamado logo ao abrir o painel.
    """
    chave = (item.id, leitura or "", provider or "regras", model or "")
    if cache is not None and chave in cache:
        return cache[chave]
    if leitura == item.leitura_inicial and llm.resolver_provider(provider) == item.provider_rascunho:
        resultado = (item.rascunho, item.origem_rascunho)
    else:
        resultado = llm.rascunho_com_origem(
            item.texto_mascarado, item.triagem, palpites=item.palpites, leitura=leitura,
            provider=provider, model=model,
        )
    if cache is not None:
        cache[chave] = resultado
    return resultado


def leituras_do_item(item: ItemFila, eventos: list[dict], config: dict) -> list[str]:
    """Leituras que a analista vê: só as ativas, reordenadas pelo que ela já escolheu."""
    from src.calibracao import reordenar
    if not item.palpites:
        return []
    return reordenar(item.palpites[0].leituras, item.triagem.intencao, eventos, config["ativas"])


def eventos_analista(eventos: list[dict]) -> list[dict]:
    return [e for e in eventos if e["agente"] == "analista"]


def ids_decididos(eventos: list[dict]) -> set[str]:
    return {e["chamado_id"] for e in eventos_analista(eventos)}


def decisao_por_texto(texto_original: str, texto_final: str) -> str:
    return "aprovou" if texto_final.strip() == texto_original.strip() else "editou"


def _normalizar_resposta(texto: str) -> str:
    """Remove marcadores [..], espaços repetidos e espaço antes de pontuação."""
    limpo = " ".join(_PLACEHOLDER.sub("", texto).split()).lower()
    return re.sub(r"\s+([.,;:!?])", r"\1", limpo)


def classificar_resposta(sugestao: str, resposta: str) -> str:
    """Classifica como a analista respondeu em relação à sugestão da IA.

    - `aprovou`: usou a sugestão (ignorando apenas marcadores e espaços);
    - `editou`: adaptou a sugestão (semelhança >= LIMIAR_ADAPTACAO);
    - `rejeitou`: escreveu resposta própria.
    A decisão é inferida do texto que a analista escreveu, sem clique extra.
    """
    final = _normalizar_resposta(resposta)
    if not final:
        raise ValueError("resposta vazia")
    base = _normalizar_resposta(sugestao)
    if final == base:
        return "aprovou"
    return "editou" if SequenceMatcher(None, base, final).ratio() >= LIMIAR_ADAPTACAO else "rejeitou"


def detalhes_supervisao(item: ItemFila, leitura: str | None, leitura_livre: str | None,
                        urgencia_analista: str | None, rascunho_ia: str,
                        origem_rascunho: str | None = None) -> dict:
    """Pacote serializável do que foi mostrado e decidido, para a supervisão revisar depois.

    Só contém texto já mascarado (chamado, trechos e sugestão da IA).
    """
    def _ev(m) -> dict:
        return {"sinal": m.sinal, "trecho": m.trecho}

    return {
        "origem_triagem": item.origem_triagem,
        "origem_rascunho": origem_rascunho or item.origem_rascunho,
        "urgencia_ia": item.triagem.urgencia,
        "urgencia_analista": urgencia_analista,
        "leitura": leitura,
        "leitura_livre": leitura_livre or None,
        "trechos": [_ev(m) for m in item.triagem.motivos_urgencia + item.triagem.motivos_intencao],
        "hipoteses": [
            {"hipotese": p.hipotese, "confianca": p.confianca, "evidencias": [_ev(e) for e in p.evidencias]}
            for p in item.palpites
        ],
        "rascunho_ia": rascunho_ia,
    }


def registrar_decisao(log: Path, item: ItemFila, decisao: str, texto_final: str | None,
                      leitura: str | None = None, leitura_livre: str | None = None,
                      urgencia_analista: str | None = None, urgencia_automatica: bool = False,
                      origem_triagem: str | None = None, origem_rascunho: str | None = None) -> None:
    if decisao not in DECISOES:
        raise ValueError(f"decisão inválida: {decisao}")
    if urgencia_analista is not None and urgencia_analista not in ORDEM_URGENCIA:
        raise ValueError(f"urgência inválida: {urgencia_analista}")
    auditoria.registrar(
        log, item.id, "analista",
        {"urgencia": item.triagem.urgencia, "intencao": item.triagem.intencao,
         "recorrente": item.triagem.recorrente, "leitura": leitura,
         "leitura_livre": (leitura_livre or None), "sem_palpites": not item.palpites,
         "confianca_triagem": item.triagem.confianca, "urgencia_analista": urgencia_analista,
         "urgencia_automatica": urgencia_automatica,
         "origem_triagem": origem_triagem or item.origem_triagem,
         "origem_rascunho": origem_rascunho or item.origem_rascunho},
        decisao=decisao, texto_final=texto_final,
    )


def metricas(eventos: list[dict]) -> dict:
    ev = eventos_analista(eventos)
    total = len(ev)
    decisoes = Counter(e["decisao_analista"] for e in ev)
    por_urgencia: dict[str, Counter] = {u: Counter() for u in ORDEM_URGENCIA}
    for e in ev:
        por_urgencia[e["saida"]["urgencia"]][e["decisao_analista"]] += 1
    leituras = Counter(e["saida"]["leitura"] for e in ev if e["saida"].get("leitura"))
    livres = sum(1 for e in ev if e["saida"].get("leitura_livre"))
    por_dia = Counter(e["quando"][:10] for e in ev)
    return {
        "total": total,
        "decisoes": {d: decisoes.get(d, 0) for d in DECISOES},
        "taxa_edicao": decisoes.get("editou", 0) / total if total else 0.0,
        "taxa_rejeicao": decisoes.get("rejeitou", 0) / total if total else 0.0,
        "por_urgencia": {u: {d: c.get(d, 0) for d in DECISOES} for u, c in por_urgencia.items()},
        "leituras": dict(leituras),
        "leituras_livres": livres,
        "recorrentes": sum(1 for e in ev if e["saida"].get("recorrente")),
        "por_dia": dict(sorted(por_dia.items())),
    }


def calibracao_triagem(eventos: list[dict]) -> dict:
    """Compara a urgência sugerida pela IA com a que a analista confirmou ou mudou."""
    ev = [e for e in eventos_analista(eventos) if e["saida"].get("urgencia_analista") and not e["saida"].get("urgencia_automatica")]
    rank = ORDEM_URGENCIA  # menor número = mais urgente
    por_conf: dict[str, dict] = {}
    matriz = {u: {v: 0 for v in ORDEM_URGENCIA} for u in ORDEM_URGENCIA}
    concordou = subiu = desceu = 0
    for e in ev:
        s = e["saida"]
        ia, an = s["urgencia"], s["urgencia_analista"]
        c = por_conf.setdefault(s.get("confianca_triagem", "desconhecida"), {"n": 0, "concordou": 0})
        c["n"] += 1
        matriz[ia][an] += 1
        if ia == an:
            concordou += 1
            c["concordou"] += 1
        elif rank[an] < rank[ia]:
            subiu += 1   # a analista achou MAIS urgente que a IA (o erro mais perigoso)
        else:
            desceu += 1
    for c in por_conf.values():
        c["taxa"] = c["concordou"] / c["n"]
    n = len(ev)
    return {"n": n, "concordancia": concordou / n if n else 0.0, "subiu": subiu, "desceu": desceu,
            "por_confianca": por_conf, "matriz": matriz}


def _urgencia_simulada(rng, ia: str) -> str:
    if rng.random() < 0.8:
        return ia
    niveis = list(ORDEM_URGENCIA)  # alta, media, baixa
    i = niveis.index(ia) + rng.choice([-1, 1])
    return niveis[min(max(i, 0), 2)]


def gerar_simulado(caminho: Path, itens: list[ItemFila], n: int = 60, semente: int = 7) -> None:
    """Gera decisões INVENTADAS (marcadas com simulado=True) só para ver os gráficos."""
    rng = random.Random(semente)
    agora = datetime.now(UTC)
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as f:
        for _ in range(n):
            item = rng.choice(itens)
            decisao = rng.choices(DECISOES, weights=[45, 40, 15])[0]
            leitura = None
            if item.palpites and decisao != "rejeitou":
                leitura = item.palpites[0].leituras[0] if rng.random() < 0.6 else rng.choice(list(LEITURAS))
            quando = agora - timedelta(days=rng.randint(0, 6), minutes=rng.randint(0, 600))
            f.write(json.dumps({
                "quando": quando.isoformat(), "chamado_id": item.id, "agente": "analista",
                "saida": {"urgencia": item.triagem.urgencia, "intencao": item.triagem.intencao,
                          "recorrente": item.triagem.recorrente, "leitura": leitura, "leitura_livre": None,
                          "sem_palpites": not item.palpites,
                          "confianca_triagem": item.triagem.confianca,
                          "urgencia_analista": _urgencia_simulada(rng, item.triagem.urgencia)},
                "decisao_analista": decisao, "texto_final": None, "simulado": True,
            }, ensure_ascii=False) + "\n")
