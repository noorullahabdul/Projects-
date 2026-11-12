from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from . import __version__
from .design import Design


def save_json(path: str | Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def record_run(path: str | Path, kind: str, design: Design, result: dict, input_sha256: str = "") -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    config = json.dumps(asdict(design), sort_keys=True, allow_nan=False)
    run_id = uuid.uuid4().hex
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY, created_utc TEXT NOT NULL, kind TEXT NOT NULL,
            version TEXT NOT NULL, config_sha256 TEXT NOT NULL,
            input_sha256 TEXT NOT NULL, config_json TEXT NOT NULL, result_json TEXT NOT NULL
        )""")
        db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?)", (
            run_id, datetime.now(timezone.utc).isoformat(), kind, __version__,
            hashlib.sha256(config.encode()).hexdigest(), input_sha256,
            config, json.dumps(result, allow_nan=False),
        ))
    return run_id


def history(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.is_file():
        raise ValueError("Run database does not exist")
    try:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(
                "SELECT run_id,created_utc,kind,version,config_sha256,input_sha256 FROM runs ORDER BY created_utc DESC"
            )]
    except sqlite3.Error as error:
        raise ValueError("Not a readable DC-link run database") from error
