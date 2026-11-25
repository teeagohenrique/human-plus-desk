"""Persistência SQLite do Human + Desk.

Camada de dados separada da UI: o painel não escreve SQL, chama estas funções.
Regras preservadas do pipeline auditado:

- **LGPD:** só texto já mascarado entra no banco (a máscara roda no seed).
- **Append-only:** reabrir nunca apaga `resolvido_por`, `resolvido_em` nem
  `resposta_final`. Uma nova decisão substitui o estado vigente do ticket, mas
  o evento `decisao` guarda os valores anteriores (resposta, resolvedor,
  timestamp e status) para que a troca não apague a trilha.
- **Transação:** cada ação (urgência, decisão, reabertura) atualiza o ticket e
  insere o evento na mesma transação.

O arquivo `human_desk.db` é criado na raiz do projeto na primeira execução.
"""
import json
import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from src.mascara import mascarar
from src.triagem import triar

RAIZ = Path(__file__).resolve().parent.parent
DB_PATH = RAIZ / "human_desk.db"
logger = logging.getLogger(__name__)

DATASET_FILA = "simulados"
DATASET_BENCHMARK = "validacao_independente"
DATASETS = (
    ("chamados_simulados.json", DATASET_FILA),
    ("chamados_validacao_independente.json", DATASET_BENCHMARK),
)

URGENCIAS = ("alta", "media", "baixa")
PONTOS_ANALISTA = {"alta": 8, "media": 4, "baixa": 2}
DECISOES = ("aprovou", "editou", "rejeitou")


def _agora() -> str:
    """Timestamp ISO 8601 em UTC, mesmo formato de `src/auditoria.py`."""
    return datetime.now(UTC).isoformat()


def conectar(caminho: Path = DB_PATH) -> sqlite3.Connection:
    """Conexão com WAL e busy_timeout para sobreviver aos reruns do Streamlit."""
    conn = sqlite3.connect(Path(caminho), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(caminho: Path = DB_PATH, concluidos: set[str] | None = None) -> None:
    """Cria tabelas e popula o banco se estiver vazio.

    `concluidos` reconcilia decisões já registradas no JSONL antes do SQLite
    existir. Só é aplicado no seed: depois disso o banco é a fonte da verdade.
    """
    concluidos = set(concluidos or ())
    with closing(conectar(caminho)) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id                 TEXT PRIMARY KEY,
                dataset            TEXT NOT NULL,
                texto_mascarado    TEXT NOT NULL,
                urgencia_sugerida  TEXT,
                pontuacao_sugerida INTEGER,
                urgencia_confirmada TEXT,
                pontuacao_analista  INTEGER,
                status             TEXT NOT NULL DEFAULT 'pendente',
                resposta_final     TEXT,
                resolvido_por      TEXT,
                resolvido_em       TEXT,
                criado_em          TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS eventos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chamado_id TEXT NOT NULL REFERENCES tickets(id),
                acao       TEXT NOT NULL,
                agente     TEXT NOT NULL,
                criado_em  TEXT NOT NULL,
                detalhes   TEXT,
                jsonl_exportado INTEGER NOT NULL DEFAULT 1,
                payload_auditoria TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_eventos_chamado ON eventos(chamado_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status, dataset);
            """
        )
        colunas_eventos = {linha[1] for linha in conn.execute("PRAGMA table_info(eventos)")}
        if "jsonl_exportado" not in colunas_eventos:
            conn.execute(
                "ALTER TABLE eventos ADD COLUMN jsonl_exportado INTEGER NOT NULL DEFAULT 1"
            )
        if "payload_auditoria" not in colunas_eventos:
            conn.execute("ALTER TABLE eventos ADD COLUMN payload_auditoria TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_eventos_jsonl_pendente "
            "ON eventos(jsonl_exportado, acao)"
        )
        total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        if total == 0:
            _semear(conn, concluidos)
        if concluidos:
            _reconciliar_respostas(conn, concluidos)


def _reconciliar_respostas(conn: sqlite3.Connection, concluidos: set[str]) -> None:
    """Preenche resposta_final/resolvido_em ausentes em chamados concluídos a partir do log."""
    pendentes_texto = conn.execute(
        "SELECT id, resolvido_por, resolvido_em FROM tickets "
        "WHERE status = 'concluido' AND (resposta_final IS NULL OR TRIM(resposta_final) = '')"
    ).fetchall()
    if not pendentes_texto:
        return

    log_path = RAIZ / "data" / "painel_log.jsonl"
    por_id: dict[str, dict] = {}
    if log_path.exists():
        for numero, linha in enumerate(log_path.read_text(encoding="utf-8").splitlines(), start=1):
            if not linha.strip():
                continue
            try:
                reg = json.loads(linha)
            except json.JSONDecodeError:
                logger.warning(
                    "reconciliacao: linha %d de %s ignorada (JSON inválido)",
                    numero, log_path.name,
                )
                continue
            if not isinstance(reg, dict):
                logger.warning(
                    "reconciliacao: linha %d de %s ignorada (registro não é objeto)",
                    numero, log_path.name,
                )
                continue
            cid = reg.get("chamado_id")
            texto = (reg.get("texto_final") or "").strip()
            if cid in concluidos and texto:
                por_id[cid] = reg

    for row in pendentes_texto:
        cid = row["id"]
        reg = por_id.get(cid)
        if not reg:
            continue
        conn.execute(
            """UPDATE tickets
                      SET resposta_final = ?,
                          resolvido_por = COALESCE(resolvido_por, ?),
                          resolvido_em = COALESCE(resolvido_em, ?)
                    WHERE id = ?""",
            (reg["texto_final"], "Marina", reg.get("quando") or _agora(), cid),
        )


def _semear(conn: sqlite3.Connection, concluidos: set[str]) -> None:
    """Insere os 16 chamados da fila e os 50 do benchmark, já mascarados."""
    agora = _agora()
    for arquivo, dataset in DATASETS:
        dados = json.loads((RAIZ / "data" / arquivo).read_text(encoding="utf-8"))
        for chamado in dados["chamados"]:
            texto_mascarado = mascarar(chamado["texto"]).texto
            sugestao = triar(texto_mascarado)
            status = "concluido" if chamado["id"] in concluidos else "pendente"
            conn.execute(
                """
                INSERT OR IGNORE INTO tickets
                    (id, dataset, texto_mascarado, urgencia_sugerida,
                     pontuacao_sugerida, status, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (chamado["id"], dataset, texto_mascarado, sugestao.urgencia,
                 sugestao.pontuacao_urgencia, status, agora),
            )


def _inserir_evento(
    conn: sqlite3.Connection,
    chamado_id: str,
    acao: str,
    agente: str,
    detalhes: dict | None = None,
    payload_auditoria: dict | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO eventos
           (chamado_id, acao, agente, criado_em, detalhes, jsonl_exportado, payload_auditoria)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            chamado_id,
            acao,
            agente,
            _agora(),
            json.dumps(detalhes or {}, ensure_ascii=False),
            0 if payload_auditoria is not None else 1,
            json.dumps(payload_auditoria, ensure_ascii=False) if payload_auditoria else None,
        ),
    )
    return int(cursor.lastrowid or 0)


