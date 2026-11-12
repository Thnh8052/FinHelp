"""Word counts of the chunks of each document, for the BM25 half of the planned search.

A multi-document question used to read the whole text of its documents from MongoDB and count the words again (about 1,500 chunks for five documents; local MongoDB 0.06 s,
over the network to Atlas much more). A document does not change after it is indexed (a new upload gets a new document id; deleting its chunks drops its entry), so the counts
are kept in memory, least recently used documents leaving first once more than MAX_CHUNKS chunks are held.
"""
from collections import Counter, OrderedDict
from typing import Dict, Optional, Tuple

MAX_CHUNKS = 8000
Entry = Dict[str, Tuple[Counter, int]]  # {chunk_id: (word counts, token count)} of one document


class TermCountCache:
    def __init__(self, max_chunks: int = MAX_CHUNKS):
        self.max_chunks = max_chunks
        self._docs: "OrderedDict[str, Entry]" = OrderedDict()
        self._chunks = 0

    def get(self, document_id: str) -> Optional[Entry]:
        entry = self._docs.get(document_id)
        if entry is not None:
            self._docs.move_to_end(document_id)
        return entry

    def put(self, document_id: str, entry: Entry) -> None:
        if not entry:  # a document with no chunk (yet) is not remembered
            return
        self.drop(document_id)
        self._docs[document_id] = entry
        self._chunks += len(entry)
        while self._chunks > self.max_chunks and len(self._docs) > 1:
            _, old = self._docs.popitem(last=False)
            self._chunks -= len(old)

    def drop(self, document_id: str) -> None:
        old = self._docs.pop(document_id, None)
        if old is not None:
            self._chunks -= len(old)

    def clear(self) -> None:
        self._docs.clear()
        self._chunks = 0


TERMS = TermCountCache()
