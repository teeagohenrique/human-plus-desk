"""Reconhecimento local de nomes de pessoas com Presidio + spaCy (português).

Usado por `mascarar()` como camada adicional à heurística de prefixos. Roda
100% offline: nenhum texto sai da máquina e nenhuma chamada de API é feita.

O reconhecedor padrão do spaCy para português erra em palavras comuns de
service desk ("Favor", "Procurei", "Olá"). Por isso esta camada só aceita um
trecho PER quando ele tem pelo menos um token PROPN e nenhum termo da lista
`_NAO_PESSOAS`. A lista é explícita e auditável, seguindo a regra do projeto:
prefere-se mascarar demais a vazar, mas sem cegar a triagem com falsos positivos.
"""
from functools import lru_cache

from presidio_analyzer import (
    AnalyzerEngine,
    EntityRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import SpacyNlpEngine

IDIOMA = "pt"
MODELO_SPACY = "pt_core_news_sm"
# O SpacyNlpEngine converte o rótulo PER do spaCy para PERSON nos NlpArtifacts:
# a entidade pedida ao Presidio e o rótulo nos artefatos são o mesmo valor.
ENTIDADE = "PERSON"
ROTULO_PRESIDIO = ENTIDADE
CONFIANCA = 0.85

# Observados em chamados de service desk: o modelo marca como PER mesmo sem
# serem nomes de pessoas. A comparação é por casefold.
_NAO_PESSOAS = {
    "abrir", "abri", "atenciosamente", "att", "abs", "bom", "cnpj", "cpf",
    "favor", "ola", "olá", "obrigada", "obrigado", "prezada", "prezado",
    "procurei", "senhor", "senhora", "sra", "sr", "srta", "dr", "dra",
}


class _ReconhecedorPessoa(EntityRecognizer):
    """Extrai PER do spaCy só quando há PROPN e não há termo conhecido como ruído."""

    def __init__(self) -> None:
        super().__init__(
            supported_entities=[ENTIDADE],
            supported_language=IDIOMA,
            name="spacy_per_com_pos",
        )

    def load(self) -> None:
        return None

    def analyze(self, text: str, entities: list[str], nlp_artifacts) -> list[RecognizerResult]:
        if ENTIDADE not in entities:
            return []
        resultados = []
        for trecho in nlp_artifacts.entities:
            if trecho.label_ != ROTULO_PRESIDIO:
                continue
            tokens = [t for t in trecho if not t.is_punct]
            palavras = [t.text.casefold() for t in tokens]
            if not tokens or any(p in _NAO_PESSOAS for p in palavras):
                continue
            if not any(t.pos_ == "PROPN" for t in tokens):
                continue
            resultados.append(
                RecognizerResult(ENTIDADE, trecho.start_char, trecho.end_char, CONFIANCA)
            )
        return resultados


@lru_cache(maxsize=1)
def _analisador() -> AnalyzerEngine:
    """Carrega o modelo uma vez por processo; chamadas seguintes reusam a engine."""
    nlp_engine = SpacyNlpEngine(models=[{"lang_code": IDIOMA, "model_name": MODELO_SPACY}])
    registry = RecognizerRegistry(
        recognizers=[_ReconhecedorPessoa()],
        supported_languages=[IDIOMA],
    )
    return AnalyzerEngine(registry=registry, nlp_engine=nlp_engine, supported_languages=[IDIOMA])


def nomes_encontrados(texto: str) -> list[tuple[int, int]]:
    """Devolve pares `(início, fim)` dos nomes detectados, sem sobreposição."""
    if not texto.strip():
        return []
    try:
        resultados = _analisador().analyze(text=texto, language=IDIOMA, entities=[ENTIDADE])
    except Exception:  # modelo ausente ou falha local: a heurística de mascara.py assume
        return []
    ordem = sorted(resultados, key=lambda r: (r.start, -r.end))
    spans: list[tuple[int, int]] = []
    for resultado in ordem:
        if resultado.start < 0 or resultado.end > len(texto) or resultado.start >= resultado.end:
            continue
        if "[" in texto[resultado.start:resultado.end] or "]" in texto[resultado.start:resultado.end]:
            continue
        if spans and resultado.start < spans[-1][1]:
            continue
        spans.append((resultado.start, resultado.end))
    return spans