def registrar_urgencia(chamado_id: str, urgencia: str, agente: str,
                       caminho: Path = DB_PATH) -> None:
    """Grava a urgência escolhida na hora, com pontuação, agente e timestamp."""
    if urgencia not in URGENCIAS:
        raise ValueError(f"urgência inválida: {urgencia}")
    with closing(conectar(caminho)) as conn, conn:
        anterior = conn.execute(
            "SELECT urgencia_confirmada FROM tickets WHERE id = ?", (chamado_id,)
        ).fetchone()
        if anterior is None:
            raise KeyError(f"chamado não encontrado: {chamado_id}")
        conn.execute(
            """UPDATE tickets
                      SET urgencia_confirmada = ?, pontuacao_analista = ?
                    WHERE id = ?""",
            (urgencia, PONTOS_ANALISTA[urgencia], chamado_id),
        )
        _inserir_evento(conn, chamado_id, "urgencia_alterada", agente, {
            "urgencia_anterior": anterior["urgencia_confirmada"],
            "urgencia_nova": urgencia,
            "pontos_analista": PONTOS_ANALISTA[urgencia],
        })


def registrar_decisao(chamado_id: str, decisao: str, texto_final: str | None,
                      agente: str, detalhes: dict | None = None,
                      caminho: Path = DB_PATH,
                      payload_auditoria: dict | None = None) -> None:
    """Fecha o chamado e registra no evento o estado que ele substituiu.

    O ticket passa a refletir a nova decisão; os valores anteriores ficam no
    detalhe do evento, inclusive na primeira decisão (todos vazios).
    """
    if decisao not in DECISOES:
        raise ValueError(f"decisão inválida: {decisao}")
    with closing(conectar(caminho)) as conn, conn:
        anterior = conn.execute(
            "SELECT status, resposta_final, resolvido_por, resolvido_em "
            "FROM tickets WHERE id = ?", (chamado_id,)
        ).fetchone()
        if anterior is None:
            raise KeyError(f"chamado não encontrado: {chamado_id}")
        agora = _agora()
        resposta_gravada = (
            texto_final
            if (texto_final is not None and texto_final.strip())
            else anterior["resposta_final"]
        )
        conn.execute(
            """UPDATE tickets
                      SET status = 'concluido', resposta_final = ?,
                          resolvido_por = ?, resolvido_em = ?
                    WHERE id = ?""",
            (resposta_gravada, agente, agora, chamado_id),
        )
        _inserir_evento(conn, chamado_id, "decisao", agente, {
            "decisao": decisao,
            "tem_resposta": bool(texto_final),
            **(detalhes or {}),
            "status_anterior": anterior["status"],
            "resposta_anterior": anterior["resposta_final"],
            "resolvido_por_anterior": anterior["resolvido_por"],
            "resolvido_em_anterior": anterior["resolvido_em"],
            "tem_resposta_anterior": bool(anterior["resposta_final"]),
        }, payload_auditoria=payload_auditoria)


