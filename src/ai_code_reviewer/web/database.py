"""SQLite database management for the web interface."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from .models import AnalysisStatus, CostRecord, WebAnalysis, WebConfiguration

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "web.db"


def get_db() -> sqlite3.Connection:
    """获取数据库连接（WAL模式）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """初始化数据库表结构"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            pr_url TEXT NOT NULL,
            pr_number INTEGER NOT NULL,
            repository TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            result TEXT,
            error TEXT,
            cost_usd REAL DEFAULT 0.0,
            risk_count INTEGER DEFAULT 0,
            suggestion_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS configurations (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cost_records (
            id TEXT PRIMARY KEY,
            analysis_id TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        );
    """)
    conn.close()


# ── Analysis CRUD ──────────────────────────────────────────────────────────


def create_analysis(analysis: WebAnalysis) -> WebAnalysis:
    """创建分析记录"""
    conn = get_db()
    conn.execute(
        """INSERT INTO analyses
           (id, pr_url, pr_number, repository, title, status,
            created_at, completed_at, result, error, cost_usd,
            risk_count, suggestion_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            analysis.id,
            analysis.pr_url,
            analysis.pr_number,
            analysis.repository,
            analysis.title,
            analysis.status.value,
            analysis.created_at.isoformat(),
            analysis.completed_at.isoformat() if analysis.completed_at else None,
            json.dumps(analysis.result) if analysis.result else None,
            analysis.error,
            analysis.cost_usd,
            analysis.risk_count,
            analysis.suggestion_count,
        ),
    )
    conn.commit()
    conn.close()
    return analysis


def get_analysis(analysis_id: str) -> Optional[WebAnalysis]:
    """获取分析记录"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
    ).fetchone()
    conn.close()
    if row:
        return _row_to_analysis(row)
    return None


def update_analysis(analysis: WebAnalysis) -> WebAnalysis:
    """更新分析记录"""
    conn = get_db()
    conn.execute(
        """UPDATE analyses SET
           pr_url=?, pr_number=?, repository=?, title=?, status=?,
           completed_at=?, result=?, error=?, cost_usd=?,
           risk_count=?, suggestion_count=?
           WHERE id=?""",
        (
            analysis.pr_url,
            analysis.pr_number,
            analysis.repository,
            analysis.title,
            analysis.status.value,
            analysis.completed_at.isoformat() if analysis.completed_at else None,
            json.dumps(analysis.result) if analysis.result else None,
            analysis.error,
            analysis.cost_usd,
            analysis.risk_count,
            analysis.suggestion_count,
            analysis.id,
        ),
    )
    conn.commit()
    conn.close()
    return analysis


def delete_analysis(analysis_id: str) -> bool:
    """删除分析记录及其关联的成本记录"""
    conn = get_db()
    cursor = conn.execute("DELETE FROM cost_records WHERE analysis_id=?", (analysis_id,))
    cursor = conn.execute("DELETE FROM analyses WHERE id=?", (analysis_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


def list_analyses(limit: int = 50, offset: int = 0) -> list[WebAnalysis]:
    """列出分析记录（按创建时间倒序）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()
    return [_row_to_analysis(r) for r in rows]


# ── Configuration CRUD ────────────────────────────────────────────────────


def get_configuration() -> WebConfiguration:
    """读取配置（不存在则返回默认值）"""
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM configurations").fetchall()
    conn.close()
    config_dict = {r["key"]: r["value"] for r in rows}
    if not config_dict:
        return WebConfiguration()
    return WebConfiguration(**config_dict)


def save_configuration(config: WebConfiguration) -> WebConfiguration:
    """保存配置"""
    conn = get_db()
    now = datetime.now(UTC).isoformat()
    data = config.model_dump()
    for key, value in data.items():
        conn.execute(
            """INSERT INTO configurations (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, str(value), now),
        )
    conn.commit()
    conn.close()
    return config


# ── CostRecord CRUD ───────────────────────────────────────────────────────


def create_cost_record(record: CostRecord) -> CostRecord:
    """创建成本记录"""
    conn = get_db()
    conn.execute(
        """INSERT INTO cost_records
           (id, analysis_id, model, input_tokens, output_tokens, cost_usd, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            record.id,
            record.analysis_id,
            record.model,
            record.input_tokens,
            record.output_tokens,
            record.cost_usd,
            record.created_at.isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return record


def get_cost_records_by_analysis(analysis_id: str) -> list[CostRecord]:
    """获取指定分析的所有成本记录"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM cost_records WHERE analysis_id = ? ORDER BY created_at",
        (analysis_id,),
    ).fetchall()
    conn.close()
    return [_row_to_cost_record(r) for r in rows]


def delete_cost_records_by_analysis(analysis_id: str) -> int:
    """删除指定分析的所有成本记录，返回删除数量"""
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM cost_records WHERE analysis_id=?", (analysis_id,)
    )
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count


