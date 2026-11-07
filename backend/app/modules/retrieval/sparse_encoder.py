import re
from collections import Counter
from typing import Dict, List, Tuple
from qdrant_client.http import models


class SimpleSparseEncoder:
    """Lightweight BM25/lexical term-frequency sparse vector encoder.

    Encodes text into sparse vector format (indices, values) for Qdrant sparse search.
    """

    def __init__(self):
        self.token_pattern = re.compile(r"(?u)\b\w+\b")

    def encode_text(self, text: str) -> models.SparseVector:
        """Tokenize and generate sparse vector based on term frequency."""
        tokens = [token.lower() for token in self.token_pattern.findall(text)]
        if not tokens:
            return models.SparseVector(indices=[0], values=[0.0])

        counts = Counter(tokens)
        indices: List[int] = []
        values: List[float] = []

        for token, count in counts.items():
            token_id = abs(hash(token)) % 2147483647
            indices.append(token_id)
            values.append(float(count))

        return models.SparseVector(indices=indices, values=values)
