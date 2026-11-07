import os
# PyTorch CUDA Allocator: chong phan manh VRAM va tu dong nha cache tren Windows
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:128,garbage_collection_threshold:0.8")
"""Shared GPU helpers for the local models (BGE-M3 embedder, Qwen3 reranker).

A 4 GB laptop card shared with the desktop cannot always hold both models at once (Windows gives each process a
shrinking VRAM budget when a browser asks for more). Calls therefore go through run_on_gpu(): both models stay
resident while that works; on the first out-of-memory error the other model is released and the call is retried, and
from then on the two models take turns (a few seconds of reload per question instead of a failed question).
"""
import asyncio
import gc
from typing import Callable, Dict

from app.core.config import settings
from app.core.logging import logger

# One GPU job at a time: embedding, reranking and Docling must not overlap on a small card.
GPU_LOCK = asyncio.Lock()

_UNLOADERS: Dict[str, Callable[[], None]] = {}
_swap_mode = settings.GPU_MODE == "swap"


def register_unloader(name: str, unload: Callable[[], None]) -> None:
    _UNLOADERS[name] = unload


def resolve_device() -> str:
    import torch

    device = ("cuda" if torch.cuda.is_available() else "cpu") if settings.DEVICE == "auto" else settings.DEVICE
    if device.startswith("cuda") and 0 < settings.GPU_MEMORY_FRACTION < 1:
        torch.cuda.set_per_process_memory_fraction(settings.GPU_MEMORY_FRACTION)  # see GPU_MEMORY_FRACTION
    return device


def free_gpu_memory() -> None:
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def release_models() -> None:
    """Free every in-process model (call while holding GPU_LOCK) before another program, e.g. the Ollama catalog model, uses the card."""
    for unload in _UNLOADERS.values():
        unload()


def _release_others(keep: str) -> None:
    for name, unload in _UNLOADERS.items():
        if name != keep:
            unload()


def memory_report() -> str:
    """What this process holds on the card, for out-of-memory logs (the CUDA message alone does not say which model)."""
    import torch

    if not torch.cuda.is_available():
        return "no CUDA"
    gib = 2**30
    free, total = torch.cuda.mem_get_info()
    return (f"process: allocated {torch.cuda.memory_allocated() / gib:.2f} GiB, reserved {torch.cuda.memory_reserved() / gib:.2f} GiB, "
            f"peak {torch.cuda.max_memory_allocated() / gib:.2f} GiB; card: {free / gib:.2f} of {total / gib:.2f} GiB free; "
            f"swap mode {_swap_mode}")


def _is_oom(exc: BaseException) -> bool:
    return isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower()


async def run_on_gpu(name: str, fn: Callable, *args):
    """Run a blocking model call in a worker thread, serialised on the GPU. See the module docstring."""
    global _swap_mode
    async with GPU_LOCK:
        if _swap_mode:
            _release_others(name)
        oom = False
        try:
            return await asyncio.to_thread(fn, *args)
        except RuntimeError as exc:
            if not _is_oom(exc) or settings.GPU_MODE == "resident":
                raise
            oom = True  # handled below, outside the except block, so the failed call's tensors can be freed
        finally:
            await asyncio.to_thread(free_gpu_memory)
        if oom:
            logger.warning(f"GPU out of memory in {name}: {memory_report()}")
            if not _swap_mode:
                logger.warning("GPU memory is tight: the embedding and reranker models will now take turns on the GPU.")
            _swap_mode = True
            _release_others(name)
            await asyncio.to_thread(free_gpu_memory)
            try:
                return await asyncio.to_thread(fn, *args)
            finally:
                await asyncio.to_thread(free_gpu_memory)
