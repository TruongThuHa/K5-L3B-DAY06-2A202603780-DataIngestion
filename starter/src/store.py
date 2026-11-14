"""Lưu và tìm vector bằng PostgreSQL + pgvector (khoảng cách cosine, tìm kiếm chính xác - exact)."""
import json
from typing import Any

import psycopg

from .models import Chunk

FILTER_COLUMNS = {"section", "document_id", "page"}  # chỉ cho phép lọc theo các cột này


def _vec(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("Thiếu DATABASE_URL trong starter/.env")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, connect_timeout=5)

    def create_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    strategy        TEXT NOT NULL,
                    chunk_id        TEXT NOT NULL,
                    document_id     TEXT NOT NULL,
                    source          TEXT NOT NULL,
                    page            INT  NOT NULL,
                    section         TEXT,
                    text            TEXT NOT NULL,
                    metadata        JSONB NOT NULL DEFAULT '{{}}',
                    embedding_model TEXT NOT NULL,
                    embedding       vector({self.dimensions}) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )""")
            row = conn.execute(
                "SELECT atttypmod FROM pg_attribute WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
            ).fetchone()
            if row and row[0] != self.dimensions:
                raise RuntimeError(f"Bảng chunks đang dùng {row[0]} chiều, model hiện tại {self.dimensions} chiều.")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]], model_name: str) -> dict[str, int]:
        """Ghi theo ID ổn định (không nhân đôi) và xóa chunk cũ không còn trong lần nạp này."""
        if len(chunks) != len(vectors):
            raise ValueError("Số chunk và số vector không khớp")
        if any(len(v) != self.dimensions for v in vectors):
            raise ValueError("Có vector sai số chiều")
        rows = [(strategy, c.chunk_id, c.document_id, c.source, c.page, c.metadata.get("section"), c.text,
                 json.dumps(c.metadata, ensure_ascii=False), model_name, _vec(v)) for c, v in zip(chunks, vectors)]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO chunks (strategy, chunk_id, document_id, source, page, section, text, metadata,
                                        embedding_model, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                        document_id = EXCLUDED.document_id, source = EXCLUDED.source, page = EXCLUDED.page,
                        section = EXCLUDED.section, text = EXCLUDED.text, metadata = EXCLUDED.metadata,
                        embedding_model = EXCLUDED.embedding_model, embedding = EXCLUDED.embedding""", rows)
                cur.execute("""DELETE FROM chunks WHERE strategy = %s AND document_id = ANY(%s)
                               AND NOT (chunk_id = ANY(%s))""",
                            (strategy, sorted({c.document_id for c in chunks}), [c.chunk_id for c in chunks]))
                removed = cur.rowcount
        return {"written": len(rows), "removed_obsolete": removed}

    def count(self, strategy: str) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT count(*) FROM chunks WHERE strategy = %s", (strategy,)).fetchone()[0]

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        where, params = ["strategy = %s"], [strategy]
        for key, value in (filters or {}).items():
            if key not in FILTER_COLUMNS:
                raise ValueError(f"Không cho phép lọc theo '{key}'")
            where.append(f"{key} = %s")
            params.append(value)
        qv = _vec(query_vector)
        sql = f"""SELECT chunk_id, document_id, source, page, section, text, metadata,
                         1 - (embedding <=> %s::vector) AS score
                  FROM chunks WHERE {' AND '.join(where)}
                  ORDER BY embedding <=> %s::vector LIMIT %s"""
        with self._connect() as conn:
            rows = conn.execute(sql, [qv, *params, qv, top_k]).fetchall()
        keys = ["chunk_id", "document_id", "source", "page", "section", "text", "metadata", "score"]
        return [dict(zip(keys, r)) | {"score": round(float(r[7]), 4)} for r in rows]
