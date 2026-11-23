"""Camada de adaptadores LLM com fallback determinístico para regras.

Princípios:
- As funções puras (`src.triagem.triar`, `src.redator.gerar_rascunho`) permanecem
  intactas; este módulo injeta o adaptador sem quebrar os testes offline.
- Import do SDK (`google.genai`) é LAZY (dentro da função do adaptador).
- Se `LLM_PROVIDER` estiver ausente ou `GEMINI_API_KEY` não estiver definida,
  seleciona o adaptador `regras` silenciosamente.
- `validar_trechos` vale para TODOS os adaptadores (regras e LLM): compara cada
  trecho exatamente (normalizando apenas espaços) contra o texto MASCARADO.
- O adaptador Gemini espaça chamadas e aplica backoff limitado: 3 tentativas
  para 429 (respeitando o `retryDelay`) e 5 para 503 (picos de demanda).
"""
import os
import re
import time
from typing import Any

from src.redator import PEND_PRAZO, PEND_PROVISORIA, Rascunho, gerar_rascunho, validar_rascunho
from src.triagem import Triagem, triar

PROVIDERS = ("regras", "gemini")

# A camada gratuita do Gemini limita a 15 requisições por minuto, por modelo.
# O espaçamento abaixo vale somente para o adaptador Gemini; o modo regras
# continua sem qualquer pausa.
INTERVALO_MINIMO_GEMINI = 4.6
MAX_TENTATIVAS_API = 3          # 429: cota por minuto
MAX_TENTATIVAS_503 = 5          # 503: pico de demanda do provedor
ESPERA_503_BASE = 10.0
ESPERA_503_TETO = 60.0
STATUS_TRANSIENTES = (429, 503)
_ULTIMA_CHAMADA_GEMINI: float | None = None


def _pausar_entre_chamadas() -> None:
    """Mantém distância mínima entre chamadas para não estourar o limite por minuto."""
    global _ULTIMA_CHAMADA_GEMINI
    agora = time.monotonic()
    if _ULTIMA_CHAMADA_GEMINI is not None:
        restante = INTERVALO_MINIMO_GEMINI - (agora - _ULTIMA_CHAMADA_GEMINI)
        if restante > 0:
            time.sleep(restante)
    _ULTIMA_CHAMADA_GEMINI = time.monotonic()


def _status_erro(exc: Exception) -> int | None:
    """Status HTTP exposto pelo SDK (`code`) ou por clientes alternativos."""
    for nome in ("code", "status_code"):
        valor = getattr(exc, nome, None)
        if isinstance(valor, int):
            return valor
    return None


def _retry_delay(exc: Exception) -> float | None:
    """Lê o `retryDelay` do RetryInfo da API (ex.: '9.099506196s')."""
    dados = getattr(exc, "details", None)
    if not isinstance(dados, dict):
        return None
    bloco = dados.get("error", dados)
    if not isinstance(bloco, dict):
        return None
    for item in bloco.get("details") or []:
        if not isinstance(item, dict):
            continue
        bruto = item.get("retryDelay")
        if not isinstance(bruto, str):
            continue
        encontrado = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*s\s*", bruto)
        if encontrado:
            # Pequena margem para não repetir no limite exato; teto de 60s.
            return min(float(encontrado.group(1)) + 0.2, 60.0)
    return None


def _chamar_api_gemini(cliente: Any, modelo: str, contents: str, config: Any) -> Any:
    """Chama a API com espaçamento e backoff limitado para 429/503."""
    for tentativa in range(max(MAX_TENTATIVAS_API, MAX_TENTATIVAS_503)):
        _pausar_entre_chamadas()
        try:
            return cliente.models.generate_content(model=modelo, contents=contents, config=config)
        except Exception as exc:
            status = _status_erro(exc)
            limite = MAX_TENTATIVAS_503 if status == 503 else MAX_TENTATIVAS_API
            if status not in STATUS_TRANSIENTES or tentativa == limite - 1:
                raise
            espera = _retry_delay(exc)
            if espera is None:
                if status == 503:
                    espera = min(ESPERA_503_BASE * 2 ** tentativa, ESPERA_503_TETO)
                else:
                    espera = min(2.0 ** tentativa, 30.0)
            time.sleep(espera)


def _normalizar_espacos(texto: str) -> str:
    return " ".join(texto.split())


def validar_trechos(trechos: list[str], texto_mascarado: str) -> tuple[bool, list[str]]:
    """Confere se cada trecho é evidência LITERAL presente em `texto_mascarado`.

    Normaliza apenas espaços consecutivos, preservando capitalização exata.
    Compara contra o texto já mascarado para barrar tanto citações inventadas
    quanto trechos que vazem dados pessoais removidos pela máscara.
    """
    base = _normalizar_espacos(texto_mascarado)
    invalidos: list[str] = []
    for trecho in trechos:
        t = _normalizar_espacos(trecho)
        if not t or t not in base:
            invalidos.append(trecho)
    return (len(invalidos) == 0), invalidos


def validar_triagem_trechos(triagem: Triagem, texto_mascarado: str) -> tuple[bool, list[str]]:
    trechos = [m.trecho for m in triagem.motivos_intencao + triagem.motivos_urgencia]
    return validar_trechos(trechos, texto_mascarado)


