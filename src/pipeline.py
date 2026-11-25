"""Núcleo compartilhado da sugestão: máscara -> triagem -> percepção -> rascunho.

CLI (`src/main.py`) e painel (`src/painel.py`) delegam as quatro etapas aqui, cada
um mantendo sua responsabilidade: a CLI grava auditoria e imprime, o painel
monta a fila com origens, histórico e progresso. Este módulo não decide nada —
a IA só sugere e a analista permanece no comando.
"""
from collections.abc import Callable
from dataclasses import dataclass

from src import llm
from src.mascara import ResultadoMascara, mascarar
from src.percepcao import Historico, Palpite, perceber
from src.redator import Rascunho
from src.triagem import Triagem


@dataclass
class ResultadoProcessamento:
    """Artefatos das quatro etapas, incluindo a origem efetiva de cada adaptador."""

    mascara: ResultadoMascara
    triagem: Triagem
    origem_triagem: str
    palpites: list[Palpite]
    rascunho: Rascunho
    origem_rascunho: str
    leitura_inicial: str | None
    provider_rascunho: str


def processar_chamado(
    texto: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    historico: list[Historico] | None = None,
    ao_etapa: Callable[[str], None] | None = None,
) -> ResultadoProcessamento:
    """Executa as quatro etapas de sugestão para um chamado.

    `ao_etapa`, quando fornecido, recebe `"triagem"` e `"rascunho"` nessa ordem.
    Quem chama decide como reportar progresso e se vai gravar auditoria.
    """
    mascara = mascarar(texto)
    triagem, origem_triagem = llm.triagem_com_origem(
        mascara.texto, provider=provider, model=model, ner_disponivel=mascara.ner_disponivel
    )
    if ao_etapa is not None:
        ao_etapa("triagem")

    palpites = perceber(mascara.texto, triagem, historico)
    leitura_inicial = palpites[0].leituras[0] if palpites else None
    rascunho, origem_rascunho = llm.rascunho_com_origem(
        mascara.texto, triagem, palpites=palpites, leitura=leitura_inicial,
        provider=provider, model=model, ner_disponivel=mascara.ner_disponivel,
    )
    if ao_etapa is not None:
        ao_etapa("rascunho")

    return ResultadoProcessamento(
        mascara=mascara,
        triagem=triagem,
        origem_triagem=origem_triagem,
        palpites=palpites,
        rascunho=rascunho,
        origem_rascunho=origem_rascunho,
        leitura_inicial=leitura_inicial,
        provider_rascunho=llm.resolver_provider(provider),
    )
