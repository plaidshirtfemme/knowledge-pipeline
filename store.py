import json
from datetime import date
import duckdb
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    note_id     VARCHAR PRIMARY KEY,
    source_url  VARCHAR UNIQUE,
    source_type VARCHAR,
    published   VARCHAR,
    added       VARCHAR,
    entities    VARCHAR,
    embedding   FLOAT[],
    cluster     VARCHAR
);
"""


def save(note_id: str, url: str, source_type: str, published: str | None, entities: list[str], text: str) -> None:
    embedding = _compute_embedding(text)
    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA)
    con.execute(
        """
        INSERT INTO notes (note_id, source_url, source_type, published, added, entities, embedding, cluster)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        ON CONFLICT (source_url) DO UPDATE SET
            entities = excluded.entities,
            embedding = excluded.embedding
        """,
        [
            note_id,
            url,
            source_type,
            published,
            date.today().isoformat(),
            json.dumps(entities, ensure_ascii=False),
            embedding,
        ],
    )
    con.close()


def _compute_embedding(text: str) -> list[float]:
    from sentence_transformers import SentenceTransformer
    from config import EMBEDDING_MODEL
    model = SentenceTransformer(EMBEDDING_MODEL)
    vector = model.encode(text[:4096], normalize_embeddings=True)
    return vector.tolist()