def reabrir(chamado_id: str, agente: str, caminho: Path = DB_PATH) -> None:
    """Reabre sem apagar nada: o histórico de resolução permanece no ticket."""
    with closing(conectar(caminho)) as conn, conn:
        atual = conn.execute(
            "SELECT status FROM tickets WHERE id = ?", (chamado_id,)
        ).fetchone()
        if atual is None:
            raise KeyError(f"chamado não encontrado: {chamado_id}")
        conn.execute(
            "UPDATE tickets SET status = 'pendente' WHERE id = ?", (chamado_id,)
        )
        _inserir_evento(conn, chamado_id, "reabriu", agente, {
            "status_anterior": atual["status"],
        })


def exportar_auditoria_pendente(
    caminho_log: Path = RAIZ / "data" / "painel_log.jsonl",
    caminho_db: Path = DB_PATH,
) -> int:
    """Publica no JSONL as decisões confirmadas no SQLite, sem duplicar após retry."""
    from src.auditoria import registrar_payload

    with closing(conectar(caminho_db)) as conn:
        pendentes = conn.execute(
            "SELECT id, chamado_id, criado_em, payload_auditoria FROM eventos "
            "WHERE acao = 'decisao' AND jsonl_exportado = 0 ORDER BY id"
        ).fetchall()

    exportados = 0
    for evento in pendentes:
        try:
            payload = json.loads(evento["payload_auditoria"] or "{}")
            if not isinstance(payload, dict):
                raise ValueError("payload de auditoria deve ser um objeto")
            registro = {
                "quando": evento["criado_em"],
                "chamado_id": evento["chamado_id"],
                "evento_db_id": evento["id"],
                **payload,
            }
            registrar_payload(caminho_log, registro)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.error(
                "auditoria: exportação do evento %s falhou (%s)",
                evento["id"], type(exc).__name__,
            )
            continue

        with closing(conectar(caminho_db)) as conn, conn:
            conn.execute(
                "UPDATE eventos SET jsonl_exportado = 1 WHERE id = ?",
                (evento["id"],),
            )
        exportados += 1
    return exportados


def estado(dataset: str | None = None, caminho: Path = DB_PATH) -> dict[str, dict]:
    """Estado atual por chamado; a UI usa para contadores e lista de concluídos."""
    sql = "SELECT * FROM tickets"
    params: tuple = ()
    if dataset is not None:
        sql += " WHERE dataset = ?"
        params = (dataset,)
    with closing(conectar(caminho)) as conn:
        return {r["id"]: dict(r) for r in conn.execute(sql, params)}


def ids_concluidos(dataset: str | None = None, caminho: Path = DB_PATH) -> set[str]:
    sql = "SELECT id FROM tickets WHERE status = 'concluido'"
    params: tuple = ()
    if dataset is not None:
        sql += " AND dataset = ?"
        params = (dataset,)
    with closing(conectar(caminho)) as conn:
        return {r[0] for r in conn.execute(sql, params)}


def eventos(caminho: Path = DB_PATH, chamado_id: str | None = None) -> list[dict]:
    """Eventos para a trilha de auditoria (detalhes já desserializados)."""
    sql = "SELECT * FROM eventos"
    params: tuple = ()
    if chamado_id is not None:
        sql += " WHERE chamado_id = ?"
        params = (chamado_id,)
    sql += " ORDER BY id"
    with closing(conectar(caminho)) as conn:
        return [
            {**dict(r), "detalhes": json.loads(r["detalhes"] or "{}")}
            for r in conn.execute(sql, params)
        ]
