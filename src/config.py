"""Configuração compartilhada pelos pontos de entrada (CLI e painel).

Este módulo define a configuração e os utilitários de ambiente; quem decide
chamá-los é o entry point. Assim a suíte de testes, que importa os módulos de
domínio, não carrega variáveis de um ``.env`` real e permanece determinística
e offline.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

PLACEHOLDER_CHAVE = "sua_chave_aqui"


@dataclass(frozen=True)
class Config:
    """Configuração resolvida, tipada e validada.

    ``gemini_api_key`` pode estar vazia até que o ambiente principal defina a
    chave. Em ``producao``, ``validar_producao()`` garante fail-closed: não se
    deve subir com a chave de exemplo, sob pena de enviar texto não mascarado.
    """

    gemini_api_key: str
    gemini_model: str
    llm_provider: str
    ambiente: str

    @property
    def segura(self) -> bool:
        """Chave presente, não vazia e diferente do placeholder."""
        return bool(self.gemini_api_key and self.gemini_api_key != PLACEHOLDER_CHAVE)

    def validar_producao(self) -> None:
        """Recusa ambiente de produção com chave de exemplo ou ausente."""
        if self.ambiente != "producao":
            return
        if not self.segura:
            raise RuntimeError(
                "APP_ENV=producao e GEMINI_API_KEY está ausente ou é o "
                "placeholder de exemplo. Corrija o arquivo .env ou rode em dev."
            )


def carregar_env(caminho: Path) -> None:
    """Carrega GEMINI_* de um ``.env`` sem sobrescrever variáveis já definidas.

    Valores vazios e o placeholder de exemplo são ignorados: eles deixam o
    fluxo cair nas regras (offline), como documentado.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        valor = valor.strip(" \"'")
        if not chave or not valor or valor == PLACEHOLDER_CHAVE:
            continue
        os.environ.setdefault(chave, valor)


def _normalizar_ambiente(raw: str) -> str:
    """Normaliza APP_ENV para o domínio ``dev``/``producao``."""
    valor = raw.strip().lower()
    if valor not in ("dev", "producao"):
        logger.warning(
            "config: APP_ENV=%r inválido; considerado 'dev'",
            raw,
        )
        return "dev"
    return valor


def resolver_config() -> Config:
    """Resolve e valida a configuração a partir do shell e do ``.env``."""
    llm_provider = os.getenv("LLM_PROVIDER", "regras").strip().lower()
    if llm_provider not in ("regras", "gemini"):
        logger.warning(
            "config: LLM_PROVIDER=%r inválido; cairá em 'regras'",
            llm_provider,
        )
        llm_provider = "regras"
    return Config(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        gemini_model=os.getenv("GEMINI_MODEL", ""),
        llm_provider=llm_provider,
        ambiente=_normalizar_ambiente(os.getenv("APP_ENV", "dev")),
    )


def validar_ambiente(config: Config) -> None:
    """Ponto de entrada da camada de segurança: fail-closed apenas em produção."""
    config.validar_producao()


def configurar_log(
    nivel: int = logging.INFO,
    formato: str = "%(asctime)s %(levelname)s %(name)s %(message)s",
) -> None:
    """Configura o logger raiz de forma idempotente."""
    logging.basicConfig(level=nivel, format=formato)


def esconde_chave(chave: str, largura: int = 4) -> str:
    """Retorna uma versão mascarada de uma chave para uso em logs."""
    if not chave:
        return "<sem chave>"
    if len(chave) <= largura * 2:
        return "<chave truncada>"
    return f"{chave[:largura]}…{chave[-largura:]}"