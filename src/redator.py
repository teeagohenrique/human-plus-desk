"""Agente 3: Redator. Gera um RASCUNHO no estilo OARS; quem decide é a analista.

OARS (adaptado de Miller & Rollnick, entrevista motivacional; a adaptação ao
service desk é decisão deste projeto): pergunta aberta, afirmação, reflexão, resumo.

Guardrail (função `validar_rascunho`): bloqueia
  1. prazo/compromisso prometido pela IA (a analista preenche);
  2. rótulo sobre a pessoa ("você está nervoso");
  3. números/fatos que não estão no chamado;
  4. dado pessoal sem máscara.
"""
import re

from pydantic import BaseModel

from src.mascara import mascarar
from src.triagem import Triagem

PEND_PRAZO = "[PRAZO DE RETORNO: a analista preenche]"
PEND_PROVISORIA = "[SOLUÇÃO PROVISÓRIA, se houver: a analista preenche]"

_PLACEHOLDER = re.compile(r"\[[^\]]*\]")
_PROMESSA = re.compile(
    r"\b(?:retorno|retornamos|resolvo|resolvemos|entrego|entregamos|normalizo|normalizamos|envio|enviamos)\b"
    r"[^.!?]{0,40}\b(?:até|em|às|as|hoje|amanhã)\b"
    r"|\b(?:garanto|prometo|sem falta|com certeza)\b"
    r"|\bdaqui\s+a\b|\bem\s+\d+\s*(?:min|minutos|hora|horas)\b",
    re.IGNORECASE,
)
_ROTULO = re.compile(
    r"\b(?:você|vc|o cliente|ele|ela)\s+(?:é|está|foi|estava)\s+(?:muito\s+|bem\s+)?"
    r"(?:nervos|ansios|agressiv|irritad|estressad|rud|impacient|grosse|furios|raivos)\w*"
    r"|\bpessoa\s+(?:nervos|ansios|agressiv|irritad|estressad)\w*",
    re.IGNORECASE,
)

PERGUNTAS = {
    "falha_sistema": "Aparece alguma mensagem de erro na tela quando isso acontece?",
    "acesso": "Qual sistema ou pasta você está tentando acessar?",
    "reclamacao": "O que, na sua visão, seria mais importante resolver primeiro?",
    "solicitacao": "Pode me contar um pouco mais sobre o que você precisa?",
    "duvida": "Em que ponto exato você ficou com dúvida?",
    "indefinida": "Pode me contar um pouco mais sobre o que aconteceu?",
}
RESUMOS = {
    "falha_sistema": "um problema de funcionamento no sistema",
    "acesso": "uma questão de acesso",
    "reclamacao": "uma insatisfação com o atendimento",
    "solicitacao": "uma solicitação",
    "duvida": "uma dúvida de uso",
}
REFLEXOES_LEITURA = {
    "pressa_prazo": "Entendo que o prazo aqui é apertado e que isso traz urgência para resolver.",
    "cansaco_repeticao": "Entendo o desgaste de precisar reportar a mesma situação mais de uma vez.",
    "perda_de_confianca": "Entendo que esse histórico pode abalar a confiança no serviço, e quero conduzir este caso com clareza.",
    "inseguranca_solucao": "Quero deixar cada passo transparente para que você acompanhe a solução com segurança.",
    "duvida_de_uso": "Vamos esclarecer esse ponto passo a passo para facilitar o uso.",
}


class Rascunho(BaseModel):
    texto: str
    pendencias: list[str]
    passou_guardrail: bool
    feedback_guardrail: str


def validar_rascunho(texto: str, chamado_mascarado: str) -> tuple[bool, str]:
    """Mesmo contrato do guardrail do CrewAI: (True, texto) ou (False, feedback)."""
    sem_pend = _PLACEHOLDER.sub("", texto)

    if _PROMESSA.search(sem_pend):
        return False, "Há promessa de prazo ou compromisso. Deixe o prazo para a analista preencher."
    if _ROTULO.search(sem_pend):
        return False, "Há rótulo sobre a pessoa. Descreva sinais do texto, nunca a pessoa."
    nums_chamado = set(re.findall(r"\d+", chamado_mascarado))
    estranhos = [n for n in re.findall(r"\d+", sem_pend) if n not in nums_chamado]
    if estranhos:
        return False, f"Números que não constam no chamado: {estranhos}."
    if mascarar(sem_pend).tipos_encontrados:
        return False, "Há dado pessoal sem máscara."
    return True, texto


def gerar_rascunho(
    chamado_mascarado: str,
    triagem: Triagem,
    palpites: list | None = None,
    leitura: str | None = None,
) -> Rascunho:
    partes = ["Olá!"]

    # Reflexão (só com o que está no chamado, em linguagem de hipótese)
    if triagem.recorrente:
        partes.append("Parece que isso já aconteceu mais de uma vez.")
    prazo = next((m.trecho for m in triagem.motivos_urgencia if m.sinal == "prazo"), None)
    if prazo:
        partes.append(f'Anotei a sua referência de prazo: "{prazo}".')

    # Reflexão adaptada à leitura escolhida pela analista (Agente 2 -> Agente 3)
    if leitura and leitura in REFLEXOES_LEITURA:
        partes.append(REFLEXOES_LEITURA[leitura])

    # Afirmação
    partes.append("Agradeço por ter nos avisado.")

    # Resumo + pergunta aberta (prioriza confirmação de necessidade não dita da Percepção)
    if triagem.intencao in RESUMOS:
        partes.append(f"Resumindo: entendi que se trata de {RESUMOS[triagem.intencao]}.")
    palpite_nao_dito = next((p for p in (palpites or []) if getattr(p, "tipo", None) == "necessidade_nao_dita"), None)
    if palpite_nao_dito:
        partes.append(palpite_nao_dito.pergunta_confirmacao)
    else:
        partes.append(PERGUNTAS[triagem.intencao])

    # Compromissos ficam em branco, para a analista decidir
    partes.append(f"Vou analisar o seu caso e te dar um retorno {PEND_PRAZO}. {PEND_PROVISORIA}")

    texto = " ".join(partes)
    ok, retorno = validar_rascunho(texto, chamado_mascarado)
    return Rascunho(
        texto=texto,
        pendencias=[PEND_PRAZO, PEND_PROVISORIA],
        passou_guardrail=ok,
        feedback_guardrail="" if ok else retorno,
    )
