"""Research spike comparing JSON file storage vs stdlib SQLite."""

import json
from pathlib import Path
import sqlite3

class StorageExperiment:
    """Deterministic comparison between JSON flat-file and SQLite storage."""

    @staticmethod
    def run_json_storage(work_dir: Path, record_count: int = 50) -> dict[str, object]:
        file_path = work_dir / "records.json"
        data = [{"id": i, "name": f"item_{i}", "val": i * 10} for i in range(record_count)]
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        
        # Read back
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
        return {
            "strategy": "json",
            "records_written": len(loaded),
            "file_size_bytes": file_path.stat().st_size,
        }

    @staticmethod
    def run_sqlite_storage(work_dir: Path, record_count: int = 50) -> dict[str, object]:
        db_path = work_dir / "records.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, name TEXT, val INTEGER)")
        cursor.executemany(
            "INSERT INTO records (id, name, val) VALUES (?, ?, ?)",
            [(i, f"item_{i}", i * 10) for i in range(record_count)]
        )
        conn.commit()
        
        # Read back
        cursor.execute("SELECT COUNT(*) FROM records")
        row_count = cursor.fetchone()[0]
        conn.close()
        return {
            "strategy": "sqlite",
            "records_written": row_count,
            "file_size_bytes": db_path.stat().st_size,
        }