# ── Helpers ───────────────────────────────────────────────────────────────


def _row_to_analysis(row: sqlite3.Row) -> WebAnalysis:
    """将数据库行转换为WebAnalysis"""
    data = dict(row)
    data["status"] = AnalysisStatus(data["status"])
    data["created_at"] = datetime.fromisoformat(data["created_at"])
    data["completed_at"] = (
        datetime.fromisoformat(data["completed_at"]) if data["completed_at"] else None
    )
    data["result"] = json.loads(data["result"]) if data["result"] else None
    return WebAnalysis(**data)


def get_cost_records_since(since: datetime) -> list[CostRecord]:
    """获取指定时间之后的所有成本记录"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM cost_records WHERE created_at >= ? ORDER BY created_at",
        (since.isoformat(),),
    ).fetchall()
    conn.close()
    return [_row_to_cost_record(r) for r in rows]


def get_cost_summary() -> dict:
    """获取成本摘要统计"""
    conn = get_db()
    row = conn.execute(
        """SELECT
               COUNT(*) as total_analyses,
               SUM(cost_usd) as total_cost,
               AVG(cost_usd) as avg_cost,
               MAX(cost_usd) as max_cost,
               SUM(risk_count) as total_risks,
               SUM(suggestion_count) as total_suggestions
           FROM analyses
           WHERE status = 'completed'"""
    ).fetchone()
    conn.close()

    if row:
        return {
            "total_analyses": row["total_analyses"] or 0,
            "total_cost_usd": round(row["total_cost"] or 0.0, 4),
            "avg_cost_usd": round(row["avg_cost"] or 0.0, 4),
            "max_cost_usd": round(row["max_cost"] or 0.0, 4),
            "total_risks": row["total_risks"] or 0,
            "total_suggestions": row["total_suggestions"] or 0,
        }
    return {
        "total_analyses": 0,
        "total_cost_usd": 0.0,
        "avg_cost_usd": 0.0,
        "max_cost_usd": 0.0,
        "total_risks": 0,
        "total_suggestions": 0,
    }


def get_daily_costs(days: int = 30) -> list[dict]:
    """获取每日成本统计"""
    conn = get_db()
    rows = conn.execute(
        """SELECT
               DATE(created_at) as date,
               COUNT(*) as analysis_count,
               SUM(cost_usd) as total_cost
           FROM analyses
           WHERE status = 'completed'
             AND created_at >= DATE('now', ?)
           GROUP BY DATE(created_at)
           ORDER BY date""",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    return [
        {
            "date": r["date"],
            "analysis_count": r["analysis_count"],
            "total_cost_usd": round(r["total_cost"] or 0.0, 4),
        }
        for r in rows
    ]


def _row_to_cost_record(row: sqlite3.Row) -> CostRecord:
    """将数据库行转换为CostRecord"""
    data = dict(row)
    data["created_at"] = datetime.fromisoformat(data["created_at"])
    return CostRecord(**data)
