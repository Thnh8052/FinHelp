from collections import Counter
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.infrastructure.database import collections
from app.shared.base_repo import BaseRepository
from app.shared.common import get_utc_now
from app.modules.documents.document import ACTIVE_STATUSES, DocumentRecord
from app.modules.query_router.catalog_route import company_key


def one_spelling_per_company(docs: List[DocumentRecord]) -> List[DocumentRecord]:
    """The documents with one spelling for each company (same company key): a cover printed in capitals ("AMAZON.COM, INC.") and a report that
    writes the name out ("Amazon.com, Inc.") are one company, and two spellings made the chat treat them as two (system test 18/11, B7: the
    follow-up "Còn Amazon thì sao?" became "compare AMAZON.COM and Amazon.com"). The spelling kept is one with lower-case letters, the most used,
    then the first; a company only ever written in capitals stays so. Copies: the stored records keep what each document says."""
    spellings: Dict[str, List[str]] = {}
    for d in docs:
        name = d.metadata.company_name
        if name and company_key(name):
            spellings.setdefault(company_key(name), []).append(name)
    chosen = {}
    for key, names in spellings.items():
        used = Counter(names)
        chosen[key] = max(used, key=lambda n: (any(ch.islower() for ch in n), used[n], -names.index(n)))
    out = []
    for d in docs:
        name = d.metadata.company_name
        best = chosen.get(company_key(name)) if name else None
        out.append(d if not best or best == name else d.model_copy(update={"metadata": d.metadata.model_copy(update={"company_name": best})}))
    return out


class DocumentRepository(BaseRepository):
    """Data Access Layer for documents."""

    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, collections.DOCUMENTS_COLLECTION)

    async def get_by_id(self, document_id: str) -> Optional[DocumentRecord]:
        doc = await self.find_one({"document_id": document_id})
        return DocumentRecord(**doc) if doc else None

    async def get_by_notebook(self, notebook_id: str) -> List[DocumentRecord]:
        """The documents of a notebook, newest first, each company under one spelling (one_spelling_per_company)."""
        docs = await self.find_many({"notebook_id": notebook_id}, sort_by=[("created_at", -1)])
        return one_spelling_per_company([DocumentRecord(**doc) for doc in docs])

    async def counts_by_notebook(self, notebook_ids: List[str]) -> Dict[str, Dict[str, int]]:
        """{notebook_id: {document_count, processing_count}} in one query, for the notebook list."""
        pipeline = [
            {"$match": {"notebook_id": {"$in": notebook_ids}}},
            {"$group": {
                "_id": "$notebook_id",
                "document_count": {"$sum": 1},
                "processing_count": {"$sum": {"$cond": [{"$in": ["$status", list(ACTIVE_STATUSES)]}, 1, 0]}},
            }},
        ]
        return {
            row["_id"]: {"document_count": row["document_count"], "processing_count": row["processing_count"]}
            async for row in self.collection.aggregate(pipeline)
        }

    async def update_status(self, document_id: str, status: str) -> bool:
        return await self.update_one({"document_id": document_id}, {"status": status, "updated_at": get_utc_now()})

    async def save_document(self, doc: DocumentRecord) -> str:
        return await self.insert_one(doc.model_dump())

    async def delete_document(self, document_id: str) -> bool:
        return await self.delete_one({"document_id": document_id})
