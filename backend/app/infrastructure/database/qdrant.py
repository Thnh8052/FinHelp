from typing import Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
from app.core.config import settings
from app.core.logging import logger


class QdrantManager:
    """Manages Async Qdrant client lifecycle and collection initialization."""

    client: Optional[AsyncQdrantClient] = None

    @classmethod
    async def connect_to_qdrant(cls) -> None:
        """Initialize AsyncQdrantClient (server, or embedded when QDRANT_PATH is set) and ensure the collection exists."""
        try:
            if settings.QDRANT_PATH:
                logger.info(f"Opening embedded Qdrant storage at {settings.QDRANT_PATH}...")
                cls.client = AsyncQdrantClient(path=settings.QDRANT_PATH)
            else:
                logger.info(f"Connecting to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}...")
                cls.client = AsyncQdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    # "" must become None: qdrant-client switches to HTTPS as soon as api_key is not None, which fails
                    # against the plain-HTTP Docker container ("QDRANT_API_KEY=" in .env gives an empty string).
                    api_key=settings.QDRANT_API_KEY or None,
                    timeout=60,  # the 5 s default fails on a first upsert that creates segments (seen: 7 s on Docker/WSL)
                )
            await cls.ensure_collection()
        except Exception as e:
            logger.warning(f"Could not connect to Qdrant: {e}")

    @classmethod
    async def close_qdrant_connection(cls) -> None:
        """Close Qdrant client session."""
        if cls.client:
            logger.info("Closing Qdrant client session...")
            await cls.client.close()
            logger.info("Qdrant client session closed.")

    @classmethod
    async def ensure_collection(cls) -> None:
        """Ensure the dense-vector collection (BGE-M3, 1024-d cosine) and its payload indexes exist."""
        if cls.client is None:
            return

        collection_name = settings.QDRANT_COLLECTION_NAME
        try:
            if await cls.client.collection_exists(collection_name):
                size = (await cls.client.get_collection(collection_name)).config.params.vectors.size
                if size != settings.EMBEDDING_DIM:
                    # Never delete data silently: point QDRANT_COLLECTION_NAME at a new collection instead.
                    logger.error(
                        f"Qdrant collection '{collection_name}' has {size}-dim vectors but the embedding model "
                        f"produces {settings.EMBEDDING_DIM}. Use a new QDRANT_COLLECTION_NAME."
                    )
                else:
                    logger.info(f"Qdrant collection '{collection_name}' already exists.")
                return

            logger.info(f"Creating Qdrant collection '{collection_name}' ({settings.EMBEDDING_DIM}-dim cosine)...")
            await cls.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=settings.EMBEDDING_DIM, distance=models.Distance.COSINE),
            )
            payload_fields = [
                ("notebook_id", models.PayloadSchemaType.KEYWORD),
                ("document_id", models.PayloadSchemaType.KEYWORD),
                ("page", models.PayloadSchemaType.INTEGER),
                ("chunk_type", models.PayloadSchemaType.KEYWORD),
                ("text_type", models.PayloadSchemaType.KEYWORD),
                ("concept_ids", models.PayloadSchemaType.KEYWORD),
            ]
            for field_name, schema_type in payload_fields:
                await cls.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
            logger.info("Qdrant payload indexes created successfully.")
        except Exception as exc:
            logger.warning(f"Could not initialize Qdrant collection: {exc}")


async def get_qdrant_client() -> AsyncQdrantClient:
    """Dependency helper to get the active Qdrant client instance."""
    if QdrantManager.client is None:
        raise RuntimeError("Qdrant connection has not been initialized.")
    return QdrantManager.client
