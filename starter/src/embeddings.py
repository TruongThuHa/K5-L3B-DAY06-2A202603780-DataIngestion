"""Embedding model thật, chạy local bằng sentence-transformers (không cần API key, chi phí 0)."""
from typing import Protocol

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
# Model BGE khuyên thêm câu dẫn này vào câu hỏi (không thêm vào tài liệu) khi tìm đoạn văn.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class LocalEmbedder:
    """Lần chạy đầu sẽ tải model (~130 MB) về máy; các lần sau dùng bản đã tải."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dimensions = int(self.model.encode(["test"], normalize_embeddings=True).shape[1])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        return self.model.encode([QUERY_PREFIX + question], normalize_embeddings=True)[0].tolist()


MyEmbedder = LocalEmbedder
