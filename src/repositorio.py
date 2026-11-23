"""Persistência SQLite do Human + Desk.

Camada de dados separada da UI: o painel não escreve SQL, chama estas funções.
Regras preservadas do pipeline auditado:

- **LGPD:** só texto já mascarado entra no banco (a máscara roda no seed).
- **Append-only:** reabrir nunca apaga `resolvido_por`, `resolvido_em` nem
  `resposta_final`; a ação vira um evento novo, com agente e timestamp UTC.
- **Transação:** cada ação (urgência, decisão, reabertura) atualiza o ticket e
  insere o evento na mesma transação.

O arquivo `human_desk.db` é criado na raiz do projeto na primeira execução.
"""
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from src.mascara import mascarar
from src.triagem import triar

RAIZ = Path(__file__).resolve().parent.parent
DB_PATH = RAIZ / "human_desk.db"

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
                detalhes   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_eventos_chamado ON eventos(chamado_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status, dataset);
            """
        )
        total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        if total == 0:
            _semear(conn, concluidos)


def _semear(conn: sqlite3.Connection, concluidos: set[str]) -> None:
    """Insere os 16 chamados da fila e os 36 do benchmark, já mascarados."""
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


def _inserir_evento(conn: sqlite3.Connection, chamado_id: str, acao: str,
                    agente: str, detalhes: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO eventos (chamado_id, acao, agente, criado_em, detalhes) VALUES (?, ?, ?, ?, ?)",
        (chamado_id, acao, agente, _agora(),
         json.dumps(detalhes or {}, ensure_ascii=False)),
    )


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
                      caminho: Path = DB_PATH) -> None:
    """Fecha o chamado na hora da aprovação/edição/rejeição."""
    if decisao not in DECISOES:
        raise ValueError(f"decisão inválida: {decisao}")
    with closing(conectar(caminho)) as conn, conn:
        existe = conn.execute(
            "SELECT 1 FROM tickets WHERE id = ?", (chamado_id,)
        ).fetchone()
        if existe is None:
            raise KeyError(f"chamado não encontrado: {chamado_id}")
        agora = _agora()
        conn.execute(
            """UPDATE tickets
                      SET status = 'concluido', resposta_final = ?,
                          resolvido_por = ?, resolvido_em = ?
                    WHERE id = ?""",
            (texto_final, agente, agora, chamado_id),
        )
        _inserir_evento(conn, chamado_id, "decisao", agente, {
            "decisao": decisao,
            "tem_resposta": bool(texto_final),
            **(detalhes or {}),
        })


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
