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
- O cliente é inicializado uma única vez por chave e reutilizado nas chamadas.
- `CONTADOR_TRIAGEM` registra a origem de cada triagem: `gemini`, `regras` ou
  `fallback` (Gemini pedido, mas respondido pelas regras).
- `CONTADOR_FALLBACK` separa o MOTIVO de cada fallback efetivo (SDK ausente,
  cliente indisponível, erro de API por status, schema inválido, trecho inválido,
  guardrail e marcadores faltantes). Assim a medição distingue falha de API de
  falha de validação sem depender de log externo.
- O espaçamento entre chamadas é global e sincronizado: a cota é por chave/modelo,
  compartilhada por todas as sessões. `usar_contadores()` isola apenas as métricas,
  que são observacionais e não podem misturar sessões ou medições.
- `triagem_com_origem` e `rascunho_com_origem` devolvem `(objeto, origem)` para
  que o painel mostre o selo de procedência em cada chamado.
"""
import logging
import os
import re
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from src.redator import (
    PEND_PRAZO,
    PEND_PROVISORIA,
    Rascunho,
    gerar_rascunho,
    validar_rascunho,
)
from src.triagem import Triagem, triar

logger = logging.getLogger(__name__)

# Timeout da requisição HTTP para o adaptador Gemini. O SDK (google-genai) aplica
# `timeout` dentro de `GenerateContentConfig`; mantêmho como constante de
# configuração, permitindo redefini-la via .env sem tocar no código.
TIMEOUT_S = 30

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

# A inicialização do cliente é custosa e a chave é a mesma em todo o processo:
# uma instância por chave, criada sob demanda e nunca fixada no código.
_CLIENTES_GEMINI: dict[str, Any] = {}
_TRAVA_CLIENTE = threading.Lock()

CONTADOR_TRIAGEM = {"gemini": 0, "regras": 0, "fallback": 0}

MOTIVOS_FALLBACK = (
    "sdk_indisponivel",
    "cliente_indisponivel",
    "erro_api_429",
    "erro_api_503",
    "erro_api_outro",
    "schema_invalido",
    "trecho_invalido",
    "guardrail",
    "marcadores_faltantes",
    "configuracao_invalida",
    "mascara_incompleta",
)
CONTADOR_FALLBACK = {motivo: 0 for motivo in MOTIVOS_FALLBACK}


def _esconder_chave(chave: str, largura: int = 4) -> str:
    """Mascara os 4 primeiros e 4 últimos caracteres de uma chave.

    Usado para não expor segredos em logs e depuradores.
    """
    if not chave:
        return "<sem chave>"
    if len(chave) <= largura * 2:
        return "<chave truncada>"
    return f"{chave[:largura]}…{chave[-largura:]}"

# A cota da API é por chave/modelo, não por sessão: o relógio do pacer continua
# global, mas agora com reserva atômica de slot e espera fora do lock.
_TRAVA_PAUSA = threading.Lock()


@dataclass
class Contadores:
    """Contadores de uma sessão ou de uma medição isolada."""

    triagem: dict[str, int] = field(
        default_factory=lambda: {"gemini": 0, "regras": 0, "fallback": 0}
    )
    fallback: dict[str, int] = field(
        default_factory=lambda: {motivo: 0 for motivo in MOTIVOS_FALLBACK}
    )


_CONTEXT_CONTADORES: ContextVar[Contadores | None] = ContextVar(
    "contadores_llm", default=None
)


@contextmanager
def usar_contadores() -> Iterator[Contadores]:
    """Isola origem e motivos de fallback no contexto atual.

    Fora dele, as funções de contagem continuam usando as variáveis globais de
    sempre — nenhuma assinatura pública mudou.
    """
    novos = Contadores()
    token = _CONTEXT_CONTADORES.set(novos)
    try:
        yield novos
    finally:
        _CONTEXT_CONTADORES.reset(token)


def _contadores() -> tuple[dict[str, int], dict[str, int]]:
    ativo = _CONTEXT_CONTADORES.get()
    if ativo is not None:
        return ativo.triagem, ativo.fallback
    return CONTADOR_TRIAGEM, CONTADOR_FALLBACK


def zerar_contador_triagem() -> None:
    """Zera as categorias antes de uma medição.

    API legada mantida apenas para os testes; a CLI usa `zerar_contadores()`.
    """
    triagem, _ = _contadores()
    for chave in triagem:
        triagem[chave] = 0


def zerar_contadores() -> None:
    """Zera origem e motivos antes de uma medição completa."""
    triagem, fallback = _contadores()
    for chave in triagem:
        triagem[chave] = 0
    for chave in fallback:
        fallback[chave] = 0


def obter_contador_triagem() -> dict[str, int]:
    """Devolve uma cópia, para que chamadores não alterem o contador."""
    return dict(_contadores()[0])


def obter_contador_fallback() -> dict[str, int]:
    """Devolve uma cópia dos motivos, sem expor o contador interno."""
    return dict(_contadores()[1])


def _registrar_triagem(categoria: str) -> None:
    _contadores()[0][categoria] += 1


def _registrar_fallback(motivo: str) -> None:
    contador = _contadores()[1]
    if motivo not in contador:
        raise ValueError(f"Motivo de fallback desconhecido: {motivo!r}")
    contador[motivo] += 1


def _pausar_entre_chamadas() -> None:
    """Reserva o próximo slot do adaptador Gemini sem estourar a cota por minuto."""
    global _ULTIMA_CHAMADA_GEMINI
    with _TRAVA_PAUSA:
        agora = time.monotonic()
        anterior = _ULTIMA_CHAMADA_GEMINI
        inicio = max(agora, anterior + INTERVALO_MINIMO_GEMINI) if anterior is not None else agora
        _ULTIMA_CHAMADA_GEMINI = inicio
    espera = inicio - time.monotonic()
    if espera > 0:
        time.sleep(espera)


def _status_erro(exc: Exception) -> int | None:
    """Status HTTP exposto pelo SDK (`code`) ou por clientes alternativos."""
    for nome in ("code", "status_code"):
        valor = getattr(exc, nome, None)
        if isinstance(valor, int):
            return valor
    return None


def _registrar_erro_api(exc: Exception) -> str:
    """Classifica a exceção da API por status e devolve o motivo registrado."""
    motivo = {429: "erro_api_429", 503: "erro_api_503"}.get(_status_erro(exc), "erro_api_outro")
    _registrar_fallback(motivo)
    return motivo


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
            if status not in STATUS_TRANSIENTES or tentativa >= limite - 1:
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


def _trecho_esta_na_base(trecho_norm: str, base: str) -> bool:
    """Confere presença literal com fronteira de palavra nas pontas alfanuméricas."""
    padrao = re.escape(trecho_norm)
    if trecho_norm[0].isalnum() or trecho_norm[0] == "_":
        padrao = rf"(?<!\w){padrao}"
    if trecho_norm[-1].isalnum() or trecho_norm[-1] == "_":
        padrao = rf"{padrao}(?!\w)"
    return re.search(padrao, base) is not None


def validar_trechos(trechos: list[str], texto_mascarado: str) -> tuple[bool, list[str]]:
    """Confere se cada trecho é evidência LITERAL presente em `texto_mascarado`.

    Normaliza apenas espaços consecutivos, preservando capitalização exata e
    fronteira de palavra (ex.: 'cai' não casa dentro de 'caiu').
    Compara contra o texto já mascarado para barrar tanto citações inventadas
    quanto trechos que vazem dados pessoais removidos pela máscara.
    """
    base = _normalizar_espacos(texto_mascarado)
    invalidos: list[str] = []
    for trecho in trechos:
        t = _normalizar_espacos(trecho)
        if not t or not _trecho_esta_na_base(t, base):
            invalidos.append(trecho)
    return (len(invalidos) == 0), invalidos


def validar_triagem_trechos(triagem: Triagem, texto_mascarado: str) -> tuple[bool, list[str]]:
    trechos = [m.trecho for m in triagem.motivos_intencao + triagem.motivos_urgencia]
    return validar_trechos(trechos, texto_mascarado)


def _triagem_regras_validada(texto_mascarado: str, origem: str) -> tuple[Triagem, str]:
    """Triagem local com `validar_trechos`, inclusive no fallback por máscara.

    A regra 'sem trecho, sem campo' vale tanto no adaptador de regras quanto no
    fallback que substitui o Gemini quando o NER local falhou: os dois caminhos
    usam `triar` e devem exigir evidência literal contra o texto mascarado.
    """
    triagem = triar(texto_mascarado)
    ok, invalidos = validar_triagem_trechos(triagem, texto_mascarado)
    if not ok:
        raise ValueError(f"Trechos inválidos na triagem por regras: {invalidos}")
    return triagem, origem


_APELIDOS_PROVIDER = {
    "motor de regras (offline)": "regras",
    "regras (offline)": "regras",
    "rule engine (offline)": "regras",
    "rules": "regras",
    "gemini (api)": "gemini",
}


def resolver_provider(provider: str | None = None) -> str:
    """Resolve o provedor ativo (`regras` por padrão).

    Aceita também os rótulos de exibição da interface (PT/EN) para evitar erro
    caso o estado de sessão carregue o texto visível em vez do identificador.
    Se `gemini` for pedido sem `GEMINI_API_KEY`, faz fallback silencioso para `regras`.
    """
    bruto = (provider or os.getenv("LLM_PROVIDER") or "regras").strip().lower()
    escolhido = _APELIDOS_PROVIDER.get(bruto, bruto)
    if escolhido not in PROVIDERS:
        raise ValueError(f"Provedor desconhecido: {escolhido!r}. Use um de: {PROVIDERS}")
    if escolhido == "gemini" and not os.getenv("GEMINI_API_KEY"):
        return "regras"
    return escolhido


def _cliente_gemini() -> Any:
    """Reutiliza o cliente Gemini da chave atual; cria um só por chave."""
    from google import genai

    chave = os.getenv("GEMINI_API_KEY") or ""
    with _TRAVA_CLIENTE:
        cliente = _CLIENTES_GEMINI.get(chave)
        if cliente is None:
            cliente = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            _CLIENTES_GEMINI[chave] = cliente
    return cliente


def _modelo_gemini(model: str | None = None) -> str:
    escolhido = (model or os.getenv("GEMINI_MODEL") or "").strip()
    if not escolhido:
        raise ValueError(
            "Defina a variável de ambiente GEMINI_MODEL (ou passe `model=...`) "
            "para usar o adaptador Gemini sem fixar modelo no código."
        )
    return escolhido


def _triagem_gemini(texto_mascarado: str, model: str | None = None, max_tentativas: int = 2) -> tuple[Triagem, str]:
    try:
        from google.genai import types
    except ImportError:
        _registrar_fallback("sdk_indisponivel")
        return _triagem_regras_validada(texto_mascarado, "fallback")[0], "fallback"

    try:
        modelo = _modelo_gemini(model)
    except ValueError:
        _registrar_fallback("configuracao_invalida")
        return _triagem_regras_validada(texto_mascarado, "fallback")[0], "fallback"
    try:
        client = _cliente_gemini()
    except Exception:
        _registrar_fallback("cliente_indisponivel")
        return _triagem_regras_validada(texto_mascarado, "fallback")[0], "fallback"
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
    motivo_falha = "schema_invalido"
    motivo_api: str | None = None
    for _ in range(max_tentativas):
        prompt = prompt_base if not feedback else f"{prompt_base}\n\nCorrija o erro anterior: {feedback}"
        try:
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
        except Exception as exc:
            # Cota esgotada, 503 persistente ou queda de rede: a tela não pode
            # quebrar. Sai do loop e devolve a triagem determinística.
            motivo_api = _registrar_erro_api(exc)
            break
        triagem = resp.parsed
        if isinstance(triagem, Triagem):
            ok, invalidos = validar_triagem_trechos(triagem, texto_mascarado)
            if ok:
                return triagem, "gemini"
            motivo_falha = "trecho_invalido"
            feedback = f"Os seguintes trechos não aparecem literalmente no chamado mascarado: {invalidos}."
        else:
            motivo_falha = "schema_invalido"
            feedback = "A resposta não seguiu o esquema Pydantic Triagem."

    if motivo_api is None:
        _registrar_fallback(motivo_falha)
        logger.warning(
            "llm: triagem caindo em fallback (modelo=%s, motivo=%s, chave=%s)",
            modelo,
            motivo_falha,
            _esconder_chave(os.getenv("GEMINI_API_KEY", "")),
        )
    else:
        logger.info(
            "llm: triagem atingiu fallback por falha de API (modelo=%s, motivo=%s)",
            modelo,
            motivo_falha,
        )
    return _triagem_regras_validada(texto_mascarado, "fallback")[0], "fallback"


def _rascunho_gemini(
    texto_mascarado: str,
    triagem: Triagem,
    palpites: list | None = None,
    leitura: str | None = None,
    model: str | None = None,
    max_tentativas: int = 2,
) -> tuple[Rascunho, str]:
    try:
        from google.genai import types
    except ImportError:
        _registrar_fallback("sdk_indisponivel")
        return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura), "fallback"

    try:
        modelo = _modelo_gemini(model)
    except ValueError:
        _registrar_fallback("configuracao_invalida")
        return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura), "fallback"
    try:
        client = _cliente_gemini()
    except Exception:
        _registrar_fallback("cliente_indisponivel")
        return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura), "fallback"
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
    motivo_falha = "guardrail"
    motivo_api: str | None = None
    for _ in range(max_tentativas):
        prompt = prompt_base if not feedback else f"{prompt_base}\n\nCorrija a violação de guardrail: {feedback}"
        try:
            resp = _chamar_api_gemini(
                client,
                modelo,
                prompt,
                types.GenerateContentConfig(temperature=0.2),
            )
        except Exception as exc:
            motivo_api = _registrar_erro_api(exc)
            break
        texto = (resp.text or "").strip()
        ok, retorno = validar_rascunho(texto, texto_mascarado)
        # Exigir os dois marcadores impede que o modelo decida o prazo no lugar
        # da analista: o guardrail sozinho remove os placeholders e não bloqueia.
        faltantes = [p for p in (PEND_PRAZO, PEND_PROVISORIA) if p not in texto]
        if ok and not faltantes:
            return Rascunho(
                texto=texto,
                pendencias=[PEND_PRAZO, PEND_PROVISORIA],
                passou_guardrail=True,
                feedback_guardrail="",
            ), "gemini"
        if not ok:
            motivo_falha = "guardrail"
            feedback = retorno
        else:
            motivo_falha = "marcadores_faltantes"
            feedback = f"Faltam os marcadores obrigatórios entre colchetes: {faltantes}. Inclua-os exatamente como fornecidos."

    if motivo_api is None:
        _registrar_fallback(motivo_falha)
        logger.warning(
            "llm: rascunho caindo em fallback (origem=%s, motivo=%s, chave=%s)",
            os.getenv("LLM_PROVIDER", "regras"),
            motivo_falha,
            _esconder_chave(os.getenv("GEMINI_API_KEY", "")),
        )
    else:
        logger.info(
            "llm: rascunho atingiu fallback por falha de API (origem=%s, motivo=%s)",
            os.getenv("LLM_PROVIDER", "regras"),
            motivo_falha,
        )
    return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura), "fallback"


def triagem_com_origem(
    texto_mascarado: str,
    provider: str | None = None,
    model: str | None = None,
    ner_disponivel: bool = False,
) -> tuple[Triagem, str]:
    """Devolve `(triagem, origem)`; sem NER local, não envia texto ao provedor externo."""
    ativo = resolver_provider(provider)
    if ativo == "gemini" and not ner_disponivel:
        _registrar_fallback("mascara_incompleta")
        triagem, origem = _triagem_regras_validada(texto_mascarado, "fallback")
    elif ativo == "gemini":
        triagem, origem = _triagem_gemini(texto_mascarado, model=model)
    else:
        triagem, origem = _triagem_regras_validada(texto_mascarado, "regras")
    _registrar_triagem(origem)
    return triagem, origem


def triagem_com_llm(
    texto_mascarado: str,
    provider: str | None = None,
    model: str | None = None,
    ner_disponivel: bool = False,
) -> Triagem:
    """Compatibilidade: devolve só a triagem, sem a origem."""
    return triagem_com_origem(texto_mascarado, provider=provider, model=model, ner_disponivel=ner_disponivel)[0]


def rascunho_com_origem(
    texto_mascarado: str,
    triagem: Triagem,
    palpites: list | None = None,
    leitura: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    ner_disponivel: bool = False,
) -> tuple[Rascunho, str]:
    """Devolve `(rascunho, origem)`; sem NER local, não envia texto ao provedor externo."""
    ativo = resolver_provider(provider)
    if ativo == "gemini" and not ner_disponivel:
        _registrar_fallback("mascara_incompleta")
        return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura), "fallback"
    if ativo == "gemini":
        return _rascunho_gemini(
            texto_mascarado, triagem, palpites=palpites, leitura=leitura, model=model
        )
    return gerar_rascunho(texto_mascarado, triagem, palpites=palpites, leitura=leitura), "regras"


def rascunho_com_llm(
    texto_mascarado: str,
    triagem: Triagem,
    palpites: list | None = None,
    leitura: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    ner_disponivel: bool = False,
) -> Rascunho:
    """Compatibilidade: devolve só o rascunho, sem a origem."""
    return rascunho_com_origem(
        texto_mascarado,
        triagem,
        palpites=palpites,
        leitura=leitura,
        provider=provider,
        model=model,
        ner_disponivel=ner_disponivel,
    )[0]
