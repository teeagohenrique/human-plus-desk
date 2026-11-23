"""Agente 2: Percepção (v1, por regras). Gera até 3 PALPITES, nunca diagnósticos.

Cada palpite tem: hipótese em tom de dúvida, evidências (trechos literais),
confiança, pergunta que a analista pode fazer para confirmar e ~5 "leituras"
alternativas (a analista escolhe uma ou escreve a sua; ver `LEITURAS`).

Regras de ouro:
- Sem evidência, sem palpite.
- Fala do TEXTO e do HISTÓRICO, nunca da pessoa (sem rótulos).
- Não muda a urgência da triagem: apenas SUGERE subir (`sugere_subir_urgencia`).
"""
from typing import Literal

from pydantic import BaseModel, Field

from src.redator import _ROTULO
from src.triagem import Motivo, Triagem, triar

MAX_PALPITES = 3
JANELA_DIAS = 14  # janela do histórico (referência B2B citada na pesquisa; ajustável)

# As 5 leituras iniciais. Reduzir a lista depende de regra + aprovação do gestor.
LEITURAS = {
    "pressa_prazo": "Pressão de prazo",
    "cansaco_repeticao": "Cansaço com a repetição do problema",
    "perda_de_confianca": "Perda de confiança no serviço",
    "inseguranca_solucao": "Insegurança sobre a solução",
    "duvida_de_uso": "Dúvida de uso, não falha",
}

# Sinais da triagem que sustentam cada interpretação (espelha as regras de `_leituras`).
# Interpretação sem sinal associado não tem trecho de apoio: a tela avisa a analista.
SINAIS_DA_LEITURA = {
    "pressa_prazo": ("prazo", "bloqueio"),
    "cansaco_repeticao": ("recorrencia",),
    "perda_de_confianca": ("recorrencia", "risco_saida"),
    "inseguranca_solucao": (),
    "duvida_de_uso": (),
}

_CONF = {"baixa": 0, "media": 1, "alta": 2}


class Historico(BaseModel):
    chamado_id: str
    texto_mascarado: str
    dias_atras: int


class Palpite(BaseModel):
    tipo: Literal["necessidade_nao_dita", "padrao", "risco_recorrencia"]
    hipotese: str
    evidencias: list[Motivo] = Field(min_length=1)  # sem evidência, sem palpite
    confianca: Literal["baixa", "media", "alta"]
    pergunta_confirmacao: str
    leituras: list[str]  # ids de LEITURAS, mais prováveis primeiro (até 5)
    sugere_subir_urgencia: bool = False


def _leituras(sinais: set[str], pelo_historico: bool) -> list[str]:
    pontos = {k: 0 for k in LEITURAS}
    if "prazo" in sinais:
        pontos["pressa_prazo"] += 2
    if "recorrencia" in sinais or pelo_historico:
        pontos["cansaco_repeticao"] += 2
        pontos["perda_de_confianca"] += 1
    if "risco_saida" in sinais:
        pontos["perda_de_confianca"] += 2
    if "bloqueio" in sinais:
        pontos["pressa_prazo"] += 1
    ordem = list(LEITURAS)  # desempate: ordem fixa
    return sorted(ordem, key=lambda k: -pontos[k])[:5]


def _historico_mesma_intencao(triagem: Triagem, historico: list[Historico]) -> list[tuple[Historico, Motivo]]:
    achados = []
    if triagem.intencao == "indefinida":
        return achados
    for h in historico:
        if h.dias_atras > JANELA_DIAS:
            continue
        passado = triar(h.texto_mascarado)
        if passado.intencao == triagem.intencao and passado.motivos_intencao:
            m = passado.motivos_intencao[0]
            achados.append((h, Motivo(sinal=f"historico:{h.chamado_id}", trecho=m.trecho)))
    return achados


def perceber(texto_mascarado: str, triagem: Triagem, historico: list[Historico] | None = None) -> list[Palpite]:
    historico = historico or []
    sinais = {m.sinal for m in triagem.motivos_urgencia}
    palpites: list[Palpite] = []
    prev = _historico_mesma_intencao(triagem, historico)

    # 1) Necessidade não dita: tem prazo e não pede solução provisória
    prazo = next((m for m in triagem.motivos_urgencia if m.sinal == "prazo"), None)
    if prazo and "provisór" not in texto_mascarado.lower() and "alternativ" not in texto_mascarado.lower():
        palpites.append(Palpite(
            tipo="necessidade_nao_dita",
            hipotese="Pode ser que, além da correção, ajude uma solução provisória para cumprir o prazo mencionado.",
            evidencias=[prazo], confianca="media",
            pergunta_confirmacao="Existe um caminho provisório que ajudaria a cumprir esse prazo antes da correção definitiva?",
            leituras=_leituras(sinais, bool(prev)),
        ))

    # 2) Padrão entre chamados: 2+ chamados anteriores com a mesma intenção na janela
    if len(prev) >= 2:
        palpites.append(Palpite(
            tipo="padrao",
            hipotese=f"Pode não ser um caso isolado: há {len(prev)} chamados parecidos nos últimos {JANELA_DIAS} dias.",
            evidencias=[m for _, m in prev],
            confianca="alta" if len(prev) >= 3 else "media",
            pergunta_confirmacao="Esses chamados podem ter a mesma causa? Vale investigar a raiz em vez de tratar cada um?",
            leituras=_leituras(sinais, True),
        ))

    # 3) Risco de recorrência / relacionamento (sugere subir urgência; quem decide é a analista)
    ev = [m for m in triagem.motivos_urgencia if m.sinal in ("recorrencia", "risco_saida")] + [m for _, m in prev]
    if ev:
        forte = ("recorrencia" in sinais or "risco_saida" in sinais) and bool(prev)
        palpites.append(Palpite(
            tipo="risco_recorrencia",
            hipotese="Parece que a repetição pode estar pesando na relação com o serviço; uma resposta padrão talvez não baste.",
            evidencias=ev, confianca="media" if forte else "baixa",
            pergunta_confirmacao="Faz sentido tratar este caso com prioridade maior e avisar que o histórico foi considerado?",
            leituras=_leituras(sinais, bool(prev)),
            sugere_subir_urgencia=True,
        ))

    palpites.sort(key=lambda p: -_CONF[p.confianca])
    palpites = palpites[:MAX_PALPITES]
    for p in palpites:  # guardrail: nada de rótulo sobre a pessoa
        assert not _ROTULO.search(p.hipotese), p.hipotese
    return palpites


def trechos_da_leitura(leitura: str, triagem: Triagem, palpites: list[Palpite]) -> list[Motivo]:
    """Trechos literais do chamado que sustentam uma interpretação.

    Garante que interpretação e evidência trabalhem juntas: o que a analista vê
    como apoio vem sempre do texto (ou do histórico), nunca de inferência solta.
    """
    sinais = SINAIS_DA_LEITURA.get(leitura, ())
    achados = [m for m in triagem.motivos_urgencia if m.sinal in sinais]
    if leitura in ("cansaco_repeticao", "perda_de_confianca"):
        achados += [e for p in palpites for e in p.evidencias if e.sinal.startswith("historico:")]
    if leitura == "duvida_de_uso" and triagem.intencao == "duvida":
        achados += list(triagem.motivos_intencao)
    unicos: dict[tuple[str, str], Motivo] = {}
    for m in achados:
        unicos.setdefault((m.sinal, m.trecho), m)
    return list(unicos.values())
