"""
Persists DataProfile snapshots so the DriftAgent has history to compare
against. Uses DuckDB -- a single embedded file (data/history.duckdb),
no server to run. Swapping this for Postgres later only means changing
this one file; nothing else in the pipeline knows or cares which
database is behind it.
"""

import os
import duckdb
from src.schemas import DataProfile

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "history.duckdb")


def _get_connection():
    conn = duckdb.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profile_snapshots (
            source_name VARCHAR,
            snapshot_date DATE,
            profile_json VARCHAR
        )
    """)
    return conn


def save_snapshot(profile: DataProfile, snapshot_date: str) -> None:
    """Stores (or overwrites) the profile snapshot for a given source+date."""
    conn = _get_connection()
    conn.execute(
        "DELETE FROM profile_snapshots WHERE source_name = ? AND snapshot_date = ?",
        [profile.source_name, snapshot_date],
    )
    conn.execute(
        "INSERT INTO profile_snapshots VALUES (?, ?, ?)",
        [profile.source_name, snapshot_date, profile.model_dump_json()],
    )
    conn.close()


def load_latest_before(source_name: str, current_date: str) -> tuple[str | None, DataProfile | None]:
    """Returns (snapshot_date, DataProfile) of the most recent snapshot strictly
    before current_date, or (None, None) if no earlier snapshot exists."""
    conn = _get_connection()
    row = conn.execute(
        """SELECT snapshot_date, profile_json FROM profile_snapshots
           WHERE source_name = ? AND snapshot_date < ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        [source_name, current_date],
    ).fetchone()
    conn.close()

    if row is None:
        return None, None

    snapshot_date, profile_json = row
    return str(snapshot_date), DataProfile.model_validate_json(profile_json)


def list_snapshot_dates(source_name: str) -> list[str]:
    conn = _get_connection()
    rows = conn.execute(
        "SELECT snapshot_date FROM profile_snapshots WHERE source_name = ? ORDER BY snapshot_date",
        [source_name],
    ).fetchall()
    conn.close()
    return [str(r[0]) for r in rows]
