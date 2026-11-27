"""Segurança: permissões mínimas, retenção e proteção de dados.

Regras de negócio (decisão do projeto):
- `SUPPORT_ALLOW_ALL` (default: false): autoriza todas as requisições apenas
  fora de produção. Com `APP_ENV=producao`, a configuração é recusada.
- `SUPPORT_RETAENCIAO_HORAS`: período de retenção dos logs de auditoria;
  padrão 24h, configurável para 30 dias em homologação.
"""

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

Role = Literal["analista", "gerente", "admin"]
Requester = Literal["analista", "gerente", "admin", "sistema", "externo"]

# Política de retenção: horas que um log de auditoria deve permanecer armazenado.
RETENCAO_HORAS_PADRAO = 24  # 24h em produção; mudar para 30*24 em homologação.

def _allow_all() -> bool:
    """Lê SUPPORT_ALLOW_ALL no momento do uso e recusa em produção."""
    if os.getenv("SUPPORT_ALLOW_ALL", "false").strip().lower() != "true":
        return False
    if os.getenv("APP_ENV", "dev").strip().lower() == "producao":
        raise RuntimeError("SUPPORT_ALLOW_ALL não pode ser usado em APP_ENV=producao")
    return True


def verificar_permissao(requerer: Requester, role: Role, permissoes: set[str] | None = None) -> None:
    """Verifica se o requerente tem permissão para executar uma ação.

    Args:
        requerer: Quem está pedindo acesso (ex.: "analista", "sistema").
        role: Papel do requerente (ex.: "analista", "gerente", "admin").
        permissoes: Conjunto de permissões solicitadas.

    Raises:
        PermissionError: Se o acesso não for autorizado.
    """
    if _allow_all():
        logger.warning(
            "seguranca: acesso permitido por SUPPORT_ALLOW_ALL (ambiente de teste/homologação)"
        )
        return

    if requerer == "externo":
        raise PermissionError("acesso de 'externo' não é permitido")

    # Mapeamento de permissões por papel (a definir conforme o projeto evolui).
    padrao = {
        "analista": {"leitura", "edicao"},
        "gerente": {"leitura", "edicao", "geracao"},
        "admin": {"leitura", "edicao", "geracao", "administracao"},
    }.get(role, set())

    if permissoes and not permissoes <= padrao:
        raise PermissionError(
            f"permissao negada: {requerer} (role={role}) nao tem acesso a {permissoes - padrao}"
        )

    logger.debug(
        "seguranca: acesso verificado (requerer=%s, role=%s, permissoes=%s)",
        requerer,
        role,
        permissoes,
    )


def reter_logs(logs_path: Path, horas: int | None = None) -> int:
    """Remove linhas de log antigas, mantendo apenas as *horas* recentes.

    Args:
        logs_path: Caminho do arquivo de auditoria (ex.: data/auditoria.jsonl).
        horas: Quantidade de horas de retenção. Padrão: `SUPPORT_RETAENCIAO_HORAS`
               ou `RETENCAO_HORAS_PADRAO` (24h); homologação pode usar 30*24.

    Returns:
        Quantidade de linhas removidas.

    Raises:
        FileNotFoundError: se o arquivo não existir.
        PermissionError: se o arquivo não for legível/escritível.
    """
    if not logs_path.exists():
        raise FileNotFoundError(f"log não encontrado: {logs_path}")

    # Remove linhas antigas e mantém apenas as *horas* recentes
    if horas is None:
        horas = int(os.getenv("SUPPORT_RETAENCIAO_HORAS", str(RETENCAO_HORAS_PADRAO)))
    limite = datetime.now(UTC) - timedelta(hours=horas)
    linhas_manter = []
    total_linhas = 0

    with logs_path.open("r", encoding="utf-8") as f:
        for linha in f:
            total_linhas += 1
            try:
                registro = json.loads(linha)
                ts_text = registro.get("quando", "")
                if not ts_text:
                    linhas_manter.append(linha)
                    continue
                ts = datetime.fromisoformat(ts_text)
                if ts >= limite:
                    linhas_manter.append(linha)
            except (ValueError, TypeError, json.JSONDecodeError):
                # Linha corrompida ou sem timestamp: mantém para não perder dados
                linhas_manter.append(linha)

    linhas_removidas = total_linhas - len(linhas_manter)

    # Sobrescreve o arquivo com o conteúdo filtrado (atomicamente)
    temp_path = logs_path.with_suffix(".jsonl.tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        f.writelines(linhas_manter)

    os.replace(temp_path, logs_path)

    return linhas_removidas
