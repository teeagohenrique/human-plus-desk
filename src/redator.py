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
PEND_PRAZO_EN = "[RETURN TIME: analyst fills]"
PEND_PROVISORIA = "[SOLUÇÃO PROVISÓRIA, se houver: a analista preenche]"
class Sugestao(str):
    """Texto de sugestao do acervo com o resultado do guardrail em atributos."""

    passou_guardrail: bool
    feedback_guardrail: str


_PLACEHOLDER = re.compile(r"\[[^\]]*\]")
_PENDENCIA_ANALISTA = re.compile(r"\[[^\]]*(?:analista\s+preenche|analyst\s+fills)[^\]]*\]", re.IGNORECASE)
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


def pendencias_abertas(texto: str) -> list[str]:
    """Retorna apenas os marcadores que ainda exigem preenchimento da analista.

    Quando a solução provisória vem do acervo entre `[ ]` (ex.: `[webmail corporativo]`),
    ela já está preenchida e editável pela analista, portanto não bloqueia o registro;
    apenas `[PRAZO DE RETORNO: a analista preenche]` (ou outro marcador com
    `analista preenche`) permanece como pendência obrigatória.
    """
    return _PENDENCIA_ANALISTA.findall(texto or "")


def formatar_sugestao_acervo(
    triagem: Triagem, solucao_provisoria: str, idioma: str = "PT",
    chamado_mascarado: str = "",
) -> Sugestao:
    """Monta a sugestao estruturada com a solucao provisoria do acervo e o `@` do paciente.

    Substitui `[SOLUCAO PROVISORIA, se houver: a analista preenche]` por
    `[<solucao_provisoria>]` e mantem apenas `[PRAZO DE RETORNO: a analista preenche]`
    para a Marina preencher com base na simulacao de tempo do acervo.

    O guardrail aplica `validar_rascunho` sobre o conteudo da solucao (o que vira entre
    `[ ]`): prazo/compromisso prometido, rotulo sobre a pessoa, numeros fora do chamado
    e dado sem mascara. O resultado fica disponivel em `passou_guardrail` e
    `feedback_guardrail`; o texto retornado segue sendo uma `str` para nao quebrar a
    interface que consome a sugestao.
    """
    prazo = next((m.trecho for m in triagem.motivos_urgencia if m.sinal == "prazo"), None)
    contexto_prazo_pt = (
        f'Prazo mencionado no chamado: "{prazo}".'
        if prazo
        else "A analista deve avaliar a prioridade com base no impacto informado."
    )
    resumo = RESUMOS.get(triagem.intencao, "uma instabilidade no sistema")
    resumos_en = {
        "falha_sistema": "a system issue",
        "acesso": "an access issue",
        "reclamacao": "a service concern",
        "solicitacao": "a request",
        "duvida": "a usage question",
        "indefinida": "the reported issue",
    }
    resumo_en = resumos_en.get(triagem.intencao, "the reported issue")
    solucao_limpa = solucao_provisoria.strip().strip("[]")
    # Guardrail do acervo: a solucao nao pode prometer prazo, rotular a pessoa,
    # citar numeros fora do chamado ou conter dado sem mascara.
    ok, feedback = validar_rascunho(solucao_limpa, chamado_mascarado or "")
    if idioma.upper() == "EN":
        contexto_prazo = (
            f'The request mentions the timeframe "{prazo}".'
            if prazo
            else "The analyst should assess priority based on the reported impact."
        )
        texto = chr(10).join([
            "Hello, @!",
            contexto_prazo,
            f"Based on the description, this may relate to {resumo_en}.",
            f"If available and authorized, the analyst may consider [{solucao_limpa}] as a temporary option.",
            f"Return timeframe, to be confirmed by the analyst: {PEND_PRAZO_EN}.",
            "Thank you for contacting us.",
            "Best regards.",
            "Marina",
            "Service Desk Analyst | Human+Desk",
        ])
    else:
        texto = (
            "Olá, @!\n"
            f"{contexto_prazo_pt} "
            f"Com base no relato, o tema pode estar relacionado a {resumo}. "
            "A equipe responsável poderá avaliar os próximos passos.\n"
            f"Se estiver disponível e autorizada, a analista pode avaliar esta alternativa provisória: "
            f"[{solucao_limpa}].\n"
            f"Prazo de retorno, a confirmar pela analista: {PEND_PRAZO}. Próxima atualização sobre o "
            "andamento dependerá da confirmação da equipe responsável. "
            "Agradecemos pelo contato. "
            "A analista confirmará os próximos passos após validar as informações.\n"
            "Atenciosamente,\n"
            "Marina\n"
            "Analista de Suporte ao Cliente | Human+Desk"
        )
    resultado = Sugestao(texto)
    resultado.passou_guardrail = ok
    resultado.feedback_guardrail = feedback
    return resultado
