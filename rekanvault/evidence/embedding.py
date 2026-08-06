from __future__ import annotations

from collections.abc import Sequence

from sentence_transformers import CrossEncoder, SentenceTransformer

from apps.api.config import settings


class EmbeddingService:
    """Thin wrapper around local sentence-transformers models (P4 ADRs 0002/0003).

    ponytail: one class, lazy-load models, no abstraction over a single provider.
    """

    def __init__(self) -> None:
        self._dense: SentenceTransformer | None = None
        self._reranker: CrossEncoder | None = None

    @property
    def dense(self) -> SentenceTransformer:
        if self._dense is None:
            self._dense = SentenceTransformer(
                settings.RV_EMBEDDING_MODEL,
                device=settings.RV_EMBEDDING_DEVICE,
                revision=settings.RV_EMBEDDING_MODEL_REVISION or None,
            )
        return self._dense

    @property
    def reranker(self) -> CrossEncoder:
        if self._reranker is None:
            self._reranker = CrossEncoder(
                settings.RV_RERANK_MODEL,
                device=settings.RV_EMBEDDING_DEVICE,
                revision=settings.RV_RERANK_MODEL_REVISION or None,
            )
        return self._reranker

    @property
    def dim(self) -> int:
        d = self.dense.get_embedding_dimension()
        return d if d is not None else 1024

    def embed(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        if batch_size is None:
            batch_size = settings.RV_EMBEDDING_BATCH_SIZE
        result = self.dense.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)
        return result.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def rerank(self, query: str, candidates: Sequence[str], top_n: int | None = None) -> list[tuple[int, float]]:
        if top_n is None:
            top_n = settings.RV_RERANK_TOP_N
        pairs = [(query, c) for c in candidates]
        scores = self.reranker.predict(pairs, show_progress_bar=False)  # type: ignore[arg-type]  # ponytail: sentence-transformers type stubs are overly strict for list[tuple[str,str]]
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(idx, float(score)) for idx, score in ranked[:top_n]]
