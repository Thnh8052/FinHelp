from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase


class BaseRepository:
    """Generic MongoDB Repository providing foundational CRUD methods."""

    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.db = db
        self.collection_name = collection_name
        self.collection = db[collection_name]

    async def find_one(self, filter_query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single document matching query filter."""
        doc = await self.collection.find_one(filter_query)
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def find_many(
        self,
        filter_query: Dict[str, Any],
        sort_by: Optional[List[tuple]] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Find multiple documents matching filter with pagination."""
        cursor = self.collection.find(filter_query).skip(skip).limit(limit)
        if sort_by:
            cursor = cursor.sort(sort_by)
        items = []
        async for doc in cursor:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            items.append(doc)
        return items

    async def insert_one(self, data: Dict[str, Any]) -> str:
        """Insert a single document and return its ID."""
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

    async def insert_many(self, items: List[Dict[str, Any]]) -> List[str]:
        """Bulk insert multiple documents."""
        if not items:
            return []
        result = await self.collection.insert_many(items)
        return [str(_id) for _id in result.inserted_ids]

    async def update_one(
        self, filter_query: Dict[str, Any], update_data: Dict[str, Any]
    ) -> bool:
        """Update a single document."""
        result = await self.collection.update_one(filter_query, {"$set": update_data})
        return result.modified_count > 0

    async def delete_one(self, filter_query: Dict[str, Any]) -> bool:
        """Delete a single document."""
        result = await self.collection.delete_one(filter_query)
        return result.deleted_count > 0
