"""Auditoria: registro (JSON Lines) do que cada agente sugeriu e do que a analista decidiu.

Só texto já mascarado entra aqui. Cada linha é um evento; nada é apagado.
"""
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)

Decisao = Literal["pendente", "aprovou", "editou", "rejeitou"]


class Evento(BaseModel):
    """Envelope de uma linha do log.

    `saida` continua livre por desenho: máscara, triagem, analista e gestor
    registram formatos diferentes. `extra="allow"` preserva campos já presentes
    no log simulado (`simulado`) e qualquer campo futuro, para não descartar
    histórico de auditoria por causa de um campo novo.
    """

    model_config = ConfigDict(extra="allow")

    quando: str
    chamado_id: str
    agente: str
    saida: dict[str, Any]
    decisao_analista: str
    texto_final: str | None = None
    simulado: bool = False


def registrar(caminho: Path, chamado_id: str, agente: str, saida: dict,
              decisao: Decisao = "pendente", texto_final: str | None = None) -> None:
    evento = {
        "quando": datetime.now(UTC).isoformat(),
        "chamado_id": chamado_id,
        "agente": agente,
        "saida": saida,
        "decisao_analista": decisao,
        "texto_final": texto_final,
    }
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as f:  # modo "a": só acrescenta
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def ler(caminho: Path) -> list[dict]:
    """Lê o log; linhas inválidas são ignoradas com aviso, sem quebrar a leitura."""
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    eventos: list[dict] = []
    with caminho.open(encoding="utf-8", errors="replace") as f:
        for numero, linha in enumerate(f, start=1):
            if not linha.strip():
                continue
            try:
                bruto = json.loads(linha)
                eventos.append(Evento.model_validate(bruto).model_dump())
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(
                    "auditoria: linha %d de %s ignorada (%s)",
                    numero, caminho.name, type(exc).__name__,
                )
    return eventos
