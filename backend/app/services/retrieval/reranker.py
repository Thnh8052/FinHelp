import threading
from typing import List, Sequence, Tuple

import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.services.retrieval.gpu import free_gpu_memory, register_unloader, resolve_device, run_on_gpu

# Instruction, prompt wrapper and scoring are the ones measured in the research (qwen_m3.py).
INSTRUCTION = (
    "Given a question about a company's financial report, judge whether the passage contains information "
    "needed to answer it, such as the relevant financial statement line items and figures or the relevant "
    "narrative disclosure."
)
PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct "
    'provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
)
SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
MAX_LEN = 8192
BATCH_TOKENS = 4096  # padded tokens per forward pass in score_pairs (as the research scored, planner_fallback/fallback_eval.py)


class QwenRerankerService:
    """Qwen3-Reranker-0.6B: P("yes") that a passage helps answer the question. Pairs are scored one at a time
    (variable length, 4 GB VRAM) and only the last-token logits are kept, which keeps memory flat."""

    _tok = None
    _model = None
    _ids = None
    _load_lock = threading.Lock()

    @classmethod
    def _load(cls):
        with cls._load_lock:
            if cls._model is None:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer

                device = resolve_device()
                logger.info(f"Loading reranker {settings.RERANKER_MODEL} on {device}...")
                tok = AutoTokenizer.from_pretrained(settings.RERANKER_MODEL, padding_side="left")
                dtype = torch.float16 if device == "cuda" else torch.float32
                if device.startswith("cuda"):  # the weights go straight to the card, not through a copy in RAM
                    model = AutoModelForCausalLM.from_pretrained(settings.RERANKER_MODEL, dtype=dtype, device_map=device).eval()
                else:
                    model = AutoModelForCausalLM.from_pretrained(settings.RERANKER_MODEL, dtype=dtype).to(device).eval()
                cls._tok, cls._model = tok, model
                cls._ids = (tok.convert_tokens_to_ids("no"), tok.convert_tokens_to_ids("yes"))
            return cls._tok, cls._model, cls._ids

    @classmethod
    def unload(cls) -> None:
        with cls._load_lock:
            cls._tok = cls._model = cls._ids = None
        free_gpu_memory()

    @classmethod
    def _score(cls, question: str, passages: List[str]) -> List[float]:
        import torch

        tok, model, (no_id, yes_id) = cls._load()
        prefix, suffix = tok.encode(PREFIX, add_special_tokens=False), tok.encode(SUFFIX, add_special_tokens=False)
        texts = [f"<Instruct>: {INSTRUCTION}\n<Query>: {question}\n<Document>: {p}" for p in passages]
        encoded = tok(
            texts,
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=MAX_LEN - len(prefix) - len(suffix),
        )["input_ids"]
        scores = np.zeros(len(encoded))
        with torch.no_grad():
            for i, ids in enumerate(encoded):
                batch = tok.pad({"input_ids": [prefix + ids + suffix]}, padding=True, return_tensors="pt").to(model.device)
                logits = model(**batch, logits_to_keep=1).logits[:, -1, :]
                pair = torch.stack([logits[:, no_id], logits[:, yes_id]], 1).float()
                scores[i] = torch.nn.functional.log_softmax(pair, 1)[:, 1].exp().item()
        return scores.tolist()

    @classmethod
    def _score_pairs(cls, pairs: Sequence[Tuple[str, str]]) -> List[float]:
        """Same scores as _score (within 0.01), several pairs per forward pass: sorted by length, a batch closes before it would pad to
        more than BATCH_TOKENS tokens. Multi-document dev: 4.9 s a question instead of 11.0 s scoring one pair at a time."""
        import torch

        tok, model, (no_id, yes_id) = cls._load()
        prefix, suffix = tok.encode(PREFIX, add_special_tokens=False), tok.encode(SUFFIX, add_special_tokens=False)
        encoded = tok(
            [f"<Instruct>: {INSTRUCTION}\n<Query>: {q}\n<Document>: {p}" for q, p in pairs],
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=MAX_LEN - len(prefix) - len(suffix),
        )["input_ids"]
        ids = [prefix + x + suffix for x in encoded]
        scores = np.zeros(len(ids))

        def flush(batch: List[int]) -> None:
            x = tok.pad({"input_ids": [ids[j] for j in batch]}, padding=True, return_tensors="pt").to(model.device)
            with torch.no_grad():
                logits = model(**x, logits_to_keep=1).logits[:, -1, :]
            pair = torch.stack([logits[:, no_id], logits[:, yes_id]], 1).float()
            scores[batch] = torch.nn.functional.log_softmax(pair, 1)[:, 1].exp().cpu().numpy()

        batch: List[int] = []
        for j in sorted(range(len(ids)), key=lambda j: len(ids[j])):
            if batch and (len(batch) + 1) * len(ids[j]) > BATCH_TOKENS:
                flush(batch)
                batch = []
            batch.append(j)
        if batch:
            flush(batch)
        return scores.tolist()

    async def score_pairs(self, pairs: Sequence[Tuple[str, str]]) -> List[float]:
        if not pairs:
            return []
        return await run_on_gpu("reranker", self._score_pairs, list(pairs))

    async def score(self, question: str, passages: List[str]) -> List[float]:
        """Batched like score_pairs (the one-pair-at-a-time _score is kept for reference: same scores within 0.01)."""
        if not passages:
            return []
        return await run_on_gpu("reranker", self._score_pairs, [(question, p) for p in passages])


register_unloader("reranker", QwenRerankerService.unload)
