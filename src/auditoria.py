"""Auditoria: registro (JSON Lines) do que cada agente sugeriu e do que a analista decidiu.

Só texto já mascarado entra aqui. Cada linha é um evento; nada é apagado.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)
_TRAVA_JSONL = threading.Lock()

Decisao = Literal["pendente", "aprovou", "editou", "rejeitou"]


def _anexar_linha(caminho: Path, linha: str) -> None:
    """Uma única escrita, com flush/fsync antes de liberar a trava do JSONL."""
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(linha)
        arquivo.flush()
        os.fsync(arquivo.fileno())


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
    logger.info(
        "auditoria: registrar chamado=%s agente=%s saida=%d decisao=%s",
        chamado_id,
        agente,
        len(saida),
        decisao,
    )
    caminho = Path(caminho)
    with _TRAVA_JSONL:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        _anexar_linha(caminho, json.dumps(evento, ensure_ascii=False) + "\n")


def registrar_payload(caminho: Path, evento: dict) -> bool:
    """Acrescenta um evento preparado pelo SQLite uma única vez, usando seu ID estável."""
    evento_id = evento.get("evento_db_id")
    if evento_id is None:
        raise ValueError("evento_db_id é obrigatório para exportação idempotente")
    caminho = Path(caminho)
    with _TRAVA_JSONL:
        if caminho.exists():
            with caminho.open(encoding="utf-8", errors="replace") as arquivo:
                for linha in arquivo:
                    try:
                        existente = json.loads(linha)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(existente, dict) and existente.get("evento_db_id") == evento_id:
                        return False
        caminho.parent.mkdir(parents=True, exist_ok=True)
        _anexar_linha(caminho, json.dumps(evento, ensure_ascii=False) + "\n")
    logger.info(
        "auditoria: exportado evento_db_id=%s",
        evento.get("evento_db_id"),
    )
    return True


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
