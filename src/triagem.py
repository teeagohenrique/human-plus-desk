"""Agente 1: Triagem (intenção + urgência), versão por regras, sem LLM.

Princípios:
- Toda classificação vem com o TRECHO LITERAL do chamado que a motivou.
- Regra "sem trecho, sem campo": urgência acima de baixa exige motivo; intenção
  definida exige motivo.
- A confiança é uma heurística simples, AINDA NÃO calibrada com dados reais.
- A empresa define as regras de urgência de verdade; aqui são um ponto de partida.
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel, model_validator

logger = logging.getLogger(__name__)


Intencao = Literal["falha_sistema", "acesso", "reclamacao", "solicitacao", "duvida", "indefinida"]

# Ordem = desempate quando duas intenções têm o mesmo número de palavras.
PALAVRAS_INTENCAO: dict[str, list[str]] = {
    "falha_sistema": ["travou", "travando", "travamento", "fora do ar", "caiu", "erro",
                      "não abre", "nao abre", "lento", "parou de funcionar", "não funciona"],
    "acesso": ["senha", "acesso", "login", "bloqueado", "não consigo entrar", "nao consigo entrar"],
    "reclamacao": ["absurdo", "inaceitável", "inaceitavel", "péssimo", "pessimo", "cancelar"],
    "solicitacao": ["instalar", "instalação", "instalacao", "liberar", "solicito", "solicitação"],
    "duvida": ["como faço", "como faco", "dúvida", "duvida", "onde fica", "é possível", "e possivel"],
}

# sinal -> (regex, peso). Cada sinal conta uma vez.
SINAIS_URGENCIA: dict[str, tuple[re.Pattern, int]] = {
    "prazo": (re.compile(
        r"até\s+(?:o\s+)?meio[- ]dia|até\s+o\s+fim\s+do\s+dia"
        r"|\b(?:até\s+(?:as\s+|às\s+)?|às\s+|as\s+|das\s+)\d{1,2}\s?(?:h|:)\d{0,2}"
        r"|até\s+(?:amanhã|segunda|terça|quarta|quinta|sexta)"
        r"|(?:até|ainda|para|pra)\s+hoje|hoje\s+ainda|urgente|urgência", re.IGNORECASE), 2),
    "recorrencia": (re.compile(
        r"(?:segunda|terceira|quarta|quinta)\s+vez|de\s+novo|novamente|outra\s+vez"
        r"|mais\s+uma\s+vez|toda\s+semana|todo\s+dia", re.IGNORECASE), 1),
    "processo_critico": (re.compile(
        r"fechamento|fechar\s+o\s+mês|faturamento|folha\s+de\s+pagamento|nota\s+fiscal|auditoria", re.IGNORECASE), 1),
    "muitos_afetados": (re.compile(
        r"\btod[oa]s?\s+(?:a|o|as|os)\s+(?:equipe|time|setor|área|departamento)|\btodos\b(?!\s+os\s+dias)"
        r"|vários\s+usuários|todo\s+mundo", re.IGNORECASE), 2),
    "bloqueio": (re.compile(
        r"sem\s+conseguir\s+trabalhar|não\s+consigo\s+trabalhar|sem\s+poder\s+trabalhar|parad[oa]s?\b", re.IGNORECASE), 1),
    "risco_saida": (re.compile(r"cancelar|trocar\s+de\s+fornecedor|desistir", re.IGNORECASE), 1),
}

LIMIAR_ALTA = 3
LIMIAR_MEDIA = 1


class Motivo(BaseModel):
    sinal: str   # ex.: "prazo", "recorrencia", "palavra_chave"
    trecho: str  # trecho LITERAL do chamado


class Triagem(BaseModel):
    intencao: Intencao
    urgencia: Literal["baixa", "media", "alta"]
    recorrente: bool
    motivos_intencao: list[Motivo]
    motivos_urgencia: list[Motivo]
    pontuacao_urgencia: int
    confianca: Literal["baixa", "media", "alta"]

    @model_validator(mode="after")
    def _sem_trecho_sem_campo(self):
        if self.urgencia != "baixa" and not self.motivos_urgencia:
            raise ValueError("urgência acima de baixa exige ao menos um trecho de motivo")
        if self.intencao != "indefinida" and not self.motivos_intencao:
            raise ValueError("intenção definida exige ao menos um trecho de motivo")
        return self


def _achar_palavras(texto: str, palavras: list[str]) -> list[Motivo]:
    achados = []
    for p in palavras:
        m = re.search(rf"\b{re.escape(p)}\w*", texto, re.IGNORECASE)
        if m:
            achados.append(Motivo(sinal="palavra_chave", trecho=m.group(0)))
    return achados


def triar(texto_mascarado: str) -> Triagem:
    """Classifica o chamado em intenção e urgência.

    Aplica as regras de PALAVRAS_INTENCAO e SINAIS_URGENCIA sobre o texto já mascarado.
    Retorna um objeto Triagem completo com os trechos literais que justificam cada campo.

    Raises:
        ValueError: se o texto estiver vazio ou não for uma string.
    """
    if not texto_mascarado or not isinstance(texto_mascarado, str):
        raise ValueError("texto_mascarado deve ser uma string não vazia")
    logger.info("triagem: classificar chamado de %d caracteres", len(texto_mascarado))
    # Intenção: vence quem tiver mais palavras-chave; empate = ordem do dicionário.
    melhor, melhores_motivos = "indefinida", []
    for intencao, palavras in PALAVRAS_INTENCAO.items():
        motivos = _achar_palavras(texto_mascarado, palavras)
        if len(motivos) > len(melhores_motivos):
            melhor, melhores_motivos = intencao, motivos

    # Urgência: soma dos pesos dos sinais encontrados.
    motivos_urg, pontos, recorrente = [], 0, False
    for sinal, (regex, peso) in SINAIS_URGENCIA.items():
        m = regex.search(texto_mascarado)
        if m:
            motivos_urg.append(Motivo(sinal=sinal, trecho=m.group(0)))
            pontos += peso
            recorrente = recorrente or sinal == "recorrencia"

    urgencia = "alta" if pontos >= LIMIAR_ALTA else "media" if pontos >= LIMIAR_MEDIA else "baixa"

    if melhor == "indefinida":
        confianca = "baixa"
    elif len(melhores_motivos) >= 2:
        confianca = "alta"
    else:
        confianca = "media"

    return Triagem(
        intencao=melhor, urgencia=urgencia, recorrente=recorrente,
        motivos_intencao=melhores_motivos, motivos_urgencia=motivos_urg,
        pontuacao_urgencia=pontos, confianca=confianca,
    )
