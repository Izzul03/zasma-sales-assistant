"""SQLite store for leads (prospects). All queries are parameterised."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterator, List, Optional

STAGES = ["Baru", "Sudah dihubungi", "Temu janji", "Tandatangan", "Tidak berminat"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT DEFAULT 'WhatsApp',
    message TEXT NOT NULL,
    name TEXT, place TEXT, coverage TEXT, segment TEXT,
    budget REAL, sqft REAL, bedrooms INTEGER, storeys INTEGER, spec TEXT, has_land INTEGER,
    intents TEXT, estimate REAL,
    stage TEXT NOT NULL DEFAULT 'Baru',
    follow_up_due TEXT,
    draft_reply TEXT, final_reply TEXT, replied_by TEXT, replied_at TEXT,
    method TEXT, is_synthetic INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS lead_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER REFERENCES leads(id),
    at TEXT NOT NULL, actor TEXT, action TEXT, details TEXT
);
"""


class LeadDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_lead(self, message: str, info: Dict, coverage: str, estimate: Optional[float], draft: str,
                 created_at: Optional[datetime] = None, stage: str = "Baru", synthetic: bool = False,
                 source: str = "WhatsApp", follow_up_due: Optional[str] = None) -> int:
        created = created_at or datetime.now()
        with self.connect() as c:
            cur = c.execute(
                "INSERT INTO leads (created_at, source, message, name, place, coverage, segment, budget, sqft, "
                "bedrooms, storeys, spec, has_land, intents, estimate, stage, follow_up_due, draft_reply, method, "
                "is_synthetic) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (created.isoformat(timespec="seconds"), source, message, info.get("name"), info.get("place"),
                 coverage, info.get("segment"), info.get("budget"), info.get("sqft"), info.get("bedrooms"),
                 info.get("storeys"), info.get("spec"),
                 None if info.get("has_land") is None else int(info["has_land"]),
                 json.dumps(info.get("intents") or []), estimate, stage,
                 follow_up_due or (created + timedelta(days=2)).date().isoformat(), draft, info.get("method"), int(synthetic)))
            lead_id = int(cur.lastrowid)
            c.execute("INSERT INTO lead_log (lead_id, at, actor, action, details) VALUES (?,?,?,?,?)",
                      (lead_id, created.isoformat(timespec="seconds"), "Sistem", "DICIPTA", "Pertanyaan direkodkan"))
        return lead_id

    def mark_replied(self, lead_id: int, final_reply: str, actor: str) -> None:
        now = datetime.now()
        with self.connect() as c:
            c.execute("UPDATE leads SET final_reply=?, replied_by=?, replied_at=?, stage=CASE WHEN stage='Baru' "
                      "THEN 'Sudah dihubungi' ELSE stage END, follow_up_due=? WHERE id=?",
                      (final_reply, actor, now.isoformat(timespec="seconds"),
                       (now + timedelta(days=3)).date().isoformat(), lead_id))
            c.execute("INSERT INTO lead_log (lead_id, at, actor, action, details) VALUES (?,?,?,?,?)",
                      (lead_id, now.isoformat(timespec="seconds"), actor, "JAWAPAN_DIHANTAR",
                       "Jurujual menyemak dan menghantar jawapan secara manual"))

    def set_stage(self, lead_id: int, stage: str, actor: str, follow_up_due: Optional[str] = None) -> None:
        if stage not in STAGES:
            raise ValueError("Peringkat tidak sah")
        with self.connect() as c:
            c.execute("UPDATE leads SET stage=?, follow_up_due=COALESCE(?, follow_up_due) WHERE id=?",
                      (stage, follow_up_due, lead_id))
            c.execute("INSERT INTO lead_log (lead_id, at, actor, action, details) VALUES (?,?,?,?,?)",
                      (lead_id, datetime.now().isoformat(timespec="seconds"), actor, "PERINGKAT", stage))

    def leads(self) -> List[Dict]:
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM leads ORDER BY created_at DESC")]

    def lead(self, lead_id: int) -> Optional[Dict]:
        with self.connect() as c:
            r = c.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            return dict(r) if r else None

    def log(self, lead_id: int) -> List[Dict]:
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM lead_log WHERE lead_id=? ORDER BY id", (lead_id,))]

    def count(self) -> int:
        with self.connect() as c:
            return c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

    def reset(self) -> None:
        with self.connect() as c:
            c.executescript("DROP TABLE IF EXISTS lead_log; DROP TABLE IF EXISTS leads;")
            c.executescript(SCHEMA)
