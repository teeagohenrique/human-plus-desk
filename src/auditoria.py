"""Auditoria: registro (JSON Lines) do que cada agente sugeriu e do que a analista decidiu.

Só texto já mascarado entra aqui. Cada linha é um evento; nada é apagado.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

Decisao = Literal["pendente", "aprovou", "editou", "rejeitou"]


def registrar(caminho: Path, chamado_id: str, agente: str, saida: dict,
              decisao: Decisao = "pendente", texto_final: str | None = None) -> None:
    evento = {
        "quando": datetime.now(timezone.utc).isoformat(),
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
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]