def resolver_provider(provider: str | None = None) -> str:
    """Resolve o provedor ativo (`regras` por padrão).

    Se `gemini` for pedido sem `GEMINI_API_KEY`, faz fallback silencioso para `regras`.
    """
    escolhido = (provider or os.getenv("LLM_PROVIDER") or "regras").strip().lower()
    if escolhido not in PROVIDERS:
        raise ValueError(f"Provedor desconhecido: {escolhido!r}. Use um de: {PROVIDERS}")
    if escolhido == "gemini" and not os.getenv("GEMINI_API_KEY"):
        return "regras"
    return escolhido


def _modelo_gemini(model: str | None = None) -> str:
    escolhido = (model or os.getenv("GEMINI_MODEL") or "").strip()
    if not escolhido:
        raise ValueError(
            "Defina a variável de ambiente GEMINI_MODEL (ou passe `model=...`) "
            "para usar o adaptador Gemini sem fixar modelo no código."
        )
    return escolhido


def _triagem_gemini(texto_mascarado: str, model: str | None = None, max_tentativas: int = 2) -> Triagem:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return triar(texto_mascarado)

    modelo = _modelo_gemini(model)
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt_base = (
        "Classifique o chamado de service desk abaixo em português.\n"
        "Regras obrigatórias:\n"
        "1. Todo motivo em `motivos_intencao` e `motivos_urgencia` deve trazer um `trecho` "
        "LITERAL copiado exatamente do texto mascarado (mesma grafia e capitalização).\n"
        "2. Nunca invente trechos nem reconstrua dados mascarados.\n"
        "3. Se não houver evidência literal para urgência acima de baixa, use urgencia='baixa'.\n\n"
        f"Chamado mascarado:\n{texto_mascarado}"
    )

    feedback = ""
    for _ in range(max_tentativas):
        prompt = prompt_base if not feedback else f"{prompt_base}\n\nCorrija o erro anterior: {feedback}"
        resp = _chamar_api_gemini(
            client,
            modelo,
            prompt,
            types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Triagem,
                temperature=0.0,
            ),
        )
        triagem = resp.parsed
        if isinstance(triagem, Triagem):
            ok, invalidos = validar_triagem_trechos(triagem, texto_mascarado)
            if ok:
                return triagem
            feedback = f"Os seguintes trechos não aparecem literalmente no chamado mascarado: {invalidos}."
        else:
            feedback = "A resposta não seguiu o esquema Pydantic Triagem."

    return triar(texto_mascarado)


def _rascunho_gemini(
    texto_mascarado: str,
    triagem: Triagem,
    palpites: list | None = None,
    leitura: str | None = None,
    model: str | None = None,
    max_tentativas: int = 2,
) -> Rascunho:
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura)

    modelo = _modelo_gemini(model)
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    contexto_palpites = "; ".join(getattr(p, "hipotese", str(p)) for p in (palpites or [])) or "nenhum"
    prompt_base = (
        "Escreva um rascunho curto de resposta de service desk em português no estilo OARS "
        "(reflexão, afirmação, resumo e pergunta aberta).\n"
        "Regras obrigatórias (verificadas por guardrail determinístico):\n"
        f"1. Nunca prometa prazo ou compromisso; inclua os marcadores {PEND_PRAZO} e {PEND_PROVISORIA}.\n"
        "2. Nunca rotule a pessoa (ex.: 'você está nervoso'); fale apenas de sinais do texto.\n"
        "3. Nunca invente números que não estejam no chamado mascarado.\n"
        "4. Nunca inclua dados pessoais sem máscara.\n\n"
        f"Chamado mascarado: {texto_mascarado}\n"
        f"Triagem: intencao={triagem.intencao}, urgencia={triagem.urgencia}, recorrente={triagem.recorrente}\n"
        f"Leitura escolhida: {leitura or 'nenhuma'}\n"
        f"Palpites: {contexto_palpites}"
    )

    feedback = ""
    for _ in range(max_tentativas):
        prompt = prompt_base if not feedback else f"{prompt_base}\n\nCorrija a violação de guardrail: {feedback}"
        resp = _chamar_api_gemini(
            client,
            modelo,
            prompt,
            types.GenerateContentConfig(temperature=0.2),
        )
        texto = (resp.text or "").strip()
        ok, retorno = validar_rascunho(texto, texto_mascarado)
        if ok:
            return Rascunho(
                texto=texto,
                pendencias=[p for p in (PEND_PRAZO, PEND_PROVISORIA) if p in texto],
                passou_guardrail=True,
                feedback_guardrail="",
            )
        feedback = retorno

    return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura)


def triagem_com_llm(texto_mascarado: str, provider: str | None = None, model: str | None = None) -> Triagem:
    ativo = resolver_provider(provider)
    if ativo == "gemini":
        return _triagem_gemini(texto_mascarado, model=model)
    resultado = triar(texto_mascarado)
    ok, invalidos = validar_triagem_trechos(resultado, texto_mascarado)
    if not ok:
        raise ValueError(f"Trechos inválidos na triagem por regras: {invalidos}")
    return resultado


def rascunho_com_llm(
    texto_mascarado: str,
    triagem: Triagem,
    palpites: list | None = None,
    leitura: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> Rascunho:
    ativo = resolver_provider(provider)
    if ativo == "gemini":
        return _rascunho_gemini(texto_mascarado, triagem, palpites=palpites, leitura=leitura, model=model)
    return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura)
