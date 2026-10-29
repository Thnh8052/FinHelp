from typing import Any, Dict, List, Optional, Sequence, Union
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from app.core.config import settings
from app.services.retrieval.embeddings import DenseEmbeddingService


class QdrantRetriever:
    """Dense retrieval in Qdrant with a strict notebook / document payload filter.

    Errors are raised, not swallowed: an empty list must mean "nothing matched", never "the search broke".
    """

    def __init__(self, client: AsyncQdrantClient):
        self.client = client
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.dense_service = DenseEmbeddingService()

    def build_payload_filter(
        self,
        notebook_id: str,
        document_id: Optional[Union[str, Sequence[str]]] = None,
        concept_ids: Optional[List[str]] = None,
        chunk_type: Optional[str] = None,
    ) -> models.Filter:
        """Build strict Qdrant payload filter ensuring users cannot leak cross-notebook data.
        `document_id` is one id or a list of ids (the multi-document path searches a chosen subset of the notebook)."""
        if not notebook_id:  # every search is scoped to one notebook the caller was checked against (api/v1/deps.require_notebook)
            raise ValueError("a Qdrant search needs a notebook_id")
        must_conditions: List[models.FieldCondition] = [
            models.FieldCondition(key="notebook_id", match=models.MatchValue(value=notebook_id))
        ]
        if isinstance(document_id, str) and document_id:
            must_conditions.append(models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)))
        elif document_id:
            must_conditions.append(models.FieldCondition(key="document_id", match=models.MatchAny(any=list(document_id))))
        if concept_ids:
            must_conditions.append(models.FieldCondition(key="concept_ids", match=models.MatchAny(any=concept_ids)))
        if chunk_type:
            must_conditions.append(models.FieldCondition(key="chunk_type", match=models.MatchValue(value=chunk_type)))
        return models.Filter(must=must_conditions)

    async def search_vectors(
        self,
        vectors: List[List[float]],
        notebook_id: str,
        document_id: Optional[Union[str, Sequence[str]]] = None,
        limit: int = 5,
        per_vector_documents: Optional[Sequence[Optional[Sequence[str]]]] = None,
    ) -> List[List[Dict[str, Any]]]:
        """One ranked hit list per query vector (best first), in a single round trip.
        `per_vector_documents[i]` (when given) restricts vector i to its own documents, falling back to `document_id`."""
        default_filter = self.build_payload_filter(notebook_id, document_id)
        filters = [
            self.build_payload_filter(notebook_id, docs) if docs else default_filter
            for docs in (per_vector_documents or [None] * len(vectors))
        ]
        responses = await self.client.query_batch_points(
            collection_name=self.collection_name,
            requests=[
                models.QueryRequest(query=vector, filter=flt, limit=limit, with_payload=True)
                for vector, flt in zip(vectors, filters)
            ],
        )
        return [
            [{"chunk_id": (p.payload or {}).get("chunk_id"), "score": p.score} for p in response.points]
            for response in responses
        ]

    async def search_hybrid(
        self,
        query: str,
        notebook_id: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Single-query dense search (kept for the /retrieval inspector endpoint)."""
        vector = await self.dense_service.get_embedding(query)
        return (await self.search_vectors([vector], notebook_id, document_id, top_k))[0]
